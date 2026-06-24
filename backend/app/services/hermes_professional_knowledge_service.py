from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.rag import HermesProfessionalKnowledgeEntry


def upsert_professional_knowledge(
    db: Session,
    *,
    domain: str,
    topic: str,
    knowledge_type: str,
    source_type: str,
    source_ref: str,
    content: str,
    structured_payload: dict[str, Any] | None = None,
    confidence: int = 80,
    valid_from: date | None = None,
    valid_to: date | None = None,
    status: str = "active",
    created_by_id: int | None = None,
    trace_id: str | None = None,
) -> HermesProfessionalKnowledgeEntry:
    clean_domain = _required_text(domain, "domain")
    clean_topic = _required_text(topic, "topic")
    clean_knowledge_type = _required_text(knowledge_type, "knowledge_type")
    clean_source_type = _required_text(source_type, "source_type")
    clean_source_ref = _required_text(source_ref, "source_ref")
    clean_content = _required_text(content, "content")
    clean_status = str(status or "active").strip() or "active"
    clean_confidence = _clamp_confidence(confidence)
    payload = dict(structured_payload or {})

    entry = (
        db.query(HermesProfessionalKnowledgeEntry)
        .filter(HermesProfessionalKnowledgeEntry.domain == clean_domain)
        .filter(HermesProfessionalKnowledgeEntry.topic == clean_topic)
        .filter(HermesProfessionalKnowledgeEntry.knowledge_type == clean_knowledge_type)
        .filter(HermesProfessionalKnowledgeEntry.source_ref == clean_source_ref)
        .one_or_none()
    )
    if entry is None:
        entry = HermesProfessionalKnowledgeEntry(
            domain=clean_domain,
            topic=clean_topic,
            knowledge_type=clean_knowledge_type,
            source_type=clean_source_type,
            source_ref=clean_source_ref,
            content=clean_content,
            structured_payload=payload,
            confidence=clean_confidence,
            valid_from=valid_from,
            valid_to=valid_to,
            status=clean_status,
            created_by_id=created_by_id,
            trace_id=trace_id,
        )
        db.add(entry)
    else:
        entry.source_type = clean_source_type
        entry.content = clean_content
        entry.structured_payload = payload
        entry.confidence = clean_confidence
        entry.valid_from = valid_from
        entry.valid_to = valid_to
        entry.status = clean_status
        entry.created_by_id = created_by_id
        entry.trace_id = trace_id

    db.flush()
    return entry


def search_professional_knowledge(
    db: Session,
    *,
    query: str,
    limit: int = 5,
    domain: str | None = None,
    knowledge_type: str | None = None,
) -> list[dict[str, Any]]:
    if not _has_professional_knowledge_table(db):
        return []

    tokens = _query_tokens(query)
    if not tokens:
        return []

    clean_domain = str(domain or "").strip()
    clean_knowledge_type = str(knowledge_type or "").strip()
    row_query = db.query(HermesProfessionalKnowledgeEntry).filter(
        HermesProfessionalKnowledgeEntry.status == "active"
    )
    if clean_domain:
        row_query = row_query.filter(HermesProfessionalKnowledgeEntry.domain == clean_domain)
    if clean_knowledge_type:
        row_query = row_query.filter(HermesProfessionalKnowledgeEntry.knowledge_type == clean_knowledge_type)

    rows = row_query.order_by(
        HermesProfessionalKnowledgeEntry.confidence.desc(),
        HermesProfessionalKnowledgeEntry.updated_at.desc(),
        HermesProfessionalKnowledgeEntry.id.desc(),
    ).all()

    scored: list[tuple[float, HermesProfessionalKnowledgeEntry]] = []
    for entry in rows:
        score = _score_entry(entry, tokens)
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda item: (-item[0], -item[1].confidence, item[1].id))

    safe_limit = max(1, min(int(limit or 5), 20))
    return [_entry_item(entry, score=score) for score, entry in scored[:safe_limit]]


def _required_text(value: str, field_name: str) -> str:
    clean_value = str(value or "").strip()
    if not clean_value:
        raise ValueError(f"{field_name}不能为空")
    return clean_value


def _clamp_confidence(value: int) -> int:
    try:
        raw_value = int(value)
    except (TypeError, ValueError):
        raw_value = 80
    return max(0, min(raw_value, 100))


def _has_professional_knowledge_table(db: Session) -> bool:
    try:
        bind = db.get_bind()
        return inspect(bind).has_table(HermesProfessionalKnowledgeEntry.__tablename__)
    except Exception:
        return False


def _query_tokens(query: str) -> list[str]:
    clean_query = re.sub(r"[\s,，。；;：:/\\|+\-_]+", " ", str(query or "")).strip()
    if not clean_query:
        return []
    tokens: set[str] = {part for part in clean_query.split(" ") if len(part) >= 2}
    compact = clean_query.replace(" ", "")
    if len(compact) >= 2:
        tokens.add(compact)
        for size in (2, 3, 4):
            if len(compact) >= size:
                tokens.update(compact[index : index + size] for index in range(0, len(compact) - size + 1))
    return sorted(tokens, key=len, reverse=True)


def _score_entry(entry: HermesProfessionalKnowledgeEntry, tokens: list[str]) -> float:
    structured_text = json.dumps(entry.structured_payload or {}, ensure_ascii=False, sort_keys=True)
    haystack = f"{entry.topic} {entry.content} {entry.source_ref} {structured_text}"
    score = 0.0
    for token in tokens:
        if token in haystack:
            score += 10 + min(len(token), 8)
    if entry.topic and entry.topic in str(tokens[0]):
        score += 5
    return score + (entry.confidence / 100)


def _entry_item(entry: HermesProfessionalKnowledgeEntry, *, score: float) -> dict[str, Any]:
    return {
        "id": entry.id,
        "domain": entry.domain,
        "topic": entry.topic,
        "knowledge_type": entry.knowledge_type,
        "source_type": entry.source_type,
        "source_ref": entry.source_ref,
        "content": entry.content,
        "structured_payload": entry.structured_payload or {},
        "confidence": entry.confidence,
        "score": round(score, 4),
        "source": "professional_knowledge",
    }
