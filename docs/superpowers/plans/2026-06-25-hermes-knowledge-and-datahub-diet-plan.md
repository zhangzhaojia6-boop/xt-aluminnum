# Hermes Knowledge and Datahub Diet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the next Hermes phase: a machine-readable fact source map, seeded professional knowledge base, Hermes source-explanation tool, data hub reduction audit, and acceptance harness so Hermes can answer with real sources while the 数据中枢 gets lighter safely.

**Architecture:** Reuse the existing Hermes factory-brain lane, DailyFactBundle, professional knowledge table, RAG service, DingTalk evidence, and LangChain/LangGraph code. Add a small fact-source-map layer and audit scripts around them. Do not delete production tables or remove fallback paths in this plan.

**Tech Stack:** FastAPI service layer, SQLAlchemy, pytest, existing `HermesProfessionalKnowledgeEntry`, existing `DailyFactBundle`, existing `hermes_langchain_tools.py`, existing `hermes_factory_brain_harness.py`, JSON seed files, markdown reports.

---

## Scope Check

This plan has one integrated scope because the work has one operational goal:

```text
Hermes answers with source-backed factory knowledge
  -> data hub knows which parts are still needed
  -> duplicate or stale surfaces can be frozen later
```

Do not implement destructive cleanup in this plan. The output of this plan is evidence, tooling, seeds, and reports. Actual deletion is a later plan after 7 to 14 days of production observation.

## Current Code Facts

- `backend/app/services/report/daily_fact_bundle.py` already builds a business-day fact bundle with source priority, DingTalk supplements, root_owner corrections, snapshots, and output skill alignment.
- `backend/app/services/hermes_professional_knowledge_service.py` already upserts and searches professional knowledge entries with redaction.
- `backend/app/services/rag_service.py::query_knowledge` already prefers professional knowledge before generic chunks.
- `backend/app/services/hermes_langchain_tools.py` already has a whitelist registry for Hermes tools.
- `backend/app/services/hermes_factory_brain_harness.py` already scores daily report, anomaly analysis, and business question scenarios.
- `docs/mes-data-hub-hermes-fact-map-2026-06-19.md` already contains a human fact map that should be turned into a machine-readable seed.
- `docs/system-understanding-database-api-route-map-2026-06-14.md` already records page to API to table mappings and notes old route risk.

## File Structure

Create:

- `backend/app/hermes/fact_source_map.json`
  Machine-readable source map seed used by Hermes and audit scripts.

- `backend/app/hermes/knowledge_seeds/phase2_factory_brain.json`
  First batch of formal/candidate knowledge units for the existing professional knowledge table.

- `backend/app/services/hermes_fact_source_map_service.py`
  Loads and validates the fact source map and provides lookup helpers.

- `backend/app/services/hermes_knowledge_seed_service.py`
  Imports JSON seeds into `HermesProfessionalKnowledgeEntry` through the existing upsert service.

- `backend/app/services/hermes_datahub_diet_audit_service.py`
  Classifies files, routes, pages, services, and docs into keep, merge, freeze, candidate_delete, or protect.

- `backend/scripts/hermes_fact_source_map_export.py`
  Writes a human-readable markdown source map from the JSON seed.

- `backend/scripts/hermes_knowledge_seed_import.py`
  Imports the Phase-2 knowledge seed into the database.

- `backend/scripts/hermes_datahub_diet_audit.py`
  Runs the non-destructive data hub reduction audit and writes a markdown report.

- `backend/tests/test_hermes_fact_source_map_service.py`
- `backend/tests/test_hermes_knowledge_seed_service.py`
- `backend/tests/test_hermes_datahub_diet_audit_service.py`
- `backend/tests/test_hermes_phase2_source_map_acceptance.py`
- `docs/hermes/fact-source-map.md`
- `docs/datahub-deprecation-register.md`
- `docs/superpowers/reports/datahub-diet-audit-2026-06-25.md`
- `docs/superpowers/reports/hermes-phase2-knowledge-source-map-qa-2026-06-25.md`

Modify:

- `backend/app/services/hermes_langchain_tools.py`
  Add a `source_map` tool to the whitelist.

- `backend/app/services/hermes_factory_brain_harness.py`
  Add acceptance checks for source map and traceable source wording.

- `backend/tests/test_hermes_langchain_tools.py`
  Update the whitelist expectation.

- `backend/tests/test_hermes_factory_brain_acceptance.py`
  Add source-backed answer scenarios.

Do not modify:

- MES sync write path.
- WMS sync write path.
- production database schema.
- mobile fill write path.
- old command fallback removal.
- production route deletion.

---

## Task 1: Add Machine-Readable Fact Source Map

**Files:**
- Create: `backend/app/hermes/fact_source_map.json`
- Create: `backend/app/services/hermes_fact_source_map_service.py`
- Create: `backend/tests/test_hermes_fact_source_map_service.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_hermes_fact_source_map_service.py`:

```python
from __future__ import annotations

from app.services.hermes_fact_source_map_service import (
    find_fact_source,
    load_fact_source_map,
    source_summary_for_metric,
)


def test_fact_source_map_loads_core_daily_report_metrics() -> None:
    source_map = load_fact_source_map()

    keys = {item["metric_key"] for item in source_map}
    assert "total_output_daily" in keys
    assert "finished_inbound_daily" in keys
    assert "cost_per_ton" in keys
    assert len(source_map) >= 12


def test_fact_source_map_protects_raw_evidence_and_audit_paths() -> None:
    item = find_fact_source("total_output_daily")

    assert item["delete_protection"] == "protect"
    assert "DailyFactBundle" in item["source_services"]
    assert "Hermes" in source_summary_for_metric("total_output_daily")


def test_fact_source_map_contains_no_sensitive_keys() -> None:
    source_map = load_fact_source_map()
    text = str(source_map).lower()

    assert "password" not in text
    assert "token" not in text
    assert "secret" not in text
    assert "连接串" not in text
```

- [ ] **Step 2: Run the tests and verify red**

Run:

```powershell
python -m pytest backend/tests/test_hermes_fact_source_map_service.py -q
```

Expected: fails because the service and JSON file do not exist.

- [ ] **Step 3: Add the JSON seed**

Create `backend/app/hermes/fact_source_map.json` with this first batch:

