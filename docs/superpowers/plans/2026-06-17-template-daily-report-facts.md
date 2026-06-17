# Template Daily Report Facts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the daily-report facts layer so the system can generate the previous business day's Chinese text report at 7:30 using the same template and口径 as `D:\输出skill`.

**Architecture:** Keep the existing scheduler and `template_daily_report.render_template_daily_report()` as the final renderer. Add a deterministic facts collection layer in front of it: MES, manual owner fill, contract, energy, yield, WIP, recovery, overhaul, and yesterday-final-report comparison values are normalized into the existing `REQUIRED_FIELDS` contract before rendering. Do not let the language model invent numbers; every rendered number must have a source and validation result.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, Vue, Vitest, existing `WorkOrderEntry` / `DailyReport` / MES models, production SQL Server adapter through existing backend settings.

---

## Scope

This plan covers only the 7:30 text daily report target:

- Generate the previous completed business day.
- Match the paragraph order, punctuation, field order, unit display, and `比昨日` wording of `D:\输出skill\YYYY-M-D_日报正文.txt`.
- Use `D:\输出skill` as the validation target, not as the daily runtime data source.
- Preserve `/entry`, `/manage`, DingTalk H5, existing report scheduler, permissions, audit, and MES sync.

This plan does not cover RAG, DingTalk chat Agent, or frontend visual redesign except where needed to fill or preview the report facts.

## Core Rule

The system must not ask the renderer to "figure out" data. The renderer only prints values. The facts layer must decide:

- which source wins,
- which unit conversion applies,
- which yesterday comparison base applies,
- whether a field is missing,
- whether the report can be generated.

## Data Source Priority

Use this priority when two sources disagree:

1. Confirmed structured daily workbook / confirmed owner daily fill in system.
2. MES data only for fields whose MES口径 has been explicitly mapped.
3. Contract source for contract fields.
4. Energy / gas source for energy fields.
5. Previous final report text for `比昨日` display-value comparison.
6. Screenshot or free-text supplement only after it is converted into a structured owner field.

Do not let screenshots or OCR directly drive production output unless converted and confirmed.

## Target Field Contract

The existing `backend/app/services/report/template_daily_report.py::REQUIRED_FIELDS` remains the source of truth. Fields are grouped as:

- `opening`: total output, outsourced output, daily delta, monthly total.
- `workshop_output`: cast rolling, foundry, hot rolling, 1650, 1850, 2050, rolling total, anneal, straightening, finishing, shearing, coating.
- `manual_supplement`: active cast-roll lines, recovery daily/month, overhaul roller grind daily/month.
- `wip`: total WIP and WIP split.
- `energy`: electricity, gas, unit consumption.
- `contract_input`: inbound, consignment, contract, cold-roll input, plate input, remaining contract.
- `yield`: daily, hot-roll, monthly and category yield rates.
- `cost`: electricity cost, gas cost, total cost, basis weight, cost per ton.

## Files

- Modify: `backend/app/services/report/template_daily_report.py`
- Modify: `backend/app/tasks/daily_report.py`
- Create: `backend/app/services/report/template_daily_fact_sources.py`
- Create: `backend/app/services/report/template_daily_field_contract.py`
- Create: `backend/app/services/report/output_skill_report_parser.py`
- Create: `backend/app/services/report/output_skill_reconciliation.py`
- Modify: `backend/app/services/report/daily_overview_builder.py`
- Modify: `backend/app/models/production.py` only if existing `WorkOrderEntry.extra_payload` cannot hold required owner facts cleanly.
- Modify: `backend/app/routers/reports.py` or existing report router for preview endpoint.
- Create or modify: `backend/tests/test_template_daily_fact_sources.py`
- Modify: `backend/tests/test_template_daily_report.py`
- Create: `backend/tests/test_output_skill_report_parser.py`
- Create: `backend/tests/test_output_skill_reconciliation.py`
- Create: `backend/tests/fixtures/output_skill_daily_reports/2026-6-16_日报正文.txt`
- Create: `backend/tests/fixtures/output_skill_daily_reports/2026-6-16_核对记录.txt`
- Modify: frontend only if a required owner-daily fill/preview UI is missing.

