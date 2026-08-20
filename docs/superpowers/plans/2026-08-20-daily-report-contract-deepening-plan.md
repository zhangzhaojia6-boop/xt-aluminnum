# Daily Report Contract Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every human-action daily fact gap one contract-owned deadline and contract version, show the deadline in the existing `/manage/alerts` queue, and remove duplicate gap action rules without changing the fixed 127 fields or any fact value.

**Architecture:** Deepen `daily_report_field_contract.py` with the static action metadata currently duplicated in `daily_report_gap_analysis.py`. Keep evidence rules in `metric_contracts.py`, keep URLs and summaries in the gap adapter, and keep the existing form templates; only validate their field names. Persist contract provenance on `AgentEvent`, pass it through the existing persisted fact surface, and display the deadline in the current alert queue.

**Tech Stack:** Python dataclasses, FastAPI, SQLAlchemy, Vue 3, Node test, pytest, PostgreSQL production compare-only gates.

---

## Verified Premise

Production read-only evidence on 2026-08-20:

- `110` open human-action `daily_fact_gap` events in the last 7 days.
- `0` missing `owner_role`; `0` missing `entry_route`.
- `110` missing `deadline`; `110` missing `contract_version`.
- All `110` route to the existing `/entry/fill` workflow.
- The existing `/manage/alerts` normalizer carries owner and action route but not deadline or contract version.

This plan is invalid and must stop if a fresh pre-implementation query no longer confirms the same bug class.

## Task 1: Move gap action metadata behind the field-contract interface

**Files:**
- Modify: `backend/app/domain/daily_report_field_contract.py`
- Modify: `backend/app/services/report/daily_report_gap_analysis.py`
- Test: `backend/tests/test_daily_report_field_contract.py`
- Test: `backend/tests/test_daily_report_gap_analysis.py`

- [x] **Step 1: RED — require the metadata schema and five representative actions**

Add one schema-level test. Existing tests already cover the 127 count, tolerance and source order, so do not duplicate those loops here.

```python
def test_field_contract_exposes_gap_metadata_schema() -> None:
    contract = contract_module.daily_report_field_contract_for("finished_inbound_daily")
    assert contract.owner_role == "storage_owner"
    assert contract.deadline
    assert contract.entry_route == "/entry/fill"
    assert contract.entry_fields == ("park_inbound_daily", "new_plant_inbound_daily")
```

Run only this test and confirm it fails because the current contract lacks action metadata.

- [x] **Step 2: GREEN — add group defaults and field overrides to the contract**

Extend the frozen contract with:

```python
owner_role: str
deadline: str
fill_strategy: str
entry_route: str
entry_fields: tuple[str, ...]
next_step: str
```

Move the existing observable values from `GROUP_ACTIONS`, `FIELD_ACTIONS`, and `_is_computed_field` into private group defaults and field overrides in `daily_report_field_contract.py`. Preserve current owner, route, entry fields, fill strategy, gap-specific `source_lane` and next-step text exactly. Do not derive the gap source lane from `source_lanes[0]`; they describe different interfaces. `/entry/fill` actions use the existing `OWNER_DAILY_LATE_TIME`; automatic/dependency actions use the existing `10:00` report cutoff and are not rendered as human deadlines. Use the existing contract version because this is backward-compatible metadata completion, not a field-set or source-order change.

- [x] **Step 3: RED — require one contract gap projection**

Add focused public tests for these high-value fields:

```python
for field in (
    "total_output_daily",
    "finished_inbound_daily",
    "wip_total",
    "total_electricity_kwh",
    "daily_yield_rate",
):
    action = daily_report_gap_action_for(field)
    assert action.field == field
    assert action.contract_version == DAILY_REPORT_FIELD_CONTRACT_VERSION
    assert action.deadline
```

Confirm RED because `daily_report_gap_action_for()` does not exist.

- [x] **Step 4: GREEN — delegate the compatibility classifier to the contract**

