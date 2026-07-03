# Daily Report Fact Closure Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the smallest production gate that proves the daily report numbers are true: run recent completed business days against real production data and `D:\输出skill`, expose field-level mismatches, mark missing facts, and let Hermes drive补齐 without reducing its autonomy.

**Architecture:** Keep `鑫泰铝业 数据中枢` small. `/entry` remains the补录入口, `/manage` remains the big dashboard, MES/WMS remain read-only external fact sources, DingTalk group files/chat remain the highest-priority evidence, and Hermes remains `鑫泰铝业智能大脑`.

**Tech Stack:** Python FastAPI backend, SQLAlchemy, existing report services, existing Hermes LangChain tools, existing pytest suite, existing frontend utility tests, existing production script `backend/scripts/check_daily_report_output_skill_alignment.py`.

---

## Scope Check

This plan does one thing first: create a daily report fact closure gate.

It does not create a new portal, does not rename the product to MES, does not rewrite the data hub, and does not make DingTalk recognition brittle. The output must be easy for a non-programmer to inspect: for each business day, each important field says “matched / different / missing / needs owner evidence”, with source and trace.

## Success Criteria

- Recent 3 completed business days can produce `DailyFactBundle` from production database.
- The alignment script writes a full field-level difference artifact against `D:\输出skill`.
- Five key facts are explicitly gated: `total_output_daily`, `finished_inbound_daily`, `wip_total`, `total_electricity_kwh`, `daily_yield_rate`.
- Every gated key fact carries `source`, `status`, `trace_id`, and a补齐 action when not confirmed.
- MES/WMS read-only health is visible in the gate result.
- DingTalk group message/file evidence can enter `multimodal_evidence` and update daily facts without hard keyword-only matching.
- Hermes acceptance stays Chinese-only and identifies itself as `鑫泰铝业智能大脑`.
- `/manage` can show source health and missing-field pressure without adding a second dashboard.

## Files To Touch

- `backend/scripts/check_daily_report_output_skill_alignment.py`
- `backend/tests/test_check_daily_report_output_skill_alignment_script.py`
- `backend/app/services/report/daily_report_gap_analysis.py`
- `backend/tests/test_daily_report_gap_analysis.py`
- `backend/app/services/report/daily_fact_bundle.py`
- `backend/tests/test_daily_fact_bundle_service.py`
- `backend/app/services/report/daily_report_fact_closure.py`
- `backend/tests/test_daily_report_fact_closure.py`
- `backend/app/services/hermes_daily_fact_update_service.py`
- `backend/tests/test_hermes_daily_fact_update_service.py`
- `backend/app/services/hermes_langchain_tools.py`
- `backend/tests/test_hermes_langchain_tools.py`
- `backend/app/services/hermes_20_question_acceptance.py`
- `backend/tests/test_hermes_20_question_real_acceptance.py`
- `backend/scripts/hermes_20_question_acceptance.py`
- `frontend/src/utils/manageDailyReportSurface.js`
- `frontend/tests/manageDailyReportSurface.test.js`
- `docs/superpowers/reports/daily-report-fact-closure-2026-06-30.md`

## Task 1: Make The Alignment Gate Produce A Full Artifact

- [ ] Extend `backend/scripts/check_daily_report_output_skill_alignment.py` with `--artifact-dir` and `--full-differences`.

Current script already computes rows. Add a writer that saves machine-readable and human-readable output.

```python
def write_alignment_artifacts(rows: list[dict[str, Any]], artifact_dir: Path) -> dict[str, str]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    json_path = artifact_dir / "daily_report_alignment.json"
    md_path = artifact_dir / "daily_report_alignment.md"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_alignment_markdown(rows), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}
```

- [ ] Add `render_alignment_markdown(rows)` in the same file.

The markdown must include:

- business date
- bundle status
- field match rate
- exact match
- missing field count
- each difference with `field`, `expected`, `actual`, `source`, `status`, `action`

- [ ] Keep the existing console output intact so current users do not lose behavior.

- [ ] Add tests in `backend/tests/test_check_daily_report_output_skill_alignment_script.py`.

Test cases:

```bash
python -m pytest backend/tests/test_check_daily_report_output_skill_alignment_script.py -q
```

Expected result:

```text
passed
```

The test should assert:

- artifact directory is created
- JSON file exists
- markdown file exists
- full differences are not truncated when `--full-differences` is active
- truncated behavior remains unchanged when the flag is not active

Commit after this task:

```bash
git add backend/scripts/check_daily_report_output_skill_alignment.py backend/tests/test_check_daily_report_output_skill_alignment_script.py
git commit -m "Add daily report alignment artifacts"
```

## Task 2: Add A Small Fact Closure Service

- [ ] Create `backend/app/services/report/daily_report_fact_closure.py`.

