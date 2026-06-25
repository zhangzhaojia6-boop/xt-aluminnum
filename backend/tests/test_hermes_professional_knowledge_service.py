from __future__ import annotations

from typing import cast

from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

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


def _legacy_rag_session() -> Session:
    engine = create_engine(
        "sqlite://",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    legacy_tables = cast(list[Table], [
        User.__table__,
        RagDocument.__table__,
        RagChunk.__table__,
        RagEmbedding.__table__,
        RagQueryLog.__table__,
    ])
    Base.metadata.create_all(
        engine,
        tables=legacy_tables,
    )
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


def test_upsert_professional_knowledge_update_preserves_owner_trace_and_inactive_status() -> None:
    db = _session()
    try:
        entry = upsert_professional_knowledge(
            db,
            domain="daily_report",
            topic="停用规则",
            knowledge_type="report_pattern",
            source_type="manual",
            source_ref="manual://inactive-rule",
            content="旧规则暂时停用。",
            status="inactive",
            created_by_id=7,
            trace_id="trace-original",
        )
        db.commit()

        updated = upsert_professional_knowledge(
            db,
            domain="daily_report",
            topic="停用规则",
            knowledge_type="report_pattern",
            source_type="manual",
            source_ref="manual://inactive-rule",
            content="旧规则仍然停用，只更新正文。",
        )
        db.commit()

        assert updated.id == entry.id
        assert updated.content == "旧规则仍然停用，只更新正文。"
        assert updated.status == "inactive"
        assert updated.created_by_id == 7
        assert updated.trace_id == "trace-original"
    finally:
        db.close()


def test_upsert_professional_knowledge_explicit_active_reactivates_existing_entry() -> None:
    db = _session()
    try:
        entry = upsert_professional_knowledge(
            db,
            domain="daily_report",
            topic="重新启用规则",
            knowledge_type="report_pattern",
            source_type="manual",
            source_ref="manual://reactivate-rule",
            content="旧规则暂时停用。",
            status="inactive",
            created_by_id=7,
            trace_id="trace-original",
        )
        db.commit()

        updated = upsert_professional_knowledge(
            db,
            domain="daily_report",
            topic="重新启用规则",
            knowledge_type="report_pattern",
            source_type="manual",
            source_ref="manual://reactivate-rule",
            content="规则重新启用。",
            status="active",
        )
        db.commit()

        assert updated.id == entry.id
        assert updated.status == "active"
        assert updated.created_by_id == 7
        assert updated.trace_id == "trace-original"
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


def test_query_knowledge_redacts_professional_entry_content_and_items() -> None:
    db = _session()
    try:
        upsert_professional_knowledge(
            db,
            domain="daily_report",
            topic="日报敏感口径",
            knowledge_type="report_pattern",
            source_type="manual",
            source_ref="manual://sensitive-rule",
            content="日报敏感口径 password=abc123 token=xyz789 总产量口径。",
            structured_payload={
                "public_text": "password=abc123 token=xyz789",
                "token": "xyz789",
            },
            confidence=90,
        )
        db.commit()

        payload = query_knowledge(db, query="日报敏感口径", limit=5)

        serialized = str(payload)
        assert "abc123" not in payload["answer"]
        assert "xyz789" not in payload["answer"]
        assert "abc123" not in payload["items"][0]["content"]
        assert "xyz789" not in payload["items"][0]["content"]
        assert "abc123" not in serialized
        assert "xyz789" not in serialized
        assert "password=<redacted>" in payload["answer"]
        assert "token=<redacted>" in payload["answer"]
    finally:
        db.close()


def test_query_knowledge_legacy_rag_tables_without_professional_table_keep_flushed_data() -> None:
    db = _legacy_rag_session()
    try:
        document = RagDocument(
            filename="legacy-rag.md",
            source_name="旧知识库资料",
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
                content="旧知识库仍然能回答热轧安全点检。",
                char_start=0,
                char_end=20,
                source_ref="legacy-rag.md#chunk-1",
            )
        )
        db.flush()

        payload = query_knowledge(db, query="热轧安全点检", limit=5)

        assert payload["items"]
        assert "旧知识库" in payload["answer"]
        assert db.query(RagDocument).filter(RagDocument.id == document.id).one().filename == "legacy-rag.md"
        assert db.query(RagChunk).filter(RagChunk.document_id == document.id).count() == 1
    finally:
        db.close()


def test_query_knowledge_professional_fallback_order_and_deduplicates_global_pass() -> None:
    db = _session()
    try:
        for domain, topic in [
            ("热轧", "车间规则"),
            ("daily_report", "日报规则"),
            ("factory", "工厂规则"),
            ("global", "全局规则"),
            ("unlisted_domain", "无显式 fallback 规则"),
        ]:
            upsert_professional_knowledge(
                db,
                domain=domain,
                topic=topic,
                knowledge_type="report_pattern",
                source_type="manual",
                source_ref=f"manual://{domain}",
                content=f"fallback顺序命中 {topic}",
                confidence=95,
            )
        db.commit()

        payload = query_knowledge(db, query="fallback顺序命中", workshop="热轧", limit=10)

        domains = [item["domain"] for item in payload["items"]]
        ids = [item["id"] for item in payload["items"]]
        assert domains == ["热轧", "daily_report", "factory", "global", "unlisted_domain"]
        assert len(ids) == len(set(ids))
    finally:
        db.close()


def test_query_knowledge_falls_back_from_workshop_domain_to_daily_report_domain() -> None:
    db = _session()
    try:
        upsert_professional_knowledge(
            db,
            domain="daily_report",
            topic="日报模板",
            knowledge_type="report_pattern",
            source_type="output_skill",
            source_ref="skill://daily-report-template",
            content="日报先输出总产量、月累计，再输出各车间明细。",
            confidence=90,
        )
        db.commit()

        payload = query_knowledge(db, query="日报先写什么", workshop="热轧", limit=5)

        assert payload["source"] == "professional_knowledge"
        assert payload["items"][0]["domain"] == "daily_report"
        assert "总产量" in payload["answer"]
    finally:
        db.close()


def test_professional_knowledge_citations_are_compatible_with_legacy_rag_fields() -> None:
    db = _session()
    try:
        upsert_professional_knowledge(
            db,
            domain="daily_report",
            topic="成本核算",
            knowledge_type="calculation_rule",
            source_type="manual",
            source_ref="manual://cost-rule",
            content="成本核算按已核电费、气费合计除以入库成品吨数。",
            confidence=95,
        )
        db.commit()

        payload = query_knowledge(db, query="成本怎么按吨算", limit=5)

        citation = payload["citations"][0]
        item = payload["items"][0]
        assert citation["document_id"] is None
        assert citation["filename"]
        assert citation["source_name"]
        assert citation["chunk_index"] == 0
        assert isinstance(citation["metadata"], dict)
        assert item["source"] == "professional_knowledge"
        assert item["entry_id"] == item["id"]
        assert item["document_id"] is None
        assert item["filename"] == citation["filename"]
        assert item["source_name"] == citation["source_name"]
    finally:
        db.close()