```json
[
  {
    "metric_key": "total_output_daily",
    "display_name": "车间总产量日合计",
    "domain": "production",
    "priority_sources": ["root_owner", "dingtalk_specialist", "DailyFactBundle", "MES/WMS readonly", "data_hub_projection"],
    "source_tables": ["daily_fact_bundle_snapshots", "multimodal_evidence", "mes_workshop_process_records", "daily_reports"],
    "source_services": ["DailyFactBundle", "Hermes", "template_daily_report", "hermes_langchain_tools"],
    "api_routes": ["/api/v1/reports/template-daily/preview", "/api/v1/dashboard/daily-production"],
    "frontend_pages": ["/manage/today", "/manage/production"],
    "hermes_tools": ["hub_query", "dingtalk_evidence", "output_skill_alignment", "source_map"],
    "delete_protection": "protect",
    "known_risks": ["包装量、入库量、车间最终日报产量不是同一个数"],
    "verification_status": "已证实"
  },
  {
    "metric_key": "finished_inbound_daily",
    "display_name": "入库成品日合计",
    "domain": "inventory",
    "priority_sources": ["root_owner", "dingtalk_specialist", "WMS final document", "DailyFactBundle", "data_hub_projection"],
    "source_tables": ["daily_fact_bundle_snapshots", "mes_stock_records", "multimodal_evidence", "daily_reports"],
    "source_services": ["DailyFactBundle", "template_daily_report", "HermesMesReadService"],
    "api_routes": ["/api/v1/dashboard/daily-production", "/api/v1/mes/extended/stock-records"],
    "frontend_pages": ["/manage/today", "/manage/workshop-dashboard"],
    "hermes_tools": ["hub_query", "mes_wms_read", "dingtalk_evidence", "source_map"],
    "delete_protection": "protect",
    "known_risks": ["成品库入库和总日报入库成品需要分字段解释"],
    "verification_status": "已证实"
  },
  {
    "metric_key": "total_electricity_kwh",
    "display_name": "全厂高压总用电量",
    "domain": "energy",
    "priority_sources": ["root_owner", "dingtalk_specialist", "data_hub_manual", "iot_energy_future"],
    "source_tables": ["machine_energy_records", "mobile_shift_reports", "daily_fact_bundle_snapshots"],
    "source_services": ["DailyFactBundle", "energy_service", "template_daily_report"],
    "api_routes": ["/api/v1/dashboard/daily-production", "/api/v1/energy/summary"],
    "frontend_pages": ["/manage/today", "/manage/energy"],
    "hermes_tools": ["hub_query", "dingtalk_evidence", "source_map"],
    "delete_protection": "protect",
    "known_risks": ["物联网能耗当前未配置，机列明细不能当全厂总量"],
    "verification_status": "已证实"
  },
  {
    "metric_key": "total_gas_m3",
    "display_name": "全厂用气量",
    "domain": "energy",
    "priority_sources": ["root_owner", "dingtalk_specialist", "data_hub_manual"],
    "source_tables": ["machine_energy_records", "mobile_shift_reports", "daily_fact_bundle_snapshots"],
    "source_services": ["DailyFactBundle", "energy_service", "template_daily_report"],
    "api_routes": ["/api/v1/dashboard/daily-production", "/api/v1/energy/summary"],
    "frontend_pages": ["/manage/today", "/manage/energy"],
    "hermes_tools": ["hub_query", "dingtalk_evidence", "source_map"],
    "delete_protection": "protect",
    "known_risks": ["用气分项和总量需要分开显示"],
    "verification_status": "已证实"
  },
  {
    "metric_key": "electricity_per_ton",
    "display_name": "日吨电耗",
    "domain": "energy",
    "priority_sources": ["DailyFactBundle", "computed", "data_hub_manual", "MES/WMS readonly"],
    "source_tables": ["daily_fact_bundle_snapshots", "machine_energy_records", "mes_workshop_process_records"],
    "source_services": ["DailyFactBundle", "operation_analysis", "template_daily_report"],
    "api_routes": ["/api/v1/dashboard/daily-production", "/api/v1/energy/summary"],
    "frontend_pages": ["/manage/today", "/manage/production", "/manage/energy"],
    "hermes_tools": ["hub_query", "rag_route", "source_map"],
    "delete_protection": "protect",
    "known_risks": ["分母必须说明是产量、包装量还是入库量"],
    "verification_status": "已证实"
  },
  {
    "metric_key": "daily_yield_rate",
    "display_name": "日成品率",
    "domain": "quality",
    "priority_sources": ["DailyFactBundle", "computed", "MES/WMS readonly", "historical_report"],
    "source_tables": ["daily_fact_bundle_snapshots", "mes_workshop_process_records", "mes_stock_records"],
    "source_services": ["DailyFactBundle", "yield_matrix_canonical_service", "template_daily_report"],
    "api_routes": ["/api/v1/dashboard/daily-production"],
    "frontend_pages": ["/manage/today", "/manage/production"],
    "hermes_tools": ["hub_query", "rag_route", "source_map"],
    "delete_protection": "protect",
    "known_risks": ["成品率必须保留分子分母口径"],
    "verification_status": "候选"
  },
  {
    "metric_key": "cost_per_ton",
    "display_name": "成本折算元/吨",
    "domain": "cost",
    "priority_sources": ["DailyFactBundle", "computed", "root_owner", "historical_report"],
    "source_tables": ["daily_fact_bundle_snapshots", "cost_daily_result", "daily_reports"],
    "source_services": ["DailyFactBundle", "operation_analysis", "executive_service"],
    "api_routes": ["/api/v1/dashboard/daily-production", "/api/v1/executive/*"],
    "frontend_pages": ["/manage/today", "/manage/production"],
    "hermes_tools": ["hub_query", "history_report", "rag_route", "source_map"],
    "delete_protection": "protect",
    "known_risks": ["电费、气费、入库吨数缺一项就不能强算最终成本"],
    "verification_status": "已证实"
  },
  {
    "metric_key": "wip_total",
    "display_name": "当天在制料",
    "domain": "production",
    "priority_sources": ["MES/WMS readonly", "data_hub_projection", "DailyFactBundle"],
    "source_tables": ["mes_wip_total_snapshots", "mes_daily_wip_snapshots", "daily_fact_bundle_snapshots"],
    "source_services": ["mes_extended_service", "DailyFactBundle", "template_daily_report"],
    "api_routes": ["/api/v1/mes/extended/wip-total-snapshots", "/api/v1/dashboard/daily-production"],
    "frontend_pages": ["/manage/today", "/manage/workshop-dashboard"],
    "hermes_tools": ["mes_wms_read", "hub_query", "source_map"],
    "delete_protection": "protect",
    "known_risks": ["在制重量单位需要持续复核"],
    "verification_status": "待复核"
  },
  {
    "metric_key": "remaining_contract_weight",
    "display_name": "总余合同量",
    "domain": "operations",
    "priority_sources": ["data_hub_projection", "MES/WMS readonly", "DailyFactBundle"],
    "source_tables": ["daily_fact_bundle_snapshots", "work_order_entries", "mes_coil_snapshots"],
    "source_services": ["DailyFactBundle", "contract_progress_projection_service", "factory_command_service"],
    "api_routes": ["/api/v1/dashboard/daily-production", "/api/v1/factory-command/overview"],
    "frontend_pages": ["/manage/today", "/manage/production"],
    "hermes_tools": ["hub_query", "mes_wms_read", "source_map"],
    "delete_protection": "protect",
    "known_risks": ["合同和发货影响需要跨库存、入库、发货一起判断"],
    "verification_status": "候选"
  },
  {
    "metric_key": "monthly_total_output",
    "display_name": "月累计产量",
    "domain": "operation_period",
    "priority_sources": ["OperationPeriodSnapshot", "DailyReportHistoryRecord", "DailyFactBundle"],
    "source_tables": ["operation_period_snapshots", "daily_report_history_records", "daily_fact_bundle_snapshots"],
    "source_services": ["period_rollup", "operation_analysis", "daily_report_history"],
    "api_routes": ["not_exposed_yet"],
    "frontend_pages": ["Hermes only"],
    "hermes_tools": ["history_report", "hub_query", "source_map"],
    "delete_protection": "protect",
    "known_risks": ["缺少历史日报日期时必须提示累计不完整"],
    "verification_status": "已证实"
  },
  {
    "metric_key": "annual_total_output",
    "display_name": "年累计产量",
    "domain": "operation_period",
    "priority_sources": ["OperationPeriodSnapshot", "DailyReportHistoryRecord", "DailyFactBundle"],
    "source_tables": ["operation_period_snapshots", "daily_report_history_records", "daily_fact_bundle_snapshots"],
    "source_services": ["period_rollup", "operation_analysis", "daily_report_history"],
    "api_routes": ["not_exposed_yet"],
    "frontend_pages": ["Hermes only"],
    "hermes_tools": ["history_report", "hub_query", "source_map"],
    "delete_protection": "protect",
    "known_risks": ["年累计必须能追溯到日快照集合"],
    "verification_status": "候选"
  },
  {
    "metric_key": "dingtalk_specialist_evidence",
    "display_name": "钉钉专项责任人证据",
    "domain": "evidence",
    "priority_sources": ["authorized_group", "specialist_sender", "content_type", "time_range"],
    "source_tables": ["multimodal_evidence", "chat_inbox", "external_message_logs"],
    "source_services": ["hermes_dingtalk_sampling_service", "agent_multimodal_evidence_service"],
    "api_routes": ["/api/v1/dingtalk/agent-inbound"],
    "frontend_pages": ["DingTalk"],
    "hermes_tools": ["dingtalk_evidence", "source_map"],
    "delete_protection": "protect",
    "known_risks": ["四条件不全时不能当高优先级事实"],
    "verification_status": "已证实"
  }
]
```

