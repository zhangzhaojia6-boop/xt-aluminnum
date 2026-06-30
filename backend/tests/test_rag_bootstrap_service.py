from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.rag import RagChunk, RagDocument
from app.services.rag_bootstrap_service import bootstrap_rag_knowledge


def _session():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    return SessionLocal()


def _write_sample_files(root: Path) -> None:
    (root / '2026-6-16_日报正文.txt').write_text(
        '\n'.join(
            [
                '日报日期：2026-06-16',
                '1650车间：1#机稳定生产，2#机待切换。',
                '1850车间：本日按固定模板核对。',
                '2050车间：继续沿用母版规则。',
                '1650冷轧：固定口径标签。',
                '1850冷轧：固定口径标签。',
                '2050冷轧：固定口径标签。',
                '天然气：57776m³',
                '成品率：84.86%',
                '成本：13.44万元',
                '加工费：1044元/吨',
                '穿带：6道',
                '缺陷：3条',
                '较昨日下降12吨',
                '合计166.992',
                '母版口径：按班组汇总。',
            ]
        ),
        encoding='utf-8',
    )
    (root / '2026-6-16_核对记录.txt').write_text(
        '\n'.join(
            [
                '报告日：6月16日',
                '1650车间核对：1#机、2#机按模板记录。',
                '1850车间核对：固定车间标签保留。',
                '2050车间核对：固定车间标签保留。',
                '天然气核对：57776m³',
                '成品率核对：84.86%',
                '成本核对：13.44万元',
                '加工费核对：1044元/吨',
                '穿带核对：6道',
                '缺陷核对：3条',
                '较昨日下降12吨',
                '合计166.992',
                '母版口径：按正文保留段落。',
            ]
        ),
        encoding='utf-8',
    )


def test_bootstrap_rag_preview_does_not_write(tmp_path: Path) -> None:
    _write_sample_files(tmp_path)
    db = _session()
    try:
        outcome = bootstrap_rag_knowledge(db, reference_root=tmp_path, apply=False)
        assert outcome.applied is False
        assert outcome.document_total == 2
        assert db.query(RagDocument).count() == 0
    finally:
        db.close()


def test_bootstrap_rag_apply_sanitizes_and_marks_rule_docs(tmp_path: Path) -> None:
    _write_sample_files(tmp_path)
    db = _session()
    try:
        outcome = bootstrap_rag_knowledge(db, reference_root=tmp_path, apply=True)
        assert outcome.applied is True
        assert outcome.document_total == 2
        docs = db.query(RagDocument).order_by(RagDocument.filename.asc()).all()
        assert [doc.metadata_payload['category'] for doc in docs] == ['daily_report_rule', 'daily_report_rule']
        assert all(doc.status == 'active' for doc in docs)
        assert all(doc.metadata_payload['reference_mode'] == 'template_example_rule' for doc in docs)
        assert all(doc.metadata_payload['fact_status'] == 'not_live_production_fact' for doc in docs)
        assert all(doc.metadata_payload['sanitized_import'] == 'true' for doc in docs)
        assert all(doc.chunk_count > 0 for doc in docs)

        chunks = db.query(RagChunk).order_by(RagChunk.document_id.asc(), RagChunk.chunk_index.asc()).all()
        assert chunks
        combined_text = ' '.join(chunk.content for chunk in chunks)
        assert '2026-06-16' not in combined_text
        assert '6月16日' not in combined_text
        assert '57776m³' not in combined_text
        assert '84.86%' not in combined_text
        assert '13.44万元' not in combined_text
        assert '1044元/吨' not in combined_text
        assert '6道' not in combined_text
        assert '3条' not in combined_text
        assert '下降12吨' not in combined_text
        assert '合计166.992' not in combined_text
        assert '1650车间' in combined_text
        assert '1850车间' in combined_text
        assert '2050车间' in combined_text
        assert '1650冷轧' in combined_text
        assert '1850冷轧' in combined_text
        assert '2050冷轧' in combined_text
        assert '1#机' in combined_text
        assert '2#机' in combined_text
        assert '[示例数值]车间' not in combined_text
        assert '[示例数值]#机' not in combined_text
        assert '天然气' in combined_text
        assert '成品率' in combined_text
        assert '成本' in combined_text
        assert '较昨日' in combined_text
        assert '合计' in combined_text
        assert '母版口径' in combined_text
        assert '[示例日期]' in combined_text
        assert '[示例数值]m³' in combined_text
        assert '[示例数值]%' in combined_text
        assert '[示例数值]万元' in combined_text
        assert '[示例数值]元/吨' in combined_text
        assert '[示例数值]道' in combined_text
        assert '[示例数值]条' in combined_text
        assert '较昨日下降[示例数值]吨' in combined_text
        assert '合计[示例数值]' in combined_text

        for doc in docs:
            doc_chunks = [chunk for chunk in chunks if chunk.document_id == doc.id]
            assert len(doc_chunks) == doc.chunk_count
            assert all(chunk.source_ref.startswith(f'{doc.filename}#chunk-') for chunk in doc_chunks)
    finally:
        db.close()


def test_bootstrap_rag_apply_is_idempotent_for_active_docs(tmp_path: Path) -> None:
    _write_sample_files(tmp_path)
    db = _session()
    try:
        bootstrap_rag_knowledge(db, reference_root=tmp_path, apply=True)
        first_doc_count = db.query(RagDocument).count()
        first_active_count = db.query(RagDocument).filter(RagDocument.status == 'active').count()
        first_chunk_count = db.query(RagChunk).count()

        bootstrap_rag_knowledge(db, reference_root=tmp_path, apply=True)

        assert db.query(RagDocument).count() == first_doc_count == 2
        assert db.query(RagDocument).filter(RagDocument.status == 'active').count() == first_active_count == 2
        assert db.query(RagChunk).count() == first_chunk_count
    finally:
        db.close()


def test_bootstrap_rag_apply_recreates_active_doc_when_previous_one_is_deleted(tmp_path: Path) -> None:
    _write_sample_files(tmp_path)
    db = _session()
    try:
        bootstrap_rag_knowledge(db, reference_root=tmp_path, apply=True)
        deleted_doc = (
            db.query(RagDocument)
            .filter(RagDocument.filename == '2026-6-16_日报正文.txt', RagDocument.status == 'active')
            .one()
        )
        deleted_doc.status = 'deleted'
        db.flush()

        bootstrap_rag_knowledge(db, reference_root=tmp_path, apply=True)

        active_docs = (
            db.query(RagDocument)
            .filter(RagDocument.filename == '2026-6-16_日报正文.txt', RagDocument.status == 'active')
            .all()
        )
        assert len(active_docs) == 1
        restored_doc = active_docs[0]
        assert restored_doc.chunk_count > 0
        assert db.query(RagDocument).filter(RagDocument.status == 'active').count() == 2
        restored_chunks = db.query(RagChunk).filter(RagChunk.document_id == restored_doc.id).all()
        assert len(restored_chunks) == restored_doc.chunk_count
        assert all(chunk.source_ref.startswith(f'{restored_doc.filename}#chunk-') for chunk in restored_chunks)
    finally:
        db.close()
