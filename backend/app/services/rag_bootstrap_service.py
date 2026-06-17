from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


def build_rag_bootstrap_manifest(reference_root: Path) -> list[RagBootstrapItem]:
    root = Path(reference_root)
    items: list[RagBootstrapItem] = []
    for path in sorted(root.glob('*_日报正文.txt')):
        items.append(RagBootstrapItem(path=path, category='daily_report_rule', source_name='输出skill日报正文样例'))
    for path in sorted(root.glob('*_核对记录.txt')):
        items.append(RagBootstrapItem(path=path, category='daily_report_rule', source_name='输出skill日报核对记录'))
    return items


def bootstrap_rag_knowledge(db: Session, *, reference_root: Path, apply: bool = False) -> RagBootstrapOutcome:
    items = build_rag_bootstrap_manifest(reference_root)
    if apply:
        existing = {name for (name,) in db.query(RagDocument.filename).all()}
        for item in items:
            if item.path.name in existing:
                continue
            create_document_from_bytes(
                db,
                filename=item.path.name,
                content=item.path.read_bytes(),
                content_type='text/plain',
                uploaded_by=None,
                source_name=item.source_name,
                metadata={'category': item.category, 'reference_root': str(reference_root)},
                scope={'permission_scope': 'factory'},
            )
        db.flush()
    return RagBootstrapOutcome(
        applied=bool(apply),
        document_total=len(items),
        filenames=[item.path.name for item in items],
    )
