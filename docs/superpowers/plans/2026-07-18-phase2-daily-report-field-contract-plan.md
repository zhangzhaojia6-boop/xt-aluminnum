# Phase 2 Daily Report Field Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 127 个投产判分字段建立代码、测试、文档共用的唯一合同，并让生产 compare-only 门禁同时暴露已出现字段匹配率、规范覆盖率和 `reference_absent`。

**Architecture:** 保留现有 130 个模板展示字段，不破坏日报渲染；新增独立的 127 字段规范合同作为判分和来源治理的唯一入口。事实优先级集中为“钉钉、授权纠错、MES/WMS、扫码补录、数据中枢投影、历史、RAG 解释”，答案钥匙永远在来源合同之外，只由对齐器读取。

**Tech Stack:** Python、dataclass、FastAPI 服务层、pytest、PostgreSQL 生产只读样本、GitHub Actions、Markdown 生成检查。

**Parent spec:** `docs/superpowers/specs/2026-07-16-production-readiness-real-fact-closure-prd.md`

**Start evidence:** `docs/superpowers/reports/2026-07-18-phase2-fact-contract-baseline.md`

---

## File Map

- Create `backend/app/domain/daily_report_field_contract.py`: 127 字段、单位、业务时间、容差、来源轨和参考角色的唯一合同。
- Modify `backend/app/services/report/template_daily_field_contract.py`: 保留旧导入接口，改为从规范合同导出字段分组和查询函数。
- Modify `backend/app/domain/metric_contracts.py`: 17 个 Hermes 指标继续保留证据锚合同，但容差必须复用 127 字段合同。
- Modify `backend/app/services/report/daily_fact_bundle.py`: 使用统一来源轨优先级，确保钉钉高于授权纠错，答案钥匙不能成为真实来源。
- Modify `backend/app/services/report/template_daily_fact_sources.py`: 使用统一来源轨优先级，确保 MES/WMS 高于扫码/owner 填报，投影和历史继续降级。
- Modify `backend/app/services/report/output_skill_reconciliation.py`: 输出双分母、N/A、`reference_absent` 和规范覆盖率。
- Modify `backend/app/services/hermes_day1_harness_service.py`: 读取可选 N/A sidecar，并把合同阻塞状态传给对齐结果。
- Modify `backend/scripts/check_daily_report_output_skill_alignment.py`: 在 JSON、Markdown 和终端输出新增合同指标。
- Create `backend/scripts/check_daily_report_field_contract.py`: 可在 CI 和生产独立运行的静态合同门禁。
- Create `backend/scripts/render_daily_report_field_contract.py`: 从代码合同生成当前 Markdown，不手工维护 127 行。
- Create `docs/hermes/daily-report-field-contract.md`: 自动生成的 127 字段合同表。
- Add/modify focused tests listed below.

### Task 1: Freeze the 127-field canonical contract

**Files:**
- Create: `backend/app/domain/daily_report_field_contract.py`
- Modify: `backend/app/services/report/template_daily_field_contract.py`
- Create: `backend/tests/test_daily_report_field_contract.py`
- Modify: `backend/tests/test_core_metric_contracts.py`

- [x] **Step 1: Write the failing contract-count test**

Test that the template keeps 130 display fields, the normative contract contains exactly 127 unique fields, and the three template-only fields are explicitly named with non-empty reasons.

- [x] **Step 2: Run the focused test and verify the current code fails**

Run:

```powershell
uv run --with-requirements backend/requirements.txt --with pytest pytest -q backend/tests/test_daily_report_field_contract.py
```

Expected: FAIL because `daily_report_field_contract.py` and the 127-field contract do not exist.

- [x] **Step 3: Add the immutable field contract**

Each `DailyReportFieldContract` must expose at least:

```python
field_name: str
group: str
unit: str
business_time_scope: str
tolerance: float
source_lanes: tuple[str, ...]
reference_role: str = "compare_only"
```

Use runtime constants for 07:50, 10:00, 09:30 and 10:00; do not duplicate free-form time strings. Tolerances must be non-negative and at most 20; percentage and per-ton fields use at most 0.2.

- [x] **Step 4: Preserve compatibility for template callers**

`field_group()`, `fields_for_group()`, `all_contract_fields()` and `group_missing_fields()` must retain their current callable behavior. Add a clearly named normative-field accessor instead of silently changing `all_contract_fields()` from 130 to 127.

- [x] **Step 5: Make Hermes metric tolerances reuse the canonical field contract**

Existing source-anchor and value-kind logic in `metric_contracts.py` stays intact. The 17 Hermes metrics may be a subset, but any shared field must have the same unit and tolerance as the 127-field contract.

