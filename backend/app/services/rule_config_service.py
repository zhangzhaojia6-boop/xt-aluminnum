from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_sessionmaker
from app.models.rule_config import RuleConfig
from app.rules.thresholds import DEFAULT_THRESHOLDS

CACHE_TTL_SECONDS = 30
VALID_SCOPE_TYPES = {"factory", "workshop"}


@dataclass(frozen=True)
class ResolvedThreshold:
    key: str
    value: float | int
    scope_type: str
    scope_key: str | None
    source: str


@dataclass(frozen=True)
class _CachedValue:
    expires_at: float
    resolved: ResolvedThreshold


_CACHE: dict[tuple[str | None, str, str], _CachedValue] = {}


def invalidate_cache() -> None:
    _CACHE.clear()


def _default_value(key: str) -> float | int:
    if key not in DEFAULT_THRESHOLDS:
        raise KeyError(f"Unknown rule threshold: {key}")
    return DEFAULT_THRESHOLDS[key]


def _value_type_for(value: Any) -> str:
    return "int" if isinstance(value, int) and not isinstance(value, bool) else "float"


def _coerce_value(value: str, value_type: str) -> float | int:
    if value_type == "int":
        return int(float(value))
    return float(value)


def _format_value(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    return f"{float(value):g}"


def _normalize_scope(scope_type: str, scope_key: str | None) -> tuple[str, str]:
    normalized_type = (scope_type or "").strip().lower()
    if normalized_type not in VALID_SCOPE_TYPES:
        raise ValueError("规则范围仅支持 factory / workshop")
    if normalized_type == "factory":
        return normalized_type, "factory"
    normalized_key = (scope_key or "").strip()
    if not normalized_key:
        raise ValueError("车间规则必须提供 scope_key")
    return normalized_type, normalized_key


def _find_row(db: Session, *, scope_type: str, scope_key: str, key: str) -> RuleConfig | None:
    query = db.query(RuleConfig).filter(
        RuleConfig.scope_type == scope_type,
        RuleConfig.scope_key == scope_key,
        RuleConfig.key == key,
    )
    first = getattr(query, "first", None)
    if first is None:
        return None
    return first()


def _fallback_threshold(key: str, workshop_code: str | None) -> ResolvedThreshold:
    return ResolvedThreshold(
        key=key,
        value=_default_value(key),
        scope_type="factory",
        scope_key=workshop_code,
        source="fallback",
    )


def _load_resolved_threshold(db: Session, *, key: str, workshop_code: str | None) -> ResolvedThreshold:
    if workshop_code:
        item = _find_row(db, scope_type="workshop", scope_key=workshop_code, key=key)
        if item is not None:
            return ResolvedThreshold(
                key=key,
                value=_coerce_value(item.value, item.value_type),
                scope_type="workshop",
                scope_key=workshop_code,
                source="workshop",
            )

    item = _find_row(db, scope_type="factory", scope_key="factory", key=key)
    if item is not None:
        return ResolvedThreshold(
            key=key,
            value=_coerce_value(item.value, item.value_type),
            scope_type="factory",
            scope_key="factory",
            source="factory",
        )
    return _fallback_threshold(key, workshop_code)


def resolve_threshold(key: str, *, workshop_code: str | None = None, db: Session | None = None) -> ResolvedThreshold:
    _default_value(key)
    normalized_workshop = (workshop_code or "").strip() or None
    cache_mode = "db" if db is not None else "fallback"
    cache_key = (normalized_workshop, key, cache_mode)
    now = time.monotonic()

    cached = _CACHE.get(cache_key)
    if cached and cached.expires_at > now:
        return cached.resolved

    if db is None:
        resolved = _fallback_threshold(key, normalized_workshop)
        _CACHE[cache_key] = _CachedValue(expires_at=now + CACHE_TTL_SECONDS, resolved=resolved)
        return resolved

    try:
        resolved = _load_resolved_threshold(db, key=key, workshop_code=normalized_workshop)
    except SQLAlchemyError:
        resolved = _fallback_threshold(key, normalized_workshop)

    _CACHE[cache_key] = _CachedValue(expires_at=now + CACHE_TTL_SECONDS, resolved=resolved)
    return resolved


def get_threshold(key: str, *, workshop_code: str | None = None, db: Session | None = None) -> float | int:
    return resolve_threshold(key, workshop_code=workshop_code, db=db).value


def set_threshold(
    db: Session,
    *,
    scope_type: str,
    scope_key: str | None,
    key: str,
    value: float | int,
    updated_by: int | None = None,
    value_type: str | None = None,
) -> RuleConfig:
    _default_value(key)
    normalized_type, normalized_key = _normalize_scope(scope_type, scope_key)
    stored_type = value_type or _value_type_for(value)
    if stored_type not in {"int", "float"}:
        raise ValueError("规则阈值仅支持 int / float")

    item = _find_row(db, scope_type=normalized_type, scope_key=normalized_key, key=key)
    if item is None:
        item = RuleConfig(
            scope_type=normalized_type,
            scope_key=normalized_key,
            key=key,
            value=_format_value(value),
            value_type=stored_type,
            version=1,
            updated_by=updated_by,
        )
        db.add(item)
    else:
        item.value = _format_value(value)
        item.value_type = stored_type
        item.version += 1
        item.updated_by = updated_by
    db.flush()
    invalidate_cache()
    return item


def _row_payload(
    *,
    scope_type: str,
    scope_key: str,
    key: str,
    value: float | int,
    value_type: str,
    source: str,
    item: RuleConfig | None = None,
) -> dict:
    return {
        "id": item.id if item is not None else None,
        "scope_type": scope_type,
        "scope_key": scope_key,
        "key": key,
        "value": value,
        "value_type": value_type,
        "version": item.version if item is not None else 0,
        "updated_by": item.updated_by if item is not None else None,
        "updated_at": item.updated_at if item is not None else None,
        "source": source,
    }


def list_for_scope(db: Session, *, scope_type: str, scope_key: str | None) -> list[dict]:
    normalized_type, normalized_key = _normalize_scope(scope_type, scope_key)
    scoped_rows = {
        item.key: item
        for item in db.query(RuleConfig)
        .filter(RuleConfig.scope_type == normalized_type, RuleConfig.scope_key == normalized_key)
        .all()
    }
    factory_rows = {
        item.key: item
        for item in db.query(RuleConfig)
        .filter(RuleConfig.scope_type == "factory", RuleConfig.scope_key == "factory")
        .all()
    }

    rows: list[dict] = []
    for key, default in DEFAULT_THRESHOLDS.items():
        if key in scoped_rows:
            item = scoped_rows[key]
            rows.append(
                _row_payload(
                    scope_type=normalized_type,
                    scope_key=normalized_key,
                    key=key,
                    value=_coerce_value(item.value, item.value_type),
                    value_type=item.value_type,
                    source="override",
                    item=item,
                )
            )
            continue
        if normalized_type == "workshop" and key in factory_rows:
            item = factory_rows[key]
            rows.append(
                _row_payload(
                    scope_type=normalized_type,
                    scope_key=normalized_key,
                    key=key,
                    value=_coerce_value(item.value, item.value_type),
                    value_type=item.value_type,
                    source="factory",
                )
            )
            continue
        rows.append(
            _row_payload(
                scope_type=normalized_type,
                scope_key=normalized_key,
                key=key,
                value=default,
                value_type=_value_type_for(default),
                source="fallback",
            )
        )
    return rows


def payload_for(item: RuleConfig) -> dict:
    return _row_payload(
        scope_type=item.scope_type,
        scope_key=item.scope_key,
        key=item.key,
        value=_coerce_value(item.value, item.value_type),
        value_type=item.value_type,
        source="override",
        item=item,
    )


def serialize(item: RuleConfig) -> dict:
    return payload_for(item)
