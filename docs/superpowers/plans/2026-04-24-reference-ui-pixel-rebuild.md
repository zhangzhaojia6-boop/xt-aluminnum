# Reference UI Pixel Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the frontend page layer into a reference-image-aligned, high-density production command center while preserving backend APIs, permissions, legacy URLs, and route names.

**Architecture:** Create a new `frontend/src/reference-command/` UI boundary and move all target-image-aligned pages into that boundary. Existing backend endpoints and existing route names remain the compatibility contract; new module catalog and adapter files translate current data into the 16-panel command-center grammar. Old frontend pages are retired only after replacement routes, E2E checks, and visual audit pass.

**Tech Stack:** Vue 3, Vue Router, Pinia, Element Plus, Vite, FastAPI, pytest, Playwright, project static contract tests.

---

## Execution Constraints

- Use TDD for every implementation slice: write or extend the failing contract first, run it red, implement the smallest passing change, then run the relevant green checks.
- Do not remove backend endpoints, legacy route names, or compatibility redirects.
- Do not introduce new npm dependencies unless the user explicitly approves.
- Do not commit, stage, or rewrite unrelated dirty worktree changes unless the user explicitly asks.
- This session must use inline execution unless the user explicitly authorizes subagents. The plan header keeps the standard worker handoff text, but current tool policy requires explicit user permission before dispatching subagents.
- UI-facing strings stay Chinese. Do not add English parenthetical subtitles such as `(Review Center)`.
- Do not add explanatory copy, marketing text, helper text, or schema fields named `description`, `explanation`, `helperText`, `tooltip`, `note`, or `rationale`.

## Source Of Truth

- Spec: `docs/superpowers/specs/2026-04-24-reference-ui-pixel-rebuild-design.md`
- Previous reference plan: `docs/superpowers/plans/2026-04-24-reference-ui-command-center.md`
- Target image: local reference image supplied outside the repository, passed via `REFERENCE_UI_TARGET_IMAGE` or `--target`
- Visual audit entry: `frontend/tmp_visual_audit.cjs`

## File Structure

### New Reference Command UI Boundary

- Create `frontend/src/reference-command/assets/logo.js`: SVG string helpers for the target-style logo and small production marks.
- Create `frontend/src/reference-command/assets/industry-graphics.js`: inline SVG/shape presets for production line, data flow, status rings, mini trends, equipment outlines, and risk pulses.
- Create `frontend/src/reference-command/data/moduleCatalog.js`: the 16-module catalog with module id, Chinese title, surface, route name, path, layout type, KPI keys, primary region type, side region type, and actions.
- Create `frontend/src/reference-command/data/moduleAdapters.js`: data adapters that normalize existing API payloads into compact KPI/table/trend/action/view-model payloads.
- Create `frontend/src/reference-command/components/CommandCanvas.vue`: 4x4 command-center canvas for `/review/overview`.
- Create `frontend/src/reference-command/components/CommandPanel.vue`: reusable numbered white panel matching the target image density.
- Create `frontend/src/reference-command/components/CommandPage.vue`: single-module page frame using the same title, KPI, primary, side, and action grammar.
- Create `frontend/src/reference-command/components/CommandKpi.vue`: compact KPI tile.
- Create `frontend/src/reference-command/components/CommandTable.vue`: compact table renderer.
- Create `frontend/src/reference-command/components/CommandTrend.vue`: SVG mini line/bar/ring renderer.
- Create `frontend/src/reference-command/components/CommandFlowMap.vue`: production/data flow graphic renderer.
- Create `frontend/src/reference-command/components/CommandActionBar.vue`: fixed compact action row.
- Create `frontend/src/reference-command/components/CommandStatus.vue`: small status and risk tags.
- Create `frontend/src/reference-command/shells/CommandEntryShell.vue`: entry-only shell.
- Create `frontend/src/reference-command/shells/CommandReviewShell.vue`: review-only shell.
- Create `frontend/src/reference-command/shells/CommandAdminShell.vue`: admin-only shell.
- Create `frontend/src/reference-command/pages/CommandLogin.vue`: target module 02 login and role handoff.
- Create `frontend/src/reference-command/pages/CommandOverview.vue`: target module 01 4x4 overview canvas.
- Create `frontend/src/reference-command/pages/CommandEntryHome.vue`: target module 03 entry terminal home.
- Create `frontend/src/reference-command/pages/CommandEntryFlow.vue`: target module 04 entry flow.
- Create `frontend/src/reference-command/pages/CommandModulePage.vue`: schema-driven module page for modules 05-14 and 16.
- Create `frontend/src/reference-command/styles/command-tokens.css`: reference image tokens.
- Create `frontend/src/reference-command/styles/command-layout.css`: responsive page, canvas, panel, shell, and density rules.
- Create `frontend/src/reference-command/styles/command-motion.css`: subtle page-load, flow, ring, and pulse animation.

