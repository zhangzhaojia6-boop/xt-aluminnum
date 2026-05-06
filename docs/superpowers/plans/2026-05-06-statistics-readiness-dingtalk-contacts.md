# Statistics Readiness DingTalk Contacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the statistics readiness gate able to optionally verify DingTalk department contact permission with a sanitized, read-only check.

**Architecture:** Keep the default readiness command non-networked beyond existing local checks. Add an explicit `--check-dingtalk-contacts` flag that calls the existing `dingtalk_cli` diagnostic and surfaces missing contact permission as a warning with structured stats.

**Tech Stack:** Python argparse, existing readiness script, pytest.

---

### Task 1: Add Opt-In DingTalk Contact Permission Check

**Files:**
- Modify: `backend/tests/test_statistics_module_ready_script.py`
- Modify: `backend/scripts/check_statistics_module_ready.py`
- Modify after verification: `docs/deploy/current-state.md`, `PLANS.md`, `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [x] **Step 1: Write failing tests**

Cover default no-op behavior and explicit `check_dingtalk_contacts=True` missing-scope warning.

- [x] **Step 2: Verify RED**

Run:

```bash
python -m pytest backend/tests/test_statistics_module_ready_script.py -q
```

Expected: fail before the new arguments exist.

- [x] **Step 3: Implement minimal readiness support**

Add optional function parameters, CLI flags, structured stats, and warning code `DINGTALK_CONTACTS_PERMISSION_MISSING`.

- [x] **Step 4: Verify GREEN**

Run:

```bash
python -m pytest backend/tests/test_statistics_module_ready_script.py -q
```

Expected: pass.
