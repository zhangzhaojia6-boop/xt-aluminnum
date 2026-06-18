from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.adapters import sqlserver_mes_adapter
from app.config import settings
from app.core.redaction import redact_secret_text
from app.models.rag import HermesApprovedLesson, HermesLearningEvent, RagDocument, RagSourceIngestion
from app.models.reports import DailyReport
from app.models.system import User
from app.services import rag_embedding_service
from app.services.rag_service import ALLOWED_EXTENSIONS, create_document_from_bytes


class HermesRagError(RuntimeError):
    pass


MES_ROUTE_FACTS: tuple[dict[str, str], ...] = (
    {
        'route': 'coil_dispatch',
        'source_table': 'MES_Product',
        'time_column': 'OperateDate/CreateDate',
        'projection': 'mes_coil_snapshots',
        'business_use': '卷级线索、随行卡、当前工序、在制基础信息',
    },
    {
        'route': 'wip_totals',
        'source_table': 'MES_Product',
        'time_column': '当前状态快照',
        'projection': 'mes_wip_total_snapshots / mes_daily_wip_snapshots',
        'business_use': '在制料总量和页面在制分布，只能当快照，不当历史日报产量',
    },
    {
        'route': 'workshop_process_records',
        'source_table': 'MES_ProductProcessRecord',
        'time_column': 'EndDatetime',
        'projection': 'mes_workshop_process_records',
        'business_use': '车间过站产量、工序下机、道次、成品率过程数据',
    },
    {
        'route': 'finished_inbound_records',
        'source_table': 'WMS_InStock',
        'time_column': 'InStockDate',
        'projection': 'mes_stock_records',
        'business_use': '包装产量、总产量、成品入库主口径',
    },
    {
        'route': 'stock_records',
        'source_table': 'WMS_InStockDetail',
        'time_column': 'CreateDate',
        'projection': 'mes_stock_records',
        'business_use': '入库明细兜底；表头 WMS_InStock 不可用时才使用',
    },
    {
        'route': 'delivery_records',
        'source_table': 'MES_DeliveryDetail',
        'time_column': 'OperateDate',
        'projection': 'mes_stock_records',
        'business_use': '发货事实主口径',
    },
    {
        'route': 'delivery_stock_records',
        'source_table': 'WMS_OutStockDetail',
        'time_column': 'CreateDate',
        'projection': 'mes_stock_records',
        'business_use': '发货事实兜底，要求 DeliveryCode 非空',
    },
    {
        'route': 'material_records',
        'source_table': 'MES_Material',
        'time_column': 'ProductionDate',
        'projection': 'mes_material_records',
        'business_use': '在制物料、库存物料、铝加工中间物料信息',
    },
    {
        'route': 'stock',
        'source_table': 'WMS_Stock',
        'time_column': 'OperateDate/CreateDate',
        'projection': 'mes_reference_items / mes_stock_records',
        'business_use': '仓储库存参考，不直接替代日报产量',
    },
    {
        'route': 'devices',
        'source_table': 'MES_Device',
        'time_column': 'OperateDate/CreateDate',
        'projection': 'mes_reference_items',
        'business_use': '设备、机列、工艺基础资料',
    },
)


def ingest_file(
    db: Session,
    *,
    path: str | Path,
    actor: User | None = None,
    source_type: str = 'uploaded_file',
    status: str = 'active',
    metadata: dict[str, Any] | None = None,
) -> RagDocument:
    file_path = Path(path)
    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HermesRagError('unsupported_file_type')
    content = file_path.read_bytes()
    document = create_document_from_bytes(
        db,
        filename=file_path.name,
        content=content,
        content_type='text/plain',
        uploaded_by=actor,
        source_name=str(file_path),
        metadata={'source_type': source_type, **(metadata or {})},
        status=status,
    )
    _record_ingestion(
        db,
        source_type=source_type,
        source_ref=str(file_path),
        status=status,
        document_id=document.id,
        actor=actor,
        metadata=metadata,
    )
    return document


def ingest_directory(
    db: Session,
    *,
    path: str | Path,
    actor: User | None = None,
    source_type: str = 'uploaded_file',
    status: str = 'active',
) -> list[RagDocument]:
    root = Path(path)
    documents: list[RagDocument] = []
    for file_path in sorted(root.rglob('*')):
        if not file_path.is_file() or file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        documents.append(ingest_file(db, path=file_path, actor=actor, source_type=source_type, status=status))
    return documents