- [ ] **Step 4: Implement the service**

Create `backend/app/services/hermes_fact_source_map_service.py`:

```python
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

SOURCE_MAP_PATH = Path(__file__).resolve().parents[1] / "hermes" / "fact_source_map.json"


@lru_cache(maxsize=1)
def load_fact_source_map(path: str | Path | None = None) -> list[dict[str, Any]]:
    source_path = Path(path) if path is not None else SOURCE_MAP_PATH
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("fact_source_map_must_be_list")
    return [_validate_item(item) for item in payload]


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
    for key in ("priority_sources", "source_tables", "source_services", "api_routes", "frontend_pages", "hermes_tools", "known_risks"):
        if not isinstance(result[key], list):
            raise ValueError(f"fact_source_map_field_must_be_list:{key}")
    if result["delete_protection"] not in {"protect", "merge_candidate", "freeze_candidate", "candidate_delete"}:
        raise ValueError("fact_source_map_invalid_delete_protection")
    return result
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest backend/tests/test_hermes_fact_source_map_service.py -q
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/hermes/fact_source_map.json backend/app/services/hermes_fact_source_map_service.py backend/tests/test_hermes_fact_source_map_service.py
git commit -m "feat: add Hermes fact source map"
```

---

## Task 2: Export the Fact Source Map for Humans

**Files:**
- Create: `backend/scripts/hermes_fact_source_map_export.py`
- Create: `docs/hermes/fact-source-map.md`
- Modify: `backend/tests/test_hermes_fact_source_map_service.py`

- [ ] **Step 1: Add export test**

Append to `backend/tests/test_hermes_fact_source_map_service.py`:

```python
from backend.scripts.hermes_fact_source_map_export import render_fact_source_map_markdown


def test_fact_source_map_export_contains_core_columns() -> None:
    markdown = render_fact_source_map_markdown()

    assert "| 指标 | 领域 | 来源优先级 | 涉及服务 | 保护级别 | 状态 |" in markdown
    assert "车间总产量日合计" in markdown
    assert "protect" in markdown
```

- [ ] **Step 2: Run the export test and verify red**

Run:

```powershell
python -m pytest backend/tests/test_hermes_fact_source_map_service.py::test_fact_source_map_export_contains_core_columns -q
```

Expected: fails because the script does not exist.

- [ ] **Step 3: Implement export script**

Create `backend/scripts/hermes_fact_source_map_export.py`:

```python
from __future__ import annotations

from pathlib import Path

from app.services.hermes_fact_source_map_service import load_fact_source_map

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "docs" / "hermes" / "fact-source-map.md"


def render_fact_source_map_markdown() -> str:
    rows = load_fact_source_map()
    lines = [
        "# Hermes 事实来源地图",
        "",
        "本文件由 `backend/app/hermes/fact_source_map.json` 生成。",
        "",
        "| 指标 | 领域 | 来源优先级 | 涉及服务 | 保护级别 | 状态 |",
        "|---|---|---|---|---|---|",
    ]
    for item in rows:
        lines.append(
            "| {display} (`{key}`) | {domain} | {sources} | {services} | {protection} | {status} |".format(
                display=item["display_name"],
                key=item["metric_key"],
                domain=item["domain"],
                sources=" > ".join(item["priority_sources"]),
                services="、".join(item["source_services"]),
                protection=item["delete_protection"],
                status=item["verification_status"],
            )
        )
    lines.append("")
    lines.append("减法原则：`protect` 项不得删除；`merge_candidate` 和 `freeze_candidate` 只能进入后续审计。")
    return "\n".join(lines)


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(render_fact_source_map_markdown(), encoding="utf-8")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Generate the markdown**

Run:

```powershell
$env:PYTHONPATH="backend"
python backend/scripts/hermes_fact_source_map_export.py
```

Expected: prints `wrote ...docs\hermes\fact-source-map.md`.

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest backend/tests/test_hermes_fact_source_map_service.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/scripts/hermes_fact_source_map_export.py docs/hermes/fact-source-map.md backend/tests/test_hermes_fact_source_map_service.py
git commit -m "docs: export Hermes fact source map"
```