- [x] **Step 6: Run focused and adjacent tests**

```powershell
uv run --with-requirements backend/requirements.txt --with pytest pytest -q backend/tests/test_daily_report_field_contract.py backend/tests/test_core_metric_contracts.py backend/tests/test_template_daily_report.py
```

- [x] **Step 7: Commit the canonical contract**

```text
feat(report): define canonical 127-field contract
```

### Task 2: Unify runtime fact-source priority

**Files:**
- Modify: `backend/app/domain/daily_report_field_contract.py`
- Modify: `backend/app/services/report/daily_fact_bundle.py`
- Modify: `backend/app/services/report/template_daily_fact_sources.py`
- Modify: `backend/tests/test_daily_fact_bundle_service.py`
- Modify: `backend/tests/test_template_daily_fact_sources.py`
- Modify: `backend/tests/test_daily_report_field_contract.py`

- [x] **Step 1: Rewrite the contradictory tests first**

Lock this order:

```text
dingtalk_evidence
authorized_correction
mes_wms_readonly
scan_supplement
data_hub_projection
historical_record
rag_explanation_only
```

Add tests proving DingTalk wins over root-owner correction, MES/WMS wins over owner/scan data, RAG cannot produce a realtime number, and `output_skill` has no real-source lane.

- [x] **Step 2: Run the tests and verify they fail for the current priorities**

Expected failures include the current `root_owner_correction=100 > dingtalk_supplement=90` and `owner_daily=100 > mes_evidence=20` behavior.

- [x] **Step 3: Implement one source-lane resolver and one score table**

Both fact builders must call the same resolver. Keep source-specific trace validation; this task changes adoption order, not evidence requirements.

- [x] **Step 4: Verify conflicts remain visible**

A lower-priority source must be retained in conflict/trace diagnostics even when not adopted. Do not delete conflicting facts to make tests pass.

- [x] **Step 5: Run focused and adjacent source tests**

```powershell
uv run --with-requirements backend/requirements.txt --with pytest pytest -q backend/tests/test_daily_report_field_contract.py backend/tests/test_template_daily_fact_sources.py backend/tests/test_daily_fact_bundle_service.py backend/tests/test_hermes_root_owner_evidence_service.py
```

- [x] **Step 6: Commit the priority unification**

```text
fix(report): enforce canonical fact-source priority
```

### Task 3: Add dual-denominator and explicit N/A handling

**Files:**
- Modify: `backend/app/services/report/output_skill_reconciliation.py`
- Modify: `backend/app/services/hermes_day1_harness_service.py`
- Modify: `backend/scripts/check_daily_report_output_skill_alignment.py`
- Modify: `backend/tests/test_output_skill_reconciliation.py`
- Modify: `backend/tests/test_hermes_day1_output_skill_alignment.py`
- Modify: `backend/tests/test_check_daily_report_output_skill_alignment_script.py`

- [x] **Step 1: Write failing reconciliation tests**

Cover these cases:

1. 124 parsed reference fields, 0 N/A -> 3 `reference_absent`, normative denominator 127, gate blocked.
2. 124 parsed fields, 3 valid explicit N/A -> denominator 124, no `reference_absent`.
3. Unknown or duplicate N/A field -> contract error, gate blocked.
4. Answer-key-present match rate and normative coverage rate are both returned.
5. Reference adoption mode remains unable to pass the real-source gate.

- [x] **Step 2: Run the tests and verify current output lacks these fields**

- [x] **Step 3: Implement a structured N/A sidecar**

For `2026-7-17_日报正文.txt`, allow optional `2026-7-17_日报正文.na.json`:

```json
{"not_applicable": ["field_name"]}
```

Only canonical field keys are accepted. Absence of the sidecar means no N/A declarations; omission is never interpreted as N/A.

- [x] **Step 4: Extend reconciliation without breaking old keys**

Keep `field_match_rate`, `matched_fields` and `expected_fields` for compatibility. Add:

```text
reference_present_fields
declared_na_fields
invalid_na_fields
reference_absent_fields
reference_absent_count
normative_fields
normative_denominator
normative_matched_fields
normative_coverage_rate
```

The alignment status is `blocked` when `reference_absent_fields` or `invalid_na_fields` is non-empty.

- [x] **Step 5: Propagate fields through JSON, Markdown and terminal output**

The artifact must list every absent field and explain that the answer key is comparison-only.

- [x] **Step 6: Run focused and adjacent tests**

