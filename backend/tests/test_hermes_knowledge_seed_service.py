from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.rag import HermesProfessionalKnowledgeEntry
from app.services.hermes_knowledge_seed_service import import_knowledge_seed, load_knowledge_seed


def _db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[HermesProfessionalKnowledgeEntry.__table__])
    return Session(engine)


def test_load_knowledge_seed_has_factory_brain_layers() -> None:
    seed = load_knowledge_seed()

    domains = {item["domain"] for item in seed}
    assert {"production", "energy", "daily_report", "data_source", "datahub_diet"}.issubset(domains)
    assert len(seed) >= 15


def test_daily_report_priority_seed_points_to_current_root_owner_spec() -> None:
    seed = load_knowledge_seed()

    item = next(row for row in seed if row["topic"] == "日报事实优先级")

    assert item["source_ref"] == "docs/superpowers/specs/2026-06-27-hermes-root-owner-production-evidence-loop-design.md"
    assert "钉钉群文件和群聊天内容" in item["content"]


def test_import_knowledge_seed_upserts_entries() -> None:
    db = _db()

    result = import_knowledge_seed(db)

    assert result["inserted_or_updated"] >= 15
    rows = db.query(HermesProfessionalKnowledgeEntry).all()
    assert any(row.topic == "日报事实优先级" for row in rows)
    assert all(row.status in {"active", "candidate"} for row in rows)