---

## Task 3: Seed the Professional Knowledge Base

**Files:**
- Create: `backend/app/hermes/knowledge_seeds/phase2_factory_brain.json`
- Create: `backend/app/services/hermes_knowledge_seed_service.py`
- Create: `backend/scripts/hermes_knowledge_seed_import.py`
- Create: `backend/tests/test_hermes_knowledge_seed_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_hermes_knowledge_seed_service.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify red**

Run:

```powershell
python -m pytest backend/tests/test_hermes_knowledge_seed_service.py -q
```

Expected: fails because service and seed file do not exist.

- [ ] **Step 3: Create the seed file**

Create `backend/app/hermes/knowledge_seeds/phase2_factory_brain.json` with at least these entries:

```json
[
  {
    "domain": "daily_report",
    "topic": "日报事实优先级",
    "knowledge_type": "rule",
    "source_type": "spec",
    "source_ref": "docs/superpowers/specs/2026-06-25-hermes-knowledge-and-datahub-diet-design.md",
    "content": "日报正式事实优先级为 root_owner 修正、满足四条件的钉钉专项证据、DailyFactBundle、MES/WMS 只读最终源、数据中枢投影、历史日报和 RAG 口径参考。",
    "structured_payload": {"layer": "E", "unit_type": "rule", "status": "formal"},
    "confidence": 95,
    "status": "active"
  },
  {
    "domain": "data_source",
    "topic": "RAG 不是实时事实库",
    "knowledge_type": "rule",
    "source_type": "spec",
    "source_ref": "docs/superpowers/specs/2026-06-25-hermes-knowledge-and-datahub-diet-design.md",
    "content": "RAG 负责解释工艺、字段、规则、案例和输出口径，不保存每日动态事实数字。每日数字进入 DailyFactBundle、历史日报、证据和审计记录。",
    "structured_payload": {"layer": "C", "unit_type": "rule", "status": "formal"},
    "confidence": 95,
    "status": "active"
  },
  {
    "domain": "production",
    "topic": "包装量、入库量、总产量不能混用",
    "knowledge_type": "metric",
    "source_type": "fact_map",
    "source_ref": "docs/mes-data-hub-hermes-fact-map-2026-06-19.md",
    "content": "包装、入库、投料、车间最终日报产量是不同指标。Hermes 回答时必须说明采用的是哪个指标，不能把 MES 过程包装量直接当车间总产量。",
    "structured_payload": {"layer": "C", "unit_type": "metric", "status": "formal"},
    "confidence": 90,
    "status": "active"
  },
  {
    "domain": "energy",
    "topic": "吨电耗解释口径",
    "knowledge_type": "metric",
    "source_type": "spec",
    "source_ref": "docs/superpowers/specs/2026-06-25-hermes-knowledge-and-datahub-diet-design.md",
    "content": "吨电耗必须同时说明电量分子和产量分母。分母可能是车间最终产量、包装量或入库量，口径不同会导致判断不同。",
    "structured_payload": {"layer": "A", "unit_type": "metric", "status": "formal"},
    "confidence": 90,
    "status": "active"
  },
  {
    "domain": "process_quality",
    "topic": "冷轧 1650/1850/2050 异常分析",
    "knowledge_type": "case",
    "source_type": "factory_brain_spec",
    "source_ref": "docs/superpowers/specs/2026-06-25-hermes-factory-brain-upgrade-design.md",
    "content": "冷轧异常分析要同时看当前事实、冷轧工艺知识、历史案例、DingTalk 异常说明和来源冲突，不能只看一个产量数字。",
    "structured_payload": {"layer": "F", "unit_type": "case", "status": "candidate"},
    "confidence": 80,
    "status": "candidate"
  },
  {
    "domain": "datahub_diet",
    "topic": "数据中枢减法顺序",
    "knowledge_type": "rule",
    "source_type": "spec",
    "source_ref": "docs/superpowers/specs/2026-06-25-hermes-knowledge-and-datahub-diet-design.md",
    "content": "数据中枢减法顺序是事实来源地图、知识种子、减法审计、冻结观察、候选删除。不能在没有来源地图时直接删表或删页面。",
    "structured_payload": {"layer": "C", "unit_type": "rule", "status": "formal"},
    "confidence": 95,
    "status": "active"
  },
  {
    "domain": "daily_report",
    "topic": "日报输出顺序",
    "knowledge_type": "output_format",
    "source_type": "output_skill",
    "source_ref": "D:/输出skill",
    "content": "正式日报先写总产量、同比昨日变化和月累计，再写各车间明细、在制料、能耗、入库合同投料、成品率和成本核算。",
    "structured_payload": {"layer": "E", "unit_type": "output_format", "status": "formal"},
    "confidence": 90,
    "status": "active"
  },
  {
    "domain": "operations",
    "topic": "经营问答必须跨域",
    "knowledge_type": "rule",
    "source_type": "factory_brain_spec",
    "source_ref": "docs/superpowers/specs/2026-06-25-hermes-factory-brain-upgrade-design.md",
    "content": "经营问答不能只看产量。必须同时看生产、库存、发货、合同、余合同、成品率和成本，缺字段时要说明缺口。",
    "structured_payload": {"layer": "B", "unit_type": "rule", "status": "formal"},
    "confidence": 90,
    "status": "active"
  },
  {
    "domain": "data_source",
    "topic": "DingTalk 四条件采样",
    "knowledge_type": "rule",
    "source_type": "factory_brain_spec",
    "source_ref": "docs/superpowers/specs/2026-06-25-hermes-factory-brain-upgrade-design.md",
    "content": "DingTalk 证据必须同时满足授权群、专项责任人、内容类型和时间范围，才能进入高优先级事实采样。",
    "structured_payload": {"layer": "D", "unit_type": "rule", "status": "formal"},
    "confidence": 95,
    "status": "active"
  },
  {
    "domain": "datahub_diet",
    "topic": "不得删除的证据链",
    "knowledge_type": "rule",
    "source_type": "spec",
    "source_ref": "docs/superpowers/specs/2026-06-25-hermes-knowledge-and-datahub-diet-design.md",
    "content": "MES/WMS 投影、DingTalk 证据、审计日志、DailyFactBundle 快照、历史日报、root_owner 修正、LangGraph checkpoint 和 Codex 施工记录属于保护链路，不进入直接删除范围。",
    "structured_payload": {"layer": "C", "unit_type": "rule", "status": "formal"},
    "confidence": 95,
    "status": "active"
  },
  {
    "domain": "production",
    "topic": "业务日窗口",
    "knowledge_type": "rule",
    "source_type": "fact_map",
    "source_ref": "docs/mes-data-hub-hermes-fact-map-2026-06-19.md",
    "content": "普通生产车间以 07:50 到次日 07:50 为业务日窗口，铸二、铸三、热轧以 10:00 到次日 10:00 为窗口，内勤每日一录按 09:30 归属。",
    "structured_payload": {"layer": "C", "unit_type": "rule", "status": "formal"},
    "confidence": 90,
    "status": "active"
  },
  {
    "domain": "data_source",
    "topic": "MES/WMS 只读边界",
    "knowledge_type": "rule",
    "source_type": "fact_map",
    "source_ref": "docs/mes-data-hub-hermes-fact-map-2026-06-19.md",
    "content": "MES/WMS 是外部数据源，Hermes 可以高权限只读查询和审计，但不能写 MES/WMS 原库。",
    "structured_payload": {"layer": "D", "unit_type": "rule", "status": "formal"},
    "confidence": 95,
    "status": "active"
  },
  {
    "domain": "datahub_diet",
    "topic": "旧入口冻结优先",
    "knowledge_type": "rule",
    "source_type": "system_understanding",
    "source_ref": "docs/system-understanding-database-api-route-map-2026-06-14.md",
    "content": "前端存在大量旧入口重定向，清理时不能只看文件是否旧。旧二维码、旧收藏链接和兼容跳转都要先冻结观察，再决定是否删除。",
    "structured_payload": {"layer": "C", "unit_type": "rule", "status": "formal"},
    "confidence": 85,
    "status": "active"
  },
  {
    "domain": "cost",
    "topic": "成本核算基础",
    "knowledge_type": "metric",
    "source_type": "output_skill",
    "source_ref": "D:/输出skill",
    "content": "成本核算通常按已核电费和气费合计，再按入库成品吨数折算元/吨。缺电费、气费或吨数时不能输出最终吨成本。",
    "structured_payload": {"layer": "E", "unit_type": "metric", "status": "formal"},
    "confidence": 88,
    "status": "active"
  },
  {
    "domain": "operation_period",
    "topic": "月度和年度经营分析",
    "knowledge_type": "rule",
    "source_type": "phase2_fact_bundle",
    "source_ref": "docs/superpowers/plans/2026-06-22-hermes-daily-fact-bundle-phase2-plan.md",
    "content": "月度和年度经营分析应从历史日报和 OperationPeriodSnapshot 追溯，不应直接从自由文本猜累计。",
    "structured_payload": {"layer": "E", "unit_type": "rule", "status": "formal"},
    "confidence": 90,
    "status": "active"
  }
]
```

- [ ] **Step 4: Implement seed service**

Create `backend/app/services/hermes_knowledge_seed_service.py`:

```python
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
```

- [ ] **Step 5: Add import script**

Create `backend/scripts/hermes_knowledge_seed_import.py`:

```python
from __future__ import annotations