### Existing Files To Modify

- Modify `frontend/src/main.js`: import new command styles before app mount.
- Modify `frontend/src/router/index.js`: wire legacy route names and paths to new command pages/shells while preserving redirects.
- Modify `frontend/src/stores/auth.js`: preserve existing auth logic and surface defaults; only adjust landing behavior if needed for the new shells.
- Modify `frontend/src/config/navigation.js`: keep route names compatible; align navigation to entry/review/admin boundaries.
- Modify `frontend/src/styles.css`: remove or neutralize old global visual residue after command styles are in place.
- Modify `frontend/src/design/theme.css`: keep only compatible tokens or redirect tokens to command design values.
- Modify `frontend/tmp_visual_audit.cjs`: upgrade target image alignment checks and screenshot capture.
- Modify `backend/tests/test_reference_command_center_spec.py`: static contract tests for catalog, routes, styles, and audit requirements.
- Modify relevant `frontend/e2e/*.spec.js`: login role handoff, entry flow, review overview, admin shell, and route compatibility.

### Existing Files To Retire After Replacement

- Retire direct route usage of old `frontend/src/views/Login.vue`.
- Retire direct route usage of old `frontend/src/views/mobile/MobileEntry.vue` and `DynamicEntryForm.vue`.
- Retire direct route usage of old review/dashboard/master pages once their route names point to `CommandModulePage`.
- Delete old unreferenced visual helpers only after static import checks and build pass.

---

## Task 1: Lock The Pixel Rebuild Contract

**Files:**
- Modify: `backend/tests/test_reference_command_center_spec.py`
- Test: `backend/tests/test_reference_command_center_spec.py`

- [ ] **Step 1: Extend the static contract test for the new boundary**

Add assertions that the new `reference-command` boundary exists and contains the required files:

```python
def test_reference_command_boundary_files_are_declared() -> None:
    expected = [
        "frontend/src/reference-command/data/moduleCatalog.js",
        "frontend/src/reference-command/data/moduleAdapters.js",
        "frontend/src/reference-command/pages/CommandLogin.vue",
        "frontend/src/reference-command/pages/CommandOverview.vue",
        "frontend/src/reference-command/pages/CommandEntryHome.vue",
        "frontend/src/reference-command/pages/CommandEntryFlow.vue",
        "frontend/src/reference-command/pages/CommandModulePage.vue",
        "frontend/src/reference-command/styles/command-tokens.css",
        "frontend/src/reference-command/styles/command-layout.css",
        "frontend/src/reference-command/styles/command-motion.css",
    ]
    for path in expected:
        assert _repo_file(path).exists(), path
```

- [ ] **Step 2: Add contract tests for forbidden UI residue**

Add assertions that the new reference command files do not contain English subtitle patterns or forbidden helper-field names:

```python
def test_reference_command_ui_uses_chinese_dense_copy_without_helper_fields() -> None:
    forbidden = [
        "(Review Center)",
        "(Hero Overview)",
        "description:",
        "explanation:",
        "helperText",
        "tooltip",
        "rationale",
    ]
    for path in _reference_command_files():
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{token} in {path}"
```

- [ ] **Step 3: Add contract tests for 16 target modules**

Add assertions for module ids, titles, routes, and surfaces:

```python
def test_reference_command_catalog_declares_16_target_modules() -> None:
    catalog = _read_repo_file("frontend/src/reference-command/data/moduleCatalog.js")
    for module_id in [f"{index:02d}" for index in range(1, 17)]:
        assert f"moduleId: '{module_id}'" in catalog
    for title in [
        "系统总览主视图",
        "登录与角色入口",
        "独立填报终端首页",
        "填报流程页",
        "工厂作业看板",
        "数据接入与字段映射中心",
        "审阅中心",
        "日报与交付中心",
        "质量与告警中心",
        "成本核算与效益中心",
        "AI 总大脑中心",
        "系统运维与可观测",
        "权限治理中心",
        "主数据与模板中心",
        "响应式录入体验",
        "路线图与下一步",
    ]:
        assert title in catalog
    for surface in ["surface: 'entry'", "surface: 'review'", "surface: 'admin'", "surface: 'system'"]:
        assert surface in catalog
```

- [ ] **Step 4: Add route compatibility contract tests**

Assert that old URLs and route names are still present in `frontend/src/router/index.js`:

```python
def test_reference_command_keeps_legacy_routes_and_route_names() -> None:
    router = _read_repo_file("frontend/src/router/index.js")
    for route_name in [
        "mobile-entry",
        "dynamic-entry-form",
        "review-overview-home",
        "factory-dashboard",
        "review-task-center",
        "report-list",
        "quality-center",
        "cost-accounting-center",
        "brain-center",
        "ops-reliability",
        "governance-center",
        "master-workshop",
        "workshop-template-config",
    ]:
        assert f"name: '{route_name}'" in router
    for legacy_path in ["/mobile", "/dashboard", "/master", "/ops/reliability"]:
        assert legacy_path in router
```

- [ ] **Step 5: Run the contract test red**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py -q`

Expected: fail because the new `frontend/src/reference-command/` files do not exist yet or are incomplete.

---

## Task 2: Create Command Tokens, Layout, Motion, Logo, And Graphics

**Files:**
- Create: `frontend/src/reference-command/styles/command-tokens.css`
- Create: `frontend/src/reference-command/styles/command-layout.css`
- Create: `frontend/src/reference-command/styles/command-motion.css`
- Create: `frontend/src/reference-command/assets/logo.js`
- Create: `frontend/src/reference-command/assets/industry-graphics.js`
- Modify: `frontend/src/main.js`
- Test: `backend/tests/test_reference_command_center_spec.py`

- [ ] **Step 1: Add style-token assertions**

Extend the test file with required target-image tokens:

```python
def test_reference_command_tokens_match_target_image_rules() -> None:
    tokens = _read_repo_file("frontend/src/reference-command/styles/command-tokens.css")
    assert "--cmd-bg: #f4f7fb" in tokens
    assert "--cmd-panel: #ffffff" in tokens
    assert "--cmd-border: #e5edf7" in tokens
    assert "--cmd-blue: #1f6fff" in tokens
    assert "DIN Alternate" in tokens
    assert "Microsoft YaHei" in tokens
```

- [ ] **Step 2: Run the style-token test red**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py::test_reference_command_tokens_match_target_image_rules -q`

Expected: fail because the file is missing.

- [ ] **Step 3: Implement `command-tokens.css`**

Add reference image tokens:

```css
:root {
  --cmd-bg: #f4f7fb;
  --cmd-panel: #ffffff;
  --cmd-panel-soft: #f8fbff;
  --cmd-border: #e5edf7;
  --cmd-border-strong: #d5e2f1;
  --cmd-blue: #1f6fff;
  --cmd-blue-deep: #0f56d9;
  --cmd-cyan: #14b8d4;
  --cmd-green: #16a37a;
  --cmd-red: #ef3e52;
  --cmd-amber: #f5a623;
  --cmd-text: #102033;
  --cmd-muted: #64748b;
  --cmd-shadow: 0 8px 24px rgba(30, 76, 138, 0.07);
  --cmd-radius: 12px;
  --cmd-radius-sm: 8px;
  --cmd-gap: 10px;
  --cmd-font: "DIN Alternate", "Barlow Condensed", "MiSans", "HarmonyOS Sans SC", "Microsoft YaHei", sans-serif;
}
```

- [ ] **Step 4: Implement layout and motion styles**

Create compact classes for `.cmd-page`, `.cmd-shell`, `.cmd-canvas`, `.cmd-panel`, `.cmd-kpi`, `.cmd-table`, `.cmd-flow`, `.cmd-action-bar`, plus responsive breakpoints for desktop/tablet/mobile.

