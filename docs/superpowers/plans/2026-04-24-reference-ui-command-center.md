# Reference UI Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reference-image-aligned, three-surface production command UI while preserving old URLs and route names.

**Architecture:** Implement surface separation first, then a reusable reference UI component layer, then map the entry/review/admin pages to reference-style modules. Backend work adds surface-aware aggregation contracts without removing existing `/api/v1/*` endpoints.

**Tech Stack:** Vue 3, Vue Router, Pinia, Element Plus, Vite, FastAPI, pytest, Playwright.

---

## File Structure

### Frontend Shells And Routing

- Modify `frontend/src/router/index.js`: add `/admin` routes, preserve old route names and redirects, enforce surface guards.
- Modify `frontend/src/stores/auth.js`: add explicit surface policy getters while keeping existing getters.
- Modify `frontend/src/config/navigation.js`: split entry/review/admin navigation and remove cross-surface leakage.
- Create `frontend/src/layout/AdminShell.vue`: management-only shell.
- Modify `frontend/src/layout/EntryShell.vue`: keep entry-only shell, improve visual baseline.
- Modify `frontend/src/views/review/ReviewLayout.vue` and `frontend/src/layout/AppShell.vue`: evolve into review shell behavior without admin/entry nav leakage.

### Reference UI Components

- Create `frontend/src/components/reference/ReferencePageFrame.vue`: numbered page frame.
- Create `frontend/src/components/reference/ReferenceModuleCard.vue`: white card with reference border, density and actions.
- Create `frontend/src/components/reference/ReferenceKpiTile.vue`: icon, value, unit, trend.
- Create `frontend/src/components/reference/ReferenceStatusTag.vue`: compact status tag.
- Create `frontend/src/components/reference/ReferenceDataTable.vue`: compact table wrapper.
- Create `frontend/src/components/reference/ReferenceFlowGraphic.vue`: production/data flow visual.
- Modify `frontend/src/styles.css`: tokens, card/table/button density, responsive rules, motion.

### Page Mapping

- Modify `frontend/src/views/Login.vue`: reference-style role handoff.
- Modify `frontend/src/views/mobile/MobileEntry.vue`: reference-style entry terminal home.
- Modify `frontend/src/views/mobile/DynamicEntryForm.vue`: reference-style step flow.
- Modify `frontend/src/views/review/OverviewCenter.vue`: 16 module map without mobile preview module.
- Modify `frontend/src/views/review/ReviewTaskCenter.vue`: reference review task table.
- Modify `frontend/src/views/review/IngestionCenter.vue`: move to admin surface while preserving route compatibility.
- Modify `frontend/src/views/reports/LiveDashboard.vue`: admin ops view.
- Modify `frontend/src/views/review/GovernanceCenter.vue`: admin governance view.
- Modify `frontend/src/views/master/WorkshopTemplateConfig.vue`: admin template/master view.
- Modify `frontend/src/views/review/CostAccountingCenter.vue`: reference cost page.
- Modify `frontend/src/views/assistant/BrainCenter.vue`: reference AI brain page.

### Backend Aggregation

- Create `backend/app/schemas/command.py`: module/kpi/table/trend/action schemas.
- Create `backend/app/services/command_service.py`: surface-aware command overview builders.
- Create `backend/app/routers/command.py`: `/api/v1/command/*` and `/api/v1/admin/*` aggregation endpoints.
- Modify `backend/app/routers/__init__.py` and `backend/app/main.py`: mount command router.

### Tests And Audit

- Modify `backend/tests/test_mobile_entry_copy_consistency.py`: static route/nav/visual contract assertions.
- Create `backend/tests/test_command_routes.py`: aggregation schema and surface tests.
- Modify `frontend/e2e/review-runtime.spec.js`: route compatibility and review surface smoke.
- Add `frontend/e2e/admin-surface.spec.js`: admin route and nav isolation smoke.
- Modify `frontend/tmp_visual_audit.cjs`: reference-image checklist, three-surface screenshots.
- Update `docs/launch-readiness-checklist.md` and `docs/known-gaps-and-todos.md`.

---