from app.database import SessionLocal
from app.services.hermes_knowledge_seed_service import import_knowledge_seed


def main() -> None:
    db = SessionLocal()
    try:
        result = import_knowledge_seed(db)
        db.commit()
        print(f"imported {result['inserted_or_updated']} Hermes knowledge seed entries")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests**

Run:

```powershell
python -m pytest backend/tests/test_hermes_knowledge_seed_service.py -q
```

Expected: `2 passed`.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/hermes/knowledge_seeds/phase2_factory_brain.json backend/app/services/hermes_knowledge_seed_service.py backend/scripts/hermes_knowledge_seed_import.py backend/tests/test_hermes_knowledge_seed_service.py
git commit -m "feat: seed Hermes professional knowledge"
```

---

## Task 4: Add Source Map as a Hermes Tool

**Files:**
- Modify: `backend/app/services/hermes_langchain_tools.py`
- Modify: `backend/tests/test_hermes_langchain_tools.py`

- [ ] **Step 1: Update the whitelist test first**

Modify `backend/tests/test_hermes_langchain_tools.py`:

```python
def test_tool_registry_exposes_only_allowed_tools() -> None:
    adapters = HermesToolAdapters(
        hub_query=_fake_tool,
        mes_wms_read=_fake_tool,
        dingtalk_evidence=_fake_tool,
        rag_route=_fake_tool,
        history_report=_fake_tool,
        output_skill_alignment=_fake_tool,
        long_term_rules=_fake_tool,
        codex_construction=_fake_tool,
        source_map=_fake_tool,
    )
    registry = build_tool_registry(adapters)

    assert set(registry.keys()) == {
        'hub_query',
        'mes_wms_read',
        'dingtalk_evidence',
        'rag_route',
        'history_report',
        'output_skill_alignment',
        'long_term_rules',
        'codex_construction',
        'source_map',
    }
    assert require_tool('source_map', registry)(metric_key='total_output_daily')['status'] == 'ok'
```

Append:

```python
def test_source_map_tool_explains_metric_source() -> None:
    registry = build_tool_registry(build_production_tool_adapters(_db()))

    result = registry['source_map'](metric_key='total_output_daily')

    assert result['status'] == 'ok'
    assert result['source'] == 'fact_source_map'
    assert result['facts']['metric_key'] == 'total_output_daily'
    assert '车间总产量' in result['facts']['summary']
```

- [ ] **Step 2: Run the updated tests and verify red**

Run:

```powershell
python -m pytest backend/tests/test_hermes_langchain_tools.py::test_source_map_tool_explains_metric_source -q
```

Expected: fails because `source_map` is not registered.

- [ ] **Step 3: Add the tool**

Modify `backend/app/services/hermes_langchain_tools.py`:

```python
from app.services.hermes_fact_source_map_service import find_fact_source, source_summary_for_metric
```

Add the field:

```python
@dataclass(frozen=True, slots=True)
class HermesToolAdapters:
    hub_query: ToolCallable
    mes_wms_read: ToolCallable
    dingtalk_evidence: ToolCallable
    rag_route: ToolCallable
    history_report: ToolCallable
    output_skill_alignment: ToolCallable
    long_term_rules: ToolCallable
    codex_construction: ToolCallable
    source_map: ToolCallable
```

Add it to `build_tool_registry()`:

```python
'source_map': adapters.source_map,
```

Add it to `build_production_tool_adapters()`:

```python
source_map=_source_map_tool,
```

Add the function:

```python
def _source_map_tool(**kwargs: object) -> dict[str, object]:
    try:
        metric_key = str(kwargs.get('metric_key') or '').strip()
        item = find_fact_source(metric_key)
        return {
            'status': 'ok',
            'source': 'fact_source_map',
            'request': _request_payload(kwargs),
            'facts': {**item, 'summary': source_summary_for_metric(metric_key)},
        }
    except Exception as exc:
        return _unavailable('fact_source_map', kwargs, exc)