- [ ] **Step 5: Implement logo and graphics helpers**

Use inline SVG strings/functions only. Include `commandLogoMark`, `factoryLineGraphic`, `dataFlowGraphic`, `statusRingGraphic`, and `riskPulseGraphic`. Keep labels Chinese where visible.

- [ ] **Step 6: Import command styles in `frontend/src/main.js`**

Add:

```js
import './reference-command/styles/command-tokens.css'
import './reference-command/styles/command-layout.css'
import './reference-command/styles/command-motion.css'
```

- [ ] **Step 7: Run green checks for this slice**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py -q`

Expected: contract tests for files and tokens pass except later catalog/router assertions that still fail.

Run: `npm --prefix frontend run build`

Expected: pass.

---

## Task 3: Build The 16-Module Catalog And Data Adapters

**Files:**
- Create: `frontend/src/reference-command/data/moduleCatalog.js`
- Create: `frontend/src/reference-command/data/moduleAdapters.js`
- Test: `backend/tests/test_reference_command_center_spec.py`

- [ ] **Step 1: Add catalog shape assertions**

Assert that each module has `moduleId`, `title`, `surface`, `routeName`, `routePath`, `layout`, `kpiKeys`, `primary`, `side`, and `actions`.

- [ ] **Step 2: Run the catalog shape test red**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py::test_reference_command_catalog_declares_16_target_modules -q`

Expected: fail because `moduleCatalog.js` is missing.

- [ ] **Step 3: Implement `moduleCatalog.js`**

Create a frozen `referenceModules` array with the target-image module grammar:

```js
export const referenceModules = Object.freeze([
  {
    moduleId: '01',
    title: '系统总览主视图',
    surface: 'review',
    routeName: 'review-overview-home',
    routePath: '/review/overview',
    layout: 'canvas-hero',
    kpiKeys: ['todayOutput', 'orderCompletion', 'qualityRate', 'inProduction', 'riskCount'],
    primary: { type: 'flowMap', source: 'commandOverview' },
    side: { type: 'statusRail', source: 'commandOverview' },
    actions: ['enterReview', 'exportSnapshot'],
  },
])
```

Then fill modules `02` through `16` using the titles and route mapping from the spec.

- [ ] **Step 4: Implement catalog helpers**

Export:

```js
export const modulesById = new Map(referenceModules.map((module) => [module.moduleId, module]))
export const modulesByRouteName = new Map(referenceModules.map((module) => [module.routeName, module]))
export const modulesBySurface = (surface) => referenceModules.filter((module) => module.surface === surface)
export const findModuleByRouteName = (routeName) => modulesByRouteName.get(routeName)
export const findModuleById = (moduleId) => modulesById.get(moduleId)
```

- [ ] **Step 5: Implement `moduleAdapters.js` with deterministic fallbacks**

Export adapter functions:

```js
export function adaptCommandOverview(payload = {}) {
  return {
    kpis: [],
    tableRows: [],
    trend: [],
    risks: [],
    actions: [],
    raw: payload,
  }
}
```

Then add named adapters for entry home, entry flow, factory, review tasks, reports, quality, cost, brain, ingestion, ops, governance, master, and roadmap. Missing data should become compact empty arrays or status tags, not explanatory paragraphs.

- [ ] **Step 6: Run green checks for this slice**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py -q`

Expected: catalog assertions pass; router/page assertions may still fail.

Run: `npm --prefix frontend run build`

Expected: pass.

---

## Task 4: Build Core Command Components

**Files:**
- Create: `frontend/src/reference-command/components/CommandPanel.vue`
- Create: `frontend/src/reference-command/components/CommandKpi.vue`
- Create: `frontend/src/reference-command/components/CommandStatus.vue`
- Create: `frontend/src/reference-command/components/CommandTable.vue`
- Create: `frontend/src/reference-command/components/CommandTrend.vue`
- Create: `frontend/src/reference-command/components/CommandFlowMap.vue`
- Create: `frontend/src/reference-command/components/CommandActionBar.vue`
- Create: `frontend/src/reference-command/components/CommandPage.vue`
- Create: `frontend/src/reference-command/components/CommandCanvas.vue`
- Test: `backend/tests/test_reference_command_center_spec.py`

- [ ] **Step 1: Add component contract assertions**

Assert component files exist and include required CSS hooks:

```python
def test_reference_command_components_expose_target_css_hooks() -> None:
    hooks = {
        "CommandPanel.vue": ["cmd-panel", "cmd-panel__number", "cmd-panel__title"],
        "CommandCanvas.vue": ["cmd-canvas", "cmd-canvas__grid"],
        "CommandPage.vue": ["cmd-module-page", "cmd-module-page__primary", "cmd-module-page__side"],
        "CommandKpi.vue": ["cmd-kpi", "cmd-kpi__value"],
        "CommandActionBar.vue": ["cmd-action-bar"],
    }
    for filename, expected_hooks in hooks.items():
        source = _read_repo_file(f"frontend/src/reference-command/components/{filename}")
        for hook in expected_hooks:
            assert hook in source
