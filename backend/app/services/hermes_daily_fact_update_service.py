from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any


SOURCE = "dingtalk_supplement"
DEFAULT_CONFIDENCE = 0.95
TEXT_CONFIDENCE = 0.86
GENERAL_NON_DAILY_MARKERS = ("本月", "月累计", "累计", "过程量", "预估", "预计", "约", "大概")
FIELD_GUARD_MARKERS = {
    "total_output_daily": GENERAL_NON_DAILY_MARKERS + ("昨日", "包装"),
    "finished_inbound_daily": GENERAL_NON_DAILY_MARKERS,
    "total_electricity_kwh": GENERAL_NON_DAILY_MARKERS,
    "wip_total": GENERAL_NON_DAILY_MARKERS,
    "daily_yield_rate": GENERAL_NON_DAILY_MARKERS,
}

FIELD_SPECS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("total_output_daily", "吨", ("总产量", "日产量", "产量")),
    ("finished_inbound_daily", "吨", ("成品入库", "入库成品", "入库")),
    ("total_electricity_kwh", "度", ("高压电", "用电", "电耗")),
    ("wip_total", "吨", ("在制合计", "在制")),
    ("daily_yield_rate", "%", ("成品率",)),
)
FIELD_DEFAULT_UNITS = {field: unit for field, unit, _phrases in FIELD_SPECS}
STRUCTURED_FACT_KEYS = ("fact_updates", "daily_facts", "facts", "extracted_facts", "fields")
TEXT_KEYS = (
    "recognized_text",
    "recognized",
    "text",
    "content",
    "file_text",
    "parsed_text",
    "ocr_text",
    "extracted_text",
    "attachment_text",
    "message_text",
    "plain_text",
    "summary",
)
TEXT_CONTAINER_KEYS = (
    "file",
    "files",
    "attachment",
    "attachments",
    "document",
    "documents",
    "workbook",
    "sheet",
    "sheets",
)
NUMBER_WITH_UNIT_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>吨|t|T|度|kwh|KWH|%)")


