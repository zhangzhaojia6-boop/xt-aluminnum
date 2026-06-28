from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.rag import HermesProfessionalKnowledgeEntry
from app.services.hermes_knowledge_seed_service import import_knowledge_seed, load_knowledge_seed


_REPO_ROOT = Path(__file__).resolve().parents[2]
_BASELINE_SOURCE_REFS = {
    "docs/agent-operating-guide.md",
    "docs/datahub-deprecation-register.md",
    "docs/hermes/fact-source-map.md",
    "docs/software-minus-agent-plus-prd.md",
}


def _db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[HermesProfessionalKnowledgeEntry.__table__])
    return Session(engine)


def test_load_knowledge_seed_has_factory_brain_layers() -> None:
    seed = load_knowledge_seed()

    domains = {item["domain"] for item in seed}
    assert {"production", "energy", "daily_report", "data_source", "datahub_diet"}.issubset(domains)
    assert len(seed) >= 15


def test_daily_report_priority_seed_points_to_current_prd() -> None:
    seed = load_knowledge_seed()

    item = next(row for row in seed if row["topic"] == "日报事实优先级")

    assert item["source_ref"] == "docs/software-minus-agent-plus-prd.md"
    assert "钉钉群文件和群聊天内容" in item["content"]


def test_dingtalk_seed_keeps_group_content_rules_soft() -> None:
    seed = load_knowledge_seed()

    item = next(row for row in seed if row["topic"] == "DingTalk 事实采样条件")

    assert item["source_ref"] == "docs/agent-operating-guide.md"
    assert "授权群、内容类型和时间范围" in item["content"]
    assert "只有标记为专项责任人证据时才额外校验专项责任人" in item["content"]
    assert "必须同时满足授权群、专项责任人" not in item["content"]


def test_seed_source_refs_use_current_baseline_docs() -> None:
    seed = load_knowledge_seed()

    for item in seed:
        source_ref = item["source_ref"]

        assert source_ref in _BASELINE_SOURCE_REFS
        assert "docs/superpowers/" not in source_ref
        assert ":/" not in source_ref
        assert (_REPO_ROOT / source_ref).exists()


def test_import_knowledge_seed_upserts_entries() -> None:
    db = _db()

    result = import_knowledge_seed(db)

    assert result["inserted_or_updated"] >= 15
    rows = db.query(HermesProfessionalKnowledgeEntry).all()
    assert any(row.topic == "日报事实优先级" for row in rows)
    assert all(row.status in {"active", "candidate"} for row in rows)