Add immutable `DailyReportGapAction` and `daily_report_gap_action_for(field_name)`. Change `classify_daily_report_field_gap()` to return its compatibility dictionary. Then delete `GROUP_ACTIONS`, `FIELD_ACTIONS`, and `_is_computed_field` from `daily_report_gap_analysis.py`.

Run:

```powershell
$env:PYTHONPATH='backend'
python -m pytest backend/tests/test_daily_report_field_contract.py backend/tests/test_daily_report_gap_analysis.py -q
```

## Task 2: Persist and expose contract provenance

**Files:**
- Modify: `backend/app/services/report/daily_fact_gap_closure_service.py`
- Modify: `backend/app/services/report/daily_report_fact_closure.py`
- Test: `backend/tests/test_daily_fact_gap_closure_service.py`
- Test: `backend/tests/test_persisted_daily_fact_surface.py`

- [x] **Step 1: RED — require provenance on a real open event**

Extend one existing event test:

```python
payload = event.payload or {}
assert payload["deadline"]
assert payload["contract_version"] == DAILY_REPORT_FIELD_CONTRACT_VERSION
```

Confirm RED on the missing keys.

Add one legacy-payload test proving an event without `action_route`, `entry_fields`, `owner_role`, `deadline` or `contract_version` still renders through the existing safe fallback.

- [x] **Step 2: GREEN — propagate metadata without resetting event history**

Carry `deadline` and `contract_version` from `classify_daily_report_field_gap()` through `_real_source_gap_items()` into create, reopen and refresh payload paths. Preserve first-detected trace, notification dedupe and resolution history.

- [x] **Step 3: RED — require the persisted alert surface to expose provenance**

Add to the existing surface test:

```python
item = payload["fact_missing"][0]
assert item["deadline"]
assert item["contract_version"] == DAILY_REPORT_FIELD_CONTRACT_VERSION
```

- [x] **Step 4: GREEN — add two fields to the existing surface**

In `build_persisted_daily_fact_surface`, copy only `deadline` and `contract_version` from event payload. Do not change routes, status, source priority or alert grouping. Update exact-dictionary assertions for the two intentional fields; use subset assertions only in the legacy compatibility test.

Run:

```powershell
$env:PYTHONPATH='backend'
python -m pytest backend/tests/test_daily_fact_gap_closure_service.py backend/tests/test_persisted_daily_fact_surface.py -q
```

## Task 3: Show the deadline in the existing alert queue

**Files:**
- Modify: `frontend/src/components/manage/_alertEventNormalize.js`
- Modify: `frontend/src/views/manage/alerts/AlertsPage.vue`
- Test: `frontend/tests/manageAlertsTimeline.test.js`

- [x] **Step 1: RED — normalize and render an action deadline**

Extend one existing daily-fact alert fixture with `deadline: "09:30"` and `contract_version`. Assert the normalizer accepts snake_case input, exposes `deadline` plus camelCase `contractVersion`, and queue metadata contains `截止 09:30` for a human `/entry/fill` action. Add a legacy fixture without deadline/version; it must render normally and must not contain `截止`.

- [x] **Step 2: GREEN — preserve provenance and add compact queue metadata**

Add `deadline` and `contractVersion` to `dailyFactEvent()`. In `queueItemMeta()`, put `截止 ${item.deadline}` first and only for `/entry/fill`; keep the owner second. When mobile space is tight, omit the low-value “补录入口已发送/待发送” phrase before omitting the deadline or owner. Do not add explanatory copy, cards, tooltips or a new page.

- [x] **Step 3: Run the focused frontend test**

```powershell
cd frontend
node --test --test-name-pattern="daily fact|deadline|work queue" tests/manageAlertsTimeline.test.js
```

## Task 4: Validate existing Entry mappings and strengthen the gate

**Files:**
- Modify: `backend/app/domain/daily_report_field_contract.py`
- Create: `backend/app/services/report/daily_report_contract_validation.py`
- Modify: `backend/scripts/check_daily_report_field_contract.py`
- Test: `backend/tests/test_daily_report_field_contract.py`
- Test: `backend/tests/test_daily_report_field_contract_scripts.py`
- Read only: `backend/app/core/templates/__init__.py`
- Read only: `backend/app/routers/mobile.py`

