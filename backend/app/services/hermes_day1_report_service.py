from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from app.services.report.output_skill_report_parser import parse_output_skill_daily_report
from app.services.report.template_daily_report import REQUIRED_FIELDS, render_template_daily_report


WORKSHOP_DETAIL_SPECS = (
    ('铸轧分厂', 'cast_roll'),
    ('铸锭车间', 'foundry'),
    ('热轧车间', 'hot_roll'),
    ('1650车间', 'cold_1650'),
    ('1850车间', 'cold_1850'),
    ('2050车间', 'cold_2050'),
    ('在线退火', 'online_anneal'),
    ('拉矫', 'straightening'),
    ('精整车间', 'finishing'),
    ('剪切车间', 'shearing'),
    ('彩涂车间', 'coating'),
    ('回收车间', 'recovery'),
)

BLOCKED_FORMAL_TEXT = '当前关键字段缺失，智能大脑未生成正式日报正文；请先补齐缺失字段后重跑。'
DINGTALK_MAX_CHARS = 3500

_OK_DIFF_STATUSES = {'matched', 'match', 'same', 'equal', 'ok', 'ready', 'passed'}
_REVIEW_STATUS_MARKERS = ('blocked', 'failed', 'partial', 'error', 'empty', 'missing', 'review-needed', 'review_needed')
_BUNDLE_READY_STATUSES = {'ready', 'ok', 'passed', 'completed', 'matched'}
_NON_BLOCKING_ADOPTED_CONFLICT_TYPES = {
    'root_owner_correction',
    'verified_owner_daily',
    'dingtalk_supplement',
    'adopted_override',
}
_SOURCE_LABELS = {
    'template_daily_report': '模板正式日报',
    'daily_fact_bundle': '日报事实包',
    'mes_wms': '外部 MES/WMS 只读源',
    'audit_run': '智能大脑数据审计',
    'dingtalk_evidence': '钉钉证据',
    'dingtalk_messages': '钉钉文本',
    'rag': 'RAG 知识库',
    'historical_reports': '历史日报',
    'output_skill_alignment': '输出 skill 对齐',
}
_FACT_SOURCE_LABELS = {
    '数据中枢 facts': '数据中枢 facts',
    'manual_mobile_coil': '数据中枢人工填报',
    'owner_daily': '数据中枢一日汇总',
    'computed': '数据中枢计算值',
    'mes_material_records': '外部 MES 物料记录',
    'mes_workshop_process_records': '外部 MES 工序记录',
    'mes_packaging_output': '外部 MES 包装产量',
    'owner_or_energy_summary': '数据中枢能耗汇总',
    'energy_cost': '数据中枢成本核算',
    'recovery_daily': '数据中枢回收日报',
    'root_owner_correction': '最高权限者确认',
    'verified_owner_daily': '责任人扫码补录',
    'dingtalk_supplement': '钉钉补充事实',
    'mes_wms': '外部 MES/WMS',
}