def build_mes_route_catalog_text() -> str:
    lines = [
        '# MES SQL 业务数据库路线知识',
        '',
        '原则：外部 MES SQL Server 只读；数据先同步到本地 mes_* 投影表，再供看板、日报、Hermes 查询。',
        '业务日核心口径：每日 07:30 到次日 07:30。',
        '实时事实必须走 CLI/API 查本地投影表，RAG 只保存字段含义、表路线和口径说明。',
        '',
        '## 重要口径',
        '- 包装产量/总产量优先来自 WMS_InStock.TotalNetWeight + InStockDate。',
        '- WMS_InStockDetail.NetWeight + CreateDate 只作为入库明细兜底。',
        '- 发货优先来自 MES_DeliveryDetail.NetWeight + OperateDate。',
        '- WMS_OutStockDetail 只在 DeliveryCode 非空时作为发货兜底。',
        '- 园区精整在数据中枢归为园区剪切，不归为精整。',
        '',
        '## 路线清单',
    ]
    for item in MES_ROUTE_FACTS:
        lines.append(
            f"- {item['route']}：来源表 {item['source_table']}，时间列 {item['time_column']}，"
            f"本地投影 {item['projection']}，用途：{item['business_use']}。"
        )
    lines.extend([
        '',
        '## SQL Server adapter 查询键',
        f"- 最新列表键：{', '.join(sorted(sqlserver_mes_adapter._QUERY_BY_KEY.keys()))}",
        f"- 日期窗口键：{', '.join(sorted(sqlserver_mes_adapter._BETWEEN_QUERY_BY_KEY.keys()))}",
    ])
    return '\n'.join(lines)


def ingest_mes_route_catalog(db: Session, *, actor: User | None = None) -> RagDocument:
    text = build_mes_route_catalog_text()
    document = create_document_from_bytes(
        db,
        filename='mes-sql-route-catalog.md',
        content=text.encode('utf-8'),
        content_type='text/markdown',
        uploaded_by=actor,
        source_name='MES SQL 业务数据库路线',
        metadata={
            'source_type': 'mes_schema',
            'mes_route_key': 'sqlserver_projection',
            'permission_scope': 'manage',
        },
    )
    _record_ingestion(
        db,
        source_type='mes_schema',
        source_ref='sqlserver_mes_adapter+mes_sync_service',
        status='active',
        document_id=document.id,
        actor=actor,
        metadata={'route_count': len(MES_ROUTE_FACTS)},
    )
    return document


def ingest_mes_page_knowledge(
    db: Session,
    *,
    url: str,
    actor: User | None = None,
    page_title: str | None = None,
    fields: list[str] | None = None,
) -> RagDocument:
    _ensure_allowed_mes_page_url(url)
    field_text = '、'.join(fields or []) or '待由 Hermes 视觉/浏览器环境读取页面字段'
    text = (
        '# MES 页面路线知识\n\n'
        f'页面：{page_title or url}\n'
        f'URL：{url}\n'
        f'字段/表格列：{field_text}\n\n'
        '说明：mes.xintaily.com 只作为只读页面证据来源，不保存登录密码，不把实时数字写入长期 RAG。'
    )
    document = create_document_from_bytes(
        db,
        filename='mes-page-route.md',
        content=text.encode('utf-8'),
        content_type='text/markdown',
        uploaded_by=actor,
        source_name='MES 页面路线',
        metadata={'source_type': 'mes_page_route', 'source_url': url, 'review_status': 'active'},
    )
    _record_ingestion(
        db,
        source_type='mes_page_route',
        source_ref=url,
        status='active',
        document_id=document.id,
        actor=actor,
        metadata={'page_title': page_title or ''},
    )
    return document


def ingest_web_source(
    db: Session,
    *,
    url: str,
    actor: User | None = None,
    status: str = 'pending_review',
) -> RagDocument:
    _ensure_allowed_web_url(url)
    text = _fetch_web_text(url)
    document = create_document_from_bytes(
        db,
        filename=_filename_for_url(url),
        content=text.encode('utf-8'),
        content_type='text/plain',
        uploaded_by=actor,
        source_name=url,
        metadata={'source_type': 'external_industry_knowledge', 'source_url': url, 'review_status': status},
        status=status,
    )
    _record_ingestion(
        db,
        source_type='external_industry_knowledge',
        source_ref=url,
        status=status,
        document_id=document.id,
        actor=actor,
        metadata={'authority_level': 'whitelist'},
    )
    return document


def archive_daily_report_to_rag(
    db: Session,
    *,
    report: DailyReport,
    actor: User | None = None,
    generated_by: str = 'hermes',
) -> RagDocument | None:
    body = str(report.final_text_summary or report.text_summary or '').strip()
    if not body:
        return None
    _mark_existing_daily_report_archive_deleted(db, report)
    text = (
        '# Hermes 日报历史记忆\n\n'
        f'日期：{report.report_date.isoformat()}\n'
        f'日报ID：{report.id}\n'
        f'类型：{report.report_type}\n'
        f'生成者：{generated_by}\n\n'
        f'{body}'
    )
    document = create_document_from_bytes(
        db,
        filename=f'daily-report-{report.report_date.isoformat()}-{report.report_type}.md',
        content=text.encode('utf-8'),
        content_type='text/markdown',
        uploaded_by=actor,
        source_name=f'Hermes 日报历史 {report.report_date.isoformat()}',
        metadata={
            'source_type': 'daily_report_archive',
            'report_date': report.report_date.isoformat(),
            'report_id': str(report.id),
            'generated_by': generated_by,
            'temporal_scope': 'historical',
        },
    )
    _record_ingestion(
        db,
        source_type='daily_report_archive',
        source_ref=f'daily_reports:{report.id}',
        status='active',
        document_id=document.id,
        actor=actor,
        metadata={'report_date': report.report_date.isoformat()},
    )
    return document