```powershell
uv run --with-requirements backend/requirements.txt --with pytest pytest -q backend/tests/test_output_skill_reconciliation.py backend/tests/test_hermes_day1_output_skill_alignment.py backend/tests/test_check_daily_report_output_skill_alignment_script.py backend/tests/test_daily_fact_closure_task.py
```

- [x] **Step 7: Commit the denominator gate**

```text
feat(report): block undeclared reference gaps
```

### Task 4: Generate and verify the contract document

**Files:**
- Create: `backend/scripts/render_daily_report_field_contract.py`
- Create: `backend/scripts/check_daily_report_field_contract.py`
- Create: `docs/hermes/daily-report-field-contract.md`
- Create: `backend/tests/test_daily_report_field_contract_scripts.py`
- Modify: `docs/hermes/fact-source-map.md`

- [x] **Step 1: Write failing script tests**

Test deterministic Markdown rendering, `--check` drift detection, machine-readable JSON output, exact field count, time constants, source order and maximum tolerance.

- [x] **Step 2: Implement the renderer and static gate**

The renderer reads only code contracts. The static gate exits non-zero on duplicate/missing fields, invalid units, invalid times, source-order drift, tolerance above 20, or stale generated documentation.

- [x] **Step 3: Generate the Markdown document**

The document header must state that `D:\输出skill` is compare-only and RAG cannot create realtime numbers.

- [x] **Step 4: Link the generated contract from the fact-source map**

Do not hand-copy 127 rows into multiple documents.

- [x] **Step 5: Run script and documentation checks**

```powershell
uv run --with-requirements backend/requirements.txt python backend/scripts/render_daily_report_field_contract.py --check
uv run --with-requirements backend/requirements.txt python backend/scripts/check_daily_report_field_contract.py --json
uv run --with-requirements backend/requirements.txt --with pytest pytest -q backend/tests/test_daily_report_field_contract_scripts.py
git diff --check
```

- [x] **Step 6: Commit the generated contract documentation**

```text
docs(report): publish generated field contract
```

### Task 5: Run review and full Phase 2 regression

**Files:**
- Review all Phase 2 changes
- Update: `docs/superpowers/reports/2026-07-18-phase2-fact-contract-baseline.md` only with newly executed evidence

- [ ] **Step 1: Run focused Phase 2 regression**

Run all tests touched above plus business time, DailyFactBundle, template report, Hermes 20-question contract and alignment script tests.

- [ ] **Step 2: Run backend full regression and frontend build through CI-equivalent commands**

Do not claim full regression from a focused subset.

- [ ] **Step 3: Perform specification review**

An independent reviewer checks every #36 acceptance criterion against code and tests. Fix findings and repeat until approved.

- [ ] **Step 4: Perform code-quality review**

A different reviewer checks source-priority regressions, import cycles, compatibility keys, unsafe answer-key adoption and missing tests. Fix findings and repeat until approved.

- [ ] **Step 5: Verify idempotency and rollback locally**

Run the generated-doc command twice and prove the second run leaves a clean diff. Run the old and new reconciliation fixtures to prove existing fields remain compatible.

### Task 6: Deploy and close the Phase 2 production loop

**Files:**
- Modify: `.github/workflows/daily-report-alignment-prod.yml` only if production artifacts cannot expose the new contract fields without it
- Update: `docs/superpowers/plans/2026-07-16-production-readiness-closed-loop-execution-plan.md`
- Create: `docs/superpowers/reports/2026-07-18-phase2-fact-contract-closure.md`

- [ ] **Step 1: Push the Phase 2 branch and require green CI**

- [ ] **Step 2: Merge through the normal reviewed path and deploy the exact accepted SHA**

- [ ] **Step 3: Run the production static contract gate**

Expected: exit 0, 127 normative fields, source order fixed, all tolerances at most 20, generated document current.

- [ ] **Step 4: Rerun 2026-07-15 through 2026-07-17 compare-only alignment**

Expected for Phase 2: the business alignment may remain below 90% and therefore remain red for Phase 4, but every day must now report both rates and exactly explain each `reference_absent`. A low match rate must not be relabeled as a Phase 2 contract failure.

- [ ] **Step 5: Exercise real rollback and redeploy**

Use the controlled production workflow to return to the recorded pre-Phase-2 SHA, verify services and `/readyz`, then redeploy the accepted Phase 2 SHA and rerun the static gate. Preserve database backup and workflow links.

- [ ] **Step 6: Archive closure evidence and close #36**

Only mark Phase 2 complete when code, tests, generated docs, production static gate, compare-only diagnostics, review and rollback evidence all exist. Then update the master plan checkboxes, close GitHub #36 and move to Phase 3 without claiming the 90% Phase 4 target is complete.