def extract_daily_fact_update_candidates(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(evidence, Mapping):
        return []

    payload = evidence.get("payload")
    if "payload" in evidence and not isinstance(payload, Mapping):
        return []
    payload_map = payload if isinstance(payload, Mapping) else {}
    raw_text = _raw_text(evidence, payload_map)
    trace_id = _trace_id(evidence, payload_map)

    fact_updates = _structured_fact_updates(payload_map)
    if "fact_updates" in payload_map and fact_updates is None:
        return []
    if fact_updates is not None:
        return _structured_candidates(
            fact_updates,
            raw_text=raw_text,
            trace_id=trace_id,
        )

    if not raw_text:
        return []
    return _plain_text_candidates(raw_text, trace_id=trace_id)


def _structured_fact_updates(payload: Mapping[str, Any]) -> Any | None:
    for key in STRUCTURED_FACT_KEYS:
        if key not in payload:
            continue
        value = payload.get(key)
        if _iter_fact_updates(value):
            return value
    return None


def _structured_candidates(
    fact_updates: Any,
    *,
    raw_text: str,
    trace_id: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for field, item in _iter_fact_updates(fact_updates):
        if not _has_value(item.get("value")):
            continue
        candidate = {
            "field": field,
            "value": item.get("value"),
            "unit": item.get("unit") or FIELD_DEFAULT_UNITS.get(field, ""),
            "confidence": _confidence(item.get("confidence"), DEFAULT_CONFIDENCE),
            "source": SOURCE,
            "trace_id": trace_id,
            "raw_text": raw_text,
        }
        if "reason" in item:
            candidate["reason"] = item.get("reason")
        candidates.append(candidate)
    return candidates


def _iter_fact_updates(fact_updates: Any) -> list[tuple[str, Mapping[str, Any]]]:
    if isinstance(fact_updates, Mapping):
        direct_field = str(fact_updates.get("field") or fact_updates.get("field_name") or "").strip()
        if direct_field:
            return [(direct_field, fact_updates)]

        updates: list[tuple[str, Mapping[str, Any]]] = []
        for raw_field, item in fact_updates.items():
            if not isinstance(item, Mapping):
                continue
            field = str(item.get("field") or item.get("field_name") or raw_field or "").strip()
            if field:
                updates.append((field, item))
        return updates

    if isinstance(fact_updates, list):
        updates = []
        for item in fact_updates:
            if not isinstance(item, Mapping):
                continue
            field = str(item.get("field") or item.get("field_name") or "").strip()
            if field:
                updates.append((field, item))
        return updates

    return []


def _plain_text_candidates(raw_text: str, *, trace_id: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for field, default_unit, phrases in FIELD_SPECS:
        value_unit = _value_near_any_phrase(
            raw_text,
            phrases,
            expected_unit=default_unit,
            guard_markers=FIELD_GUARD_MARKERS.get(field, ()),
        )
        if value_unit is None:
            continue
        value, unit = value_unit
        candidates.append(
            {
                "field": field,
                "value": value,
                "unit": unit,
                "confidence": TEXT_CONFIDENCE,
                "source": SOURCE,
                "trace_id": trace_id,
                "raw_text": raw_text,
            }
        )
    return candidates


def _value_near_any_phrase(
    text: str,
    phrases: tuple[str, ...],
    *,
    expected_unit: str,
    guard_markers: tuple[str, ...],
) -> tuple[int | float, str] | None:
    for phrase in phrases:
        for phrase_match in re.finditer(re.escape(phrase), text):
            after = text[phrase_match.end() : phrase_match.end() + 24]
            after_match = NUMBER_WITH_UNIT_RE.search(after)
            if after_match is not None:
                local_start = max(0, phrase_match.start() - 6)
                local_end = phrase_match.end() + after_match.end()
                segment = text[local_start:local_end]
                if not any(marker in segment for marker in guard_markers):
                    value_unit = _value_unit_from_match(after_match, expected_unit=expected_unit)
                    if value_unit is not None:
                        return value_unit

            before = text[max(0, phrase_match.start() - 16) : phrase_match.start()]
            before_matches = list(NUMBER_WITH_UNIT_RE.finditer(before))
            for before_match in reversed(before_matches):
                segment = before[before_match.start() :] + text[phrase_match.start() : phrase_match.end()]
                if any(marker in segment for marker in guard_markers):
                    continue
                value_unit = _value_unit_from_match(before_match, expected_unit=expected_unit)
                if value_unit is not None:
                    return value_unit
    return None


def _value_unit_from_match(
    match: re.Match[str] | None,
    *,
    expected_unit: str,
) -> tuple[int | float, str] | None:
    if match is None:
        return None
    unit = _normalize_unit(match.group("unit"))
    if unit != expected_unit:
        return None
    return _number(match.group("value")), unit


def _raw_text(evidence: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for source in (evidence, payload):
        _collect_text_parts(source, parts=parts, seen=seen)
    return "\n".join(parts)


def _collect_text_parts(value: Any, *, parts: list[str], seen: set[str], depth: int = 0) -> None:
    if depth > 4:
        return
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key or "").strip().lower()
            if key in TEXT_KEYS or key.endswith("_text"):
                _append_text_part(item, parts=parts, seen=seen)
        for key in TEXT_CONTAINER_KEYS:
            if key in value:
                _collect_text_parts(value.get(key), parts=parts, seen=seen, depth=depth + 1)
        return
    if isinstance(value, list):
        for item in value:
            _collect_text_parts(item, parts=parts, seen=seen, depth=depth + 1)


def _append_text_part(value: Any, *, parts: list[str], seen: set[str]) -> None:
    if not isinstance(value, str):
        return
    text = value.strip()
    if text and text not in seen:
        parts.append(text)
        seen.add(text)


def _trace_id(evidence: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    for source in (payload, evidence):
        value = source.get("trace_id")
        if value is not None and value != "":
            return str(value)
    for source in (payload, evidence):
        value = source.get("id")
        if value is not None and value != "":
            return str(value)
    return ""


def _confidence(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def _normalize_unit(unit: str) -> str:
    if unit in {"t", "T"}:
        return "吨"
    if unit.lower() == "kwh":
        return "度"
    return unit


def _number(value: str) -> int | float:
    if "." in value:
        return float(value)
    return int(value)