## Done Definition

- 2026-06-10 through 2026-06-16 can be generated in dry-run mode.
- For each date, generation returns either `ready` with text or `blocked` with exact missing fields and source categories.
- After required manual facts are seeded or filled, 2026-06-16 exact text matches `D:\输出skill\2026-6-16_日报正文.txt`.
- Regression comparison reports field-level match rate and first differences.
- Scheduler still runs `daily_report` at `hour=7, minute=30`.
- No secrets, passwords, webhook URLs, or database connection strings are committed or printed.

---

### Task 1: Freeze The Template Field Contract

**Files:**
- Create: `backend/app/services/report/template_daily_field_contract.py`
- Modify: `backend/app/services/report/template_daily_report.py`
- Test: `backend/tests/test_template_daily_report.py`

- [ ] **Step 1: Write the field contract module**

Create `template_daily_field_contract.py` with groups, source expectations, display precision, and criticality.

```python
FIELD_GROUPS = {
    "opening": (
        "total_output_daily",
        "outsourced_daily",
        "total_output_delta",
        "total_output_month",
        "outsourced_month",
    ),
    "manual_supplement": (
        "cast_roll_active_lines",
        "recovery_daily",
        "recovery_month",
        "roller_grind_daily",
        "roller_grind_month",
    ),
}

FIELD_SOURCE_POLICY = {
    "hot_roll_daily": ("owner_daily",),
    "foundry_daily": ("owner_daily",),
    "cast_2_daily": ("owner_daily",),
    "cast_3_daily": ("owner_daily",),
    "cold_1650_daily": ("mes_workshop_process_records",),
    "daily_contract_weight": ("contract_projection", "owner_daily"),
}
```

- [ ] **Step 2: Add a test that every required field is classified**

```python
def test_all_template_required_fields_have_contract_metadata():
    from app.services.report import template_daily_report
    from app.services.report.template_daily_field_contract import field_group

    missing = [key for key in template_daily_report.REQUIRED_FIELDS if field_group(key) == "unclassified"]

    assert missing == []
```

- [ ] **Step 3: Run the failing test**

Run: `cd backend && python -m pytest tests/test_template_daily_report.py::test_all_template_required_fields_have_contract_metadata -q`

Expected: FAIL until all fields are mapped.

- [ ] **Step 4: Fill the contract metadata minimally**

Add every `REQUIRED_FIELDS` key into one clear group. Do not add new template fields.

- [ ] **Step 5: Run the test again**

Run: `cd backend && python -m pytest tests/test_template_daily_report.py::test_all_template_required_fields_have_contract_metadata -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/report/template_daily_field_contract.py backend/tests/test_template_daily_report.py
git commit -m "test: classify template daily report fields"
```

---

### Task 2: Parse OutputSkill Reports As Validation Targets

**Files:**
- Create: `backend/app/services/report/output_skill_report_parser.py`
- Create: `backend/tests/test_output_skill_report_parser.py`
- Create: `backend/tests/fixtures/output_skill_daily_reports/2026-6-16_日报正文.txt`

- [ ] **Step 1: Add a small fixture**

Copy only the 2026-06-16 final daily report text into `backend/tests/fixtures/output_skill_daily_reports/2026-6-16_日报正文.txt`.

Do not copy secrets or database configuration.

- [ ] **Step 2: Write parser tests for key values**

```python
def test_parse_output_skill_daily_report_20260616_key_fields():
    text = fixture_text("2026-6-16_日报正文.txt")
    parsed = parse_output_skill_daily_report(text)

    assert parsed["report_date"] == date(2026, 6, 16)
    assert parsed["total_output_daily"] == 328
    assert parsed["outsourced_daily"] == 0
    assert parsed["cold_1650_daily"] == 144
    assert parsed["cold_1850_daily"] == 33
    assert parsed["cold_2050_daily"] == 96
    assert parsed["rolling_daily"] == 272
    assert parsed["daily_yield_rate"] == 84.86
    assert parsed["cost_per_ton"] == 1044
```