## Task 1: Lock Three-Surface Routing And Compatibility Tests

**Files:**
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/stores/auth.js`
- Modify: `frontend/src/config/navigation.js`

- [ ] **Step 1: Add static tests for required route compatibility**

Add assertions to `backend/tests/test_mobile_entry_copy_consistency.py`:

```python
def test_reference_ui_keeps_legacy_route_names_and_urls() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "name: 'mobile-entry'" in source
    assert "name: 'review-overview-home'" in source
    assert "name: 'factory-dashboard'" in source
    assert "name: 'workshop-dashboard'" in source
    assert "name: 'master-workshop'" in source
    assert "path: '/mobile'" in source
    assert "redirect: (to) => ({ path: '/entry'" in source
    assert "path: '/dashboard/factory', redirect: '/review/factory'" in source
    assert "path: 'master/workshop'" in source
```

- [ ] **Step 2: Add static tests for three-surface isolation**

Add:

```python
def test_reference_ui_declares_three_independent_surfaces() -> None:
    router_source = _read_repo_file("frontend/src/router/index.js")
    nav_source = _read_repo_file("frontend/src/config/navigation.js")
    auth_source = _read_repo_file("frontend/src/stores/auth.js")

    assert "path: '/entry'" in router_source
    assert "path: '/review'" in router_source
    assert "path: '/admin'" in router_source
    assert "entrySurface()" in auth_source
    assert "reviewSurface()" in auth_source
    assert "adminSurface()" in auth_source
    assert "const entryNavigation" in nav_source
    assert "const reviewNavigation" in nav_source
    assert "const adminNavigation" in nav_source
