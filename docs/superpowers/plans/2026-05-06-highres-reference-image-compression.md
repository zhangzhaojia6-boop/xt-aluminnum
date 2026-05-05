# Highres Reference Image Compression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item S15 by reducing tracked highres UI reference PNG size while preserving the 15-panel baseline contract.

**Architecture:** Keep the existing `docs/ui-reference/highres/` PNG baseline and add a static regression test that locks file count, dimensions, and total size. Use Pillow only as a local mechanical compression tool, not as a new runtime dependency or committed script.

**Tech Stack:** Python pytest, built-in PNG header reads, Pillow for one-time PNG recompression, Markdown audit docs.

---

### Task 1: Add A Red Size-Budget Gate

**Files:**
- Modify: `backend/tests/test_reference_command_center_spec.py`
- Create: `docs/superpowers/plans/2026-05-06-highres-reference-image-compression.md`

- [ ] **Step 1: Add a PNG header helper**

Add `_read_png_size(path: Path) -> tuple[int, int]` near the existing repo file helpers. Read the PNG signature and IHDR width/height bytes directly so the test does not depend on image libraries.

- [ ] **Step 2: Add the failing S15 test**

Add `test_highres_reference_images_keep_size_budget_and_dimensions()` to assert:
- the 15 expected files exist in `docs/ui-reference/highres/`
- no extra PNG files exist in that directory
- every image stays `1672 x 941`
- total bytes are `<= 5_600_000`
- `docs/ui-reference/REFERENCE_MANIFEST.md` records `尺寸门槛`, `1672 x 941`, `体积门槛`, and `<= 5.6 MB`

- [ ] **Step 3: Run the red test**

Run:

```powershell
python -m pytest backend/tests/test_reference_command_center_spec.py::test_highres_reference_images_keep_size_budget_and_dimensions -q
```

Expected: FAIL because current highres PNG total is about 6.11 MB and the manifest has no budget section.

### Task 2: Compress And Document The Highres Baseline

**Files:**
- Modify: `docs/ui-reference/highres/*.png`
- Modify: `docs/ui-reference/REFERENCE_MANIFEST.md`
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [ ] **Step 1: Recompress PNGs mechanically**

Use a one-time Pillow shell command to rewrite each highres PNG with `optimize=True` and `compress_level=9`. Preserve image dimensions and filenames.

- [ ] **Step 2: Update the manifest**

Add a concise baseline budget section documenting:
- dimensions stay `1672 x 941`
- tracked highres PNG total must stay `<= 5.6 MB`
- images remain visual and information-architecture references, not product-embedded screenshots

- [ ] **Step 3: Update the audit**

Move S15 from pending to resolved by adding `R74` and deleting the S15 pending row.

### Task 3: Verify And Commit

**Files:**
- Verify all changed files and binary image edits.

- [ ] **Step 1: Run targeted tests**

Run:

```powershell
python -m pytest backend/tests/test_reference_command_center_spec.py backend/tests/test_quick_cloud_trial_docs_and_ops.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full project checks**

Run:

```powershell
python -m pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

Expected: PASS. Existing CRLF warnings from `git diff --check` are acceptable only if the command exits 0.

- [ ] **Step 3: Review, commit, and push**

Run:

```powershell
git status --short
git diff --stat
git add backend/tests/test_reference_command_center_spec.py docs/ui-reference/REFERENCE_MANIFEST.md docs/audits/2026-05-02-cleanup-round2-test-audit.md docs/superpowers/plans/2026-05-06-highres-reference-image-compression.md docs/ui-reference/highres/*.png
git commit -m "docs: 压缩 highres 参考图"
git push
```

Expected: `main` and `origin/main` point to the new commit.