- [ ] **Step 3: Run the parser test and verify it fails**

Run: `cd backend && python -m pytest tests/test_output_skill_report_parser.py -q`

Expected: FAIL because parser is not implemented.

- [ ] **Step 4: Implement deterministic parser**

Use regex anchored to stable Chinese labels such as:

- `车间总产量日合计`
- `1650车间日产量`
- `当天在制料`
- `全厂高压总用电量`
- `总余合同量`
- `日成品率`
- `成本核算方面`

Do not use AI or fuzzy guessing.

- [ ] **Step 5: Run parser tests**

Run: `cd backend && python -m pytest tests/test_output_skill_report_parser.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/report/output_skill_report_parser.py backend/tests/test_output_skill_report_parser.py backend/tests/fixtures/output_skill_daily_reports/2026-6-16_日报正文.txt
git commit -m "test: parse output skill daily report target"
```

---

### Task 3: Build The Facts Source Layer

**Files:**
- Create: `backend/app/services/report/template_daily_fact_sources.py`
- Modify: `backend/app/services/report/template_daily_report.py`
- Test: `backend/tests/test_template_daily_fact_sources.py`

- [ ] **Step 1: Write source-layer tests for source priority**

```python
def test_owner_daily_wins_for_manual_workshop_outputs(db):
    seed_owner_daily(db, "hot_roll_daily", 275)
    seed_mes_workshop_output(db, "热轧", 999)

    facts = collect_template_daily_facts(db, target_date=date(2026, 6, 16))

    assert facts.values["hot_roll_daily"] == 275
    assert facts.sources["hot_roll_daily"]["source_type"] == "owner_daily"
```

- [ ] **Step 2: Write source-layer tests for MES-only mapped fields**

```python
def test_mes_mapped_workshop_outputs_use_explicit_process_mapping(db):
    seed_mes_process(db, process_code="COLD_1650_OUTPUT", output_tons=143.95)

    facts = collect_template_daily_facts(db, target_date=date(2026, 6, 16))

    assert facts.values["cold_1650_daily"] == 143.95
```

- [ ] **Step 3: Run tests and verify failure**

Run: `cd backend && python -m pytest tests/test_template_daily_fact_sources.py -q`

Expected: FAIL.

- [ ] **Step 4: Implement `collect_template_daily_facts`**

The collector should call small functions:

- `collect_opening_facts`
- `collect_manual_workshop_facts`
- `collect_mes_workshop_facts`
- `collect_wip_facts`
- `collect_energy_facts`
- `collect_contract_facts`
- `collect_yield_facts`
- `collect_cost_facts`
- `collect_yesterday_comparison_facts`

Return a simple object or dict:

```python
{
    "values": {...},
    "sources": {...},
    "missing_fields": [...],
    "conflicts": [...],
}
```

- [ ] **Step 5: Replace direct source copying in `template_daily_report.py`**

Change `build_template_daily_report_facts()` so it delegates to the new source-layer collector, while keeping the same public return shape.

- [ ] **Step 6: Run focused tests**

Run: `cd backend && python -m pytest tests/test_template_daily_fact_sources.py tests/test_template_daily_report.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/report/template_daily_fact_sources.py backend/app/services/report/template_daily_report.py backend/tests/test_template_daily_fact_sources.py
git commit -m "feat: add template daily facts source layer"
```

---

### Task 4: Fix MES Workshop Mapping For Report口径

**Files:**
- Modify: `backend/app/services/report/template_daily_fact_sources.py`
- Modify: `backend/app/services/mes_projection_service.py` only if current projection lacks stable process identifiers.
- Test: `backend/tests/test_template_daily_fact_sources.py`

- [ ] **Step 1: Write failing tests for 1650/1850/2050 split**

```python
def test_rolling_total_is_sum_of_report_mapped_1650_1850_2050(db):
    seed_mes_process(db, process_code="COLD_1650_REPORT_OUTPUT", output_tons=143.95, pass_count=55)
    seed_mes_process(db, process_code="COLD_1850_REPORT_OUTPUT", output_tons=32.68, pass_count=15)
    seed_mes_process(db, process_code="COLD_2050_REPORT_OUTPUT", output_tons=95.72, pass_count=33)

    facts = collect_template_daily_facts(db, target_date=date(2026, 6, 16))

    assert facts.values["rolling_daily"] == 272.35
    assert facts.values["rolling_pass_daily"] == 103
```

