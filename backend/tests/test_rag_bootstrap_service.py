from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.rag import RagDocument
from app.services.rag_bootstrap_service import bootstrap_rag_knowledge


def _session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    return SessionLocal()


def test_bootstrap_rag_preview_does_not_write(tmp_path: Path) -> None:
    (tmp_path / '2026-6-16_日报正文.txt').write_text('6月16日，车间总产量日合计328吨。', encoding='utf-8')
    (tmp_path / '2026-6-16_核对记录.txt').write_text('报告日：2026-06-16\n母版口径：按正文保留段落。', encoding='utf-8')
    db = _session()
    try:
        outcome = bootstrap_rag_knowledge(db, reference_root=tmp_path, apply=False)
        assert outcome.applied is False
        assert outcome.document_total == 2
        assert db.query(RagDocument).count() == 0
    finally:
        db.close()


def test_bootstrap_rag_apply_imports_output_skill_as_rule_docs(tmp_path: Path) -> None:
    (tmp_path / '2026-6-16_日报正文.txt').write_text('6月16日，车间总产量日合计328吨。', encoding='utf-8')
    (tmp_path / '2026-6-16_核对记录.txt').write_text('报告日：2026-06-16\n母版口径：按正文保留段落。', encoding='utf-8')
    db = _session()
    try:
        outcome = bootstrap_rag_knowledge(db, reference_root=tmp_path, apply=True)
        assert outcome.applied is True
        assert outcome.document_total == 2
        docs = db.query(RagDocument).order_by(RagDocument.filename.asc()).all()
        assert [doc.metadata_payload['category'] for doc in docs] == ['daily_report_rule', 'daily_report_rule']
        assert all(doc.status == 'active' for doc in docs)
    finally:
        db.close()