```

- [ ] **Step 4: Run tool tests**

Run:

```powershell
python -m pytest backend/tests/test_hermes_langchain_tools.py -q
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/hermes_langchain_tools.py backend/tests/test_hermes_langchain_tools.py
git commit -m "feat: expose Hermes fact source map tool"
```

---

## Task 5: Strengthen Factory Brain Acceptance for Source-Backed Answers

**Files:**
- Modify: `backend/app/services/hermes_factory_brain_harness.py`
- Modify: `backend/tests/test_hermes_factory_brain_acceptance.py`
- Create: `backend/tests/test_hermes_phase2_source_map_acceptance.py`

- [ ] **Step 1: Add failing acceptance tests**

Create `backend/tests/test_hermes_phase2_source_map_acceptance.py`:

```python
from __future__ import annotations

from app.services.hermes_factory_brain_harness import evaluate_factory_brain_response


def test_source_backed_production_answer_requires_source_map_tool() -> None:
    result = evaluate_factory_brain_response(
        scenario='source_backed_answer',
        response_text='结论：今天产量已出。数据来源：DailyFactBundle 和 Hermes 事实来源地图。trace_id：abc',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok'},
            {'tool': 'source_map', 'status': 'ok', 'facts': {'metric_key': 'total_output_daily'}},
        ],
    )

    assert result.passed is True
    assert result.missing == []


def test_source_backed_answer_fails_without_trace_id() -> None:
    result = evaluate_factory_brain_response(
        scenario='source_backed_answer',
        response_text='结论：今天产量已出。数据来源：DailyFactBundle。',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok'},
            {'tool': 'source_map', 'status': 'ok'},
        ],
    )

    assert result.passed is False
    assert 'trace_id' in result.missing
```

- [ ] **Step 2: Run tests and verify red**

Run:

```powershell
python -m pytest backend/tests/test_hermes_phase2_source_map_acceptance.py -q
```

Expected: fails because `source_backed_answer` checks do not exist.

- [ ] **Step 3: Add harness checks**

Modify `backend/app/services/hermes_factory_brain_harness.py`.

In `_checks_for_scenario()` add:

```python
if scenario == 'source_backed_answer':
    return ['conclusion', 'sources', 'source_map', 'trace_id']
```

In `_check()` add:

```python
if name == 'conclusion':
    return '结论' in response_text
if name == 'source_map':
    return any(item.get('tool') == 'source_map' and item.get('status') == 'ok' for item in tool_trace)
if name == 'trace_id':
    return 'trace_id' in response_text or 'trace' in response_text
```

- [ ] **Step 4: Run acceptance tests**

Run:

```powershell
python -m pytest backend/tests/test_hermes_factory_brain_acceptance.py backend/tests/test_hermes_phase2_source_map_acceptance.py -q
```

Expected: tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/hermes_factory_brain_harness.py backend/tests/test_hermes_factory_brain_acceptance.py backend/tests/test_hermes_phase2_source_map_acceptance.py
git commit -m "test: require source-backed Hermes answers"
```

---

## Task 6: Add Non-Destructive Data Hub Diet Audit

**Files:**
- Create: `backend/app/services/hermes_datahub_diet_audit_service.py`
- Create: `backend/scripts/hermes_datahub_diet_audit.py`
- Create: `backend/tests/test_hermes_datahub_diet_audit_service.py`
- Create: `docs/datahub-deprecation-register.md`
- Create: `docs/superpowers/reports/datahub-diet-audit-2026-06-25.md`

- [ ] **Step 1: Write failing audit tests**

Create `backend/tests/test_hermes_datahub_diet_audit_service.py`:

```python
from __future__ import annotations

from app.services.hermes_datahub_diet_audit_service import classify_audit_item, render_diet_audit_report


def test_diet_audit_protects_evidence_paths() -> None:
    item = classify_audit_item("backend/app/models/agent_communication.py")

    assert item["classification"] == "protect"
    assert "证据" in item["reason"] or "审计" in item["reason"]


def test_diet_audit_freezes_legacy_routes_before_delete() -> None:
    item = classify_audit_item("frontend/src/reference-command/pages/README.md")

    assert item["classification"] in {"freeze", "candidate_delete"}
    assert item["action"] != "delete_now"


def test_diet_audit_report_contains_no_delete_now() -> None:
    report = render_diet_audit_report([
        "backend/app/models/agent_communication.py",
        "frontend/src/reference-command/pages/README.md",
    ])

    assert "delete_now" not in report
    assert "protect" in report
    assert "freeze" in report or "candidate_delete" in report
```

- [ ] **Step 2: Run tests and verify red**

Run:

```powershell
python -m pytest backend/tests/test_hermes_datahub_diet_audit_service.py -q
```

Expected: fails because the audit service does not exist.

- [ ] **Step 3: Implement audit service**

Create `backend/app/services/hermes_datahub_diet_audit_service.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Iterable

PROTECT_MARKERS = (
    "agent_communication",
    "daily_fact_bundle",
    "daily_report_history",
    "operation_period",
    "mes_sync",
    "mes_",
    "rag",
    "hermes_",
    "audit",
)

FREEZE_MARKERS = (
    "reference-command",
    "ui-reference",
    "/review/",
    "/mobile/",
    "legacy",
)

MERGE_MARKERS = (
    "daily_overview_builder",
    "dashboard_builder",
    "template_daily_report",
)


def classify_audit_item(path: str) -> dict[str, str]:
    clean = str(path).replace("\\", "/")
    lowered = clean.lower()
    if any(marker in lowered for marker in PROTECT_MARKERS):
        return {
            "path": clean,
            "classification": "protect",
            "action": "keep",
            "reason": "涉及 Hermes、MES/WMS 投影、RAG、证据或审计链路，不能删。",
        }
    if any(marker in lowered for marker in MERGE_MARKERS):
        return {
            "path": clean,
            "classification": "merge",
            "action": "merge_after_source_map",
            "reason": "属于报表加工层，可在 DailyFactBundle 稳定后逐步合并。",
        }
    if any(marker in lowered for marker in FREEZE_MARKERS):
        return {
            "path": clean,
            "classification": "freeze",
            "action": "freeze_and_observe",
            "reason": "疑似旧入口或参考资产，先冻结观察，不直接删除。",
        }
    return {
        "path": clean,
        "classification": "review",
        "action": "manual_review",
        "reason": "需要结合引用、路由、测试和生产访问再判断。",
    }


def render_diet_audit_report(paths: Iterable[str]) -> str:
    items = [classify_audit_item(path) for path in paths]
    lines = [
        "# 数据中枢减法瘦身审计报告",
        "",
        "日期：2026-06-25",
        "",
        "本报告只做分类和建议，不删除任何文件、表或生产数据。",
        "",
        "| 分类 | 动作 | 路径 | 原因 |",
        "|---|---|---|---|",
    ]
    for item in items:
        lines.append(f"| {item['classification']} | {item['action']} | `{item['path']}` | {item['reason']} |")
    lines.append("")
    lines.append("硬规则：本阶段没有 `delete_now`。所有删除必须另开计划，并提供回滚办法。")
    return "\n".join(lines)


def candidate_paths(repo_root: str | Path) -> list[str]:
    root = Path(repo_root)
    patterns = [
        "backend/app/services/*.py",
        "backend/app/routers/*.py",
        "frontend/src/views/**/*.vue",
        "frontend/src/reference-command/**/*",
        "docs/**/*.md",
    ]
    result: list[str] = []
    for pattern in patterns:
        result.extend(str(path.relative_to(root)) for path in root.glob(pattern) if path.is_file())
    return sorted(set(result))
```