```

- [ ] **Step 3: Run static tests and confirm they fail**

Run: `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`

Expected: fail because `/admin`, surface getters, and admin navigation do not exist yet.

- [ ] **Step 4: Add auth surface getters**

In `frontend/src/stores/auth.js`, add getters while preserving existing getters:

```js
entrySurface() {
  return this.canAccessFillSurface
},
reviewSurface() {
  return this.canAccessReviewSurface
},
adminSurface() {
  return this.canAccessDesktopConfig
},
superAdminSurface() {
  return this.isAdmin && this.entrySurface && this.reviewSurface && this.adminSurface
},
defaultSurface() {
  if (this.entrySurface && !this.reviewSurface && !this.adminSurface) return 'entry'
  if (this.reviewSurface && !this.adminSurface) return 'review'
  if (this.adminSurface) return 'admin'
  return 'login'
}
```

- [ ] **Step 5: Split navigation config**

In `frontend/src/config/navigation.js`:

- Keep route meta names unchanged.
- Add `entryNavigation`, `reviewNavigation`, and `adminNavigation`.
- Remove `mobile-entry` and `entry-drafts` from review navigation.
- Move ops/governance/template/master-oriented items into admin navigation.
- Update `buildShellNavigation(zone, auth)` to return by zone.

- [ ] **Step 6: Add `/admin` route shell**

In `frontend/src/router/index.js`:

- Add lazy import `const AdminShell = () => import('../layout/AdminShell.vue')`.
- Add `/admin` route with `zone: 'admin'`.
- Add children for admin overview, ingestion, ops, governance, master/templates/users/roadmap.
- Preserve old `/master/*` and `/review/template-center` compatibility via redirects or existing route names.

- [ ] **Step 7: Update router guards**

In `frontend/src/router/index.js`:

- Keep fill-only hard redirect to `/entry`.
- Add `zone === 'admin'` guard using `authStore.adminSurface`.
- Ensure old desktop config routes redirect to default/admin where appropriate.

- [ ] **Step 8: Run tests**

Run: `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`

Expected: pass.

- [ ] **Step 9: Run build**

Run: `npm --prefix frontend run build`

Expected: pass.

---

## Task 2: Create AdminShell And Clean Cross-Surface Residue

**Files:**
- Create: `frontend/src/layout/AdminShell.vue`
- Modify: `frontend/src/layout/AppShell.vue`
- Modify: `frontend/src/layout/EntryShell.vue`
- Modify: `frontend/src/views/review/ReviewLayout.vue`
- Test: `backend/tests/test_mobile_entry_copy_consistency.py`

- [ ] **Step 1: Add tests for shell separation**

Add:

```python
def test_shells_do_not_leak_cross_surface_navigation() -> None:
    entry = _read_repo_file("frontend/src/layout/EntryShell.vue")
    app_shell = _read_repo_file("frontend/src/layout/AppShell.vue")
    admin = _read_repo_file("frontend/src/layout/AdminShell.vue")

    assert "独立填报端" in entry
    assert "审阅任务" not in entry
    assert "主数据" not in entry
    assert "AI 助手" in app_shell
    assert "管理控制台" in admin
    assert "现场填报" not in admin
```

- [ ] **Step 2: Run test to confirm failure**

Run: `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py::test_shells_do_not_leak_cross_surface_navigation -q`

Expected: fail because `AdminShell.vue` is missing.

- [ ] **Step 3: Implement `AdminShell.vue`**

Create a shell with:

- Reference-style topbar.
- Admin navigation from `buildShellNavigation('admin', auth)`.
- No entry links.
- Optional super admin switch buttons to review/entry.

- [ ] **Step 4: Clean `AppShell.vue` surface wording**

Make `AppShell.vue` render surface-specific labels:

- `review`: `审阅指挥台`
- `admin`: `管理控制台`
- `desktop`: `兼容配置台`

Avoid long explanatory copy.

- [ ] **Step 5: Keep `EntryShell.vue` entry-only**

Use only:

- `独立填报端`
- `今日任务`
- `历史`
- `草稿`

No review/admin actions.

- [ ] **Step 6: Run static test**

Run: `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`

Expected: pass.

---

## Task 3: Build Reference UI Component Layer

**Files:**
- Create: `frontend/src/components/reference/ReferencePageFrame.vue`
- Create: `frontend/src/components/reference/ReferenceModuleCard.vue`
- Create: `frontend/src/components/reference/ReferenceKpiTile.vue`
- Create: `frontend/src/components/reference/ReferenceStatusTag.vue`
- Create: `frontend/src/components/reference/ReferenceDataTable.vue`
- Create: `frontend/src/components/reference/ReferenceFlowGraphic.vue`
- Modify: `frontend/src/styles.css`
- Test: `backend/tests/test_mobile_entry_copy_consistency.py`

- [ ] **Step 1: Add static component contract test**

Add:

```python
def test_reference_ui_component_layer_exists() -> None:
    for path in [
        "frontend/src/components/reference/ReferencePageFrame.vue",
        "frontend/src/components/reference/ReferenceModuleCard.vue",
        "frontend/src/components/reference/ReferenceKpiTile.vue",
        "frontend/src/components/reference/ReferenceStatusTag.vue",
        "frontend/src/components/reference/ReferenceDataTable.vue",
        "frontend/src/components/reference/ReferenceFlowGraphic.vue",
    ]:
        assert (_resolve_repo_root() / path).exists()

    styles = _read_repo_file("frontend/src/styles.css")
    assert "--reference-bg" in styles
    assert "--reference-blue" in styles
    assert ".reference-page" in styles
```

- [ ] **Step 2: Run test to confirm failure**

Run: `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py::test_reference_ui_component_layer_exists -q`

Expected: fail because files and tokens are missing.

- [ ] **Step 3: Create reference components**

Implement simple focused components:

- `ReferencePageFrame`: props `moduleNumber`, `title`, `tags`.
- `ReferenceModuleCard`: slots `header`, default, `actions`.
- `ReferenceKpiTile`: props `icon`, `label`, `value`, `unit`, `trend`, `status`.
- `ReferenceStatusTag`: props `status`, `label`.
- `ReferenceDataTable`: wraps `el-table` with dense class and slot passthrough.
- `ReferenceFlowGraphic`: SVG/CSS production flow line with status dots.

- [ ] **Step 4: Add tokens and base classes**

In `frontend/src/styles.css`, add:

- `--reference-bg`
- `--reference-panel`
- `--reference-border`
- `--reference-blue`
- `--reference-green`
- `--reference-red`
- `.reference-page`
- `.reference-grid`
- `.reference-card`
- `.reference-number`
- `.reference-table`

- [ ] **Step 5: Run tests and build**

Run:

- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `npm --prefix frontend run build`

Expected: both pass.

---

## Task 4: Reference-Style Login And Entry Terminal

**Files:**
- Modify: `frontend/src/views/Login.vue`
- Modify: `frontend/src/views/mobile/MobileEntry.vue`
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`
- Test: `backend/tests/test_mobile_entry_copy_consistency.py`
- Test: `frontend/e2e/mobile-entry-smoke.spec.js`
- Test: `frontend/e2e/dynamic-entry-layout.spec.js`

- [ ] **Step 1: Add static assertions for no English subtitle and entry-only copy**

Add:

```python
def test_reference_login_and_entry_use_cn_titles_and_no_english_subtitles() -> None:
    login = _read_repo_file("frontend/src/views/Login.vue")
    entry = _read_repo_file("frontend/src/views/mobile/MobileEntry.vue")

    assert "Login & Role Handoff" not in login
    assert "Independent Entry Terminal" not in entry
    assert "02" in login
    assert "03" in entry
    assert "审阅中心" not in entry
    assert "管理端" not in entry
```

- [ ] **Step 2: Run test to confirm failure**

Run: `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py::test_reference_login_and_entry_use_cn_titles_and_no_english_subtitles -q`

Expected: fail until reference titles are added.

- [ ] **Step 3: Redesign Login**

Use reference layout:

- Module number `02`.
- Three role cards: `录入端`、`审阅端`、`管理端`.
- Account form.
- No English subtitles.
- Role cards influence user expectation but do not bypass auth.

- [ ] **Step 4: Redesign MobileEntry**

Use module number `03`.

Show:

- 今日班次。
- 待填任务。
- 已提交。
- 异常待补。
- 最近提交状态。
- 快捷操作.

No review/admin navigation.

- [ ] **Step 5: Redesign DynamicEntryForm**

Use module number `04`.

Keep form logic, but align:

- Stepper.
- Main form card.
- Right-side current step summary on desktop.
- Stacked cards on mobile.
- AI hint as compact status card, not long explanation.

- [ ] **Step 6: Run focused tests**

Run:

- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 npm --prefix frontend run e2e -- e2e/mobile-entry-smoke.spec.js e2e/dynamic-entry-layout.spec.js`

Expected: pass.

---

## Task 5: Reference-Style Review Overview And Core Centers

**Files:**
- Modify: `frontend/src/views/review/OverviewCenter.vue`
- Modify: `frontend/src/views/review/ReviewTaskCenter.vue`
- Modify: `frontend/src/views/review/CostAccountingCenter.vue`
- Modify: `frontend/src/views/assistant/BrainCenter.vue`
- Modify: `frontend/src/views/reports/ReportList.vue`
- Modify: `frontend/src/views/quality/QualityCenter.vue`
- Test: `backend/tests/test_mobile_entry_copy_consistency.py`
- Test: `frontend/e2e/review-runtime.spec.js`

- [ ] **Step 1: Add static assertions for module mapping**

Add:

```python
def test_reference_review_modules_use_numbered_cn_titles() -> None:
    modules = {
        "frontend/src/views/review/OverviewCenter.vue": "01",
        "frontend/src/views/review/ReviewTaskCenter.vue": "07",
        "frontend/src/views/reports/ReportList.vue": "08",
        "frontend/src/views/quality/QualityCenter.vue": "09",
        "frontend/src/views/review/CostAccountingCenter.vue": "10",
        "frontend/src/views/assistant/BrainCenter.vue": "11",
    }
    for path, number in modules.items():
        source = _read_repo_file(path)
        assert number in source
        assert "Overview" not in source
        assert "Center" not in source
```

- [ ] **Step 2: Run test to confirm failure**

Run: `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py::test_reference_review_modules_use_numbered_cn_titles -q`

Expected: fail.

- [ ] **Step 3: Redesign OverviewCenter**

Make it the 16-module reference map:

- `01 系统总览主视图`.
- KPI row.
- Quick entries.
- Production flow graphic.
- Module grid excluding mobile preview module.
- Module `15` becomes responsive entry experience acceptance card.

- [ ] **Step 4: Redesign ReviewTaskCenter**

Make `07 审阅中心`:

- Tabs: 待审、已审、已驳回.
- Compact table with source, shift, risk, AI advice, action.
- Batch action row.

- [ ] **Step 5: Redesign Cost/AI/Reports/Quality**

Use existing logic, reference frames and cards.

- Cost: `10 成本核算与效益中心`.
- AI: `11 AI 总大脑中心`.
- Reports: `08 日报与交付中心`.
- Quality: `09 质量与告警中心`.

- [ ] **Step 6: Run review tests**

Run:

- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 npm --prefix frontend run e2e -- e2e/review-runtime.spec.js e2e/review-home-redesign.spec.js`
- `npm --prefix frontend run build`

Expected: pass.

---

## Task 6: Admin Surface Pages

**Files:**
- Modify: `frontend/src/views/review/IngestionCenter.vue`
- Modify: `frontend/src/views/reports/LiveDashboard.vue`
- Modify: `frontend/src/views/review/GovernanceCenter.vue`
- Modify: `frontend/src/views/master/WorkshopTemplateConfig.vue`
- Create: `frontend/src/views/admin/AdminHome.vue`
- Test: `frontend/e2e/admin-surface.spec.js`
- Test: `backend/tests/test_mobile_entry_copy_consistency.py`

- [ ] **Step 1: Add E2E admin smoke**

Create `frontend/e2e/admin-surface.spec.js`:

```js
import { expect, test } from '@playwright/test'

test('admin surface is separate from review and entry surfaces', async ({ page }) => {
  await page.goto('/login')
  await page.getByTestId('login-username').fill(process.env.PLAYWRIGHT_ADMIN_USERNAME || 'admin')
  await page.getByTestId('login-password').fill(process.env.PLAYWRIGHT_ADMIN_PASSWORD || process.env.PLAYWRIGHT_PASSWORD || process.env.INIT_ADMIN_PASSWORD || 'Admin#Gate2026_Strong')
  await page.getByTestId('login-submit').click()
  await page.goto('/admin')

  await expect(page.getByTestId('admin-shell')).toBeVisible()
  await expect(page.getByText('管理控制台')).toBeVisible()
  await expect(page.getByText('现场填报')).toHaveCount(0)
})
```

- [ ] **Step 2: Run E2E to confirm failure**

Run: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 npm --prefix frontend run e2e -- e2e/admin-surface.spec.js`

Expected: fail until admin route/page exists.

- [ ] **Step 3: Create AdminHome**

Create `14 主数据与模板中心` / admin landing module grid.

- [ ] **Step 4: Move admin-oriented pages into admin routes**

Keep old routes as redirects:

- `/review/ingestion` -> `/admin/ingestion` or compatibility alias.
- `/review/ops-reliability` -> `/admin/ops` or compatibility alias.
- `/review/governance` -> `/admin/governance`.
- `/review/template-center` -> `/admin/templates`.

If immediate redirects break existing E2E, keep both route paths pointing to same component for one transition phase.

- [ ] **Step 5: Run admin tests**

Run:

- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 npm --prefix frontend run e2e -- e2e/admin-surface.spec.js`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `npm --prefix frontend run build`

Expected: pass.

---

## Task 7: Backend Command Aggregation Contracts

**Files:**
- Create: `backend/app/schemas/command.py`
- Create: `backend/app/services/command_service.py`
- Create: `backend/app/routers/command.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/routers/__init__.py`
- Create: `backend/tests/test_command_routes.py`

- [ ] **Step 1: Write schema/route tests first**

Create tests:

```python
def test_command_overview_returns_reference_modules(client, auth_headers):
    response = client.get("/api/v1/command/overview", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert "modules" in payload
    assert any(module["module_id"] == "01" for module in payload["modules"])
    assert any(module["module_id"] == "15" for module in payload["modules"])
    assert all("title" in module for module in payload["modules"])
    assert all("kpis" in module for module in payload["modules"])
```

Add surface test:

```python
def test_entry_surface_command_payload_is_entry_only(client, mobile_auth_headers):
    response = client.get("/api/v1/command/entry-terminal", headers=mobile_auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["surface"] == "entry"
    assert "review_tasks" not in payload
    assert "admin_modules" not in payload
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `python -m pytest backend/tests/test_command_routes.py -q`

Expected: fail because router is missing.

- [ ] **Step 3: Implement schemas**

In `backend/app/schemas/command.py`, define Pydantic models:

- `CommandKpi`
- `CommandAction`
- `CommandTrendPoint`
- `CommandTableRow`
- `CommandModule`
- `CommandOverviewResponse`

- [ ] **Step 4: Implement service**

In `backend/app/services/command_service.py`, build adapters from existing dashboard/report services. First version can return deterministic view model using existing service data and safe fallbacks.

- [ ] **Step 5: Implement router**

Create endpoints:

- `/api/v1/command/overview`
- `/api/v1/command/entry-terminal`
- `/api/v1/command/review-center`
- `/api/v1/admin/ops-overview`
- `/api/v1/admin/governance-overview`
- `/api/v1/admin/master-overview`

- [ ] **Step 6: Mount router**

Modify `backend/app/main.py` to include `command.router`.

- [ ] **Step 7: Run backend tests**

Run:

- `python -m pytest backend/tests/test_command_routes.py -q`
- `python -m pytest backend/tests -q`

Expected: pass.

---

## Task 8: Visual Audit Against Reference Granularity

**Files:**
- Modify: `frontend/tmp_visual_audit.cjs`
- Create: `docs/reference-ui-granularity-checklist.md`
- Modify: `docs/launch-readiness-checklist.md`
- Modify: `docs/known-gaps-and-todos.md`

- [ ] **Step 1: Create reference granularity checklist**

Create `docs/reference-ui-granularity-checklist.md` with checks:

- module number visible.
- Chinese-only title.
- KPI density.
- card border/radius/shadow.
- table density.
- graph/flow area.
- action area.
- responsive consistency.
- old URL compatibility.
- three-surface isolation.

- [ ] **Step 2: Upgrade visual audit script**

In `frontend/tmp_visual_audit.cjs`, add routes:

- `/login`
- `/entry`
- `/review/overview`
- `/review/tasks`
- `/review/cost-accounting`
- `/admin`
- `/admin/ops`

Add checks for:

- `.reference-number`.
- `data-testid="entry-shell"`.
- `data-testid="review-shell"`.
- `data-testid="admin-shell"`.
- no visible admin nav on entry.

- [ ] **Step 3: Run visual audit**

Run: `node frontend/tmp_visual_audit.cjs`

Expected: `failedChecks=0`.

- [ ] **Step 4: Update docs**

Update:

- `docs/launch-readiness-checklist.md`
- `docs/known-gaps-and-todos.md`

Document any remaining backend aggregation follow-ups.

---

## Task 9: Full Verification

**Files:**
- No new files unless tests reveal issues.

- [ ] **Step 1: Run frontend build**

Run: `npm --prefix frontend run build`

Expected: pass.

- [ ] **Step 2: Run frontend E2E**

Run: `npm --prefix frontend run e2e`

Expected: all tests pass.

- [ ] **Step 3: Run backend tests**

Run: `python -m pytest backend/tests -q`

Expected: all tests pass.

- [ ] **Step 4: Run visual audit**

Run: `node frontend/tmp_visual_audit.cjs`

Expected: `failedChecks=0`.

- [ ] **Step 5: Run go-live gate**

Run: `bash -lc "cd '/mnt/d/zzj Claude code/aluminum-bypass' && ./scripts/go_live_gate.sh https://localhost --date 2026-04-24"`

Expected: `GO_LIVE_READY=true`.

- [ ] **Step 6: Final report**

Report:

- files changed.
- route compatibility evidence.
- three-surface isolation evidence.
- reference-image granularity evidence.
- build/test/e2e/audit/gate results.
