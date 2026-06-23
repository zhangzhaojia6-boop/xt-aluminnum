from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from sqlalchemy import func
from sqlalchemy.orm import Session

load_dotenv(ROOT / '.env')

from app.adapters import get_mes_adapter
from app.adapters.mes_adapter import NullMesAdapter
from app.config import settings
from app.core.business_time import last_completed_production_business_date
from app.core.redaction import filter_sensitive_mapping, redact_secret_text
from app.database import get_sessionmaker
from app.models.agent_communication import AgentOperationApproval, AgentOutboxMessage, ChatInboxMessage
from app.models.mes import MesSyncRunLog
from app.models.rag import HermesApprovedLesson
from app.models.reports import DailyFactCorrection, DailyReport
from app.models.system import User
from app.services import agent_designated_operation_service, hermes_governance_service, hermes_memory_service, hermes_rag_service
from app.services.agent_command_service import handle_agent_command
from app.services.hermes_day1_intent_service import (
    Day1CommandParseError,
    HermesDay1Command,
    classify_day1_actor,
    parse_day1_command,
    require_root_owner_for_day1_report,
)
from app.services.hermes_day1_orchestrator import run_day1_super_brain
from app.services.hermes_intent_service import parse_hermes_intent
from app.services.rag_service import query_knowledge
from app.tasks import daily_report as daily_report_task
from app.tasks import mes_sync


COMMAND_LEVELS = {
    'dingtalk-command': 'L0',
    'agent-ask': 'L0',
    'rag-query': 'L0',
    'mes-status': 'L0',
    'mes-preview': 'L0',
    'outbox-status': 'L0',
    'rag-ingest-file': 'L1',
    'rag-ingest-directory': 'L1',
    'rag-ingest-mes-route': 'L1',
    'rag-ingest-mes-page': 'L1',
    'rag-ingest-web-source': 'L1',
    'rag-ingest-system-understanding': 'L1',
    'rag-rebuild-index': 'L1',
    'learning-approve': 'L3',
    'agent-governance-status': 'L0',
    'agent-governance-apply': 'L1',
    'mes-sync-realtime': 'L1',
    'mes-sync-business': 'L1',
    'mes-sync-reference': 'L1',
    'mes-mvc-preview': 'L1',
    'ops-status': 'L1',
    'visual-inspect': 'L2',
    'approval-preview': 'L3',
    'day1-report': 'L3',
}
SQL_KEYWORDS = {'select', 'insert', 'update', 'delete', 'drop', 'alter', 'truncate', 'exec', 'execute'}
VISUAL_URL_HOSTS = {'xtmijd.com', 'www.xtmijd.com', 'mes.xintaily.com'}
BUSINESS_DATE_TEXT_RE = re.compile(r'(?:\d{4}[-._]\d{1,2}[-._]\d{1,2}|\d{1,2}月\d{1,2}日)')


@dataclass(frozen=True, slots=True)
class HermesAuth:
    user: User
    is_owner: bool
    level: str


class AgentCliError(RuntimeError):
    pass


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise AgentCliError(f'invalid_arguments:{message}')

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if status:
            raise AgentCliError(f'invalid_arguments:{message or status}')
        raise SystemExit(status)


def main(argv: list[str] | None = None) -> int:
    args = None
    try:
        args = _parse_args(argv if argv is not None else sys.argv[1:])
        if args.command not in COMMAND_LEVELS:
            _reject_if_sql(args.command)
            raise AgentCliError('command_not_allowed')
        auth = _authorize(args)
        result = _run_with_db(args, auth)
        _emit({'ok': True, **result})
        return 0
    except SystemExit as exc:
        _emit({'ok': False, 'error': 'invalid_arguments', 'detail': str(exc)})
        return 2
    except AgentCliError as exc:
        error_code = redact_secret_text(str(exc) or type(exc).__name__)
        payload: dict[str, Any] = {'ok': False, 'error': error_code}
        detail = _cli_error_detail(error_code, args)
        if detail:
            payload['detail'] = detail
        _emit(payload)
        return 1
    except Exception as exc:
        _emit({'ok': False, 'error': redact_secret_text(str(exc) or type(exc).__name__)})
        return 1


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = JsonArgumentParser(prog='agent_cli', add_help=False)
    parser.add_argument('command')
    parser.add_argument('--text', default='')
    parser.add_argument('--query', default='')
    parser.add_argument('--path', default='')
    parser.add_argument('--output', default='')
    parser.add_argument('--directory', default='')
    parser.add_argument('--url', default='')
    parser.add_argument('--page-title', default='')
    parser.add_argument('--field', action='append', default=[])
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--target-date', default='')
    parser.add_argument('--report-id', type=int)
    parser.add_argument('--learning-event-id', type=int)
    parser.add_argument('--group-id', default='')
    parser.add_argument('--channel', default='dingtalk_group')
    parser.add_argument('--agent-code', default='factory_dispatch')
    parser.add_argument('--trace-id', default='')
    parser.add_argument('--dingtalk-user-id', default='')
    parser.add_argument('--dingtalk-union-id', default='')
    parser.add_argument('--workshop', default='')
    parser.add_argument('--machine-code', default='')
    parser.add_argument('--doctor', action='store_true')
    parser.add_argument('--queue-outbox', action='store_true')
    return parser.parse_args(argv)