- [ ] **Step 4: Add audit script**

Create `backend/scripts/hermes_datahub_diet_audit.py`:

```python
from __future__ import annotations

from pathlib import Path

from app.services.hermes_datahub_diet_audit_service import candidate_paths, render_diet_audit_report

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = REPO_ROOT / "docs" / "superpowers" / "reports" / "datahub-diet-audit-2026-06-25.md"


def main() -> None:
    report = render_diet_audit_report(candidate_paths(REPO_ROOT))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(report, encoding="utf-8")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Add deprecation register**

Create `docs/datahub-deprecation-register.md`:

```markdown
# 数据中枢冻结与候选删除登记表

本文件记录可以冻结、合并或进入候选删除的对象。

硬规则：

- 不直接删除生产表。
- 不删除原始证据。
- 不删除审计日志。
- 不删除 Hermes、DingTalk、DailyFactBundle、MES/WMS 投影依赖链。
- 候选删除必须先观察 7 到 14 天。

| 对象 | 分类 | 当前动作 | 观察期 | 回滚方式 |
|---|---|---|---|---|
| `frontend/src/reference-command/pages/*` | freeze | 仅作为历史参考资产 | 14 天 | 保留 git 文件，不挂载生产路由 |
| `/review/*` 旧入口 | freeze | 保留重定向 | 14 天 | 恢复当前路由配置 |
| `/mobile/*` 旧入口 | freeze | 保留到 `/entry/*` 的兼容跳转 | 14 天 | 恢复当前路由配置 |
```

- [ ] **Step 6: Run audit script**

Run:

```powershell
$env:PYTHONPATH="backend"
python backend/scripts/hermes_datahub_diet_audit.py
```

Expected: writes `docs/superpowers/reports/datahub-diet-audit-2026-06-25.md`.

- [ ] **Step 7: Run tests**

Run:

```powershell
python -m pytest backend/tests/test_hermes_datahub_diet_audit_service.py -q
```

Expected: tests pass.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/services/hermes_datahub_diet_audit_service.py backend/scripts/hermes_datahub_diet_audit.py backend/tests/test_hermes_datahub_diet_audit_service.py docs/datahub-deprecation-register.md docs/superpowers/reports/datahub-diet-audit-2026-06-25.md
git commit -m "chore: add data hub diet audit"
```

---

## Task 7: Run Knowledge and Source QA

**Files:**
- Create: `docs/superpowers/reports/hermes-phase2-knowledge-source-map-qa-2026-06-25.md`

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest `
  backend/tests/test_hermes_fact_source_map_service.py `
  backend/tests/test_hermes_knowledge_seed_service.py `
  backend/tests/test_hermes_langchain_tools.py `
  backend/tests/test_hermes_phase2_source_map_acceptance.py `
  backend/tests/test_hermes_professional_knowledge_service.py `
  -q --tb=short
```

Expected: all selected tests pass.

- [ ] **Step 2: Run high-risk Hermes regressions**

Run:

```powershell
python -m pytest `
  backend/tests/test_hermes_factory_brain_acceptance.py `
  backend/tests/test_hermes_factory_brain_orchestrator.py `
  backend/tests/test_hermes_rag_router_service.py `
  backend/tests/test_dingtalk_factory_brain_inbound.py `
  backend/tests/test_rag_routes.py `
  -q --tb=short
```

Expected: all selected tests pass.

- [ ] **Step 3: Run compile check**

Run:

```powershell
python -m compileall backend/app/services backend/scripts
```

Expected: exits `0`.

- [ ] **Step 4: Run diff check**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 5: Create QA report**

Create `docs/superpowers/reports/hermes-phase2-knowledge-source-map-qa-2026-06-25.md`:

```markdown
# Hermes Phase-2 Knowledge and Source Map QA

日期：2026-06-25

## 状态

ready

## 已验证

- 事实来源地图可加载。
- 事实来源地图不含敏感字段。
- Hermes source_map 工具可解释核心指标来源。
- 专业知识种子可导入。
- RAG 仍优先使用专业知识库。
- 数据中枢减法审计不执行删除。
- Hermes 来源型回答必须包含来源和 trace_id。

## 关键命令

- `python -m pytest backend/tests/test_hermes_fact_source_map_service.py backend/tests/test_hermes_knowledge_seed_service.py backend/tests/test_hermes_langchain_tools.py backend/tests/test_hermes_phase2_source_map_acceptance.py backend/tests/test_hermes_professional_knowledge_service.py -q --tb=short`: pass
- `python -m pytest backend/tests/test_hermes_factory_brain_acceptance.py backend/tests/test_hermes_factory_brain_orchestrator.py backend/tests/test_hermes_rag_router_service.py backend/tests/test_dingtalk_factory_brain_inbound.py backend/tests/test_rag_routes.py -q --tb=short`: pass
- `python -m compileall backend/app/services backend/scripts`: pass
- `git diff --check`: pass

## 结论

