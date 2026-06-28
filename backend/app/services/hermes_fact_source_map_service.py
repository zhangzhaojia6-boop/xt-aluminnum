from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SOURCE_MAP_PATH = Path(__file__).resolve().parents[1] / "hermes" / "fact_source_map.json"
DINGTALK_EVIDENCE_CONDITION_KEYS = {
    "authorized_group",
    "content_type",
    "time_range",
}


@lru_cache(maxsize=1)
def load_fact_source_map(path: str | Path | None = None) -> list[dict[str, Any]]:
    source_path = Path(path) if path is not None else SOURCE_MAP_PATH
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("fact_source_map_must_be_list")
    result: list[dict[str, Any]] = []
    seen_metric_keys: set[str] = set()
    for item in payload:
        validated = _validate_item(item)
        metric_key = validated["metric_key"]
        if metric_key in seen_metric_keys:
            raise ValueError(f"fact_source_map_duplicate_metric_key:{metric_key}")
        seen_metric_keys.add(metric_key)
        result.append(validated)
    return result


def find_fact_source(metric_key: str, *, path: str | Path | None = None) -> dict[str, Any]:
    clean_key = str(metric_key or "").strip()
    for item in load_fact_source_map(path):
        if item["metric_key"] == clean_key:
            return item
    raise KeyError(f"unknown_fact_metric:{clean_key}")


def source_summary_for_metric(metric_key: str, *, path: str | Path | None = None) -> str:
    item = find_fact_source(metric_key, path=path)
    sources = " > ".join(item["priority_sources"])
    services = "、".join(item["source_services"])
    risks = "；".join(item["known_risks"])
    return f"{item['display_name']}：优先级 {sources}。涉及服务：{services}。风险：{risks}"


def _validate_item(item: object) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("fact_source_map_item_must_be_object")
    required = {
        "metric_key",
        "display_name",
        "domain",
        "priority_sources",
        "source_tables",
        "source_services",
        "api_routes",
        "frontend_pages",
        "hermes_tools",
        "delete_protection",
        "known_risks",
        "verification_status",
    }
    missing = sorted(required - set(item))
    if missing:
        raise ValueError(f"fact_source_map_missing_fields:{','.join(missing)}")
    result = dict(item)
    for key in (
        "priority_sources",
        "source_tables",
        "source_services",
        "api_routes",
        "frontend_pages",
        "hermes_tools",
        "known_risks",
    ):
        if not isinstance(result[key], list):
            raise ValueError(f"fact_source_map_field_must_be_list:{key}")
    if result["delete_protection"] not in {"protect", "merge_candidate", "freeze_candidate", "candidate_delete"}:
        raise ValueError("fact_source_map_invalid_delete_protection")
    if "dingtalk_group_content" in result["priority_sources"] or "dingtalk_specialist" in result["priority_sources"]:
        conditions = result.get("dingtalk_evidence_conditions")
        if not isinstance(conditions, dict):
            raise ValueError("fact_source_map_missing_dingtalk_evidence_conditions")
        missing = sorted(DINGTALK_EVIDENCE_CONDITION_KEYS - set(conditions))
        if missing:
            raise ValueError(
                "fact_source_map_missing_dingtalk_evidence_condition_fields:" + ",".join(missing)
            )
    return result
