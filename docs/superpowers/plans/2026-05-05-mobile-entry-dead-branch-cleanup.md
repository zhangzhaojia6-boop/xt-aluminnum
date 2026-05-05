# Mobile Entry Dead Branch Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除移动首页中没有模板入口绑定的死分支，避免首页加载多余模板请求。

**Architecture:** 保持移动首页现有可见流程不变，只移除未被模板调用的函数和它们唯一依赖的 OCR 支持状态。用现有跨层源码契约测试锁定“不再存在无绑定模板分支”，再更新审计清单。

**Tech Stack:** Vue 3 `<script setup>`、Element Plus、pytest 静态契约测试、npm 前端测试与构建。

---

### Task 1: Lock The Dead Branch Contract

**Files:**
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`

- [ ] **Step 1: Write the failing test**

Add a focused assertion that `frontend/src/views/mobile/MobileEntry.vue` no longer imports or calls the unused workshop template branch and no longer defines unbound entry functions:

```python
def test_mobile_entry_has_no_unbound_template_branch() -> None:
    source = _read_repo_file("frontend/src/views/mobile/MobileEntry.vue")

    assert "fetchWorkshopTemplate" not in source
    assert "ocrSupported" not in source
    assert "function handleLogout" not in source
    assert "function goAdvancedReport" not in source
    assert "function goOcr" not in source
```

- [ ] **Step 2: Verify red**

Run: `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py::test_mobile_entry_has_no_unbound_template_branch -q`

Expected: FAIL because the current component still contains `fetchWorkshopTemplate`.

### Task 2: Remove The Unbound Branches

**Files:**
- Modify: `frontend/src/views/mobile/MobileEntry.vue`

- [ ] **Step 1: Remove the unused API import**

Change:

```js
import { fetchCurrentShift, fetchMobileBootstrap, fetchWorkshopTemplate } from '../../api/mobile.js'
```

To:

```js
import { fetchCurrentShift, fetchMobileBootstrap } from '../../api/mobile.js'
```

- [ ] **Step 2: Remove the unused OCR state**

Delete `const ocrSupported = ref(false)`.

- [ ] **Step 3: Remove the extra template fetch from `load()`**

Delete only the `templateKey` block that calls `fetchWorkshopTemplate`. Keep bootstrap/current shift loading and error handling unchanged.

- [ ] **Step 4: Remove unbound functions**

Delete `handleLogout`, `goAdvancedReport`, and `goOcr`. Keep `goReport`, `goLogin`, and `goReportHistory` unchanged.

- [ ] **Step 5: Verify green**

Run: `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`

Expected: PASS.

### Task 3: Update Audit And Validate

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [ ] **Step 1: Add the resolved audit row**

Add `R65` under "已直接修复" describing the F13 cleanup.

- [ ] **Step 2: Remove F13 from pending issues**

Delete the `F13` row from "待处理问题清单".

- [ ] **Step 3: Run relevant verification**

Run:

```powershell
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q
cd frontend; npm run test; npm run build
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected: all commands exit 0; `git diff --check` has no staged or unstaged whitespace errors.

### Task 4: Commit And Push

**Files:**
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`
- Modify: `frontend/src/views/mobile/MobileEntry.vue`
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`
- Add: `docs/superpowers/plans/2026-05-05-mobile-entry-dead-branch-cleanup.md`

- [ ] **Step 1: Review the diff**

Run: `git diff -- backend/tests/test_mobile_entry_copy_consistency.py frontend/src/views/mobile/MobileEntry.vue docs/audits/2026-05-02-cleanup-round2-test-audit.md docs/superpowers/plans/2026-05-05-mobile-entry-dead-branch-cleanup.md`

- [ ] **Step 2: Commit**

Run:

```powershell
git add backend/tests/test_mobile_entry_copy_consistency.py frontend/src/views/mobile/MobileEntry.vue docs/audits/2026-05-02-cleanup-round2-test-audit.md docs/superpowers/plans/2026-05-05-mobile-entry-dead-branch-cleanup.md
git commit -m "refactor: 清理移动首页无绑定死分支"
```

- [ ] **Step 3: Push and confirm remote alignment**

Run:

```powershell
git push
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
```

Expected: working tree clean and `HEAD` equals `origin/main`.
