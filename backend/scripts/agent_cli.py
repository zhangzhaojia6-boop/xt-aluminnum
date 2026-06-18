from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.adapters import get_mes_adapter
from app.adapters.mes_adapter import NullMesAdapter
from app.config import settings
from app.core.business_time import last_completed_production_business_date
from app.core.redaction import filter_sensitive_mapping, redact_secret_text
from app.database import get_sessionmaker
from app.models.agent_communication import AgentOperationApproval, AgentOutboxMessage
from app.models.mes import MesSyncRunLog
from app.models.reports import DailyReport
from app.models.system import User
from app.services import agent_designated_operation_service, hermes_governance_service, hermes_memory_service, hermes_rag_service
from app.services.agent_command_service import handle_agent_command
from app.services.rag_service import query_knowledge
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
    'agent-governance-status': 'L0',
    'agent-governance-apply': 'L1',
    'mes-sync-realtime': 'L1',
    'mes-sync-business': 'L1',
    'mes-sync-reference': 'L1',
    'mes-mvc-preview': 'L1',
    'ops-status': 'L1',
    'visual-inspect': 'L2',
    'approval-preview': 'L3',
}
SQL_KEYWORDS = {'select', 'insert', 'update', 'delete', 'drop', 'alter', 'truncate', 'exec', 'execute'}
VISUAL_URL_HOSTS = {'xtmijd.com', 'www.xtmijd.com', 'mes.xintaily.com'}


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
    parser.add_argument('--group-id', default='')
    parser.add_argument('--channel', default='dingtalk_group')
    parser.add_argument('--agent-code', default='factory_dispatch')
    parser.add_argument('--trace-id', default='')
    parser.add_argument('--dingtalk-user-id', default='')
    parser.add_argument('--dingtalk-union-id', default='')
    parser.add_argument('--workshop', default='')
    parser.add_argument('--machine-code', default='')
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
    command, rest = _split_slash_command(text)
    if command in {'查知识', '字段', '口径', 'MES路线', 'mes路线', '缺陷原因', '工艺解释'}:
        query_text = rest or text
        payload = _query_rag(db, query_text=query_text, args=args, auth=auth)
        return {'action': 'rag-query', 'reply': payload['reply'], 'data': payload['data'], 'trace_id': _trace_id(args)}
    if command in {'同步MES', '同步mes'}:
        if not auth.is_owner:
            raise AgentCliError('owner_required')
        if not _ops_enabled():
            raise AgentCliError('hermes_ops_disabled')
        return _cmd_mes_sync_business(db, args, auth)
    if command in {'日报', '发日报', '补产量', '正式通知'}:
        if not auth.is_owner:
            raise AgentCliError('owner_required')
        return _cmd_approval_preview(db, args, auth)
    if command in {'巡检页面'}:
        if not auth.is_owner:
            raise AgentCliError('owner_required')
        return _cmd_visual_inspect(db, args, auth)
    if command and command not in {'产量', '能耗', '停机', '异常'}:
        raise AgentCliError('dingtalk_command_not_allowed')
    return _cmd_agent_ask(db, args, auth, text_override=rest or text)


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
        channel=args.channel,
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
    return {'action': 'rag-query', 'reply': payload.get('answer'), 'data': payload, 'trace_id': _trace_id(args)}


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
        parts = clean.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else ''
    return clean


def _split_slash_command(text: str) -> tuple[str, str]:
    clean = str(text or '').strip()
    if clean.startswith('/'):
        clean = clean[1:].strip()
    if not clean:
        return '', ''
    parts = clean.split(maxsplit=1)
    return parts[0], parts[1].strip() if len(parts) > 1 else ''


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


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(filter_sensitive_mapping(payload), ensure_ascii=False, default=str))


if __name__ == '__main__':
    raise SystemExit(main())