Purpose in plain language: take a `DailyFactBundle` and say whether the most important numbers are believable enough to publish.

Public functions:

```python
CRITICAL_DAILY_FACT_FIELDS = (
    "total_output_daily",
    "finished_inbound_daily",
    "wip_total",
    "total_electricity_kwh",
    "daily_yield_rate",
)

def build_daily_report_fact_closure(bundle: Mapping[str, Any]) -> dict[str, Any]:
    ...
```

Return shape:

```python
{
    "status": "blocked",
    "critical_fields": [
        {
            "field": "total_output_daily",
            "status": "mismatch",
            "source": "mes_packaging_output",
            "trace_id": "daily-fact-...",
            "value": 384.0,
            "action": "核对钉钉日报与MES包装产量口径",
        }
    ],
    "counts": {
        "confirmed": 2,
        "mismatch": 1,
        "missing": 2,
    },
}
```

Rules:

- `confirmed`: value exists and source is allowed for this field.
- `missing`: no value, no source, or bundle already marks the field missing.
- `mismatch`: alignment difference names this field.
- `needs_evidence`: value exists but source is too weak, such as projection-only data.
- `blocked`: any critical field is `missing`, `mismatch`, or `needs_evidence`.
- `pass`: all critical fields are confirmed.

- [ ] Use `build_daily_report_gap_plan(...)` for action wording when possible.

- [ ] Add unit tests in `backend/tests/test_daily_report_fact_closure.py`.

Test cases:

- all five fields confirmed returns `pass`
- missing energy returns `blocked`
- output-skill mismatch returns `blocked`
- projection-only source returns `needs_evidence`
- every critical field has `field`, `status`, `source`, `trace_id`, `action`

Run:

```bash
python -m pytest backend/tests/test_daily_report_fact_closure.py backend/tests/test_daily_report_gap_analysis.py -q
```

Expected result:

```text
passed
```

Commit after this task:

```bash
git add backend/app/services/report/daily_report_fact_closure.py backend/tests/test_daily_report_fact_closure.py backend/app/services/report/daily_report_gap_analysis.py backend/tests/test_daily_report_gap_analysis.py
git commit -m "Add daily report fact closure gate"
```

## Task 3: Attach Closure Status To DailyFactBundle

- [ ] Modify `backend/app/services/report/daily_fact_bundle.py`.

After `gap_plan` is built, add:

```python
from backend.app.services.report.daily_report_fact_closure import build_daily_report_fact_closure

bundle["fact_closure"] = build_daily_report_fact_closure(bundle)
```

Keep this near existing `gap_plan` logic so the data path stays obvious.

- [ ] Update `backend/tests/test_daily_fact_bundle_service.py`.

Assertions:

- bundle contains `fact_closure`
- closure includes the five critical fields
- when a critical field is missing, bundle status does not pretend the report is publish-ready
- DingTalk supplement can make a missing critical field become confirmed when source and trace exist

Run:

```bash
python -m pytest backend/tests/test_daily_fact_bundle_service.py backend/tests/test_daily_report_fact_closure.py -q
```

Expected result:

```text
passed
```

Commit after this task:

```bash
git add backend/app/services/report/daily_fact_bundle.py backend/tests/test_daily_fact_bundle_service.py
git commit -m "Attach fact closure to daily fact bundle"
```

## Task 4: Make DingTalk Fact Updates Flexible, Not Brittle

- [ ] Create `backend/app/services/hermes_daily_fact_update_service.py`.

Purpose in plain language: take DingTalk group text/file evidence and extract possible daily fact updates without rejecting useful messages just because the wording is different.

Public function:

```python
def extract_daily_fact_update_candidates(evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    ...
```

Rules:

- Accept explicit structured `payload.fact_updates` first.
- For plain Chinese text, detect candidates using soft patterns and number+unit context.
- Unknown messages return an empty list, not an error.
- Candidates must include `field`, `value`, `unit`, `confidence`, `source`, `trace_id`, `raw_text`.
- Confidence is advisory only. It must not block Hermes from asking follow-up questions.

Soft examples to support:

```text
今日总产量371吨
成品入库 365.2 t
昨日用电 18420 度
在制合计1136吨
成品率98.4%
```

- [ ] Wire this into `_apply_dingtalk_supplements(...)` in `backend/app/services/report/daily_fact_bundle.py`.

Behavior:

- If `payload.fact_updates` exists, keep current behavior.
- If not, call `extract_daily_fact_update_candidates(...)`.
- Only apply candidates when `business_date` matches the bundle date or can be safely inferred from the evidence payload.
- Record candidate trace in conflicts/evidence metadata even when not applied.

- [ ] Add tests in `backend/tests/test_hermes_daily_fact_update_service.py` and extend `backend/tests/test_daily_fact_bundle_service.py`.