def _run_with_db(args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        handlers: dict[str, Callable[[Session, argparse.Namespace, HermesAuth], dict[str, Any]]] = {
            'dingtalk-command': _cmd_dingtalk_command,
            'agent-ask': _cmd_agent_ask,
            'rag-query': _cmd_rag_query,
            'rag-ingest-file': _cmd_rag_ingest_file,
            'rag-ingest-directory': _cmd_rag_ingest_directory,
            'rag-ingest-mes-route': _cmd_rag_ingest_mes_route,
            'rag-ingest-mes-page': _cmd_rag_ingest_mes_page,
            'rag-ingest-web-source': _cmd_rag_ingest_web_source,
            'rag-ingest-system-understanding': _cmd_rag_ingest_system_understanding,
            'rag-rebuild-index': _cmd_rag_rebuild_index,
            'learning-approve': _cmd_learning_approve,
            'agent-governance-status': _cmd_agent_governance_status,
            'agent-governance-apply': _cmd_agent_governance_apply,
            'mes-status': _cmd_mes_status,
            'mes-preview': _cmd_mes_preview,
            'mes-sync-realtime': _cmd_mes_sync_realtime,
            'mes-sync-business': _cmd_mes_sync_business,
            'mes-sync-reference': _cmd_mes_sync_reference,
            'mes-mvc-preview': _cmd_mes_mvc_preview,
            'ops-status': _cmd_ops_status,
            'outbox-status': _cmd_outbox_status,
            'approval-preview': _cmd_approval_preview,
            'visual-inspect': _cmd_visual_inspect,
            'day1-report': _cmd_day1_report,
        }
        try:
            result = handlers[args.command](db, args, auth)
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise


def _authorize(args: argparse.Namespace) -> HermesAuth:
    level = COMMAND_LEVELS.get(args.command)
    if level is None:
        raise AgentCliError('command_not_allowed')
    group_ids = _csv_env('HERMES_ALLOWED_GROUP_IDS') or settings.hermes_allowed_group_ids
    group_id = _clean(args.group_id)
    if group_ids and group_id and group_id not in group_ids:
        raise AgentCliError('group_not_allowed')

    dingtalk_user_id = _clean(args.dingtalk_user_id)
    dingtalk_union_id = _clean(args.dingtalk_union_id)
    if not dingtalk_user_id and not dingtalk_union_id:
        raise AgentCliError('dingtalk_identity_required')

    SessionLocal = get_sessionmaker()
    with SessionLocal() as db:
        user = _find_user(db, dingtalk_user_id=dingtalk_user_id, dingtalk_union_id=dingtalk_union_id)
        if user is None or not user.is_active:
            raise AgentCliError('dingtalk_user_not_bound')
        owner_ids = _csv_env('HERMES_OWNER_DINGTALK_USER_IDS') or settings.hermes_owner_dingtalk_user_ids
        allowed_ids = _csv_env('HERMES_ALLOWED_DINGTALK_USER_IDS') or settings.hermes_allowed_dingtalk_user_ids
        identity_values = {dingtalk_user_id, dingtalk_union_id, _clean(user.dingtalk_user_id), _clean(user.dingtalk_union_id)}
        is_owner = bool(owner_ids & identity_values) or user.name == '张兆嘉'
        is_allowed = is_owner or bool(allowed_ids & identity_values)
        if not is_allowed:
            raise AgentCliError('user_not_allowed')
        if level in {'L1', 'L2', 'L3'} and not is_owner:
            raise AgentCliError('owner_required')
        if level == 'L1' and args.command.startswith('mes-sync') and not _ops_enabled():
            raise AgentCliError('hermes_ops_disabled')
        db.expunge(user)
        return HermesAuth(user=user, is_owner=is_owner, level=level)


def _cmd_dingtalk_command(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    text = _normalize_dingtalk_text(args.text)
    if not text:
        raise AgentCliError('command_text_required')
    if _is_duplicate_dingtalk_message(db, args):
        return {
            'action': 'dingtalk-duplicate',
            'reply': '',
            'trace_id': _trace_id(args),
            'data': {'should_reply': False, 'reason': 'duplicate_message'},
        }

    is_slash = text.startswith('/')
    is_direct = is_slash or _is_direct_dingtalk_mention(args.text)
    command, rest = _split_slash_command(text) if is_slash or is_direct else ('', '')

    if not is_slash:
        flexible_intent = parse_hermes_intent(text, default_year=_day1_default_year(args))
        business_date_text = flexible_intent.get('business_date')
        if flexible_intent.get('intent') == 'daily_report':
            if business_date_text:
                day1_command = HermesDay1Command(
                    source_text=text,
                    business_date=date.fromisoformat(str(business_date_text)),
                    report_type='daily_report',
                    audience=str(flexible_intent.get('audience') or 'root_owner'),
                    output_format='three_part',
                )
                return _cmd_day1_report(db, args, auth, parsed_command=day1_command)
            if _looks_like_business_date_text(text):
                raise AgentCliError('invalid_date')
            raise AgentCliError('day1_command_unrecognized')

    if _is_natural_language_day1_text(text):
        try:
            day1_command = parse_day1_command(text, default_year=_day1_default_year(args))
        except Day1CommandParseError as exc:
            raise AgentCliError(exc.code) from exc
        if day1_command is not None:
            return _cmd_day1_report(db, args, auth, parsed_command=day1_command)

    if command in {'查知识', '字段', '口径', 'MES路线', 'mes路线', '缺陷原因', '工艺解释'}:
        inbox = _record_dingtalk_command_inbox(db, args, auth, text=text, handling='rag_query')
        query_text = rest or text
        payload = _query_rag(db, query_text=query_text, args=args, auth=auth)
        payload['data']['chat_inbox_id'] = inbox.id
        return {'action': 'rag-query', 'reply': payload['reply'], 'data': payload['data'], 'trace_id': _trace_id(args)}
    if command in {'同步MES', '同步mes'}:
        if not auth.is_owner:
            raise AgentCliError('owner_required')
        if not _ops_enabled():
            raise AgentCliError('hermes_ops_disabled')
        inbox = _record_dingtalk_command_inbox(db, args, auth, text=text, handling='mes_sync')
        payload = _cmd_mes_sync_business(db, args, auth)
        payload.setdefault('data', {})['chat_inbox_id'] = inbox.id
        return payload
    if command in {'日报', '发日报'}:
        if not auth.is_owner:
            raise AgentCliError('owner_required')
        inbox = _record_dingtalk_command_inbox(db, args, auth, text=text, handling='daily_report')
        payload = _cmd_daily_report_product(db, args, auth)
        payload.setdefault('data', {})['chat_inbox_id'] = inbox.id
        return payload
    if command in {'补产量', '正式通知'}:
        if not auth.is_owner:
            raise AgentCliError('owner_required')
        inbox = _record_dingtalk_command_inbox(db, args, auth, text=text, handling='approval_preview')
        payload = _cmd_approval_preview(db, args, auth)
        payload.setdefault('data', {})['chat_inbox_id'] = inbox.id
        return payload
    if command in {'巡检页面'}:
        if not auth.is_owner:
            raise AgentCliError('owner_required')
        inbox = _record_dingtalk_command_inbox(db, args, auth, text=text, handling='visual_inspect')
        payload = _cmd_visual_inspect(db, args, auth)
        payload.setdefault('data', {})['chat_inbox_id'] = inbox.id
        return payload
    if is_slash and command and command not in {'产量', '能耗', '停机', '异常'}:
        raise AgentCliError('dingtalk_command_not_allowed')
    if is_direct or _should_auto_reply_to_dingtalk_text(text):
        return _cmd_agent_ask(db, args, auth, text_override=rest or text.lstrip('/'))
    return _record_dingtalk_message_without_reply(db, args, auth, text=text)


def _cmd_agent_ask(
    db: Session,
    args: argparse.Namespace,
    auth: HermesAuth,
    *,
    text_override: str | None = None,
) -> dict[str, Any]:
    text = text_override or args.text or args.query
    _reject_if_sql(text)
    result = handle_agent_command(
        db,
        channel=_resolved_dingtalk_channel(args),
        group_id=args.group_id or None,
        sender_external_id=args.dingtalk_user_id or args.dingtalk_union_id,
        text=text,
        agent_code=args.agent_code,
        trace_id=_trace_id(args),
        workshop=args.workshop or None,
        machine_code=args.machine_code or None,
        queue_outbox=bool(args.queue_outbox),
        source_payload={'source': 'hermes_cli', 'command': args.command},
        current_user=auth.user,
    )
    hermes_memory_service.remember_short_term(
        db,
        conversation_key=args.group_id or f'user:{auth.user.id}',
        memory_key='last_agent_command',
        memory_value={'text': text, 'intent': result.intent, 'answer': result.answer},
        actor=auth.user,
        trace_id=result.trace_id,
    )
    _record_learning_memory(
        db,
        question=text,
        answer=result.answer,
        trace_id=result.trace_id,
        tools_called=['handle_agent_command'],
        sources=_learning_sources_from_agent_result(result),
        actor=auth.user,
    )
    return {
        'action': 'agent-ask',
        'reply': result.answer,
        'trace_id': result.trace_id,
        'data': {
            'intent': result.intent,
            'status_color': result.status_color,
            'facts': result.facts,
            'rag': result.rag,
            'chat_inbox_id': result.chat_inbox_id,
            'agent_run_id': result.agent_run_id,
            'outbox_message_id': result.outbox_message_id,
        },
    }


def _cmd_rag_query(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    return _query_rag(db, query_text=args.query or args.text, args=args, auth=auth)


def _query_rag(db: Session, *, query_text: str, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    _reject_if_sql(query_text)
    payload = query_knowledge(
        db,
        query=query_text,
        limit=max(1, min(int(args.limit or 5), 10)),
        user=auth.user,
        workshop=args.workshop or None,
        machine_code=args.machine_code or None,
    )
    trace_id = _trace_id(args)
    _record_learning_memory(
        db,
        question=query_text,
        answer=str(payload.get('answer') or ''),
        trace_id=trace_id,
        tools_called=['query_knowledge'],
        sources=payload.get('citations') or [],
        actor=auth.user,
    )
    return {'action': 'rag-query', 'reply': payload.get('answer'), 'data': payload, 'trace_id': trace_id}


def _cmd_rag_ingest_file(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    document = hermes_rag_service.ingest_file(db, path=args.path, actor=auth.user)
    return _document_result('rag-ingest-file', document)


def _cmd_rag_ingest_directory(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    documents = hermes_rag_service.ingest_directory(db, path=args.directory or args.path, actor=auth.user)
    return {'action': 'rag-ingest-directory', 'reply': f'已入库 {len(documents)} 个文档', 'data': {'document_count': len(documents)}, 'trace_id': _trace_id(args)}


def _cmd_rag_ingest_mes_route(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    document = hermes_rag_service.ingest_mes_route_catalog(db, actor=auth.user)
    return _document_result('rag-ingest-mes-route', document)


def _cmd_rag_ingest_mes_page(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    document = hermes_rag_service.ingest_mes_page_knowledge(
        db,
        url=args.url,
        actor=auth.user,
        page_title=args.page_title or None,
        fields=args.field or None,
    )
    return _document_result('rag-ingest-mes-page', document)


def _cmd_rag_ingest_web_source(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    document = hermes_rag_service.ingest_web_source(db, url=args.url, actor=auth.user)
    return _document_result('rag-ingest-web-source', document)


def _cmd_rag_ingest_system_understanding(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    result = hermes_governance_service.write_safe_system_understanding_copy(
        source_path=args.path,
        output_path=args.output or None,
    )
    document = hermes_rag_service.ingest_file(
        db,
        path=result.output_path,
        actor=auth.user,
        source_type='internal_system_understanding',
        metadata={
            'review_status': 'approved',
            'temporal_scope': 'stable_knowledge',
            'source_type': 'internal_system_understanding',
            'redacted_line_count': result.redacted_line_count,
        },
    )
    payload = _document_result('rag-ingest-system-understanding', document)
    payload['data'].update(
        {
            'safe_output_path': result.output_path,
            'redacted_line_count': result.redacted_line_count,
            'original_size': result.original_size,
            'safe_size': result.safe_size,
        }
    )
    return payload


def _cmd_rag_rebuild_index(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    count = hermes_rag_service.rebuild_rag_embeddings(db)
    return {'action': 'rag-rebuild-index', 'reply': f'已重建 {count} 个切片向量', 'data': {'embedding_count': count}, 'trace_id': _trace_id(args)}


def _cmd_learning_approve(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    if not args.learning_event_id:
        raise AgentCliError('learning_event_id_required')
    lesson = hermes_rag_service.approve_learning_event(db, event_id=args.learning_event_id, approver=auth.user)
    return {
        'action': 'learning-approve',
        'reply': f'学习候选 #{args.learning_event_id} 已进入长期知识库',
        'trace_id': _trace_id(args),
        'data': {
            'learning_event_id': args.learning_event_id,
            'approved_lesson_id': lesson.id,
            'document_id': lesson.document_id,
            'status': lesson.status,
        },
    }


def _cmd_agent_governance_status(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    payload = hermes_governance_service.apply_legacy_agent_governance(db, apply=False)
    return {'action': 'agent-governance-status', 'reply': 'Agent 治理状态已读取', 'data': payload, 'trace_id': _trace_id(args)}


def _cmd_agent_governance_apply(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    payload = hermes_governance_service.apply_legacy_agent_governance(db, apply=True)
    return {'action': 'agent-governance-apply', 'reply': '旧 Agent 已标记为后台工具层', 'data': payload, 'trace_id': _trace_id(args)}


def _cmd_mes_status(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    latest = db.query(MesSyncRunLog).order_by(MesSyncRunLog.started_at.desc(), MesSyncRunLog.id.desc()).first()
    return {
        'action': 'mes-status',
        'reply': 'MES 同步状态已读取',
        'trace_id': _trace_id(args),
        'data': {
            'adapter': settings.MES_ADAPTER,
            'latest': _mes_log_payload(latest),
            'configured': (settings.MES_ADAPTER or 'null').lower() != 'null',
        },
    }


def _cmd_mes_preview(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    adapter = get_mes_adapter()
    if isinstance(adapter, NullMesAdapter):
        raise AgentCliError('mes_adapter_unconfigured')
    records = adapter.list_workshop_process_records(limit=max(1, min(args.limit, 20)))
    return {
        'action': 'mes-preview',
        'reply': f'只读预览 {len(records)} 条 MES 过站记录',
        'trace_id': _trace_id(args),
        'data': {'row_count': len(records), 'rows': [_source_record_payload(item) for item in records[:5]]},
    }


def _cmd_mes_sync_realtime(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    return _sync_result('mes-sync-realtime', mes_sync.sync_mes_realtime_projection())


def _cmd_mes_sync_business(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    return _sync_result('mes-sync-business', mes_sync.sync_mes_business_projection())


def _cmd_mes_sync_reference(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    return _sync_result('mes-sync-reference', mes_sync.sync_mes_reference_projection())


def _cmd_mes_mvc_preview(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    return {
        'action': 'mes-mvc-preview',
        'reply': 'MES MVC 备用通道为只读预览模式',
        'trace_id': _trace_id(args),
        'data': {
            'configured': all([settings.MES_MVC_BASE_URL, settings.MES_MVC_USERNAME, settings.MES_MVC_PASSWORD]),
            'base_url': _safe_url(settings.MES_MVC_BASE_URL),
            'read_only': True,
            'allowed_host': 'mes.xintaily.com',
        },
    }


def _cmd_ops_status(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    return {
        'action': 'ops-status',
        'reply': '运维状态已读取',
        'trace_id': _trace_id(args),
        'data': {
            'database': 'connected',
            'mes_adapter': settings.MES_ADAPTER,
            'hermes_ops_enabled': _ops_enabled(),
            'write_guards': ['no_free_sql', 'no_free_shell', 'mes_original_read_only'],
            'memory': hermes_memory_service.memory_architecture(),
        },
    }


def _cmd_outbox_status(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    rows = db.query(AgentOutboxMessage.status, func.count(AgentOutboxMessage.id)).group_by(AgentOutboxMessage.status).all()
    return {
        'action': 'outbox-status',
        'reply': 'outbox 状态已读取',
        'trace_id': _trace_id(args),
        'data': {'status_counts': {str(status): int(count) for status, count in rows}},
    }


def _cmd_daily_report_product(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    business_date = _target_date(args)
    product = daily_report_task.build_daily_report_product(
        db,
        target_date=business_date,
        generated_by='hermes_cli',
    )
    hermes_rag_service.archive_latest_daily_report_to_rag(
        db,
        report_date=business_date,
        actor=auth.user,
        generated_by='hermes',
    )
    return {
        'action': 'daily-report',
        'reply': product.get('text') or '日报已生成，但当前没有可输出的正文。',
        'trace_id': _trace_id(args),
        'data': {
            'business_date': product.get('business_date'),
            'report_id': product.get('report_id'),
            'status': product.get('status'),
            'missing_fields': product.get('missing_fields') or [],
            'conflicts': product.get('conflicts') or [],
            'scheduled_at': product.get('scheduled_at') or '07:30',
            'sent': False,
            'delivery': 'command_reply_and_scheduled_job',
        },
    }


def _cmd_approval_preview(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    report_id = args.report_id or _latest_report_id(db, target_date=_target_date(args))
    if report_id is None:
        return {
            'action': 'approval-preview',
            'reply': '未找到可预览的日报档案，未正式发送；请先生成日报后再发起审批。',
            'trace_id': _trace_id(args),
            'data': {'status': 'daily_report_not_found', 'sent': False, 'approval_id': None},
        }
    approval = agent_designated_operation_service.request_publish_daily_report_preview(
        db,
        requester_user_id=auth.user.id,
        channel_key=args.group_id,
        allowed_user_ids={auth.user.id},
        report_id=report_id,
        trace_id=_trace_id(args),
    )
    return {
        'action': 'approval-preview',
        'reply': f'已生成日报审批预览 #{approval.id}，未正式发送',
        'trace_id': approval.trace_id,
        'approval_id': approval.id,
        'data': {'approval_id': approval.id, 'status': approval.status, 'preview_payload': approval.preview_payload},
    }


def _cmd_visual_inspect(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    url = args.url or 'https://xtmijd.com/manage/today'
    host = _host(url)
    if host not in VISUAL_URL_HOSTS:
        raise AgentCliError('visual_url_not_allowed')
    evidence = {
        'url': url,
        'allowed_host': host,
        'screenshot_required': True,
        'read_numbers_required': True,
        'compare_sources': ['page', 'api', 'mes_projection'],
    }
    return {'action': 'visual-inspect', 'reply': '已生成视觉巡检工具契约，等待 Hermes 浏览器环境执行', 'trace_id': _trace_id(args), 'evidence': evidence, 'data': evidence}


def _cmd_day1_report(
    db: Session,
    args: argparse.Namespace,
    auth: HermesAuth,
    *,
    parsed_command=None,
) -> dict[str, Any]:
    command_text = args.text or args.query
    flexible_intent = None
    try:
        command = parsed_command or parse_day1_command(command_text, default_year=_day1_default_year(args))
    except Day1CommandParseError as exc:
        raise AgentCliError(exc.code) from exc
    if command is None:
        flexible_intent = parse_hermes_intent(command_text, default_year=_day1_default_year(args))
        business_date_text = flexible_intent.get('business_date')
        if flexible_intent.get('intent') == 'daily_report' and business_date_text:
            command = HermesDay1Command(
                source_text=command_text,
                business_date=date.fromisoformat(str(business_date_text)),
                report_type='daily_report',
                audience=str(flexible_intent.get('audience') or 'root_owner'),
                output_format='three_part',
            )
    if command is None:
        raise AgentCliError('day1_command_unrecognized')
    if flexible_intent is None:
        flexible_intent = parse_hermes_intent(
            args.text or args.query or getattr(command, 'source_text', ''),
            default_year=_day1_default_year(args),
        )

    decision = classify_day1_actor(
        auth.user,
        sender_user_id=args.dingtalk_user_id,
        sender_union_id=args.dingtalk_union_id,
        channel=_resolved_dingtalk_channel(args),
        group_id=args.group_id,
    )
    try:
        require_root_owner_for_day1_report(decision)
    except PermissionError as exc:
        raise AgentCliError(str(exc)) from exc

    if args.doctor:
        return _cmd_day1_report_doctor(args, command, decision)

    if not _day1_enabled():
        raise AgentCliError('hermes_day1_disabled')
    if _output_skill_root_path() is None:
        raise AgentCliError('output_skill_source_missing')

    _persist_direct_root_owner_corrections(db, args=args, auth=auth, command=command, intent=flexible_intent)

    trace_id = _trace_id(args)
    inbox = _record_dingtalk_command_inbox(
        db,
        args,
        auth,
        text=str(command.source_text or args.text or args.query),
        handling='day1_report',
        trace_id=trace_id,
    )
    result = run_day1_super_brain(
        db,
        command=command,
        actor=auth.user,
        trace_id=trace_id,
        chat_inbox=inbox,
    )
    return {
        'action': 'day1-report',
        'reply': result.answer,
        'trace_id': result.trace_id,
        'data': {
            'status': result.status,
            'agent_run_id': result.agent_run_id,
            'report_id': result.report_id,
            'chat_inbox_id': inbox.id,
            'message_count': len(result.reply_messages),
        },
    }


def _persist_direct_root_owner_corrections(
    db: Session,
    *,
    args: argparse.Namespace,
    auth: HermesAuth,
    command: HermesDay1Command,
    intent: dict[str, Any],
) -> None:
    if intent.get('correction_policy') != 'root_owner_direct':
        return
    for item in intent.get('requested_corrections') or []:
        if not isinstance(item, dict):
            continue
        field_name = str(item.get('field_name') or '').strip()
        if not field_name:
            continue
        db.add(
            DailyFactCorrection(
                business_date=command.business_date,
                field_name=field_name,
                value_payload={'value': item.get('value')},
                unit=str(item.get('unit') or '') or None,
                source_text=str(intent.get('raw_text') or ''),
                before_value=None,
                reason=str(item.get('reason') or 'root_owner 自然语言修正'),
                actor_user_id=getattr(auth.user, 'id', None),
                trace_id=_trace_id(args),
            )
        )
    db.flush()


def _cmd_day1_report_doctor(
    args: argparse.Namespace,
    command,
    decision,
) -> dict[str, Any]:
    output_skill_root = _output_skill_root_path()
    checks = {
        'feature_flag': 'ok' if _day1_enabled() else 'disabled',
        'root_owner_identity': 'ok' if decision.is_root_owner else decision.reason,
        'command_parse': 'ok',
        'output_skill_source': 'ok' if output_skill_root is not None else 'missing',
    }
    return {
        'action': 'day1-report-doctor',
        'reply': 'Day-1 预检完成',
        'trace_id': _trace_id(args),
        'data': {
            'business_date': command.business_date.isoformat(),
            'checks': checks,
            'next': _doctor_next_step(checks),
        },
    }


def _find_user(db: Session, *, dingtalk_user_id: str, dingtalk_union_id: str) -> User | None:
    query = db.query(User)
    if dingtalk_user_id:
        user = query.filter(User.dingtalk_user_id == dingtalk_user_id).first()
        if user is not None:
            return user
    if dingtalk_union_id:
        return query.filter(User.dingtalk_union_id == dingtalk_union_id).first()
    return None


def _normalize_dingtalk_text(text: str) -> str:
    clean = str(text or '').strip()
    if clean.startswith('@'):
        return re.sub(r'^@\S+\s*', '', clean).strip()
    return clean


def _split_slash_command(text: str) -> tuple[str, str]:
    clean = str(text or '').strip()
    if clean.startswith('/'):
        clean = clean[1:].strip()
    if not clean:
        return '', ''
    parts = clean.split(maxsplit=1)
    return parts[0], parts[1].strip() if len(parts) > 1 else ''


def _is_direct_dingtalk_mention(text: str) -> bool:
    clean = str(text or '').strip()
    return clean.startswith('@')


def _should_auto_reply_to_dingtalk_text(text: str) -> bool:
    clean = str(text or '').strip()
    if not clean:
        return False
    keywords = (
        '产量',
        '包装',
        '入库',
        '发货',
        '在制',
        '能耗',
        '电耗',
        '气耗',
        '吨耗',
        '停机',
        '异常',
        '质量',
        '日报',
        '口径',
        'MES',
        'mes',
        '同步',
        '铸锭',
        '铸二',
        '铸三',
        '热轧',
        '精整',
        '拉矫',
        '剪切',
        '园区',
        '1650',
        '1850',
        '2050',
    )
    return any(keyword in clean for keyword in keywords)


def _is_duplicate_dingtalk_message(db: Session, args: argparse.Namespace) -> bool:
    trace_id = _clean(args.trace_id)
    if not trace_id:
        return False
    query = db.query(ChatInboxMessage.id).filter(
        ChatInboxMessage.channel == _resolved_dingtalk_channel(args),
        ChatInboxMessage.trace_id == trace_id,
    )
    group_id = _clean(args.group_id)
    if group_id:
        query = query.filter(ChatInboxMessage.group_id == group_id)
    return query.first() is not None


def _record_dingtalk_message_without_reply(
    db: Session,
    args: argparse.Namespace,
    auth: HermesAuth,
    *,
    text: str,
) -> dict[str, Any]:
    trace_id = _trace_id(args)
    inbox = _record_dingtalk_command_inbox(db, args, auth, text=text, handling='record_only', trace_id=trace_id)
    hermes_memory_service.remember_short_term(
        db,
        conversation_key=args.group_id or f'user:{auth.user.id}',
        memory_key='last_group_message',
        memory_value={'text': text, 'handling': 'record_only'},
        actor=auth.user,
        trace_id=trace_id,
    )
    return {
        'action': 'dingtalk-message-recorded',
        'reply': '',
        'trace_id': trace_id,
        'data': {
            'should_reply': False,
            'chat_inbox_id': inbox.id,
            'handling': 'record_only',
        },
    }


def _record_dingtalk_command_inbox(
    db: Session,
    args: argparse.Namespace,
    auth: HermesAuth,
    *,
    text: str,
    handling: str,
    trace_id: str | None = None,
) -> ChatInboxMessage:
    inbox = ChatInboxMessage(
        channel=_resolved_dingtalk_channel(args),
        group_id=_clean(args.group_id) or None,
        sender_external_id=_clean(args.dingtalk_user_id) or _clean(args.dingtalk_union_id) or None,
        text=text,
        agent_code=args.agent_code or 'factory_dispatch',
        trace_id=trace_id or _trace_id(args),
        source_payload={
            'source': 'hermes_cli',
            'command': args.command,
            'handling': handling,
            'actor_user_id': auth.user.id,
        },
    )
    db.add(inbox)
    db.flush()
    return inbox


def _record_learning_memory(
    db: Session,
    *,
    question: str,
    answer: str,
    trace_id: str,
    tools_called: list,
    sources: list,
    actor: User | None,
) -> None:
    if not str(answer or '').strip():
        return
    event = hermes_rag_service.record_learning_event(
        db,
        question=question,
        answer=answer,
        trace_id=trace_id,
        tools_called=tools_called,
        sources=sources,
        actor=actor,
    )
    if _should_auto_promote_learning(question=question, answer=answer, tools_called=tools_called, sources=sources):
        _auto_approve_learning_event(db, event=event, approver=actor)


def _auto_approve_learning_event(db: Session, *, event, approver: User | None) -> HermesApprovedLesson:
    event.status = 'approved'
    lesson = HermesApprovedLesson(
        learning_event_id=event.id,
        lesson_text=str(event.answer or '').strip(),
        source_payload={
            'trace_id': event.trace_id,
            'sources': event.sources or [],
            'auto_promoted': True,
            'storage': 'approved_lessons_only',
        },
        document_id=None,
        approved_by_id=getattr(approver, 'id', None),
        status='active',
    )
    db.add(lesson)
    db.flush()
    return lesson


def _should_auto_promote_learning(
    *,
    question: str,
    answer: str,
    tools_called: list,
    sources: list,
) -> bool:
    clean_answer = str(answer or '').strip()
    if not clean_answer or '数据不足' in clean_answer:
        return False
    tool_names = {str(item) for item in (tools_called or [])}
    if 'handle_agent_command' in tool_names:
        return False
    if 'query_knowledge' not in tool_names:
        return False
    clean_question = str(question or '').strip()
    stable_keywords = (
        '口径',
        '规则',
        'SOP',
        'sop',
        '模板',
        '字段',
        '路线',
        '来自哪里',
        '归哪里',
        '怎么',
        '知识',
        '制度',
        '说明',
    )
    realtime_keywords = (
        '今天',
        '今日',
        '现在',
        '实时',
        '当前',
        '多少',
        '产量',
        '能耗',
        '停机',
        '异常',
        '入库',
        '发货',
    )
    has_stable_intent = any(keyword in clean_question for keyword in stable_keywords)
    has_realtime_intent = any(keyword in clean_question for keyword in realtime_keywords)
    if has_realtime_intent and not has_stable_intent:
        return False
    stable_source_types = {
        'approved_lesson',
        'daily_report_archive',
        'external_industry_knowledge',
        'internal_system_understanding',
        'mes_page_route',
        'mes_route_catalog',
        'uploaded_file',
    }
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        metadata = source.get('metadata') if isinstance(source.get('metadata'), dict) else {}
        source_type = str(source.get('source_type') or metadata.get('source_type') or '').strip()
        if source_type == 'business_fact':
            return False
        if source_type in stable_source_types:
            return True
    return bool(has_stable_intent and sources)


def _learning_sources_from_agent_result(result) -> list:
    sources: list = []
    facts = getattr(result, 'facts', None) or {}
    data_source = facts.get('data_source')
    if data_source:
        sources.append({'source_type': 'business_fact', 'source_ref': data_source})
    rag = getattr(result, 'rag', None) or {}
    sources.extend(rag.get('citations') or [])
    return sources


def _reject_if_sql(text: str) -> None:
    tokens = {item.strip().lower() for item in str(text or '').replace(';', ' ').split()}
    if SQL_KEYWORDS & tokens:
        raise AgentCliError('free_sql_not_allowed')


def _trace_id(args: argparse.Namespace) -> str:
    return _clean(args.trace_id) or uuid4().hex


def _target_date(args: argparse.Namespace) -> date:
    if args.target_date:
        return date.fromisoformat(args.target_date)
    return last_completed_production_business_date()


def _latest_report_id(db: Session, *, target_date: date) -> int | None:
    report = (
        db.query(DailyReport)
        .filter(DailyReport.report_date == target_date, DailyReport.report_type == 'production')
        .order_by(DailyReport.published_at.desc().nullslast(), DailyReport.id.desc())
        .first()
    )
    return report.id if report is not None else None


def _document_result(action: str, document) -> dict[str, Any]:
    return {
        'action': action,
        'reply': f'已入库文档 {document.filename}',
        'trace_id': uuid4().hex,
        'data': {'document_id': document.id, 'filename': document.filename, 'status': document.status, 'chunk_count': document.chunk_count},
    }


def _sync_result(action: str, result: dict[str, Any]) -> dict[str, Any]:
    return {'action': action, 'reply': 'MES 同步任务已执行', 'trace_id': uuid4().hex, 'data': filter_sensitive_mapping(result)}


def _mes_log_payload(item: MesSyncRunLog | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {
        'cursor_key': item.cursor_key,
        'status': item.status,
        'fetched_count': item.fetched_count,
        'upserted_count': item.upserted_count,
        'lag_seconds': float(item.lag_seconds) if item.lag_seconds is not None else None,
        'started_at': item.started_at.isoformat() if item.started_at else None,
        'finished_at': item.finished_at.isoformat() if item.finished_at else None,
        'error_message': redact_secret_text(item.error_message or '') or None,
    }


def _source_record_payload(item) -> dict[str, Any]:
    return {
        'source_id': getattr(item, 'source_id', None),
        'event_time': getattr(item, 'event_time', None).isoformat() if getattr(item, 'event_time', None) else None,
        'metadata': filter_sensitive_mapping(getattr(item, 'metadata', {}) or {}),
    }


def _ops_enabled() -> bool:
    raw = os.getenv('HERMES_OPS_ENABLED')
    if raw is not None:
        return raw.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(settings.HERMES_OPS_ENABLED)


def _day1_enabled() -> bool:
    raw = os.getenv('HERMES_DAY1_ENABLED')
    if raw is not None:
        return raw.strip().lower() in {'1', 'true', 'yes', 'on'}
    return bool(settings.hermes_day1_enabled)


def _resolved_dingtalk_channel(args: argparse.Namespace) -> str:
    channel = _clean(args.channel)
    if channel and channel != 'dingtalk_group':
        return channel
    return 'dingtalk_group' if _clean(args.group_id) else 'dingtalk_private'


def _is_natural_language_day1_text(text: str) -> bool:
    clean = str(text or '').strip()
    return bool(clean) and not clean.startswith('/') and '日报' in clean


def _is_flexible_day1_text(text: str, args: argparse.Namespace | None = None) -> bool:
    clean = str(text or '').strip()
    if not clean or clean.startswith('/'):
        return False
    default_year = date.today().year
    if args is not None:
        try:
            default_year = _day1_default_year(args)
        except AgentCliError:
            pass
    return parse_hermes_intent(clean, default_year=default_year).get('intent') == 'daily_report'


def _looks_like_business_date_text(text: str) -> bool:
    return bool(BUSINESS_DATE_TEXT_RE.search(str(text or '')))


def _day1_default_year(args: argparse.Namespace) -> int:
    try:
        return _target_date(args).year
    except ValueError as exc:
        raise AgentCliError('invalid_date') from exc


def _output_skill_root_path() -> Path | None:
    raw = os.getenv('OUTPUT_SKILL_ROOT') or os.getenv('OUTPUT_SKILL_REFERENCE_ROOT')
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.exists() or not path.is_dir():
        return None
    return path


def _doctor_next_step(checks: dict[str, str]) -> str:
    if checks.get('feature_flag') != 'ok':
        return 'set HERMES_DAY1_ENABLED=true, then rerun day1-report --doctor'
    if checks.get('root_owner_identity') != 'ok':
        return 'bind root_owner DingTalk user_id or union_id, then rerun day1-report --doctor'
    if checks.get('output_skill_source') != 'ok':
        return 'set OUTPUT_SKILL_ROOT to a readable output skill directory, then rerun day1-report --doctor'
    return 'run day1-report smoke'


def _csv_env(name: str) -> set[str]:
    return {item.strip() for item in os.getenv(name, '').split(',') if item.strip()}


def _clean(value: str | None) -> str:
    return str(value or '').strip()


def _host(url: str) -> str:
    from urllib.parse import urlparse

    return (urlparse(url).hostname or '').lower()


def _safe_url(url: str | None) -> str | None:
    if not url:
        return None
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if not parsed.hostname:
        return None
    return f'{parsed.scheme}://{parsed.hostname}'


def _cli_error_detail(error_code: str, args: argparse.Namespace | None) -> dict[str, str] | None:
    if args is None or not _should_use_day1_cli_detail(args):
        return None
    trace_id = _trace_id(args)
    details = {
        'dingtalk_identity_required': {
            'cause': '钉钉身份缺失，Day-1 需要知道是谁在请求。',
            'fix': '运行时传 --dingtalk-user-id 或 --dingtalk-union-id；钉钉回调要传 senderStaffId 或 senderUnionId。',
        },
        'dingtalk_user_not_bound': {
            'cause': '这个钉钉身份未绑定到数据中枢用户，Day-1 不知道该按谁授权。',
            'fix': '先在用户管理里绑定该钉钉 user_id 或 union_id；本地测试可先创建带 dingtalk_user_id 的用户。',
        },
        'owner_required': {
            'cause': 'day1-report 是 root_owner 完整日报入口，普通授权用户或授权群不能触发。',
            'fix': '把 root_owner 的钉钉 user_id 或 union_id 加到 HERMES_OWNER_DINGTALK_USER_IDS；只加 HERMES_ALLOWED_DINGTALK_USER_IDS 不够。',
        },
        'day1_command_unrecognized': {
            'cause': 'Day-1 只识别带日期的日报生成指令，普通聊天不会进入完整日报链路。',
            'fix': '改成类似“生成 6月19日正式日报”或“/日报 2026-06-19”的指令后重试。',
        },
        'invalid_date': {
            'cause': '日期非法，例如 6月32日不存在，Day-1 不会继续生成日报。',
            'fix': '使用真实日期，例如“生成 2026-06-19 日报”或“生成 6月19日正式日报”。',
        },
        'hermes_day1_disabled': {
            'cause': 'HERMES_DAY1_ENABLED=false，Day-1 开关当前关闭。',
            'fix': '本地 smoke 可设置 HERMES_DAY1_ENABLED=true；生产验证前保持 false。',
        },
        'output_skill_source_missing': {
            'cause': 'OUTPUT_SKILL_ROOT 未配置或目录不存在，无法读取输出 skill 真实值参考源。',
            'fix': '设置 OUTPUT_SKILL_ROOT=D:\\输出skill，或设置到只读 fixture/挂载目录后重试。',
        },
        'hermes_day1_orchestrator_not_implemented': {
            'cause': 'Day-1 orchestrator 还没有接入；Lane A 只提供 intent、权限、开关和 doctor。',
            'fix': '先运行 day1-report --doctor 做预检；等 orchestrator 接入后再跑正式 day1-report。',
        },
    }
    detail = details.get(error_code)
    if detail is None:
        return None
    return {'trace_id': trace_id, **detail}


def _should_use_day1_cli_detail(args: argparse.Namespace) -> bool:
    command = getattr(args, 'command', None)
    if command == 'day1-report':
        return True
    if command != 'dingtalk-command':
        return False
    text = _normalize_dingtalk_text(getattr(args, 'text', ''))
    return _is_natural_language_day1_text(text) or _is_flexible_day1_text(text, args)


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(filter_sensitive_mapping(payload), ensure_ascii=False, default=str))


if __name__ == '__main__':
    raise SystemExit(main())