def build_day1_three_part_report(*, business_date: date, sources: dict[str, Any]) -> dict[str, Any]:
    template_payload = _as_mapping(sources.get('template_daily_report'))
    facts = _as_mapping(template_payload.get('facts'))
    values = dict(_as_mapping(facts.get('values')))
    fact_sources = dict(_as_mapping(facts.get('sources')))
    bundle_values, bundle_sources = _bundle_fact_values_and_sources(sources)
    values.update(bundle_values)
    fact_sources.update(bundle_sources)
    template_formal_text = _text_or_empty(template_payload.get('text'))
    rendered_formal_text, render_error = _render_formal_text_from_merged_values(
        template_formal_text,
        business_date=business_date,
        values=values,
        sources=fact_sources,
        template_facts=facts,
    )
    missing_fields = _merged_missing_fields(sources, template_payload=template_payload)
    conflicts = _collect_conflicts(sources)
    if render_error:
        conflicts.append(
            {
                'type': 'formal_render_error',
                'source': 'template_daily_report',
                'field': 'formal_text',
                'message': render_error,
                'status': 'failed',
                'severity': 'high',
                'blocking': True,
            }
        )
    field_match_rate = _field_match_rate(sources)
    alignment = _as_mapping(sources.get('output_skill_alignment'))
    alignment_threshold = _alignment_threshold(alignment)
    alignment_blocked = _alignment_blocks_release(alignment, field_match_rate=field_match_rate, threshold=alignment_threshold)
    release_blocked = (
        alignment_blocked
        or bool(missing_fields)
        or _daily_fact_bundle_blocks_release(sources)
        or _conflicts_block_release(conflicts)
    )
    status = (
        'ready'
        if template_payload.get('status') == 'ready' and rendered_formal_text and not release_blocked
        else 'blocked'
    )

    brain_judgment = _build_brain_judgment(
        business_date=business_date,
        sources=sources,
        missing_fields=missing_fields,
        conflicts=conflicts,
        status=status,
        field_match_rate=field_match_rate,
        alignment_threshold=alignment_threshold,
    )
    workshop_details = _build_workshop_details(values=values, sources=fact_sources)
    formal_section_text = rendered_formal_text if status == 'ready' else BLOCKED_FORMAL_TEXT
    text = render_three_part_daily_report(
        formal_text=formal_section_text,
        workshop_details=workshop_details,
        judgment=brain_judgment,
    )

    dingtalk_messages = render_dingtalk_day1_reply(
        business_date_label=_date_label(business_date),
        status=status,
        field_match_rate=field_match_rate,
        alignment_threshold=alignment_threshold,
        judgment_summary=str(brain_judgment['summary']),
        formal_text=formal_section_text,
        workshop_details=workshop_details,
        trace_id=_trace_id(sources),
        requires_review=_requires_review(brain_judgment),
    )
    return {
        'status': status,
        'text': text,
        'formal_text': formal_section_text,
        'brain_judgment': brain_judgment,
        'workshop_details': workshop_details,
        'dingtalk_answer': '\n\n'.join(dingtalk_messages),
        'dingtalk_messages': dingtalk_messages,
        'missing_fields': missing_fields,
        'conflicts': conflicts,
    }


def _render_formal_text_from_merged_values(
    template_text: str,
    *,
    business_date: date,
    values: Mapping[str, Any],
    sources: Mapping[str, Any],
    template_facts: Mapping[str, Any],
) -> tuple[str, str | None]:
    if not template_text.strip():
        return '', None
    parsed_values = parse_output_skill_daily_report(template_text)
    merged_values = {
        **parsed_values,
        **dict(_as_mapping(template_facts.get('values'))),
        **dict(values),
    }
    merged_values.setdefault('report_date', business_date)
    if any(merged_values.get(field_name) is None for field_name in REQUIRED_FIELDS):
        return template_text.strip(), None
    try:
        return render_template_daily_report(
            {
                **dict(template_facts),
                'values': merged_values,
                'sources': dict(sources),
            }
        ).strip(), None
    except Exception as exc:
        return '', f'正式日报重渲染失败：{exc.__class__.__name__}: {exc}'


