from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.adapters.llm import generate_llm_summary_with_usage
from app.config import Settings, settings as runtime_settings
from app.core.scope import build_scope_summary
from app.models.assistant import AiContextPack
from app.models.assistant_usage import AssistantUsage
from app.services import factory_command_service
from app.services.report import daily_report_fact_closure


_SENSITIVE_KEY_PARTS = ('password', 'secret', 'token', 'credential', 'api_key', 'apikey')
_SYNC_DEGRADED_STATUSES = {'stale', 'failed', 'unconfigured', 'migration_missing', 'offline_or_blocked'}
_SYNC_CRITICAL_STATUSES = {'failed', 'migration_missing', 'offline_or_blocked'}
_SYNC_MISSING_DATA_KEYS = {
    'stale': 'mes_stale',
    'failed': 'mes_failed',
    'unconfigured': 'mes_unconfigured',
    'migration_missing': 'mes_projection_unready',
    'offline_or_blocked': 'mes_offline',
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                continue
            sanitized[str(key)] = _sanitize(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _source_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()[:32]


def _llm_ready(runtime: Settings) -> bool:
    has_model_ref = bool(str(runtime.LLM_ENDPOINT_ID or runtime.LLM_MODEL or '').strip())
    return bool(
        runtime.LLM_ENABLED
        and str(runtime.LLM_API_BASE or '').strip()
        and str(runtime.LLM_API_KEY or '').strip()
        and has_model_ref
    )


def _daily_window_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    return datetime(current.year, current.month, current.day, tzinfo=timezone.utc)


def _can_record_usage(db: Session, user: Any) -> bool:
    return callable(getattr(db, 'query', None)) and callable(getattr(db, 'add', None)) and getattr(user, 'id', None) is not None


def _within_daily_limit(db: Session, user: Any, *, runtime: Settings) -> bool:
    if not _can_record_usage(db, user):
        return True
    used = (
        db.query(AssistantUsage)
        .filter(AssistantUsage.user_id == int(user.id), AssistantUsage.created_at >= _daily_window_start())
        .count()
    )
    return used < int(runtime.LLM_DAILY_QUERY_LIMIT or 0)


def _record_llm_usage(db: Session, user: Any, *, runtime: Settings, response) -> None:
    if not _can_record_usage(db, user):
        return
    db.add(
        AssistantUsage(
            user_id=int(user.id),
            endpoint='ai_context_answer',
            model=str(runtime.LLM_ENDPOINT_ID or runtime.LLM_MODEL or '').strip(),
            input_tokens=max(0, int(getattr(response, 'input_tokens', 0) or 0)),
            output_tokens=max(0, int(getattr(response, 'output_tokens', 0) or 0)),
            total_tokens=max(0, int(getattr(response, 'total_tokens', 0) or 0)),
            raw_usage=dict(getattr(response, 'raw_usage', None) or {}),
        )
    )
    commit = getattr(db, 'commit', None)
    if callable(commit):
        commit()


def _delay_hours(item: Mapping[str, Any]) -> float:
    try:
        return float(item.get('delay_hours') or 0)
    except (TypeError, ValueError):
        return 0.0


def _rules_for(coils: list[Mapping[str, Any]], freshness: Mapping[str, Any]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    freshness_status = str(freshness.get('status') or '')
    if freshness_status in _SYNC_DEGRADED_STATUSES:
        rules.append(
            {
                'key': 'sync_stale',
                'severity': 'critical' if freshness_status in _SYNC_CRITICAL_STATUSES else 'warning',
                'evidence_refs': [{'kind': 'sync', 'key': 'mes_projection'}],
                'recommended_next_actions': ['检查外部 MES 同步状态'],
            }
        )
    if any(_delay_hours(coil) > 0 for coil in coils):
        rules.append(
            {
                'key': 'delay_hours_high',
                'severity': 'warning',
                'evidence_refs': [
                    {'kind': 'coil', 'key': str(coil.get('coil_key') or '')}
                    for coil in coils
                    if _delay_hours(coil) > 0
                ][:5],
                'recommended_next_actions': ['查看停滞卷证据', '确认下一工序资源'],
            }
        )
    return rules


def _call_scoped(func, db: Session, *, scope):
    try:
        return func(db, scope=scope)
    except TypeError:
        return func(db)


def _filter_for_assistant_scope(
    *,
    machine_lines: list[Any],
    coils: list[Any],
    scope_payload: Mapping[str, Any],
) -> tuple[list[Any], list[Any]]:
    scope_type = str(scope_payload.get('type') or 'factory')
    scope_key = str(scope_payload.get('key') or 'all')
    if scope_type == 'factory' or scope_key == 'all':
        return machine_lines, coils
    if scope_type == 'machine':
        return (
            [line for line in machine_lines if str(line.get('line_code') or '') == scope_key],
            [
                coil
                for coil in coils
                if scope_key
                in {
                    str(coil.get('line_code') or ''),
                    str(coil.get('machine_code') or ''),
                }
            ],
        )
    if scope_type == 'coil':
        return (
            machine_lines,
            [
                coil
                for coil in coils
                if scope_key
                in {
                    str(coil.get('coil_key') or ''),
                    str(coil.get('tracking_card_no') or ''),
                    str(coil.get('batch_no') or ''),
                }
            ],
        )
    if scope_type in {'workshop', 'process'}:
        key_fields = ('current_workshop', 'workshop_name') if scope_type == 'workshop' else ('current_process', 'next_process')
        return (
            [
                line
                for line in machine_lines
                if scope_type != 'workshop' or str(line.get('workshop_name') or '') == scope_key
            ],
            [coil for coil in coils if any(str(coil.get(field) or '') == scope_key for field in key_fields)],
        )
    return machine_lines, coils


def _selected_business_date(scope_payload: Mapping[str, Any]) -> date | None:
    try:
        return date.fromisoformat(str(scope_payload.get('business_date') or '').strip())
    except ValueError:
        return None


def _daily_facts_for(db: Session, business_date: date) -> dict[str, Any]:
    snapshot = daily_report_fact_closure._latest_daily_fact_snapshot(db, target_date=business_date)
    if snapshot is None:
        return {'business_date': business_date.isoformat(), 'status': 'missing'}
    adopted_values = dict(snapshot.adopted_values or {})
    return {
        'business_date': business_date.isoformat(),
        'status': 'available',
        'fact_version': snapshot.payload_hash,
        'trace_id': snapshot.trace_id,
        'adopted_values': adopted_values,
        'missing_fields': [key for key, value in adopted_values.items() if value is None],
        'conflict_count': len(snapshot.conflicts or []),
    }


def _compact_for_llm(pack: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'scope': pack.get('scope') or {},
        'daily_facts': pack.get('daily_facts') or {},
        'freshness': pack.get('freshness') or {},
        'top_abnormal_coils': list(pack.get('top_abnormal_coils') or [])[:5],
        'machine_line_metrics': list(pack.get('machine_line_metrics') or [])[:8],
        'route_refs': list(pack.get('route_refs') or [])[:8],
        'rules_fired': list(pack.get('rules_fired') or [])[:6],
        'known_missing_data': list(pack.get('known_missing_data') or []),
    }


def _build_deterministic_answer(pack: Mapping[str, Any]) -> dict[str, Any]:
    missing_data = list(pack.get('known_missing_data') or [])
    freshness_status = (pack.get('freshness') or {}).get('status')
    confidence = 'high'
    if freshness_status in {'stale', 'unconfigured'}:
        confidence = 'medium'
    if freshness_status in _SYNC_CRITICAL_STATUSES:
        confidence = 'low'
    evidence_refs = []
    for rule in pack.get('rules_fired') or []:
        evidence_refs.extend(rule.get('evidence_refs') or [])
    if not evidence_refs and pack.get('machine_line_metrics'):
        first_line = pack['machine_line_metrics'][0]
        evidence_refs.append({'kind': 'machine', 'key': str(first_line.get('line_code') or '')})
    daily_facts = pack.get('daily_facts') or {}
    if daily_facts.get('status') == 'available':
        evidence_refs.insert(
            0,
            {
                'kind': 'daily_fact_bundle',
                'key': daily_facts['fact_version'],
                'business_date': daily_facts['business_date'],
                'trace_id': daily_facts.get('trace_id'),
            },
        )
        missing_data.extend(field for field in daily_facts['missing_fields'] if field not in missing_data)

    if daily_facts.get('status') == 'missing':
        confidence = 'low'
        answer = f"{daily_facts['business_date']} 暂无日报事实快照，无法按该日日报口径回答。"
    elif pack.get('top_abnormal_coils'):
        answer = f"已找到 {len(pack['top_abnormal_coils'])} 条需关注卷，建议先看停滞和缺下工序记录。"
    else:
        answer = '当前上下文未发现明确异常，建议继续查看同步新鲜度和机列负荷。'

    return {
        'answer': answer,
        'confidence': confidence,
        'evidence_refs': evidence_refs[:8],
        'missing_data': missing_data,
        'recommended_next_actions': ['查看证据卷', '打开工厂总览', '创建关注项'],
        'can_create_watch': True,
    }


def _parse_llm_answer(content: str) -> dict[str, Any] | None:
    text = str(content or '').strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{')
        end = text.rfind('}')
        if start < 0 or end <= start:
            return {'answer': text}
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {'answer': text}
    return payload if isinstance(payload, dict) else None


_NUMBER_PATTERN = re.compile(r'\d+(?:\.\d+)?')
_VERIFICATION_CLAIMS = ('已核验', '核验完成', '已验证', '验证完成', '已确认', '确认无误')


def _numbers_in(text: str) -> list[str]:
    return _NUMBER_PATTERN.findall(re.sub(r'(?<=\d),(?=\d{3})', '', text))


def _is_grounded_number(token: str, allowed: list[float]) -> bool:
    value = float(token)
    if '.' not in token and value < 10:
        return True
    decimals = len(token.split('.', 1)[1]) if '.' in token else 0
    return any(round(candidate, decimals) == value for candidate in allowed)


def _llm_answer_rejection(
    answer_text: str,
    *,
    question: str,
    safe_context: Mapping[str, Any],
    deterministic: Mapping[str, Any],
) -> str | None:
    facts_text = json.dumps(
        {'question': question, 'context': safe_context, 'deterministic': deterministic},
        ensure_ascii=False,
        default=str,
    )
    allowed = [float(token) for token in _numbers_in(facts_text)]
    if any(not _is_grounded_number(token, allowed) for token in _numbers_in(answer_text)):
        return 'ungrounded_number'
    has_evidence = bool(deterministic.get('evidence_refs'))
    if any(claim in answer_text for claim in _VERIFICATION_CLAIMS) and (
        deterministic.get('confidence') != 'high' or not has_evidence
    ):
        return 'unsupported_verification_claim'
    return None


def _ground_answer_with_llm(
    *,
    db: Session,
    user: Any,
    question: str,
    pack: Mapping[str, Any],
    deterministic: dict[str, Any],
    runtime: Settings,
) -> dict[str, Any]:
    if not _llm_ready(runtime) or not _within_daily_limit(db, user, runtime=runtime):
        return deterministic

    safe_context = _sanitize(_compact_for_llm(pack))
    messages = [
        {
            'role': 'system',
            'content': (
                '你是鑫泰铝业 数据中枢的 AI 总管。只能基于给定事实回答，'
                '不得编造产量、能耗、合同量、成品率或人员信息。'
                '如果事实不足，必须明确说“数据不足”。严格返回 JSON。'
            ),
        },
        {
            'role': 'user',
            'content': (
                '请把系统已算出的事实组织成管理者能直接执行的中文回答。'
                '仅允许输出字段：answer、recommended_next_actions。'
                f'\nQUESTION={question}'
                f'\nDETERMINISTIC_ANSWER={json.dumps(deterministic, ensure_ascii=False, default=str)}'
                f'\nSAFE_CONTEXT={json.dumps(safe_context, ensure_ascii=False, default=str)}'
            ),
        },
    ]
    try:
        response = generate_llm_summary_with_usage(messages=messages, settings=runtime, max_tokens=512)
        parsed = _parse_llm_answer(response.content)
    except Exception:  # noqa: BLE001
        rollback = getattr(db, 'rollback', None)
        if callable(rollback):
            rollback()
        return deterministic

    answer_text = str((parsed or {}).get('answer') or '').strip()
    if not answer_text:
        return deterministic
    if _llm_answer_rejection(
        answer_text,
        question=question,
        safe_context=safe_context,
        deterministic=deterministic,
    ):
        _record_llm_usage(db, user, runtime=runtime, response=response)
        return deterministic

    next_actions = (parsed or {}).get('recommended_next_actions')
    if not isinstance(next_actions, list):
        next_actions = deterministic['recommended_next_actions']
    else:
        next_actions = [str(item).strip() for item in next_actions if str(item or '').strip()][:4]
        if not next_actions:
            next_actions = deterministic['recommended_next_actions']

    _record_llm_usage(db, user, runtime=runtime, response=response)
    return {
        **deterministic,
        'answer': answer_text[:500],
        'recommended_next_actions': next_actions,
    }


def build_runtime_status(*, settings: Settings | None = None) -> dict[str, Any]:
    runtime = settings or runtime_settings
    model_ref_set = bool(str(runtime.LLM_ENDPOINT_ID or runtime.LLM_MODEL or '').strip())
    llm_configured = _llm_ready(runtime)
    return {
        'engine': 'grounded_llm' if llm_configured else 'deterministic',
        'llm_configured': llm_configured,
        'model_ref_set': model_ref_set,
        'canonical_entry': '/manage/ai-assistant',
        'legacy_llm_entry': '/api/v1/assistant',
    }


def build_context_pack(
    db: Session,
    *,
    user: Any,
    intent: str,
    scope: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or _now()
    scope_payload = scope or {'type': 'factory', 'key': 'all'}
    freshness = factory_command_service.build_freshness(db)
    data_scope = build_scope_summary(user)
    machine_lines = _sanitize(_call_scoped(factory_command_service.list_machine_lines, db, scope=data_scope))
    coils = _sanitize(_call_scoped(factory_command_service.list_coils, db, scope=data_scope))
    machine_lines, coils = _filter_for_assistant_scope(
        machine_lines=machine_lines,
        coils=coils,
        scope_payload=scope_payload,
    )
    top_abnormal_coils = [
        coil
        for coil in coils
        if isinstance(coil, Mapping) and (_delay_hours(coil) > 0 or not coil.get('current_process'))
    ][:8]
    route_refs = [
        {
            'coil_key': coil.get('coil_key'),
            'current_process': coil.get('current_process'),
            'next_process': coil.get('next_process'),
        }
        for coil in coils
        if isinstance(coil, Mapping)
    ][:12]
    known_missing_data = []
    missing_data_key = _SYNC_MISSING_DATA_KEYS.get(str(freshness.get('status') or ''))
    if missing_data_key:
        known_missing_data.append(missing_data_key)
    business_date = _selected_business_date(scope_payload)
    daily_facts = _daily_facts_for(db, business_date) if business_date else {}
    if daily_facts.get('status') == 'missing':
        known_missing_data.append('daily_fact_bundle')

    pack = {
        'intent': intent,
        'scope': scope_payload,
        'freshness': freshness,
        'top_abnormal_coils': top_abnormal_coils,
        'machine_line_metrics': machine_lines,
        'route_refs': route_refs,
        'rules_fired': _rules_for(coils, freshness),
        'known_missing_data': known_missing_data,
        'daily_facts': daily_facts,
        'created_at': current.isoformat(),
    }
    safe_pack = _sanitize(pack)
    if hasattr(db, 'add'):
        entity = AiContextPack(
            owner_user_id=getattr(user, 'id', None),
            intent=intent,
            scope_payload=scope_payload,
            payload=safe_pack,
            source_hash=_source_hash(safe_pack),
            expires_at=current + timedelta(minutes=10),
        )
        db.add(entity)
        if hasattr(db, 'flush'):
            db.flush()
    return safe_pack


def answer_from_context(
    db: Session,
    *,
    user: Any,
    question: str,
    intent: str = 'factory_status',
    scope: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    pack = build_context_pack(db, user=user, intent=intent, scope=scope)
    deterministic = _build_deterministic_answer(pack)
    return _ground_answer_with_llm(
        db=db,
        user=user,
        question=question,
        pack=pack,
        deterministic=deterministic,
        runtime=settings or runtime_settings,
    )
