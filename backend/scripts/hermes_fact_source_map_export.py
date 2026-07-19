from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.hermes_fact_source_map_service import load_fact_source_map
from app.domain.daily_report_field_contract import normative_daily_report_fields

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "docs" / "hermes" / "fact-source-map.md"


def _cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, list):
        if not value:
            return "-"
        return " > ".join(_cell(item) for item in value)
    if isinstance(value, dict):
        if not value:
            return "-"
        parts = [f"{key}={_cell(item)}" for key, item in value.items()]
        return "; ".join(parts)
    text = str(value).strip()
    if not text:
        return "-"
    return text.replace("|", "\\|").replace("\n", "<br>")


def _join(items: list[Any]) -> str:
    return "、".join(_cell(item) for item in items) if items else "-"


def render_fact_source_map_markdown() -> str:
    rows = load_fact_source_map()
    normative_field_count = len(normative_daily_report_fields())
    lines = [
        "# Hermes 事实来源地图",
        "",
        "本文件由 `backend/app/hermes/fact_source_map.json` 自动生成，不手工维护。",
        "",
        f"完整字段、业务时间、容差和统一来源顺序见：[日报 {normative_field_count} 字段合同](daily-report-field-contract.md)。",
        "",
        "| 指标 | 领域 | 来源优先级 | 涉及服务 | 保护级别 | 状态 | 接口 | 页面 | 涉及表 | Hermes 工具 | 证据条件 | 已知风险 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for item in rows:
        evidence_conditions = item.get("dingtalk_evidence_conditions")
        lines.append(
            "| {metric} ({key}) | {domain} | {sources} | {services} | {protection} | {status} | {routes} | {pages} | {tables} | {tools} | {conditions} | {risks} |".format(
                metric=_cell(item["display_name"]),
                key=_cell(item["metric_key"]),
                domain=_cell(item["domain"]),
                sources=_join(item["priority_sources"]),
                services=_join(item["source_services"]),
                protection=_cell(item["delete_protection"]),
                status=_cell(item["verification_status"]),
                routes=_join(item["api_routes"]),
                pages=_join(item["frontend_pages"]),
                tables=_join(item["source_tables"]),
                tools=_join(item["hermes_tools"]),
                conditions=_cell(evidence_conditions) if evidence_conditions else "-",
                risks=_join(item["known_risks"]),
            )
        )
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- `protect` 表示不要删除。",
            "- `merge_candidate`、`freeze_candidate`、`candidate_delete` 表示后续还要审计。",
            "- 空接口、空页面、空表或空工具表示当前 seed 没有列出对应入口。",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render_fact_source_map_markdown(), encoding="utf-8")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
