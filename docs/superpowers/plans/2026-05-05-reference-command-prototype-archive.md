# Reference Command Prototype Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `frontend/src/reference-command/pages/*` 明确标识为历史参考原型，避免它们被误认为当前生产路由页面。

**Architecture:** 保留现有 `reference-command/pages` 文件位置，避免影响仍读取这些文件的契约测试。新增目录 README 说明其非生产挂载边界，同时修正 `docs/current-route-map.md` 中过期的 Command 页面描述，并用现有静态测试锁定该边界。

**Tech Stack:** Markdown 文档、Vue Router 静态契约、pytest 文档/源码一致性测试。

---

### Task 1: Lock The Archive Boundary

**Files:**
- Modify: `backend/tests/test_reference_command_center_spec.py`

- [ ] **Step 1: Write the failing test**

Add a test that expects:

```python
def test_reference_command_pages_are_marked_as_archived_prototypes() -> None:
    readme = _read_repo_file("frontend/src/reference-command/pages/README.md")
    route_map = _read_repo_file("docs/current-route-map.md")
    router = _read_repo_file("frontend/src/router/index.js")

    assert "历史参考原型" in readme
    assert "不挂载到生产路由" in readme
    assert "../reference-command/pages" not in router
    assert "frontend/src/reference-command/pages/CommandLogin.vue" not in route_map
    assert "`/entry` -> `mobile-entry` -> `MobileEntry.vue`" in route_map
```

- [ ] **Step 2: Verify red**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py::test_reference_command_pages_are_marked_as_archived_prototypes -q`

Expected: FAIL because `frontend/src/reference-command/pages/README.md` does not exist yet.

### Task 2: Mark The Prototype Directory

**Files:**
- Add: `frontend/src/reference-command/pages/README.md`

- [ ] **Step 1: Add archive README**

Create a concise README that states:

- Files in this folder are historical reference prototypes.
- Current production routes do not mount this directory.
- Runtime pages live under `frontend/src/views/*` and shells under `frontend/src/layout/*`.
- Keep this folder only as visual/copy reference while older contracts still read it.

- [ ] **Step 2: Verify the test moves past the missing README**

Run the same targeted pytest command.

Expected: still fail until route map stale entries are corrected.

### Task 3: Correct The Current Route Map

**Files:**
- Modify: `docs/current-route-map.md`

- [ ] **Step 1: Replace stale page names**

Update `/login` from `CommandLogin.vue` to `Login.vue`.

Update `/entry` from `CommandEntryHome.vue` to `MobileEntry.vue`.

- [ ] **Step 2: Add the prototype boundary note**

Add one short note that `frontend/src/reference-command/pages/*` is historical reference material and not mounted by current production routes.

- [ ] **Step 3: Verify green**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py::test_reference_command_pages_are_marked_as_archived_prototypes -q`

Expected: PASS.

### Task 4: Update Audit And Validate

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [ ] **Step 1: Add the resolved audit row**

Add `R66` under "已直接修复" describing the F05 archive boundary.

- [ ] **Step 2: Remove F05 from pending issues**

Delete the `F05` row from "待处理问题清单".

- [ ] **Step 3: Run relevant verification**

Run:

```powershell
python -m pytest backend/tests/test_reference_command_center_spec.py -q
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected: all commands exit 0; no whitespace errors.

### Task 5: Commit And Push

**Files:**
- Modify: `backend/tests/test_reference_command_center_spec.py`
- Modify: `docs/current-route-map.md`
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`
- Add: `frontend/src/reference-command/pages/README.md`
- Add: `docs/superpowers/plans/2026-05-05-reference-command-prototype-archive.md`

- [ ] **Step 1: Review staged diff**

Run: `git diff --cached --check` and inspect the staged diff.

- [ ] **Step 2: Commit**

Run:

```powershell
git add backend/tests/test_reference_command_center_spec.py docs/current-route-map.md docs/audits/2026-05-02-cleanup-round2-test-audit.md frontend/src/reference-command/pages/README.md docs/superpowers/plans/2026-05-05-reference-command-prototype-archive.md
git commit -m "docs: 标识参考原型页边界"
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