本阶段可以进入生产灰度验证，但只允许导入知识、增加来源解释和生成减法审计报告。不得直接删除生产表、生产路由或证据链。
```

If any command fails, set `状态` to `blocked` and record the failing command and error summary.

- [ ] **Step 6: Commit**

```powershell
git add docs/superpowers/reports/hermes-phase2-knowledge-source-map-qa-2026-06-25.md
git commit -m "docs: record Hermes phase2 knowledge source QA"
```

---

## Task 8: Production Grey Verification

**Files:**
- Modify only if needed: `docs/deploy/current-state.md`

- [ ] **Step 1: Keep runtime switches conservative**

Confirm production does not require immediate wide rollout:

```powershell
git grep -n "HERMES_FACTORY_BRAIN_ENABLED" backend/.env.example backend/app/config.py
```

Expected: feature flag exists and defaults remain conservative.

- [ ] **Step 2: Import knowledge seed in staging or production only after backup**

Run only after DB backup or in staging:

```powershell
$env:PYTHONPATH="backend"
python backend/scripts/hermes_knowledge_seed_import.py
```

Expected:

```text
imported 15 Hermes knowledge seed entries
```

- [ ] **Step 3: Run a local source-map smoke**

Run:

```powershell
$env:PYTHONPATH="backend"
python backend/scripts/hermes_fact_source_map_export.py
```

Expected: `docs/hermes/fact-source-map.md` regenerates successfully.

- [ ] **Step 4: Test 20 natural-language prompts**

Use Hermes DingTalk or API smoke. Record pass/fail for these prompts:

```text
今天产量出来了吗？
今天这个数从哪来的？
生成昨天日报草稿。
6月19日正式日报和历史成品能对齐吗？
2050 今天吨电耗为什么高？
今天生产和发货会不会影响合同交付？
本月经营情况怎么样？
今年累计产量和成本趋势怎么样？
哪个车间今天异常最大？
这个钉钉文件能作为正式数据吗？
这个数能信吗？
如果 MES 和钉钉冲突，采用谁？
日报里的成品率怎么算？
入库和包装为什么不是一个数？
数据中枢哪些旧页面可以冻结？
哪些表绝对不能删？
哪些文档已经过期？
把今天日报按老板看的版本发我。
把这条规则记住，以后日报先看责任人文件。
现在你缺什么证据？
```

Expected:

- At least 16 of 20 produce useful answers.
- Every fact answer names a source.
- Every uncertain answer names missing evidence.
- No answer exposes secrets.
- No answer claims deletion was performed.

- [ ] **Step 5: Update deployment state only after production smoke**

Append to `docs/deploy/current-state.md` only after production smoke passes:

```markdown

## 2026-06-25 Hermes Phase-2 Knowledge and Source Map Grey

- 已导入 Hermes Phase-2 知识种子。
- 已生成事实来源地图。
- 已生成数据中枢减法审计报告。
- 已完成 20 条自然语言灰度问题测试。
- 本阶段没有删除生产表、生产路由或证据链。
```

- [ ] **Step 6: Commit deployment note**

Only run if Step 5 changed the file:

```powershell
git add docs/deploy/current-state.md
git commit -m "docs: record Hermes phase2 grey verification"
```

---

## CEO / Eng / Design / DevEx Review Hardening

### CEO Review

Decision: selective expansion.

The highest-leverage move is not another dashboard or another command. It is source-backed intelligence. Hermes becomes more valuable when every answer can say:

```text
我采用了哪个数，为什么采用它，另一个数为什么没采用。
```

Accepted scope:

- Fact source map.
- Knowledge seed import.
- Data hub reduction audit.
- Source-backed answer harness.
- Production grey verification.

Rejected scope:

- Immediate destructive cleanup.
- Full frontend redesign.
- Replacing the factory-brain lane.

### Eng Review

Decision: full review.

The main technical risk is breaking a chain Hermes already depends on. The plan controls that risk by:

- Reusing existing services.
- Adding JSON seed files instead of schema changes.
- Adding tests before tool registration changes.
- Keeping all deletion work as audit-only.
- Running focused Hermes regressions before completion.

Blocking engineering rule:

```text
No production deletion in this plan.
```

### Design Review

Decision: no new UI design scope.

Design quality here means conversation clarity:

- Conclusion first.
- Source visible.
- Conflict visible.
- Missing evidence visible.
- Suggested action visible.
- trace_id visible.

No landing page, no decorative dashboard, no new card-heavy UI.

### DevEx Review

Decision: polish operator workflow.

The operator should be able to run:

```powershell
python backend/scripts/hermes_fact_source_map_export.py
python backend/scripts/hermes_knowledge_seed_import.py
python backend/scripts/hermes_datahub_diet_audit.py
```

and immediately see what was generated. Debugging target:

```text
10 分钟内知道某个指标从哪里来。
2 分钟内确认某个文件是否只是审计候选，还是可以删。
```

## Self-Review

### Spec Coverage

- Knowledge base enrichment: Task 3.
- Fact source map: Task 1 and Task 2.
- Hermes source-backed answers: Task 4 and Task 5.
- Data hub reduction without dangerous deletion: Task 6.
- QA and grey verification: Task 7 and Task 8.
- DingTalk as high-priority supplemental data: knowledge seed entries and source map entries.
- Monthly and annual operating context: source map entries and knowledge seed entries.
- Professional RAG boundary: knowledge seed entries and RAG regression tests.

### Placeholder Scan

This plan avoids open-ended implementation steps. Every task names files, test commands, expected results, and commit boundaries.

### Type Consistency

Stable names used throughout:

- `load_fact_source_map`
- `find_fact_source`
- `source_summary_for_metric`
- `import_knowledge_seed`
- `render_diet_audit_report`
- `classify_audit_item`
- `source_map`

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope and leverage | 1 offline merged pass | CLEAR | Chose source-backed intelligence and audit-first reduction over building more surfaces. |
| Codex Review | `/codex review` | Independent second opinion | 0 | NOT RUN | Not required before writing the plan; run after implementation if diff is large. |
| Eng Review | `/plan-eng-review` | Architecture and tests | 1 offline merged pass | CLEAR | Reuses existing Hermes services, avoids migrations, protects evidence paths, and adds focused tests. |
| Design Review | `/plan-design-review` | Conversation and operator clarity | 1 offline merged pass | CLEAR | No new UI scope; answer design requires conclusion, sources, conflicts, missing evidence, action, and trace. |
| DX Review | `/plan-devex-review` | Operator execution quality | 1 offline merged pass | CLEAR | Adds three direct scripts, focused test commands, report files, and conservative grey verification. |

- **UNRESOLVED:** 0
- **VERDICT:** CEO + ENG + DESIGN + DX CLEARED. Ready for subagent-driven implementation. The hard rule for execution is simple: enrich knowledge and produce audit evidence first; do not delete production data or active routes in this phase.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-25-hermes-knowledge-and-datahub-diet-plan.md`.

Recommended execution:

```text
Use superpowers:subagent-driven-development.
Run one subagent per task.
Review after each task.
Do not continue to deletion work from this plan.
```
