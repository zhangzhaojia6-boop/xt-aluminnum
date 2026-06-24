from __future__ import annotations

from typing import cast

from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models.rag import HermesProfessionalKnowledgeEntry, RagChunk, RagDocument, RagEmbedding, RagQueryLog
from app.models.system import User
from app.services.hermes_professional_knowledge_service import (
    search_professional_knowledge,
    upsert_professional_knowledge,
)
from app.services.rag_service import query_knowledge


TABLES = cast(list[Table], [
    User.__table__,
    HermesProfessionalKnowledgeEntry.__table__,
    RagDocument.__table__,
    RagChunk.__table__,
    RagEmbedding.__table__,
    RagQueryLog.__table__,
])


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine, tables=TABLES)
    return Session(engine)


def test_upsert_professional_knowledge_creates_then_updates_same_entry() -> None:
    db = _session()
    try:
        first = upsert_professional_knowledge(
            db,
            domain="daily_report",
            topic=" 成本核算 ",
            knowledge_type="calculation_rule",
            source_type="output_skill",
            source_ref="D:/输出skill/2026-6-19.txt",
            content="成本核算按已核电费、气费合计除以入库成品吨数。",
            structured_payload={"formula": "(electricity_fee + gas_fee) / finished_goods_tons"},
            confidence=150,
            trace_id="trace-knowledge",
        )
        db.commit()

        second = upsert_professional_knowledge(
            db,
            domain="daily_report",
            topic="成本核算",
            knowledge_type="calculation_rule",
            source_type="output_skill",
            source_ref="D:/输出skill/2026-6-19.txt",
            content="成本核算按已核电费和已核气费合计除以入库成品吨数。",
            structured_payload=None,
            confidence=-5,
            status="active",
        )
        db.commit()

        assert second.id == first.id
        assert second.topic == "成本核算"
        assert second.content == "成本核算按已核电费和已核气费合计除以入库成品吨数。"
        assert second.structured_payload == {}
        assert second.confidence == 0
        assert db.query(HermesProfessionalKnowledgeEntry).count() == 1
    finally:
        db.close()


def test_search_professional_knowledge_filters_active_domain_and_type() -> None:
    db = _session()
    try:
        upsert_professional_knowledge(
            db,
            domain="daily_report",
            topic="成本核算",
            knowledge_type="calculation_rule",
            source_type="output_skill",
            source_ref="skill://cost",
            content="成本核算按已核电费、气费合计除以入库成品吨数。",
            structured_payload={"formula": "cost / tons"},
            confidence=95,
        )
        upsert_professional_knowledge(
            db,
            domain="daily_report",
            topic="停用成本规则",
            knowledge_type="calculation_rule",
            source_type="manual",
            source_ref="manual://inactive-cost",
            content="成本按旧口径计算。",
            status="inactive",
        )
        upsert_professional_knowledge(
            db,
            domain="energy",
            topic="成本核算",
            knowledge_type="calculation_rule",
            source_type="manual",
            source_ref="manual://energy-cost",
            content="能源侧成本说明。",
        )
        db.commit()

        matches = search_professional_knowledge(
            db,
            query="成本怎么按吨算",
            domain="daily_report",
            knowledge_type="calculation_rule",
        )

        assert len(matches) == 1
        assert matches[0]["topic"] == "成本核算"
        assert matches[0]["source_type"] == "output_skill"
        assert matches[0]["confidence"] == 95
        assert matches[0]["source"] == "professional_knowledge"
        assert matches[0]["score"] > 0
    finally:
        db.close()


def test_query_knowledge_uses_professional_entries_before_generic_chunks() -> None:
    db = _session()
    try:
        document = RagDocument(
            filename="generic-daily-report.md",
            source_name="普通日报资料",
            content_type="text/markdown",
            encoding="utf-8",
            status="active",
            file_size=100,
            chunk_count=1,
            metadata_payload={},
        )
        db.add(document)
        db.flush()
        db.add(
            RagChunk(
                document_id=document.id,
                chunk_index=0,
                content="日报普通资料：日报要先写设备巡检，再写其他内容。",
                char_start=0,
                char_end=30,
                source_ref="generic-daily-report.md#chunk-1",
            )
        )
        upsert_professional_knowledge(
            db,
            domain="daily_report",
            topic="日报模板",
            knowledge_type="report_pattern",
            source_type="dingtalk_file",
            source_ref="dingtalk://file/daily-report-template",
            content="日报先输出总产量、月累计，再输出各车间明细和成本核算。",
            confidence=90,
        )
        db.commit()

        payload = query_knowledge(db, query="日报要先写什么", limit=5)

        assert payload["items"][0]["source"] == "professional_knowledge"
        assert "总产量" in payload["answer"]
        assert payload["citations"][0]["source"] == "professional_knowledge"
        assert payload["citations"][0]["entry_id"] == payload["items"][0]["id"]
        assert payload["citations"][0]["topic"] == "日报模板"
        assert payload["citations"][0]["source_ref"] == "dingtalk://file/daily-report-template"
    finally:
        db.close()