Run:

```bash
python -m pytest backend/tests/test_hermes_daily_fact_update_service.py backend/tests/test_daily_fact_bundle_service.py -q
```

Expected result:

```text
passed
```

Commit after this task:

```bash
git add backend/app/services/hermes_daily_fact_update_service.py backend/tests/test_hermes_daily_fact_update_service.py backend/app/services/report/daily_fact_bundle.py backend/tests/test_daily_fact_bundle_service.py
git commit -m "Extract flexible DingTalk daily fact candidates"
```

## Task 5: Strengthen Hermes Source Order Without Reducing Autonomy

- [ ] Modify `backend/app/services/hermes_langchain_tools.py`.

Keep existing tools, but make the returned source guidance explicit:

1. DingTalk group chat/file evidence first.
2. MES/WMS read-only facts second.
3. Data hub bundle and projection third.
4. RAG only for rules, definitions, and historical context.

Add this to tool outputs as metadata, not as a hard refusal. Hermes can still reason and choose actions.

- [ ] Ensure `_dingtalk_evidence_tool` keeps broad matching.

Do not add a fixed keyword gate. Search should tolerate date, sender, file, text, and semantic hints.

- [ ] Ensure `_mes_wms_read_tool` returns readable health information.

It should expose:

- adapter name
- readonly status
- query key
- source errors
- record count

- [ ] Extend `backend/tests/test_hermes_langchain_tools.py`.

Assertions:

- DingTalk evidence result says it is priority 1.
- MES/WMS read result says it is read-only.
- RAG result is not labeled as current numeric fact source.
- No English identity such as `developer` or `Factory Brain` appears in Hermes-facing source guidance.

Run:

```bash
python -m pytest backend/tests/test_hermes_langchain_tools.py backend/tests/test_hermes_mes_read_service.py -q
```

Expected result:

```text
passed
```

Commit after this task:

```bash
git add backend/app/services/hermes_langchain_tools.py backend/tests/test_hermes_langchain_tools.py
git commit -m "Clarify Hermes source priority"
```

## Task 6: Connect The Gate To Hermes 20-Question Acceptance

- [ ] Modify `backend/scripts/hermes_20_question_acceptance.py`.

Add optional arguments:

```bash
--output-skill-root "D:\输出skill"
--alignment-artifact-dir docs\superpowers\reports\daily-report-fact-closure-smoke
--require-daily-report-gate
```

When `--require-daily-report-gate` is present, run the alignment check for the selected business date before question execution and attach the result to `source_health.daily_report_gate`.

- [ ] Modify `backend/app/services/hermes_20_question_acceptance.py`.

Acceptance gate must fail if:

- Hermes answer is not Chinese
- Hermes identity is not `鑫泰铝业智能大脑`
- current numeric answer uses RAG as the only source
- `daily_report_gate` is required but missing

Acceptance gate must not fail merely because a DingTalk message wording is unfamiliar. That should become a follow-up action.

- [ ] Extend `backend/tests/test_hermes_20_question_real_acceptance.py`.

Test cases:

- daily report gate present passes source-health prerequisite
- daily report gate missing fails only when required
- unfamiliar DingTalk wording becomes action, not hard parse failure

Run:

```bash
python -m pytest backend/tests/test_hermes_20_question_real_acceptance.py backend/tests/test_hermes_20_question_runner.py -q
```

Expected result:

```text
passed
```

Commit after this task:

```bash
git add backend/scripts/hermes_20_question_acceptance.py backend/app/services/hermes_20_question_acceptance.py backend/tests/test_hermes_20_question_real_acceptance.py
git commit -m "Gate Hermes acceptance on daily report facts"
```

## Task 7: Surface Fact Closure Pressure In /manage Without A New Portal

- [ ] Modify `frontend/src/utils/manageDailyReportSurface.js`.

Keep current layout model. Add derived state for source pressure:

```javascript
export function buildFactClosureSurface(factClosure) {
  const fields = Array.isArray(factClosure?.critical_fields)
    ? factClosure.critical_fields
    : []

  return {
    status: factClosure?.status || 'unknown',
    blockedCount: fields.filter((field) => field.status !== 'confirmed').length,
    criticalFields: fields.map((field) => ({
      key: field.field,
      status: field.status,
      source: field.source || '暂无可信来源',
      action: field.action || '等待鑫泰铝业智能大脑追踪',
      traceId: field.trace_id || '',
    })),
  }
}
```

- [ ] Extend `frontend/tests/manageDailyReportSurface.test.js`.

Assertions:

- confirmed facts show zero blocked count
- missing/mismatch facts show blocked count
- missing source displays `暂无可信来源`
- no helper marketing text is introduced

Run:

```bash
node --test frontend/tests/manageDailyReportSurface.test.js
```

Expected result:

```text
pass
```

Commit after this task:

```bash
git add frontend/src/utils/manageDailyReportSurface.js frontend/tests/manageDailyReportSurface.test.js
git commit -m "Expose daily fact closure state for manage dashboard"
```

## Task 8: Add A Production Smoke Report

- [ ] Create `docs/superpowers/reports/daily-report-fact-closure-2026-06-30.md`.

Report sections:

- command used
- database target, with secrets omitted
- output-skill root
- business dates tested
- match rate by day
- five critical fields by day
- MES/WMS read health
- DingTalk evidence count
- missing fields grouped by owner action
- next highest-leverage fixes

- [ ] Run local smoke with current available database.

```bash
python backend\scripts\check_daily_report_output_skill_alignment.py --recent-business-days 3 --output-skill-root "D:\输出skill" --artifact-dir docs\superpowers\reports\daily-report-fact-closure-local --full-differences --json
```

Expected result:

```text
JSON output printed, artifact files written, failure rows explain missing database/table/output-skill causes instead of crashing.
```

- [ ] Run production smoke on the cloud machine according to existing deploy access.

Use the production database and the same `D:\输出skill` content copied or mounted to the production machine.

```bash
python backend/scripts/check_daily_report_output_skill_alignment.py --recent-business-days 3 --output-skill-root "/tmp/output-skill" --artifact-dir docs/superpowers/reports/daily-report-fact-closure-production --full-differences --json
```

Expected result:

```text
Three business-day rows exist. Each row contains field_match_rate, differences, gap_plan, and fact_closure.
```

Commit after this task:

```bash
git add docs/superpowers/reports/daily-report-fact-closure-2026-06-30.md
git commit -m "Record daily report fact closure smoke"
```

## Task 9: Full Verification Gate

- [ ] Run backend focused tests.

```bash
python -m pytest backend/tests/test_check_daily_report_output_skill_alignment_script.py backend/tests/test_daily_report_gap_analysis.py backend/tests/test_daily_report_fact_closure.py backend/tests/test_daily_fact_bundle_service.py backend/tests/test_hermes_daily_fact_update_service.py backend/tests/test_hermes_langchain_tools.py backend/tests/test_hermes_mes_read_service.py backend/tests/test_hermes_20_question_real_acceptance.py backend/tests/test_hermes_20_question_runner.py -q
```

Expected result:

```text
passed
```

- [ ] Run frontend focused tests.

```bash
node --test frontend/tests/manageDailyReportSurface.test.js
```

Expected result:

```text
pass
```

- [ ] Run syntax checks.

```bash
python -m compileall backend/app/services backend/scripts
git diff --check
```

Expected result:

```text
No syntax errors. No whitespace errors.
```

- [ ] Run Hermes real acceptance smoke when production credentials are available.

```bash
python backend\scripts\hermes_20_question_acceptance.py --business-date 2026-06-29 --real-delivery --target "configured-dingtalk-target" --sender-external-id "configured-sender" --output-skill-root "D:\输出skill" --alignment-artifact-dir docs\superpowers\reports\hermes-daily-report-gate-smoke --require-daily-report-gate
```

Expected result:

```text
Hermes answers in Chinese, identifies as 鑫泰铝业智能大脑, attaches source trace, and reports missing facts as actions.
```

Final commit:

```bash
git status --short
git log --oneline -5
```

Expected result:

```text
Only intentional files are changed. Recent commits match the task sequence.
```

## Rollback Plan

- Alignment artifact flags are additive. If production smoke fails, run the old command without the new flags.
- `fact_closure` is additive data on the bundle. If UI or caller code rejects unknown keys, remove only the bundle attachment commit.
- DingTalk extraction is additive and returns empty candidates for unknown messages. If it creates bad candidates, disable only the call from `_apply_dingtalk_supplements(...)` while keeping structured `payload.fact_updates`.
- Hermes acceptance gate is controlled by `--require-daily-report-gate`. If production delivery must continue, omit that flag while fixing the source issue.

## Self-Review Checklist

- [ ] The plan has one P0 outcome: prove daily report facts.
- [ ] No new portal, second dashboard, or product rename is introduced.
- [ ] MES/WMS remains read-only.
- [ ] DingTalk group files/chat remain highest-priority evidence.
- [ ] Data hub projection is not treated as the highest fact source.
- [ ] Hermes remains Chinese-only as `鑫泰铝业智能大脑`.
- [ ] Unknown DingTalk wording does not cause a hard failure.
- [ ] Every implementation task has files, tests, commands, and expected output.
- [ ] Production validation compares against `D:\输出skill`.
- [ ] The plan can be executed task by task with commits after each meaningful slice.
