from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from sqlalchemy.orm import Session

from app.models.rag import RagDocument
from app.services.rag_service import create_document_from_bytes


@dataclass(frozen=True, slots=True)
class RagBootstrapItem:
    path: Path
    category: str
    source_name: str


@dataclass(frozen=True, slots=True)
class RagBootstrapOutcome:
    applied: bool
    document_total: int
    filenames: list[str]


DATE_PLACEHOLDER = '[示例日期]'
VALUE_PLACEHOLDER = '[示例数值]'
DATE_PATTERNS = (
    re.compile(r'\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b'),
    re.compile(r'\b\d{4}年\d{1,2}月\d{1,2}日\b'),
    re.compile(r'\b\d{1,2}月\d{1,2}[日号]\b'),
)
VALUE_WITH_UNIT_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*(吨|kwh|KWH|kWh|千瓦时|度)')


def build_rag_bootstrap_manifest(reference_root: Path) -> list[RagBootstrapItem]:
    root = Path(reference_root)
    items: list[RagBootstrapItem] = []
    for path in sorted(root.glob('*_日报正文.txt')):
        items.append(RagBootstrapItem(path=path, category='daily_report_rule', source_name='输出skill日报正文样例'))
    for path in sorted(root.glob('*_核对记录.txt')):
        items.append(RagBootstrapItem(path=path, category='daily_report_rule', source_name='输出skill日报核对记录'))
    return items


def sanitize_bootstrap_text(text: str) -> str:
    sanitized = str(text or '')
    for pattern in DATE_PATTERNS:
        sanitized = pattern.sub(DATE_PLACEHOLDER, sanitized)
    sanitized = VALUE_WITH_UNIT_PATTERN.sub(lambda match: f'{VALUE_PLACEHOLDER}{match.group(2)}', sanitized)
    return sanitized


def _load_sanitized_content(path: Path) -> bytes:
    raw = path.read_bytes()
    text: str | None = None
    for encoding in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise UnicodeDecodeError('bootstrap', raw, 0, len(raw), '仅支持 UTF-8 或 GBK 文本')
    return sanitize_bootstrap_text(text).encode('utf-8')


def bootstrap_rag_knowledge(db: Session, *, reference_root: Path, apply: bool = False) -> RagBootstrapOutcome:
    items = build_rag_bootstrap_manifest(reference_root)
    if apply:
        existing = {
            name
            for (name,) in db.query(RagDocument.filename)
            .filter(RagDocument.status == 'active')
            .all()
        }
        for item in items:
            if item.path.name in existing:
                continue
            create_document_from_bytes(
                db,
                filename=item.path.name,
                content=_load_sanitized_content(item.path),
                content_type='text/plain',
                uploaded_by=None,
                source_name=item.source_name,
                metadata={
                    'category': item.category,
                    'reference_root': str(reference_root),
                    'reference_mode': 'template_example_rule',
                    'fact_status': 'not_live_production_fact',
                    'sanitized_import': 'true',
                },
                scope={'permission_scope': 'factory'},
            )
        db.flush()
    return RagBootstrapOutcome(
        applied=bool(apply),
        document_total=len(items),
        filenames=[item.path.name for item in items],
    )