def archive_latest_daily_report_to_rag(
    db: Session,
    *,
    report_date: date,
    actor: User | None = None,
    generated_by: str = 'hermes',
) -> RagDocument | None:
    report = (
        db.query(DailyReport)
        .filter(DailyReport.report_date == report_date, DailyReport.report_type == 'production')
        .order_by(DailyReport.published_at.desc().nullslast(), DailyReport.id.desc())
        .first()
    )
    if report is None:
        return None
    return archive_daily_report_to_rag(db, report=report, actor=actor, generated_by=generated_by)


def record_learning_event(
    db: Session,
    *,
    question: str,
    answer: str,
    trace_id: str | None = None,
    tools_called: list | None = None,
    sources: list | None = None,
    user_feedback: str | None = None,
    human_correction: str | None = None,
    actor: User | None = None,
) -> HermesLearningEvent:
    event = HermesLearningEvent(
        trace_id=trace_id,
        question=redact_secret_text(question),
        tools_called=tools_called or [],
        sources=sources or [],
        answer=redact_secret_text(answer),
        user_feedback=redact_secret_text(user_feedback or '') or None,
        human_correction=redact_secret_text(human_correction or '') or None,
        status='candidate',
        actor_user_id=getattr(actor, 'id', None),
    )
    db.add(event)
    db.flush()
    return event


def approve_learning_event(db: Session, *, event_id: int, approver: User | None = None) -> HermesApprovedLesson:
    event = db.get(HermesLearningEvent, int(event_id))
    if event is None:
        raise HermesRagError('learning_event_not_found')
    lesson_text = str(event.human_correction or event.answer or '').strip()
    if not lesson_text:
        raise HermesRagError('lesson_text_empty')
    document = create_document_from_bytes(
        db,
        filename=f'hermes-approved-lesson-{event.id}.md',
        content=lesson_text.encode('utf-8'),
        content_type='text/markdown',
        uploaded_by=approver,
        source_name=f'Hermes 审核经验 {event.id}',
        metadata={'source_type': 'approved_lesson', 'learning_event_id': str(event.id)},
    )
    event.status = 'approved'
    lesson = HermesApprovedLesson(
        learning_event_id=event.id,
        lesson_text=lesson_text,
        source_payload={'trace_id': event.trace_id, 'sources': event.sources or []},
        document_id=document.id,
        approved_by_id=getattr(approver, 'id', None),
        status='active',
    )
    db.add(lesson)
    db.flush()
    return lesson


def rebuild_rag_embeddings(db: Session) -> int:
    return rag_embedding_service.rebuild_embeddings(db)


def _record_ingestion(
    db: Session,
    *,
    source_type: str,
    source_ref: str,
    status: str,
    document_id: int | None,
    actor: User | None,
    metadata: dict[str, Any] | None,
) -> None:
    db.add(
        RagSourceIngestion(
            source_type=source_type,
            source_ref=redact_secret_text(source_ref),
            status=status,
            document_id=document_id,
            actor_user_id=getattr(actor, 'id', None),
            metadata_payload={key: redact_secret_text(str(value)) for key, value in (metadata or {}).items()},
        )
    )
    db.flush()


def _mark_existing_daily_report_archive_deleted(db: Session, report: DailyReport) -> None:
    documents = db.query(RagDocument).filter(RagDocument.status == 'active').all()
    for document in documents:
        metadata = document.metadata_payload or {}
        if metadata.get('source_type') == 'daily_report_archive' and str(metadata.get('report_id')) == str(report.id):
            document.status = 'deleted'


def _ensure_allowed_mes_page_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.hostname != 'mes.xintaily.com':
        raise HermesRagError('mes_page_url_not_allowed')


def _ensure_allowed_web_url(url: str) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or '').lower()
    if parsed.scheme not in {'http', 'https'} or not hostname:
        raise HermesRagError('web_url_invalid')
    allowed = settings.rag_web_source_allowlist
    if not any(hostname == item or hostname.endswith(f'.{item}') for item in allowed):
        raise HermesRagError('web_url_not_allowed')


def _fetch_web_text(url: str) -> str:
    try:
        response = httpx.get(url, timeout=15, follow_redirects=True)
        response.raise_for_status()
    except Exception as exc:
        raise HermesRagError(redact_secret_text(str(exc))) from exc
    text = redact_secret_text(response.text)
    if '<' in text and '>' in text:
        text = _strip_html(text)
    return text[:200000]


def _strip_html(text: str) -> str:
    import re

    text = re.sub(r'(?is)<(script|style).*?</\1>', ' ', text)
    text = re.sub(r'(?s)<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _filename_for_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or 'web-source'
    path = parsed.path.strip('/').replace('/', '-')
    base = f'{host}-{path or "index"}'
    return f'{base[:180]}.txt'