- [ ] **Step 2: Run test and verify failure**

Run: `cd backend && python -m pytest tests/test_template_daily_fact_sources.py::test_rolling_total_is_sum_of_report_mapped_1650_1850_2050 -q`

Expected: FAIL with current fuzzy mapping.

- [ ] **Step 3: Implement explicit mapping**

Use a mapping table or constant, for example:

```python
MES_REPORT_PROCESS_MAPPING = {
    "cold_1650_daily": {"workshop_aliases": ("1650",), "process_aliases": ("冷轧",), "exclude_aliases": ()},
    "cold_1850_daily": {"workshop_aliases": ("1850",), "process_aliases": ("冷轧",), "exclude_aliases": ()},
    "cold_2050_daily": {"workshop_aliases": ("2050",), "process_aliases": ("冷轧",), "exclude_aliases": ()},
    "online_anneal_daily": {"process_aliases": ("在线退火",)},
    "straightening_daily": {"process_aliases": ("拉矫",)},
    "finishing_daily": {"process_aliases": ("精整",)},
    "shearing_daily": {"process_aliases": ("剪切",)},
    "coating_daily": {"process_aliases": ("彩涂",)},
}
```

Do not count the same MES row twice.

- [ ] **Step 4: Add duplicate-protection test**

```python
def test_mes_row_cannot_count_into_multiple_report_fields(db):
    seed_mes_process(db, process_name="2050冷轧精整", output_tons=10)

    facts = collect_template_daily_facts(db, target_date=date(2026, 6, 16))

    counted = [
        facts.values.get("cold_2050_daily"),
        facts.values.get("finishing_daily"),
    ]
    assert sum(1 for value in counted if value == 10) <= 1
```

- [ ] **Step 5: Run focused tests**

Run: `cd backend && python -m pytest tests/test_template_daily_fact_sources.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/report/template_daily_fact_sources.py backend/tests/test_template_daily_fact_sources.py
git commit -m "fix: map mes workshop outputs to report口径"
```

---

### Task 5: Add Owner Daily Facts For Manual Fields

**Files:**
- Modify: `backend/app/services/report/template_daily_fact_sources.py`
- Modify: existing owner daily entry schema or config used by `/entry`
- Test: `backend/tests/test_template_daily_fact_sources.py`

- [ ] **Step 1: Define required owner-daily field names**

The owner daily payload must support:

- `cast_roll_active_lines`
- `cast_2_daily`
- `cast_3_daily`
- `foundry_daily`
- `hot_roll_daily`
- `recovery_daily`
- `roller_grind_daily`
- `wip_*`
- `energy_*`
- `gas_*`
- `yield_*`
- `consignment_weight`
- `outsourced_daily`
- `outsourced_month`
- `cold_*_input_daily`
- `medium_plate_input_daily`

- [ ] **Step 2: Add tests for owner payload aliases**

```python
def test_owner_daily_payload_aliases_fill_template_fields(db):
    seed_owner_daily_payload(db, {
        "plant_wide_yield_rate": 84.86,
        "heating_furnace_gas_m3": 8194,
        "daily_input_weight": 197,
    })

    facts = collect_template_daily_facts(db, target_date=date(2026, 6, 16))

    assert facts.values["daily_yield_rate"] == 84.86
    assert facts.values["hot_roll_furnace_gas_m3"] == 8194
    assert facts.values["cold_roll_input_daily"] == 197
```

- [ ] **Step 3: Run tests and verify failure**

Run: `cd backend && python -m pytest tests/test_template_daily_fact_sources.py -q`

Expected: FAIL for missing aliases or missing payload handling.

- [ ] **Step 4: Implement owner-daily extraction**

Keep implementation simple:

- latest submitted/verified/approved owner daily row wins,
- empty strings do not override real values,
- sources record `source_type="owner_daily"` and original field name.

- [ ] **Step 5: Add validation that critical manual fields block generation**

```python
def test_missing_energy_fields_block_template_report(db):
    facts = collect_template_daily_facts(db, target_date=date(2026, 6, 16))

    assert "total_electricity_kwh" in facts.missing_fields
```

- [ ] **Step 6: Run focused tests**

Run: `cd backend && python -m pytest tests/test_template_daily_fact_sources.py tests/test_template_daily_report.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/report/template_daily_fact_sources.py backend/tests/test_template_daily_fact_sources.py
git commit -m "feat: fill template daily manual owner facts"
```

---

### Task 6: Implement Yesterday Display-Value Comparison

**Files:**
- Modify: `backend/app/services/report/template_daily_fact_sources.py`
- Create or modify: `backend/tests/test_template_daily_comparisons.py`

- [ ] **Step 1: Write tests for previous final report comparison**

```python
def test_total_output_delta_uses_yesterday_final_display_value(db):
    seed_daily_report(db, date(2026, 6, 15), final_text_summary="6月15日，车间总产量日合计306吨（外加工0吨）比昨日↑85吨，月累计4686吨（外加工月累计270吨）。")
    seed_owner_daily_payload(db, {"total_output_daily": 328})

    facts = collect_template_daily_facts(db, target_date=date(2026, 6, 16))

    assert facts.values["total_output_delta"] == 22
```

- [ ] **Step 2: Add tests for remaining contract and yield deltas**

Expected behavior:

- today's rendered remaining contract minus yesterday displayed remaining contract,
- today's rendered yield percent minus yesterday displayed yield percent.

- [ ] **Step 3: Run tests and verify failure**

Run: `cd backend && python -m pytest tests/test_template_daily_comparisons.py -q`

Expected: FAIL until comparison extraction exists.

- [ ] **Step 4: Implement comparison extraction**

Use `output_skill_report_parser.py` logic or a shared parser to extract prior final values from `DailyReport.final_text_summary`.

Do not recompute yesterday from raw data if final text exists.

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_template_daily_comparisons.py tests/test_template_daily_report.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/report/template_daily_fact_sources.py backend/app/services/report/output_skill_report_parser.py backend/tests/test_template_daily_comparisons.py
git commit -m "feat: use final report display values for daily comparisons"
```

---

### Task 7: Add OutputSkill Reconciliation Dry-Run

**Files:**
- Create: `backend/app/services/report/output_skill_reconciliation.py`
- Create: `backend/tests/test_output_skill_reconciliation.py`

- [ ] **Step 1: Write comparison tests**

```python
def test_reconciliation_reports_exact_text_match():
    expected = fixture_text("2026-6-16_日报正文.txt")
    result = reconcile_rendered_daily_report(expected, expected)

    assert result["exact_match"] is True
    assert result["char_match_rate"] == 100
    assert result["field_match_rate"] == 100
```

- [ ] **Step 2: Write first-difference test**

```python
def test_reconciliation_reports_first_difference():
    expected = "6月16日，车间总产量日合计328吨。"
    actual = "6月16日，车间总产量日合计309吨。"

    result = reconcile_rendered_daily_report(actual, expected)

    assert result["exact_match"] is False
    assert result["differences"][0]["field"] == "total_output_daily"
