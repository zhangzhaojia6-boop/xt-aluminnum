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


def test_import_knowledge_seed_upserts_entries() -> None:
    db = _db()

    result = import_knowledge_seed(db)

    assert result["inserted_or_updated"] >= 15
    rows = db.query(HermesProfessionalKnowledgeEntry).all()
    assert any(row.topic == "日报事实优先级" for row in rows)
    assert all(row.status in {"active", "candidate"} for row in rows)