- [x] **Step 1: RED — reject unknown entry fields and incomplete metadata**

Add one contract validation path that fails when:

- contract count is not 127;
- a contract owner, deadline, route or version is blank;
- an `/entry/fill` action has no fields;
- a declared contract field cannot traverse `contract field -> entry alias -> existing writable template field`;
- a tolerance exceeds 20;
- output-skill reference is not compare-only.

- [x] **Step 2: GREEN — implement read-only validation**

Put `validate_daily_report_contract()` in `daily_report_contract_validation.py`, not in the domain module. It may import the domain contract and `app.core.templates`; the domain must not import routers, services or FastAPI. Make `check_daily_report_field_contract.py --json` call this adapter and fail non-zero on errors. Add focused `/mobile/entry-fields` tests proving the five representative aliases are visible to their responsible roles. Do not modify form templates or the endpoint response shape.

- [x] **Step 3: Run contract gates**

```powershell
$env:PYTHONPATH='backend'
python -m pytest backend/tests/test_daily_report_field_contract.py backend/tests/test_daily_report_field_contract_scripts.py backend/tests/test_mobile_bootstrap.py -q
python backend/scripts/check_daily_report_field_contract.py --json
```

Expected contract count: exactly `127`.

## Task 5: Review, compare-only production proof and ship

**Files:**
- Update: `docs/superpowers/plans/2026-08-20-daily-report-contract-deepening-plan.md`

- [x] **Step 1: Run focused regression suites**

Run contract, gap analysis, gap closure, persisted surface, DailyFactBundle and the single manage-alert test file. Update exact-dictionary fixtures for the two intentional fields. Run frontend build because a production Vue file changed; do not broaden unrelated suites.

- [x] **Step 2: Run independent review**

Use one code-reviewer and one security-reviewer. Required questions:

- Did any path change the 127 denominator?
- Did source priority or compare-only behavior change?
- Can automatic gaps accidentally become human actions?
- Can old event payloads still render safely?
- Is the field-contract module deeper, or did the change only move dictionaries?

- [x] **Step 3: Run a real compare-only gate**

Run `check_daily_report_output_skill_alignment.py` for the latest completed production business day with output-skill reference in compare-only mode. Do not use `--help` as proof and do not adopt answer-key values.

Hard pass conditions: `reference_mode=compare`, `reference_only=false`, and `real_source_gate_passed=true`. Any other mode is a failed production proof.

- [x] **Step 4: Commit, push and exact-SHA deploy**

Commit the reviewed code, push `main`, wait for CI, then deploy via `production-sync-status.yml` using the exact data-hub SHA and unchanged trusted Hermes SHA.

- [x] **Step 5: Production acceptance**

Verify read-only:

- production denominator is 127;
- latest completed business-day gap count did not increase from its pre-deploy baseline;
- every open human action has owner, entry route, deadline and contract version;
- automatic recheck gaps did not generate new human notifications;
- `/manage/alerts` payload exposes deadline and contract version;
- `/readyz=ready`, MES sync `ok`, DingTalk Stream `connected`;
- data hub and Hermes tracked worktrees are clean and exact-SHA synchronized.

Before these checks, run the existing open-gap refresh once after deploy. It refreshes at most the latest 7 open business dates through normal closure code and preserves notification dedupe; do not write a one-off SQL backfill. Record the pre/post human-notification Outbox count and reject any unexpected increase.

## Not In Scope

- Historical gap cleanup or automatic N/A declarations.
- Escalation roles and escalation reminders; add them only with a real phase-3 consumer.
- Action-batch aggregation.
- New pages or a generic form engine.
- Energy database integration.
- Any change to facts, source priority, MES write access or answer-key adoption.

## Rollback

