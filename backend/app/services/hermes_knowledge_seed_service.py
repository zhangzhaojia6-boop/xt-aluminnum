from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.services.hermes_professional_knowledge_service import upsert_professional_knowledge

SEED_PATH = Path(__file__).resolve().parents[1] / "hermes" / "knowledge_seeds" / "phase2_factory_brain.json"


def load_knowledge_seed(path: str | Path | None = None) -> list[dict[str, Any]]:
    seed_path = Path(path) if path is not None else SEED_PATH
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("knowledge_seed_must_be_list")
    return [_validate_seed_item(item) for item in payload]


def import_knowledge_seed(db: Session, *, path: str | Path | None = None) -> dict[str, int]:
    count = 0
    for item in load_knowledge_seed(path):
        upsert_professional_knowledge(
            db,
            domain=item["domain"],
            topic=item["topic"],
            knowledge_type=item["knowledge_type"],
            source_type=item["source_type"],
            source_ref=item["source_ref"],
            content=item["content"],
            structured_payload=item["structured_payload"],
            confidence=item["confidence"],
            status=item["status"],
        )
        count += 1
    db.flush()
    return {"inserted_or_updated": count}


def _validate_seed_item(item: object) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("knowledge_seed_item_must_be_object")
    required = {
        "domain",
        "topic",
        "knowledge_type",
        "source_type",
        "source_ref",
        "content",
        "structured_payload",
        "confidence",
        "status",
    }
    missing = sorted(required - set(item))
    if missing:
        raise ValueError(f"knowledge_seed_missing_fields:{','.join(missing)}")
    result = dict(item)
    result["confidence"] = max(0, min(int(result["confidence"]), 100))
    if result["status"] not in {"active", "candidate"}:
        raise ValueError("knowledge_seed_invalid_status")
    return result