```

- [ ] **Step 2: Run the component contract red**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py::test_reference_command_components_expose_target_css_hooks -q`

Expected: fail because components are missing.

- [ ] **Step 3: Implement smallest reusable components**

Implement components with stable props and no business-specific copy. Use slots for primary/side content where necessary. Keep class names stable for visual audit.

- [ ] **Step 4: Keep `CommandPage.vue` schema-driven**

`CommandPage.vue` accepts `module` and `viewModel` props. It renders:

```text
module number/title
KPI strip
primary region
side region
action bar
```

- [ ] **Step 5: Keep `CommandCanvas.vue` dense**

`CommandCanvas.vue` renders all 16 modules as target-image-like panels, but module 15 uses responsive-entry wording instead of a deleted mobile preview module.

- [ ] **Step 6: Run green checks for this slice**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py -q`

Expected: component assertions pass; page/router assertions may still fail.

Run: `npm --prefix frontend run build`

Expected: pass.

---

## Task 5: Rebuild Login As Target Module 02

**Files:**
- Create: `frontend/src/reference-command/pages/CommandLogin.vue`
- Modify: `frontend/src/router/index.js`
- Test: `frontend/e2e/login-delivery-smoke.spec.js`
- Test: `backend/tests/test_reference_command_center_spec.py`

- [ ] **Step 1: Add static login assertions**

Assert the login route points to `CommandLogin.vue` and the page contains the three Chinese role entrances:

```python
def test_command_login_replaces_old_login_route_with_three_roles() -> None:
    router = _read_repo_file("frontend/src/router/index.js")
    login = _read_repo_file("frontend/src/reference-command/pages/CommandLogin.vue")
    assert "CommandLogin" in router
    for role in ["录入端", "审阅端", "管理端"]:
        assert role in login
    assert "(Login" not in login
```

- [ ] **Step 2: Run the login static test red**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py::test_command_login_replaces_old_login_route_with_three_roles -q`

Expected: fail until route and page are wired.

- [ ] **Step 3: Implement `CommandLogin.vue`**

Use the target module 02 structure:

- logo row with Chinese product name only
- three role cards as real buttons
- login form
- compact security/status row
- no marketing paragraphs

- [ ] **Step 4: Wire `/login` to `CommandLogin.vue`**

Replace only the route component import for the login route. Keep the route path and name unchanged.

- [ ] **Step 5: Run login checks**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py::test_command_login_replaces_old_login_route_with_three_roles -q`

Expected: pass.

Run: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 npm --prefix frontend run e2e -- login-delivery-smoke.spec.js`

Expected: pass. If the script does not accept a spec argument, run the full frontend E2E command in Task 13.

---

## Task 6: Rebuild Three Shells And Route Main Chain

**Files:**
- Create: `frontend/src/reference-command/shells/CommandEntryShell.vue`
- Create: `frontend/src/reference-command/shells/CommandReviewShell.vue`
- Create: `frontend/src/reference-command/shells/CommandAdminShell.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/config/navigation.js`
- Modify: `frontend/src/stores/auth.js`
- Test: `backend/tests/test_reference_command_center_spec.py`
- Test: `frontend/e2e/admin-surface.spec.js`

- [ ] **Step 1: Add shell isolation tests**

Assert entry shell does not contain review/admin nav text, review shell does not contain admin management nav text, and admin shell does not contain entry task actions.