```

- [ ] **Step 3: Run tests and verify failure**

Run: `cd backend && python -m pytest tests/test_output_skill_reconciliation.py -q`

Expected: FAIL.

- [ ] **Step 4: Implement reconciliation**

Return:

```python
{
    "exact_match": False,
    "char_match_rate": 98.5,
    "field_match_rate": 95.0,
    "differences": [
        {"field": "total_output_daily", "actual": 309, "expected": 328}
    ],
}
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_output_skill_reconciliation.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/report/output_skill_reconciliation.py backend/tests/test_output_skill_reconciliation.py
git commit -m "feat: compare rendered daily report with output skill target"
```

---

### Task 8: Add Dry-Run Preview Endpoint

**Files:**
- Modify: `backend/app/routers/reports.py` or the existing report router that owns report generation.
- Modify: `backend/app/main.py` only if router registration is missing.
- Test: existing API tests or create `backend/tests/test_template_daily_report_routes.py`

- [ ] **Step 1: Write route test**

```python
def test_template_daily_report_preview_blocks_with_missing_fields(client, admin_token):
    response = client.post(
        "/api/v1/reports/template-daily/preview",
        json={"target_date": "2026-06-16"},
        headers=auth(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["status"] in {"ready", "blocked"}
    assert "missing_fields" in response.json()
```

- [ ] **Step 2: Run route test and verify failure**

Run: `cd backend && python -m pytest tests/test_template_daily_report_routes.py -q`

Expected: FAIL because endpoint does not exist.

- [ ] **Step 3: Implement endpoint**

Endpoint behavior:

- `POST /api/v1/reports/template-daily/preview`
- admin/manager only,
- no database writes,
- returns status, text, missing fields, conflicts, sources,
- optional `reference_output_skill_path` only for local/dev dry-run, never required in production.

- [ ] **Step 4: Run route tests**

Run: `cd backend && python -m pytest tests/test_template_daily_report_routes.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/reports.py backend/tests/test_template_daily_report_routes.py
git commit -m "feat: preview template daily report facts"
```

---

### Task 9: Keep Scheduler Behavior And Add Guardrails

**Files:**
- Modify: `backend/app/tasks/daily_report.py`
- Modify: `backend/app/core/scheduler.py` only if existing schedule is wrong.
- Test: `backend/tests/test_daily_report_task.py`, `backend/tests/test_scheduler.py`

- [ ] **Step 1: Add task test for previous business day**

```python
def test_generate_daily_reports_uses_last_completed_business_date(monkeypatch):
    monkeypatch.setattr("app.tasks.daily_report.last_completed_production_business_date", lambda: date(2026, 6, 16))

    result = generate_daily_reports()

    assert result["business_date"] == "2026-06-16"
```

- [ ] **Step 2: Add task test for blocked report**

If facts are blocked, task should store blocked status in `DailyReport.report_data["template_daily_report"]` and not invent final text.

- [ ] **Step 3: Run tests**

Run: `cd backend && python -m pytest tests/test_daily_report_task.py tests/test_scheduler.py -q`

Expected: PASS after implementation.

- [ ] **Step 4: Confirm scheduler remains 7:30**

Expected code in `backend/app/core/scheduler.py`:

```python
_add_job_once(active_scheduler, generate_daily_reports, 'cron', job_id='daily_report', hour=7, minute=30)
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/daily_report.py backend/tests/test_daily_report_task.py backend/tests/test_scheduler.py
git commit -m "fix: guard template daily report scheduled generation"
```

---

### Task 10: Backfill 2026-06-10 To 2026-06-16 Validation Harness

**Files:**
- Create: `backend/scripts/dry_run_template_daily_reports.py`
- Create: `docs/audits/template-daily-report-outputskill-baseline.md`
- Test: script smoke through pytest or direct command.

- [ ] **Step 1: Create dry-run script**

The script should:

- accept `--start-date`,
- accept `--end-date`,
- accept `--output-skill-dir`,
- generate system text in dry-run mode,
- compare to `YYYY-M-D_日报正文.txt`,
- print a table with status, missing count, field match rate, and first differences.

- [ ] **Step 2: Add a safe local command**

Run:

```bash
cd backend
python scripts/dry_run_template_daily_reports.py --start-date 2026-06-10 --end-date 2026-06-16 --output-skill-dir D:\输出skill
```

Expected before all fields are connected: blocked rows with exact missing fields.

Expected after all facts are seeded/connected: ready rows with high match rate.

- [ ] **Step 3: Write the audit baseline**

Document:

- which dates were tested,
- which fields matched,
- which fields still need owner fill or source mapping,
- which MES fields had口径 differences,
- next fixes.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/dry_run_template_daily_reports.py docs/audits/template-daily-report-outputskill-baseline.md
git commit -m "chore: add template daily output skill dry run"
```

---

### Task 11: Optional Minimal Frontend Preview

**Files:**
- Modify: existing report management page under `frontend/src/views/`
- Modify: API client if needed.
- Test: relevant frontend test.

- [ ] **Step 1: Check if current management page can preview report text**

If it already can, skip this task.

- [ ] **Step 2: Add a small preview action**

UI behavior:

- pick date,
- click preview,
- show status `ready` or `blocked`,
- show generated text if ready,
- show missing fields grouped by category if blocked.

- [ ] **Step 3: Run frontend tests**

Run: `cd frontend && npm test`

Expected: PASS.

- [ ] **Step 4: Run frontend build**

Run: `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat: preview template daily report status"
```

---

### Task 12: Full Verification And Production QA

**Files:**
- No code changes unless tests fail.

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
cd backend
python -m pytest tests/test_template_daily_report.py tests/test_template_daily_fact_sources.py tests/test_output_skill_report_parser.py tests/test_output_skill_reconciliation.py tests/test_daily_report_task.py tests/test_scheduler.py -q
```

Expected: PASS.

- [ ] **Step 2: Run backend full tests**

Run:

```bash
cd backend
python -m pytest -q
```

Expected: PASS, allowing existing skipped tests only.

- [ ] **Step 3: Run migration**

Run:

```bash
cd backend
python -m alembic upgrade head
```

Expected: PASS.

- [ ] **Step 4: Run frontend tests and build**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: PASS.

- [ ] **Step 5: Run outputskill dry-run**

Run:

```bash
cd backend
python scripts/dry_run_template_daily_reports.py --start-date 2026-06-10 --end-date 2026-06-16 --output-skill-dir D:\输出skill
```

Expected:

- If manual facts are not seeded: clear blocked report with missing categories.
- If manual facts are seeded: field match rate 95%+ and 2026-06-16 exact match or documented local differences.

- [ ] **Step 6: Deploy to production**

Use the existing deployment script, without printing secrets:

```bash
ssh root@8.140.218.13 "cd /srv/aluminum-bypass && ./scripts/deploy_systemd_host.sh --pull http://8.140.218.13"
```

Expected: deploy exits 0.

- [ ] **Step 7: Verify production health**

Run:

```powershell
Invoke-RestMethod -Uri 'http://8.140.218.13/readyz'
```

Expected:

- `status = ready`
- `checks.database = ok`
- `checks.mes_sync = ok`
- no `error_message`
- no `last_error`

- [ ] **Step 8: Verify scheduler on production**

Run:

```bash
ssh root@8.140.218.13 "cd /srv/aluminum-bypass && grep -n daily_report backend/app/core/scheduler.py"
```

Expected: `hour=7, minute=30`.

- [ ] **Step 9: Commit final evidence**

If docs changed:

```bash
git add docs/audits/template-daily-report-outputskill-baseline.md
git commit -m "docs: record template daily report output skill validation"
```

---

## Implementation Order Summary

1. Freeze field contract.
2. Parse outputskill target reports.
3. Add facts source layer.
4. Fix MES report口径 mapping.
5. Add owner daily manual facts.
6. Add yesterday display-value comparisons.
7. Add reconciliation dry-run.
8. Add preview endpoint.
9. Keep scheduler guarded.
10. Run 6.10-6.16 validation.
11. Add frontend preview only if missing.
12. Full test, deploy, production QA.

## Risk Notes

- The largest risk is not template rendering; it is source口径. Do not tune the renderer to hide wrong data.
- MES rows can be double-counted if workshop/process/device aliases are too broad. Add explicit tests before changing aggregation.
- `比昨日` must use yesterday final displayed value where available. Recomputing from raw data can produce a different delta.
- Some fields are intentionally manual today: recovery, overhaul, active cast-roll lines, energy details, yield, and cost. They must enter system as structured owner facts before 7:30.
- If a required owner fact is missing, the correct behavior is `blocked` with missing field names, not a guessed report.

## Handoff

Plan complete. Recommended execution mode is task-by-task with `superpowers:executing-plans`. Use a fresh commit after each task so failed mapping changes can be reverted safely.
