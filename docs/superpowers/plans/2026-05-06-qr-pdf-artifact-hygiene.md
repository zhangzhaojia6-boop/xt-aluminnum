# QR PDF Artifact Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item S14 by removing tracked QR PDF artifacts and documenting the runtime generation path.

**Architecture:** Keep QR login, QR seed scripts, and the management QR print page unchanged. Treat printable QR PDFs as generated artifacts: ignore them in git, generate them from the running system, and store them outside the repository.

**Tech Stack:** Git ignore rules, Markdown docs, pytest static repository guard.

---

### Task 1: Prove The Current S14 Gap

**Files:**
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`
- Read: `docs/role_qr_codes.pdf`
- Read: `docs/workshop_qr_codes.pdf`
- Read: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Write the failing guard**

Add a static test that asserts:
- `docs/role_qr_codes.pdf` and `docs/workshop_qr_codes.pdf` do not exist.
- `.gitignore` ignores those generated QR PDFs.
- `docs/快速试跑运维手册.md` documents the runtime QR print route.
- The audit file no longer has pending `S14`.
- The audit file has a resolved `R73` row.

- [x] **Step 2: Run the guard**

Run:

```bash
cd backend
python -m pytest tests/test_quick_cloud_trial_docs_and_ops.py::test_qr_pdf_artifacts_are_not_tracked_in_repository -q
```

Expected: FAIL because the two PDF artifacts still exist and S14 is pending.

Result: historical red completed before cleanup; current guard passes with PDFs absent and `R73` recorded.

### Task 2: Remove Artifacts And Document Runtime Path

**Files:**
- Delete: `docs/role_qr_codes.pdf`
- Delete: `docs/workshop_qr_codes.pdf`
- Modify: `.gitignore`
- Modify: `docs/快速试跑运维手册.md`

- [x] **Step 1: Delete the tracked PDFs**

Remove both QR PDF artifacts from git. Do not touch QR login runtime code.

- [x] **Step 2: Add ignore rules**

Add:

```gitignore
docs/*qr_codes.pdf
```

- [x] **Step 3: Document the operator path**

Add a short operations note that QR printable materials should be generated from `/manage/admin/qr-print` in the deployed system and stored outside git.

### Task 3: Update Audit Ledger

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move S14 to resolved**

Add `R73` describing the artifact cleanup and runtime generation path.

- [x] **Step 2: Remove pending S14**

Delete S14 from "待处理问题清单".

- [x] **Step 3: Re-run the static guard**

Run:

```bash
cd backend
python -m pytest tests/test_quick_cloud_trial_docs_and_ops.py::test_qr_pdf_artifacts_are_not_tracked_in_repository -q
```

Expected: PASS.

Result: static guard passes; QR PDFs are absent, `.gitignore` covers generated QR PDFs, and operations docs point to `/manage/admin/qr-print`.

### Task 4: Verification And Commit

**Files:**
- Verify all files touched in Tasks 1-3.

- [x] **Step 1: Run targeted docs/static tests**

```bash
cd backend
python -m pytest tests/test_quick_cloud_trial_docs_and_ops.py -q
```

- [x] **Step 2: Run backend full suite**

```bash
cd backend
python -m pytest tests -q
```

- [x] **Step 3: Run frontend baseline**

```bash
cd frontend
npm test
npm run build
```

- [x] **Step 4: Review diff and commit**

```bash
git diff --check
git status --short
git diff -- .gitignore docs/快速试跑运维手册.md docs/audits/2026-05-02-cleanup-round2-test-audit.md backend/tests/test_quick_cloud_trial_docs_and_ops.py docs/superpowers/plans/2026-05-06-qr-pdf-artifact-hygiene.md
git add .gitignore docs/快速试跑运维手册.md docs/audits/2026-05-02-cleanup-round2-test-audit.md backend/tests/test_quick_cloud_trial_docs_and_ops.py docs/superpowers/plans/2026-05-06-qr-pdf-artifact-hygiene.md docs/role_qr_codes.pdf docs/workshop_qr_codes.pdf
git commit -m "docs: 移除 QR PDF 制品"
git push
```

Result:
- `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q` -> `30 passed, 1 deselected`
- `python -m pytest backend/tests -q --durations=10` -> `651 passed, 123 deselected`
- `npm --prefix frontend test` -> `110 passed`
- `npm --prefix frontend run build` -> pass
- `git diff --check` -> pass