- [ ] **Step 2: Run shell isolation tests red**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py::test_reference_command_shells_keep_three_surfaces_separate -q`

Expected: fail until shells are created.

- [ ] **Step 3: Implement `CommandEntryShell.vue`**

Render only entry navigation and quick status. It should contain `独立填报端`, `今日填报`, `历史记录`, and no review/admin links.

- [ ] **Step 4: Implement `CommandReviewShell.vue`**

Render review navigation for overview, factory, tasks, reports, quality, cost, AI, and roadmap.

- [ ] **Step 5: Implement `CommandAdminShell.vue`**

Render admin navigation for ingestion, ops, governance, master/templates, users, and roadmap.

- [ ] **Step 6: Wire router shells**

Update `frontend/src/router/index.js`:

- `/entry` uses `CommandEntryShell`
- `/review` uses `CommandReviewShell`
- `/admin` uses `CommandAdminShell`
- old `/mobile/*`, `/dashboard/*`, `/master/*`, and `/ops/reliability` remain compatible
- old route names remain searchable in source

- [ ] **Step 7: Run shell and route checks**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py -q`

Expected: shell and route compatibility checks pass except page-specific checks not implemented yet.

Run: `npm --prefix frontend run build`

Expected: pass.

---

## Task 7: Rebuild `/review/overview` As The 4x4 Command Canvas

**Files:**
- Create: `frontend/src/reference-command/pages/CommandOverview.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/tmp_visual_audit.cjs`
- Test: `backend/tests/test_reference_command_center_spec.py`
- Test: `frontend/e2e/review-runtime.spec.js`

- [ ] **Step 1: Add overview contract assertions**

Assert `CommandOverview.vue` imports `CommandCanvas`, uses `referenceModules`, and renders the 16 module ids.

- [ ] **Step 2: Run overview contract red**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py::test_review_overview_uses_16_panel_command_canvas -q`

Expected: fail until page is implemented.

- [ ] **Step 3: Implement `CommandOverview.vue`**

Use `CommandCanvas` with `referenceModules`. Fetch `/api/v1/command/surface/review` where available; fall back to adapter defaults. Keep the visual density close to the target image.

- [ ] **Step 4: Wire route name `review-overview-home`**

Ensure `/review/overview` and any compatible dashboard default route land on `CommandOverview.vue`.

- [ ] **Step 5: Update visual audit overview capture**

Make `frontend/tmp_visual_audit.cjs` capture `/review/overview`, assert:

- target image meta width `1672`
- target image meta height `941`
- `referencePanelChecks.length === 16`
- rendered `.cmd-panel` count is at least `16`
- no English subtitle regex in the overview DOM

- [ ] **Step 6: Run overview checks**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py -q`

Expected: pass for overview contract.

Run: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 node frontend/tmp_visual_audit.cjs`

Expected: visual audit passes or reports only later module-page gaps that are not yet wired.

---

## Task 8: Rebuild Entry Terminal Modules 03 And 04

**Files:**
- Create: `frontend/src/reference-command/pages/CommandEntryHome.vue`
- Create: `frontend/src/reference-command/pages/CommandEntryFlow.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/e2e/mobile-entry-smoke.spec.js`
- Modify: `frontend/e2e/dynamic-entry-layout.spec.js`
- Test: `backend/tests/test_reference_command_center_spec.py`

- [ ] **Step 1: Add entry-surface contract tests**

Assert entry pages contain module ids `03` and `04`, entry-only actions, and no review/admin route labels.

- [ ] **Step 2: Run entry contract tests red**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py::test_entry_surface_is_entry_only_and_matches_modules_03_04 -q`

Expected: fail until pages are implemented.

- [ ] **Step 3: Implement `CommandEntryHome.vue`**

Target module 03 structure:

- top compact user/status row
- today shift card
- pending tasks
- submitted count
- abnormal supplement count
- recent submission statuses
- quick actions for fill/report/history/photo

- [ ] **Step 4: Implement `CommandEntryFlow.vue`**

Target module 04 structure:

- six-step progress row
- compact form grid
- right-side reference/AI summary panel
- bottom action row
- existing submit APIs and form semantics remain unchanged

- [ ] **Step 5: Wire legacy entry routes**

Ensure:

- `/entry` and `/entry/home` show `CommandEntryHome`
- `/entry/form` or current fill route shows `CommandEntryFlow`
- `/mobile/*` compatibility routes still redirect or map to entry routes
- old route names `mobile-entry` and `dynamic-entry-form` are preserved

- [ ] **Step 6: Run entry checks**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py -q`

Expected: pass for entry contracts.

Run: `npm --prefix frontend run build`

Expected: pass.

---

## Task 9: Rebuild Review Module Pages 05, 07, 08, 09, 10, 11, And 16

**Files:**
- Create: `frontend/src/reference-command/pages/CommandModulePage.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/e2e/review-runtime.spec.js`
- Test: `backend/tests/test_reference_command_center_spec.py`

- [ ] **Step 1: Add review-module route contract tests**

Assert review route names map to module ids:

```text
05 factory-dashboard
07 review-task-center
08 report-list
09 quality-center
10 cost-accounting-center
11 brain-center
16 review-roadmap-center
```

- [ ] **Step 2: Run review-module contract tests red**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py::test_review_modules_are_schema_driven_command_pages -q`

Expected: fail until pages/routes are wired.

- [ ] **Step 3: Implement `CommandModulePage.vue`**

Read module by route name or explicit prop. Render `CommandPage` with adapter output. Keep each page within the 5-zone grammar:

```text
numbered title
KPI strip
primary table/graphic
right side risk/trend/summary
fixed action bar
```

- [ ] **Step 4: Wire review module routes to `CommandModulePage.vue`**

Use route props or meta to pass `moduleId`. Keep legacy paths and names. Do not expose admin-only modules in review navigation.

- [ ] **Step 5: Implement adapter payloads for review modules**

Use existing endpoints where already available. If a payload is missing, render compact placeholders such as `暂无数据` inside table rows/status tags only.

- [ ] **Step 6: Run review checks**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py -q`

Expected: pass for review module contracts.

Run: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 npm --prefix frontend run e2e -- review-runtime.spec.js`

Expected: pass where the script supports spec filtering.

---

## Task 10: Rebuild Admin Module Pages 06, 12, 13, 14, And 16

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/reference-command/pages/CommandModulePage.vue`
- Modify: `frontend/src/reference-command/data/moduleAdapters.js`
- Modify: `frontend/e2e/admin-surface.spec.js`
- Test: `backend/tests/test_reference_command_center_spec.py`

- [ ] **Step 1: Add admin-module route contract tests**

Assert admin route names map to module ids:

```text
06 ingestion-center
12 ops-reliability
13 governance-center
13 user-management
14 master-workshop
14 workshop-template-config
16 admin-roadmap-center
```

- [ ] **Step 2: Run admin-module contract tests red**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py::test_admin_modules_are_schema_driven_command_pages -q`

Expected: fail until admin pages/routes are wired.

- [ ] **Step 3: Wire admin routes to `CommandModulePage.vue`**

Keep admin shell and route names. Preserve redirects from `/master/*` and `/ops/reliability`.

- [ ] **Step 4: Implement adapter payloads for admin modules**

Use `/api/v1/admin/ops-overview`, `/api/v1/admin/governance-overview`, `/api/v1/admin/master-overview`, and existing templates/users endpoints where available.

- [ ] **Step 5: Ensure admin does not show daily review task processing**

Admin pages can show governance/ops/template state, but should not render review approval action buttons.

- [ ] **Step 6: Run admin checks**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py -q`

Expected: pass for admin module contracts.

Run: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 npm --prefix frontend run e2e -- admin-surface.spec.js`

Expected: pass where the script supports spec filtering.

---

## Task 11: Clean Old Frontend Visual Residue

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/design/theme.css`
- Modify: `frontend/src/router/index.js`
- Delete only if unreferenced: old visual-only components/pages replaced by command routes
- Test: `backend/tests/test_reference_command_center_spec.py`
- Test: `npm --prefix frontend run build`

- [ ] **Step 1: Add static residue tests**

Assert command-routed pages no longer import replaced old page components and new styles do not contain known old visual residue:

```python
def test_old_frontend_visual_residue_is_not_used_by_command_routes() -> None:
    router = _read_repo_file("frontend/src/router/index.js")
    for old_component in [
        "../views/Login.vue",
        "../views/mobile/MobileEntry.vue",
        "../views/mobile/DynamicEntryForm.vue",
    ]:
        assert old_component not in router
    styles = _read_repo_file("frontend/src/styles.css") + _read_repo_file("frontend/src/design/theme.css")
    for token in ["warm", "orange", "glassmorphism"]:
        assert token not in styles.lower()
```

- [ ] **Step 2: Run residue tests red**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py::test_old_frontend_visual_residue_is_not_used_by_command_routes -q`

Expected: fail until route imports and old style residue are cleaned.

- [ ] **Step 3: Remove old route imports only after replacement routes pass**

Delete only direct imports that are no longer referenced by router, E2E, or build.

- [ ] **Step 4: Neutralize old global styles**

Keep necessary resets. Remove or override warm backgrounds, oversized rounded cards, loose marketing sections, and old shell-specific visual rules that fight command layout.

- [ ] **Step 5: Run cleanup checks**

Run: `python -m pytest backend/tests/test_reference_command_center_spec.py -q`

Expected: pass.

Run: `npm --prefix frontend run build`

Expected: pass.

---

## Task 12: Upgrade Visual Audit To Reference-Image Granularity

**Files:**
- Modify: `frontend/tmp_visual_audit.cjs`
- Modify: `.omx/state/reference-ui-visual-verdict/ralph-progress.json`
- Test: `frontend/tmp_visual_audit.cjs`

- [ ] **Step 1: Add stricter audit assertions**

Audit should verify:

- target image path exists
- target image dimensions are `1672x941`
- `referencePanelChecks` has 16 entries
- every target module has `moduleId`, `route`, `title`, `screenshot`
- overview page has at least 16 `.cmd-panel` nodes
- all module pages contain `.cmd-module-page` or `.cmd-panel`
- pages contain no English parenthetical subtitles
- entry pages do not contain admin/review nav actions
- review pages do not contain admin-only nav actions
- admin pages do not contain entry fill actions

- [ ] **Step 2: Run visual audit red or partial**

Run: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 node frontend/tmp_visual_audit.cjs`

Expected: fail until all routed pages render the new command classes.

- [ ] **Step 3: Implement audit route matrix**

Use the module catalog route mapping where possible. Keep the current target image meta and JSON report output.

- [ ] **Step 4: Update verdict state**

Only write pass verdict after all audit checks pass. If checks fail, write the failure summary rather than claiming completion.

- [ ] **Step 5: Run visual audit green**

Run: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 node frontend/tmp_visual_audit.cjs`

Expected: report summary has `failedChecks: 0` and includes all 16 module screenshots/checks.

---

## Task 13: Full Functional Verification

**Files:**
- No code changes unless a verification failure exposes a root cause.

- [ ] **Step 1: Run backend tests**

Run: `python -m pytest backend/tests -q`

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend build**

Run: `npm --prefix frontend run build`

Expected: Vite build passes.

- [ ] **Step 3: Run frontend E2E**

Run: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 npm --prefix frontend run e2e`

Expected: all Playwright tests pass.

- [ ] **Step 4: Run reference visual audit**

Run: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 node frontend/tmp_visual_audit.cjs`

Expected: `failedChecks: 0`, target image meta present, 16 module checks present.

- [ ] **Step 5: Run whitespace/diff check**

Run: `git diff --check`

Expected: exit code 0. Existing CRLF warnings can be noted if they are pre-existing and not caused by this work.

- [ ] **Step 6: Manual browser sanity**

Use the in-app browser at `http://127.0.0.1:5173/login` and verify:

- login visually matches module 02 grammar
- role buttons land on the correct default surface
- entry surface only records/submits
- review surface shows command overview and review pages
- admin surface shows ingestion/ops/governance/master pages
- no English small subtitles remain

---

## Completion Criteria

- `frontend/src/reference-command/` owns the new UI system.
- The login, entry, review, and admin main routes render target-image-aligned command pages.
- The 16 target modules are represented in `moduleCatalog.js`.
- The old URL and route-name compatibility contract remains intact.
- Old frontend visual residue no longer controls command routes.
- Backend full test suite, frontend build, E2E, visual audit, and diff check pass.