def _bundle_fact_values_and_sources(sources: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    daily_fact_bundle = _as_mapping(sources.get('daily_fact_bundle'))
    facts = _as_mapping(daily_fact_bundle.get('facts'))
    values: dict[str, Any] = {}
    fact_sources: dict[str, Any] = {}
    for raw_field_name, raw_fact in facts.items():
        field_name = str(raw_field_name)
        fact = _as_mapping(raw_fact)
        if 'value' not in fact:
            continue
        values[field_name] = fact.get('value')
        fact_sources[field_name] = _bundle_fact_source(fact)
    return values, fact_sources


def _bundle_fact_source(fact: Mapping[str, Any]) -> dict[str, Any]:
    source_detail = dict(_as_mapping(fact.get('source_detail')))
    source_type = (
        source_detail.get('source_type')
        or source_detail.get('source')
        or fact.get('source_type')
        or fact.get('source')
    )
    source = source_detail.get('source') or fact.get('source') or source_type
    if source_type not in (None, ''):
        source_detail['source_type'] = source_type
    if source not in (None, ''):
        source_detail['source'] = source
    adoption_reason = fact.get('adoption_reason')
    if adoption_reason not in (None, ''):
        source_detail['adoption_reason'] = adoption_reason
    return source_detail


def _daily_fact_bundle_blocks_release(sources: dict[str, Any]) -> bool:
    daily_fact_bundle = _as_mapping(sources.get('daily_fact_bundle'))
    if not daily_fact_bundle:
        return False
    status = str(daily_fact_bundle.get('status') or '').strip().lower()
    if not status:
        return False
    return status not in _BUNDLE_READY_STATUSES or _source_incomplete(status)


def _merged_missing_fields(sources: dict[str, Any], *, template_payload: Mapping[str, Any]) -> list[str]:
    daily_fact_bundle = _as_mapping(sources.get('daily_fact_bundle'))
    items = [
        *_as_list(template_payload.get('missing_fields')),
        *_as_list(daily_fact_bundle.get('missing_fields')),
        *_as_list(daily_fact_bundle.get('missing')),
    ]
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def render_three_part_daily_report(
    *,
    formal_text: str,
    workshop_details: list[dict[str, Any]],
    judgment: dict[str, Any],
) -> str:
    return '\n\n'.join(
        [
            '智能大脑判断单\n' + _render_brain_judgment(judgment),
            '正式日报正文\n' + formal_text.strip(),
            '各车间明细\n' + _render_workshop_details(workshop_details),
        ]
    )


def render_dingtalk_day1_reply(
    *,
    business_date_label: str,
    status: str,
    field_match_rate: float | None,
    alignment_threshold: float,
    judgment_summary: str,
    formal_text: str,
    workshop_details: list[dict[str, Any]],
    trace_id: str,
    requires_review: bool = False,
) -> list[str]:
    status_label = (
        '已对齐'
        if status == 'ready' and not requires_review and field_match_rate is not None and field_match_rate >= alignment_threshold
        else '需复核'
    )
    match_text = _field_match_rate_text(field_match_rate)
    text = '\n\n'.join(
        [
            '\n'.join(
                [
                    f'鑫泰铝业智能大脑日报｜{business_date_label}',
                    f'状态：{status_label}',
                    f'字段匹配率：{match_text}',
                    f'智能大脑判断：{judgment_summary}',
                    f'追踪编号：{trace_id or "暂无"}',
                ]
            ),
            '正式日报正文\n' + formal_text.strip(),
            '各车间明细\n' + _render_workshop_details(workshop_details),
        ]
    )
    return split_dingtalk_messages(text)


def split_dingtalk_messages(text: str, *, max_chars: int = DINGTALK_MAX_CHARS) -> list[str]:
    clean = text.strip()
    if len(clean) <= max_chars:
        return [clean]

    prefix_reserve = 20
    chunks = _split_on_paragraph_boundary(clean, max_chars=max_chars - prefix_reserve)
    total = len(chunks)
    return [f'[{index}/{total}]\n{chunk}' for index, chunk in enumerate(chunks, start=1)]


def _build_workshop_details(*, values: Mapping[str, Any], sources: Mapping[str, Any]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for title, prefix in WORKSHOP_DETAIL_SPECS:
        lines = [
            f'日产量：{_display(values.get(f"{prefix}_daily"), "吨")}，'
            f'月累计：{_display(values.get(f"{prefix}_month"), "吨")}。',
            f'日吨电耗：{_display(values.get(f"{prefix}_electricity_per_ton_daily"), "度")}，'
            f'月吨电耗：{_display(values.get(f"{prefix}_electricity_per_ton_month"), "度")}。',
        ]
        gas_daily = values.get(f'{prefix}_gas_per_ton_daily')
        gas_month = values.get(f'{prefix}_gas_per_ton_month')
        if gas_daily is not None or gas_month is not None:
            lines.append(
                f'日吨气耗：{_display(gas_daily, "m³")}，月吨气耗：{_display(gas_month, "m³")}。'
            )
        lines.append(f'数据来源：{_workshop_source_text(prefix, values=values, sources=sources)}。')
        lines.append('智能大脑判断：已按模板 facts 纳入全厂日报核验。')
        details.append({'title': title, 'lines': lines})
    return details


def _build_brain_judgment(
    *,
    business_date: date,
    sources: dict[str, Any],
    missing_fields: list[str],
    conflicts: list[dict[str, Any]],
    status: str,
    field_match_rate: float | None,
    alignment_threshold: float,
) -> dict[str, Any]:
    audit = _as_mapping(sources.get('audit_run'))
    alignment = _as_mapping(sources.get('output_skill_alignment'))
    daily_fact_bundle = _as_mapping(sources.get('daily_fact_bundle'))
    source_status = _as_mapping(audit.get('source_status'))
    reference_absent_fields = _alignment_named_fields(alignment, 'reference_absent_fields')
    invalid_na_fields = _alignment_named_fields(alignment, 'invalid_na_fields')
    risks: list[str] = []
    audit_status = audit.get('status')
    if status != 'ready':
        risks.append('正式日报正文被阻断')
    bundle_status = daily_fact_bundle.get('status')
    if daily_fact_bundle and _daily_fact_bundle_blocks_release(sources):
        risks.append(f'日报事实包状态需复核：{_plain_text(bundle_status)}')
    if missing_fields:
        risks.append(f'缺失字段 {len(missing_fields)} 个：{_join_text(missing_fields)}')
    if conflicts:
        risks.append(f'发现冲突 {len(conflicts)} 条：{_render_conflicts_inline(conflicts)}')
    if _source_incomplete(audit_status):
        risks.append(f'审计状态需复核：{_plain_text(audit_status)}')
    source_status_risks = [
        *_source_status_risks(source_status, skip_keys={'mes'}),
        *_source_status_risks(_as_mapping(_as_mapping(sources.get('mes_wms')).get('source_status')), skip_keys={'mes'}),
    ]
    if source_status_risks:
        risks.append(f'数据源状态需复核：{_join_text(source_status_risks)}')
    if _source_incomplete(source_status.get('mes')) or _source_incomplete(
        _as_mapping(_as_mapping(sources.get('mes_wms')).get('source_status')).get('mes')
    ):
        risks.append('MES 只读数据源读取不完整')
    if field_match_rate is not None and field_match_rate < alignment_threshold:
        risks.append(f'字段匹配率低于 {alignment_threshold:.1f}%：{_field_match_rate_text(field_match_rate)}')
        difference_fields = _alignment_difference_fields(alignment)
        if difference_fields:
            risks.append(f'输出 skill 差异字段：{"、".join(difference_fields)}')
    if reference_absent_fields:
        risks.append(
            f'输出 skill 答案钥匙未声明字段 {len(reference_absent_fields)} 个：'
            f'{_join_text(reference_absent_fields)}'
        )
    if invalid_na_fields:
        risks.append(
            f'输出 skill 答案钥匙 N/A 声明无效 {len(invalid_na_fields)} 个：'
            f'{_join_text(invalid_na_fields)}'
        )

    actions = [text for item in _as_list(audit.get('suggested_actions')) if (text := _action_text(item))]
    actions.insert(0, '已生成三段式日报' if status == 'ready' else '已阻断正式正文并列出缺失字段')

    return {
        'status': status,
        'summary': _summary_text(business_date=business_date, status=status, risks=risks),
        'field_match_rate': field_match_rate,
        'risks': risks,
        'missing_fields': missing_fields,
        'reference_absent_fields': reference_absent_fields,
        'invalid_na_fields': invalid_na_fields,
        'conflicts': conflicts,
        'source_names': _source_names(sources),
        'actions': actions,
        'learning_note': '本次查证路径已记录为 Day-1 学习候选，后续可复用到同类日报生成。',
    }


def _collect_conflicts(sources: dict[str, Any]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    daily_fact_bundle = _as_mapping(sources.get('daily_fact_bundle'))
    for item in _as_list(daily_fact_bundle.get('conflicts')):
        conflicts.append(_normalise_conflict(item, conflict_type='daily_fact_bundle_conflict', source='daily_fact_bundle'))
    _append_source_errors(conflicts, 'daily_fact_bundle', daily_fact_bundle.get('source_errors'))

    template_payload = _as_mapping(sources.get('template_daily_report'))
    facts = _as_mapping(template_payload.get('facts'))
    for item in [*_as_list(template_payload.get('conflicts')), *_as_list(facts.get('conflicts'))]:
        conflicts.append(_normalise_conflict(item, conflict_type='template_conflict', source='template_daily_report'))

    audit = _as_mapping(sources.get('audit_run'))
    for field, diff in _as_mapping(audit.get('diffs')).items():
        diff_payload = _as_mapping(diff)
        diff_values = _as_mapping(diff_payload.get('values'))
        diff_status = str(diff_payload.get('status') or '').strip()
        if diff_status and diff_status.lower() not in _OK_DIFF_STATUSES:
            conflicts.append(
                {
                    'type': 'audit_diff',
                    'source': 'audit_run',
                    'field': str(field),
                    'status': diff_status,
                    'hub_value': _diff_value(diff_payload, diff_values, direct_key='hub_value', values_key='hub'),
                    'mes_value': _diff_value(diff_payload, diff_values, direct_key='mes_value', values_key='mes'),
                    'output_skill_value': _diff_value(
                        diff_payload,
                        diff_values,
                        direct_key='output_skill_value',
                        values_key='output_skill',
                    ),
                }
            )

    _append_source_errors(conflicts, 'audit_run', audit.get('source_errors'))
    for key in ('mes_wms', 'rag', 'dingtalk_evidence', 'dingtalk_messages', 'historical_reports'):
        payload = sources.get(key)
        if isinstance(payload, Mapping):
            _append_source_errors(conflicts, key, payload.get('source_errors'))

    return _dedupe_conflicts(conflicts)


def _conflicts_block_release(conflicts: Sequence[Mapping[str, Any]]) -> bool:
    return any(_conflict_blocks_release(conflict) for conflict in conflicts)


def _conflict_blocks_release(conflict: Mapping[str, Any]) -> bool:
    conflict_type = str(conflict.get('type') or '').strip()
    if conflict_type in _NON_BLOCKING_ADOPTED_CONFLICT_TYPES:
        return False
    if conflict_type == 'source_error':
        return True
    status = str(conflict.get('status') or '').strip().lower()
    if status and status not in _OK_DIFF_STATUSES:
        return True
    severity = str(conflict.get('severity') or '').strip().lower()
    if severity in {'critical', 'high', 'blocking'}:
        return True
    if conflict.get('blocking') is True:
        return True
    return conflict_type in {'daily_fact_bundle_conflict', 'template_conflict', 'audit_diff'}


def _normalise_conflict(item: Any, *, conflict_type: str, source: str) -> dict[str, Any]:
    if isinstance(item, Mapping):
        payload = {str(key): value for key, value in item.items()}
        payload.setdefault('type', conflict_type)
        payload.setdefault('source', source)
        return payload
    return {'type': conflict_type, 'source': source, 'message': str(item)}


def _append_source_errors(conflicts: list[dict[str, Any]], source: str, errors: Any) -> None:
    for key, value in _as_mapping(errors).items():
        if value in (None, '', [], {}):
            continue
        conflicts.append(
            {
                'type': 'source_error',
                'source': source,
                'field': str(key),
                'message': _plain_text(value),
            }
        )


def _diff_value(diff_payload: Mapping[str, Any], diff_values: Mapping[str, Any], *, direct_key: str, values_key: str) -> Any:
    if direct_key in diff_payload and diff_payload.get(direct_key) is not None:
        return diff_payload.get(direct_key)
    if values_key in diff_values:
        return diff_values.get(values_key)
    return None


def _dedupe_conflicts(conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for conflict in conflicts:
        key = '|'.join(
            [
                str(conflict.get('type') or ''),
                str(conflict.get('source') or ''),
                str(conflict.get('field') or ''),
                str(conflict.get('status') or ''),
                str(conflict.get('message') or ''),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(conflict)
    return result


def _render_brain_judgment(judgment: Mapping[str, Any]) -> str:
    risks = [str(item) for item in _as_list(judgment.get('risks')) if str(item).strip()]
    missing_fields = [str(item) for item in _as_list(judgment.get('missing_fields')) if str(item).strip()]
    actions = [str(item) for item in _as_list(judgment.get('actions')) if str(item).strip()]
    source_names = [str(item) for item in _as_list(judgment.get('source_names')) if str(item).strip()]
    conflicts = [_as_mapping(item) for item in _as_list(judgment.get('conflicts'))]
    return '\n'.join(
        [
            f'智能大脑判断：{judgment.get("summary") or "暂无"}',
            f'状态：{judgment.get("status") or "暂无"}',
            f'字段匹配率：{_field_match_rate_text(judgment.get("field_match_rate"))}',
            f'主要风险：{_join_text(risks, empty="暂无明显风险")}。',
            f'缺失字段：{_join_text(missing_fields)}。',
            f'冲突与错误：{_render_conflicts_inline(conflicts)}。',
            f'数据源：{_join_text(source_names)}。',
            f'建议动作：{_join_text(actions)}。',
            f'成长记录：{judgment.get("learning_note") or "暂无"}',
        ]
    )


def _render_workshop_details(workshop_details: list[dict[str, Any]]) -> str:
    paragraphs = []
    for detail in workshop_details:
        title = str(detail.get('title') or '未命名车间')
        lines = [str(line) for line in _as_list(detail.get('lines')) if str(line).strip()]
        paragraphs.append('\n'.join([f'【{title}】', *lines]))
    return '\n\n'.join(paragraphs) if paragraphs else '暂无'


def _render_conflicts_inline(conflicts: Sequence[Mapping[str, Any]]) -> str:
    if not conflicts:
        return '暂无'
    return '；'.join(_conflict_text(conflict) for conflict in conflicts)


def _conflict_text(conflict: Mapping[str, Any]) -> str:
    conflict_type = str(conflict.get('type') or 'conflict')
    field = str(conflict.get('field') or conflict.get('key') or conflict.get('source') or '未命名字段')
    message = _plain_text(conflict.get('message'))
    status = _plain_text(conflict.get('status'))
    pieces = [field]
    if message != '暂无':
        pieces.append(message)
    if status != '暂无':
        pieces.append(status)

    value_parts = []
    previous_value = conflict.get('previous_value')
    adopted_value = conflict.get('adopted_value')
    previous_source = conflict.get('previous_source')
    adopted_source = conflict.get('adopted_source')
    reason = conflict.get('reason') or conflict.get('adoption_reason')
    if previous_value not in (None, '', [], {}) or previous_source not in (None, '', [], {}):
        value_parts.append(
            f'原来源 {_source_label(previous_source)}={_plain_text(previous_value)}'
        )
    if adopted_value not in (None, '', [], {}) or adopted_source not in (None, '', [], {}):
        value_parts.append(
            f'采用 {_source_label(adopted_source)}={_plain_text(adopted_value)}'
        )
    for label, key in (
        ('数据中枢', 'hub_value'),
        ('外部 MES', 'mes_value'),
        ('输出 skill', 'output_skill_value'),
        ('模板', 'template_value'),
    ):
        value = conflict.get(key)
        if value not in (None, '', [], {}):
            value_parts.append(f'{label}={_plain_text(value)}')
    if value_parts:
        pieces.append('，'.join(value_parts))
    if reason not in (None, '', [], {}):
        pieces.append(f'原因={_plain_text(reason)}')
    if conflict_type == 'source_error':
        pieces.append('数据源错误')
    return '：'.join(pieces)


def _workshop_source_text(prefix: str, *, values: Mapping[str, Any], sources: Mapping[str, Any]) -> str:
    source_types: list[str] = []
    for key in values:
        if not str(key).startswith(prefix):
            continue
        source = _as_mapping(sources.get(key))
        source_type = source.get('source_type') or source.get('source')
        if source_type in (None, ''):
            continue
        label = _source_label(source_type)
        if label not in source_types:
            source_types.append(label)
    return '、'.join(source_types) if source_types else '暂无明确来源'


def _source_label(value: Any) -> str:
    text = _plain_text(value)
    return _FACT_SOURCE_LABELS.get(text, text)


def _field_match_rate(sources: dict[str, Any]) -> float | None:
    if 'output_skill_alignment' in sources:
        alignment = _as_mapping(sources.get('output_skill_alignment'))
        value = alignment.get('field_match_rate')
        if value is not None:
            return _normalise_rate(value)
        return None

    audit = _as_mapping(sources.get('audit_run'))
    audit_rate = audit.get('match_rate')
    if audit_rate is None:
        return None
    return _normalise_rate(audit_rate)


def _alignment_threshold(alignment: Mapping[str, Any]) -> float:
    return _normalise_threshold(alignment.get('threshold'))


def _alignment_blocks_release(
    alignment: Mapping[str, Any],
    *,
    field_match_rate: float | None,
    threshold: float,
) -> bool:
    if not alignment:
        return False
    status = str(alignment.get('status') or '').strip().lower()
    if status in {'missing', 'failed', 'review_needed', 'review-needed', 'blocked'}:
        return True
    if field_match_rate is None:
        return True
    return field_match_rate < threshold


def _alignment_difference_fields(alignment: Mapping[str, Any]) -> list[str]:
    fields: list[str] = []
    for item in _as_list(alignment.get('differences')):
        if not isinstance(item, Mapping):
            continue
        field = str(item.get('field') or '').strip()
        if field and field not in fields:
            fields.append(field)
    return fields


def _alignment_named_fields(alignment: Mapping[str, Any], key: str) -> list[str]:
    fields: list[str] = []
    for item in _as_list(alignment.get(key)):
        field = str(item).strip()
        if field and field not in fields:
            fields.append(field)
    return fields


def _normalise_rate(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 1.0:
        return round(number * 100, 3)
    return round(number, 3)


def _normalise_threshold(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 95.0
    if number <= 1.0:
        return round(number * 100, 3)
    return round(number, 3)


def _split_on_paragraph_boundary(text: str, *, max_chars: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in text.split('\n\n'):
        paragraph_len = len(paragraph)
        separator_len = 2 if current else 0
        if paragraph_len > max_chars:
            if current:
                chunks.append('\n\n'.join(current))
                current = []
                current_len = 0
            chunks.extend(_split_oversized_paragraph(paragraph, max_chars=max_chars))
            continue
        if current and current_len + separator_len + paragraph_len > max_chars:
            chunks.append('\n\n'.join(current))
            current = []
            current_len = 0
            separator_len = 0
        current.append(paragraph)
        current_len += separator_len + paragraph_len

    if current:
        chunks.append('\n\n'.join(current))
    return chunks


def _split_oversized_paragraph(paragraph: str, *, max_chars: int) -> list[str]:
    lines = paragraph.split('\n')
    chunks: list[str] = []
    current = ''
    for line in lines:
        candidate = line if not current else current + '\n' + line
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ''
        while len(line) > max_chars:
            chunks.append(line[:max_chars])
            line = line[max_chars:]
        current = line
    if current:
        chunks.append(current)
    return chunks


def _display(value: Any, unit: str = '') -> str:
    if value is None or value == '':
        return '暂无'
    if isinstance(value, bool):
        return f'{value}{unit}'
    if isinstance(value, (int, float, Decimal)):
        return f'{_format_number(float(value))}{unit}'
    text = str(value).strip()
    if not text:
        return '暂无'
    try:
        return f'{_format_number(float(text))}{unit}'
    except ValueError:
        return f'{text}{unit}'


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f'{value:.3f}'.rstrip('0').rstrip('.')


def _summary_text(*, business_date: date, status: str, risks: list[str]) -> str:
    date_text = _date_label(business_date)
    if status == 'ready' and not risks:
        return f'{date_text}日报已按模板正式正文和 facts 明细生成，当前未发现需要阻断的问题。'
    if status == 'ready':
        return f'{date_text}日报已生成，但仍需关注：{_join_text(risks)}。'
    return f'{date_text}日报需复核，智能大脑已阻断正式正文输出：{_join_text(risks)}。'


def _source_names(sources: dict[str, Any]) -> list[str]:
    names = [
        _SOURCE_LABELS[key]
        for key in _SOURCE_LABELS
        if key in sources and _source_has_meaningful_content(key, sources.get(key))
    ]
    return names or ['暂无明确来源']


def _source_has_meaningful_content(key: str, payload: Any) -> bool:
    if key in {'dingtalk_evidence', 'dingtalk_messages'}:
        return bool(payload)
    if key == 'daily_fact_bundle':
        if not isinstance(payload, Mapping):
            return False
        return any(payload.get(name) not in (None, '', [], {}) for name in ('status', 'facts', 'conflicts', 'missing_fields', 'missing'))
    if key == 'historical_reports':
        return any(_historical_report_usable(row) for row in _as_list(payload))
    if key == 'output_skill_alignment':
        return isinstance(payload, Mapping) and payload.get('field_match_rate') is not None
    if key == 'rag':
        if not isinstance(payload, Mapping) or _source_incomplete(payload.get('status')):
            return False
        return bool(payload.get('answer') or payload.get('citations') or payload.get('items'))
    if key == 'mes_wms':
        if not isinstance(payload, Mapping):
            return False
        source_status = _as_mapping(payload.get('source_status'))
        return _has_non_empty_payload(payload.get('records')) or str(source_status.get('mes') or '').lower() == 'ok'
    if key == 'audit_run':
        if not isinstance(payload, Mapping):
            return False
        return any(payload.get(name) not in (None, '', [], {}) for name in ('status', 'id', 'match_rate', 'diffs', 'source_status'))
    if key == 'template_daily_report':
        if not isinstance(payload, Mapping):
            return False
        facts = _as_mapping(payload.get('facts'))
        return bool(payload.get('status') or payload.get('text') or _as_mapping(facts.get('values')))
    return payload not in (None, '', [], {})


def _has_non_empty_payload(value: Any) -> bool:
    if value in (None, '', [], {}):
        return False
    if isinstance(value, Mapping):
        return any(_has_non_empty_payload(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_has_non_empty_payload(item) for item in value)
    return True


def _historical_report_usable(row: Any) -> bool:
    if not isinstance(row, Mapping):
        return False
    status = str(row.get('status') or '').lower()
    quality_gate_status = str(row.get('quality_gate_status') or '').lower()
    return bool(
        row.get('has_final_text')
        or row.get('delivery_ready')
        or status in {'published', 'generated', 'approved'}
        or quality_gate_status == 'passed'
    )


def _source_status_risks(statuses: Mapping[str, Any], *, skip_keys: set[str] | None = None, prefix: str = '') -> list[str]:
    skip = skip_keys or set()
    risks: list[str] = []
    for key, value in statuses.items():
        key_text = str(key)
        if key_text in skip:
            continue
        name = f'{prefix}.{key_text}' if prefix else key_text
        if isinstance(value, Mapping):
            status_value = value.get('status')
            if _source_incomplete(status_value):
                risks.append(f'{name}={_plain_text(status_value)}')
            risks.extend(_source_status_risks(value, skip_keys=skip, prefix=name))
        elif _source_incomplete(value):
            risks.append(f'{name}={_plain_text(value)}')
    return risks


def _source_incomplete(value: Any) -> bool:
    normalized = str(value or '').lower()
    return any(marker in normalized for marker in _REVIEW_STATUS_MARKERS)


def _field_match_rate_text(value: Any) -> str:
    rate = _normalise_rate(value)
    return '暂无' if rate is None else f'{rate:.1f}%'


def _action_text(action: Any) -> str:
    if isinstance(action, Mapping):
        parts = []
        action_type = action.get('action_type')
        risk_level = action.get('risk_level')
        field_name = action.get('field_name') or action.get('field')
        target_key = action.get('target_key') or action.get('target_table')
        if action_type not in (None, ''):
            parts.append(f'动作={_plain_text(action_type)}')
        if risk_level not in (None, ''):
            parts.append(f'风险={_plain_text(risk_level)}')
        if field_name not in (None, ''):
            parts.append(f'字段={_plain_text(field_name)}')
        if target_key not in (None, ''):
            parts.append(f'目标={_plain_text(target_key)}')
        return '，'.join(parts) if parts else '待复核动作'
    return str(action).strip()


def _requires_review(judgment: Mapping[str, Any]) -> bool:
    return bool(_as_list(judgment.get('risks')))


def _trace_id(sources: dict[str, Any]) -> str:
    value = sources.get('trace_id') or _as_mapping(sources.get('audit_run')).get('trace_id')
    return str(value).strip() if value is not None else ''


def _date_label(value: date) -> str:
    return f'{value.month}月{value.day}日'


def _join_text(items: list[str], *, empty: str = '暂无') -> str:
    clean = [item for item in items if item]
    return '；'.join(clean) if clean else empty


def _plain_text(value: Any) -> str:
    if value in (None, '', [], {}):
        return '暂无'
    if isinstance(value, Mapping):
        parts = [f'{key}={_plain_text(item)}' for key, item in value.items() if item not in (None, '', [], {})]
        return '，'.join(parts) if parts else '暂无'
    if isinstance(value, (list, tuple, set)):
        parts = [_plain_text(item) for item in value if item not in (None, '', [], {})]
        return '、'.join(parts) if parts else '暂无'
    return str(value).strip() or '暂无'


def _text_or_empty(value: Any) -> str:
    return '' if value is None else str(value).strip()


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]