No migration and no fact rewrite are introduced. On regression, deploy the previous exact data-hub SHA and rerun the same compare-only and health gates.

## Execution Evidence

Completed on 2026-08-20:

- Data hub SHA deployed: `7f60cc072fe0c3727454c5c68fef5183ac587ce3`.
- Hermes SHA unchanged: `4d4452067cb43ebcd437eba78b0c67d9f1c64652`.
- CI run `32380580040`: frontend build, backend tests and compose Playwright smoke all passed.
- Production deploy run `32382811640`: success.
- Local merged verification: backend `254 passed`, alert timeline `25 passed`, frontend build passed.
- Contract gate: `127` normative fields, `130` template fields, maximum tolerance `20`, compare-only source order, `errors=[]`.
- Open-gap refresh: `7` dates processed through the normal task, status `pass`.
- 2026-08-19 before/after: open gaps `82 -> 82`; human gaps `15`; deadline coverage `0 -> 15`; contract-version coverage `0 -> 15`.
- Existing alert surface exposes deadline for all `15` human fill actions.
- Daily closure Outbox stayed at count `81`, max ID `835`; the refresh created no duplicate human notification.
- Production health: `/readyz=ready`, MES sync `ok`, pipeline `ok`, DingTalk Stream `connected`, both tracked worktrees clean.

Compare-only was run directly against production facts and UTF-8 references for 2026-08-17 through 2026-08-19. It correctly remained blocked rather than false-green:

| Date | Mode | Reference only | Denominator | Coverage | Matched | Missing | Real-source gate |
|---|---|---:|---:|---:|---:|---:|---|
| 2026-08-17 | compare | false | 127 | 3.94% | 5 | 93 | blocked |
| 2026-08-18 | compare | false | 127 | 4.72% | 6 | 93 | blocked |
| 2026-08-19 | compare | false | 127 | 3.94% | 5 | 79 | blocked |

Deployment did not change these values. The original hard pass condition `real_source_gate_passed=true` is not achieved and is explicitly carried into the next loop; this plan proves contract provenance and no regression, not daily-report accuracy completion.

## GSTACK REVIEW REPORT

Review mode: Autoplan-compatible non-interactive degradation. The interactive AskUserQuestion tool was unavailable. CEO, design, engineering and test reviews ran with independent subagents; Codex CLI produced no usable review because its local model cache and transport failed.

### Phase Results

| Phase | Result | Plan change |
|---|---|---|
| CEO | Initial refactor-only premise rejected | Added production evidence; made deadline visible in existing alerts; removed speculative escalation metadata. |
| Design | Existing queue can carry the change if compact | Deadline appears first only for human fill actions; legacy payload and mobile density are explicit. |
| Engineering | Circular dependency and wrong template path found | Validation moved to an adapter module; real templates path and alias chain are explicit; post-deploy refresh added. |
| Test/DX | Focused command and compare gate could false-green | Corrected Node command; added exact compare-only success conditions and legacy fixtures. |

### Auto-Decisions

| Decision | Choice | Reason |
|---|---|---|
| Keep this P0 | Yes, after reframing | Production proves 110/110 human gaps lack deadline/version; the result is user-visible, not refactor theater. |
| Add escalation role now | No | No consumer exists until phase 3; adding it now would be speculative infrastructure. |
| Rewrite form engine | No | Existing `/entry/fill` works; validate aliases against current templates instead. |
| Add a page | No | Existing `/manage/alerts` already owns the action queue. |
| Backfill with SQL | No | Reuse normal open-gap refresh to preserve event and notification invariants. |
| Broaden tests | No | Use focused behavioral tests, one contract gate and real production compare-only proof. |

### Remaining Risks Addressed by the Plan

- Domain imports remain one-way; no router/service import enters the contract module.
- Legacy AgentEvent payloads remain renderable.
- Gap-specific source lanes remain distinct from fact source priority lanes.
- Exact-dictionary test fixtures account for the two intentional output fields.
- Production acceptance rejects any denominator change, answer-key adoption, new human notification or gap-count increase.
