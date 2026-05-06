# Local Weight Quality Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent `mobile_coil_agg` raw kg values from leaking into reconciliation comparisons as ton-level production output.

**Architecture:** Keep raw coil weights unchanged in `ShiftProductionData`. Quality service was audited and its direct sum is only a zero guard, so kg-to-ton conversion does not change any observable behavior there. Add source-aware ton conversion at the reconciliation read/compare points that currently use direct SQL sums.

**Tech Stack:** Python, SQLAlchemy ORM, pytest, existing SQLite test fixtures.

---

### Task 1: Audit the Quality Check Entry

**Files:**
- Read: `backend/app/services/quality_service.py`

- [ ] **Step 1: Confirm no visible kg leak**

Confirm the direct `func.sum(ShiftProductionData.output_weight)` in quality checks is only used for `output_weight <= 0`.

- [ ] **Step 2: Do not change quality code this round**

Because positive kg and positive tons both satisfy the zero guard, there is no failing behavior to reproduce for quality.

### Task 2: Reproduce the Reconciliation Leak

**Files:**
- Modify: `backend/tests/test_reconciliation_granularity.py`

- [ ] **Step 1: Add failing direct service tests**

Add coverage for:
- `production_vs_mes`: local `mobile_coil_agg` output `250_000.0` should compare equal to external MES metric `250.0`.
- `energy_vs_production`: energy exists and local `mobile_coil_agg` output `250_000.0` should store production side as `250.0` tons.

- [ ] **Step 2: Run the red tests**

Run:

```bash
python -m pytest backend/tests/test_reconciliation_granularity.py::test_reconciliation_treats_mobile_coil_aggregate_output_as_tons -q
```

Expected before implementation: fail because source B is `250000.0`, not `250.0`.

### Task 3: Implement Source-Aware Reconciliation Reads

**Files:**
- Modify: `backend/app/services/reconciliation_service.py`

- [ ] **Step 1: Replace raw SQL output sums**

In reconciliation, query `ShiftProductionData` rows and sum `output_weight` with:

```python
if item.data_source == 'mobile_coil_agg':
    output_tons = output_weight / 1000
else:
    output_tons = output_weight
```

- [ ] **Step 2: Keep non-coil sources unchanged**

Do not change quality checks, `MobileShiftReport`, external MES metrics, energy records, or persisted raw coil values.

### Task 4: Verify and Commit

**Files:**
- Verify: targeted tests, backend tests if touched behavior warrants it, diff check

- [ ] **Step 1: Run targeted tests**

```bash
python -m pytest backend/tests/test_reconciliation_granularity.py -q
```

- [ ] **Step 2: Run broader backend regression**

```bash
python -m pytest backend/tests -q
```

- [ ] **Step 3: Run diff check**

```bash
git diff --check
```

- [ ] **Step 4: Commit and push only touched files**

```bash
git add backend/app/services/reconciliation_service.py backend/tests/test_reconciliation_granularity.py docs/superpowers/plans/2026-05-06-local-weight-quality-reconciliation.md
git commit -m "fix: 统一质量对账卷级吨口径"
git push origin main
```
