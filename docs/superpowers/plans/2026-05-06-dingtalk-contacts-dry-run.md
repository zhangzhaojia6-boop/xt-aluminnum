# DingTalk Contacts Dry Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only DingTalk department contacts diagnostic so production can verify member-list permission and user-match readiness without writing user records.

**Architecture:** Extend `backend/scripts/dingtalk_cli.py` with a `contacts` command. It calls the existing DingTalk service, returns sanitized counts and optional local user-match counts, and never prints contact names, phones, user ids, tokens, or secrets.

**Tech Stack:** Python argparse, SQLAlchemy sessionmaker, pytest.

---

### Task 1: Add Read-Only Contacts Diagnostic

**Files:**
- Modify: `backend/tests/test_dingtalk_cli.py`
- Modify: `backend/scripts/dingtalk_cli.py`
- Modify after verification: `docs/deploy/current-state.md`, `PLANS.md`, `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [x] **Step 1: Write failing tests**

Add tests for:
- sanitized contact counts and local mobile username matching;
- permission error reports `missing_scope=qyapi_get_department_member` without leaking contact values.

- [x] **Step 2: Verify RED**

Run:

```bash
python -m pytest backend/tests/test_dingtalk_cli.py -q
```

Expected: fail because `check_department_contacts()` and `contacts` command do not exist.

- [x] **Step 3: Implement minimal CLI support**

Add `check_department_contacts()`, `contacts --department-id <id>`, plaintext and JSON output handling, and nonzero exit when the permission check fails.

- [x] **Step 4: Verify GREEN**

Run:

```bash
python -m pytest backend/tests/test_dingtalk_cli.py -q
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_current_deploy_state_tracks_current_head_and_validation_evidence backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_exec_plan_tracks_phase_progress_without_hiding_external_gates -q
git diff --check
```
