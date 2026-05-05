# Master Legacy Route Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 关闭 F04：把未挂载的主数据旧页面标识为历史兼容页，并用契约测试锁定 `/master/*` 兼容路由的当前重定向行为。

**Architecture:** 不删除 `Employee.vue`、`Equipment.vue`、`MachineWizard.vue`、`ShiftConfig.vue`、`Team.vue`，因为部分文件仍被静态契约测试读取。新增 `frontend/src/views/master/README.md` 标明运行时与历史页边界，补充 `docs/current-route-map.md` 的 `/master/*` 兼容路由说明，并用 pytest 静态契约锁定路由不再挂载这些旧页。

**Tech Stack:** Vue Router 静态源码契约、Markdown 文档、pytest。

---

### Task 1: Lock The Master Legacy Route Contract

**Files:**
- Modify: `backend/tests/test_reference_command_center_spec.py`

- [ ] **Step 1: Write the failing test**

Add a test that expects:

```python
def test_legacy_master_routes_redirect_without_mounting_orphan_pages() -> None:
    router = _read_repo_file("frontend/src/router/index.js")
    route_map = _read_repo_file("docs/current-route-map.md")
    readme = _read_repo_file("frontend/src/views/master/README.md")

    for redirect in [
        "{ path: '/master/team', name: 'master-team', redirect: '/manage/master' }",
        "{ path: '/master/employee', name: 'master-employee', redirect: '/manage/master' }",
        "{ path: '/master/equipment', name: 'master-equipment', redirect: '/manage/master' }",
        "{ path: '/master/shift-config', name: 'master-shift-config', redirect: '/manage/master' }",
    ]:
        assert redirect in router

    for orphan_import in [
        "const Employee = () => import('../views/master/Employee.vue')",
        "const Equipment = () => import('../views/master/Equipment.vue')",
        "const MachineWizard = () => import('../views/master/MachineWizard.vue')",
        "const ShiftConfig = () => import('../views/master/ShiftConfig.vue')",
        "const Team = () => import('../views/master/Team.vue')",
    ]:
        assert orphan_import not in router

    assert "不挂载到生产路由" in readme
    assert "`/master/team`、`/master/employee`、`/master/equipment`、`/master/shift-config` -> `/manage/master`" in route_map
```

- [ ] **Step 2: Verify red**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py::test_legacy_master_routes_redirect_without_mounting_orphan_pages -q`

Expected: FAIL because `frontend/src/views/master/README.md` does not exist yet.

### Task 2: Mark The Master Page Boundary

**Files:**
- Add: `frontend/src/views/master/README.md`

- [ ] **Step 1: Add README**

Document:

- Runtime master pages: `Workshop.vue`, `UserManagement.vue`, `WorkshopTemplateConfig.vue`, `RuleConfigCenter.vue`, `QRCodePrint.vue`, `AliasMapping.vue`.
- Historical compatibility/reference pages: `Employee.vue`, `Equipment.vue`, `MachineWizard.vue`, `ShiftConfig.vue`, `Team.vue`.
- Historical pages are not mounted by production routes.
- `/master/*` compatibility routes redirect to `/manage/*`.

- [ ] **Step 2: Verify the test moves past missing README**

Run the same targeted pytest command.

Expected: still fail until `docs/current-route-map.md` includes the explicit compatibility route row.

### Task 3: Document The Compatibility Routes

**Files:**
- Modify: `docs/current-route-map.md`

- [ ] **Step 1: Add `/master/*` compatibility details**

Under "Desktop 兼容链路", add:

```markdown
- `/master/team`、`/master/employee`、`/master/equipment`、`/master/shift-config` -> `/manage/master`
- `/master/alias` -> `/manage/alias`
- `/master/workshop-template`、`/master/workshop-templates`、`/master/yield-rate-map` -> `/manage/admin/templates`
- `/master/rules` -> `/manage/admin/rules`
```

- [ ] **Step 2: Verify green**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py::test_legacy_master_routes_redirect_without_mounting_orphan_pages -q`

Expected: PASS.

### Task 4: Update Audit And Validate

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [ ] **Step 1: Add resolved audit row**

Add `R67` under "已直接修复" describing F04.

- [ ] **Step 2: Remove F04 from pending issues**

Delete the `F04` row.

- [ ] **Step 3: Run verification**

Run:

```powershell
python -m pytest backend/tests/test_reference_command_center_spec.py -q
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q
npm run test
npm run build
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected: all commands exit 0; no whitespace errors.

### Task 5: Commit And Push

**Files:**
- Modify: `backend/tests/test_reference_command_center_spec.py`
- Modify: `docs/current-route-map.md`
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`
- Add: `frontend/src/views/master/README.md`
- Add: `docs/superpowers/plans/2026-05-05-master-legacy-route-contract.md`

- [ ] **Step 1: Review and stage**

Run `git diff`, then stage only the files listed above.

- [ ] **Step 2: Commit**

Run:

```powershell
git commit -m "test: 锁定主数据兼容路由边界"
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
