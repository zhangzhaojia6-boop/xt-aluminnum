# Industrial AI Frontend Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the frontend visual system into a high-finish industrial AI product: factory war map, AI manager sidecar, execution rail, richer AI thinking states, and a unified Xintai brand language across desktop and mobile.

**Architecture:** This is a frontend-only wide visual refactor. Shared design tokens and reusable XT components provide the new visual vocabulary, then shell/login/overview/AI/mobile/business pages consume that vocabulary without changing routes, API contracts, permissions, or backend behavior.

**Tech Stack:** Vue 3.5, Vite 8, Element Plus 2.8, Pinia, existing scoped CSS and `frontend/src/design/*` tokens. No new npm dependencies.

---

## Scope And Guardrails

This plan intentionally touches more than 8 frontend files. The user explicitly requested a large visual refactor because the current frontend looks too generic.

Do not touch:

- Backend files.
- API contracts.
- Auth, JWT, permissions, roles, schedule, equipment binding, MES sync.
- readyz, hard gate, AI validation, workflow dispatcher, audit log logic.
- npm dependencies or Vite config.

Non-negotiable quality bar:

- Treat the user benchmark “像opus 4.7在Claude code编码设计前端一样，参考其设计前端多好看，你gpt5.5设计的前端太难看了” as a hard frontend quality constraint.
- Avoid generic GPT-style dashboard UI.
- Browser-check desktop and mobile before claiming any batch is done.
- Preserve AI Workstation's simple question-answer path while enriching thinking/tool/action states.

## Data Flow

More than 3 visual components will exchange display state, but they must stay acyclic:

```text
Existing API/store/mock data
  -> page component computed view models
  -> XtFactoryMap / XtExecutionRail / XtAiThinking / XtLogo
  -> display only, or existing authorized UI actions
```

Do not let shared visual components call APIs directly.

## File Structure

### Create

- `frontend/src/components/xt/XtFactoryMap.vue`
  - Reusable factory war-map visual for management overview and factory dashboard.
  - Props only: lines, nodes, alerts, activeKey, compact.
  - No API calls.

- `frontend/src/components/xt/XtExecutionRail.vue`
  - Reusable “发现 → 判断 → 执行 → 留痕 → 发布” rail.
  - Props only: steps, activeIndex, compact.
  - No API calls.

- `frontend/src/components/xt/XtAiThinking.vue`
  - AI thinking/tool/action state component for AI Workstation.
  - Props only: streaming, toolCalls, lastError.
  - Must support `prefers-reduced-motion`.

- `frontend/src/components/xt/XtAiActionCard.vue`
  - Compact action card rendered under AI answers when tool calls or suggested actions exist.
  - No direct execution unless the existing page already has an authorized handler.

### Modify Foundation

- `frontend/src/design/xt-tokens.css`
  - New industrial AI palette, surface hierarchy, shadow, radius, motion tokens.

- `frontend/src/design/xt-base.css`
  - Global body, panels, tables, stat cards, mobile cards, scrollbars, reduced-motion support.

- `frontend/src/design/industrial.css`
  - Factory-map utilities, scan-line animation, execution rail animation, responsive surface rules.

- `frontend/src/design/xt-motion.css`
  - Remove or replace old shimmer/gradient-only motion that conflicts with the new language.

- `frontend/src/design/theme.css`
  - De-emphasize legacy app-shell styles that conflict with the active `ManageShell`.

- `frontend/src/components/xt/index.js`
  - Export new XT components.

- `frontend/src/components/xt/XtLogo.vue`
  - Upgrade logo from generic hex mark to stylized Xintai aluminum/furnace/batch-flow mark.

- `frontend/src/components/xt/XtCard.vue`
- `frontend/src/components/xt/XtKpi.vue`
- `frontend/src/components/xt/XtTable.vue`
- `frontend/src/components/xt/XtPageHeader.vue`
- `frontend/src/components/xt/XtActionBar.vue`
- `frontend/src/components/xt/XtSearch.vue`
- `frontend/src/components/xt/XtEmpty.vue`
- `frontend/src/components/xt/XtStatus.vue`
  - Bring shared components into the new surface vocabulary.

### Modify Shell And Entry Points

- `frontend/src/views/Login.vue`
  - Rebuild first screen with brand mark, factory-map preview, and precise login panel.

- `frontend/src/layout/ManageShell.vue`
  - Apply new logo, command-bar density, side navigation, topbar, and elevated workspace surfaces.

- `frontend/src/layout/EntryShell.vue`
  - Apply lightweight mobile brand language without adding map complexity.

- `frontend/src/layout/AppShell.vue`
  - Keep compatibility shell visually aligned for legacy routes that still import `AppShell`.

### Modify Core Pages

- `frontend/src/views/review/OverviewCenter.vue`
  - Replace generic module grid first impression with factory war map, AI manager sidecar, execution rail.

- `frontend/src/views/dashboard/FactoryDirector.vue`
  - Align factory dashboard with war-map language and reduce old card/template feel.

- `frontend/src/views/ai/AiWorkstation.vue`
  - Preserve simple chat path; add AI thinking strip, tool/action states, richer composer.

- `frontend/src/views/ai/AiChatMessage.vue`
  - Upgrade assistant/user messages, tool calls, action card placement.

- `frontend/src/views/ai/AiConversationList.vue`
  - Align conversation list with workspace surfaces.

### Modify Management Page Families

- `frontend/src/views/reports/ReportList.vue`
- `frontend/src/views/reports/ReportDetail.vue`
- `frontend/src/views/quality/QualityCenter.vue`
- `frontend/src/views/quality/QualityDetail.vue`
- `frontend/src/views/reconciliation/ReconciliationCenter.vue`
- `frontend/src/views/reconciliation/ReconciliationDetail.vue`
- `frontend/src/views/attendance/AttendanceOverview.vue`
- `frontend/src/views/attendance/AttendanceDetail.vue`
- `frontend/src/views/attendance/ExceptionList.vue`
- `frontend/src/views/imports/FileImport.vue`
- `frontend/src/views/imports/ImportHistory.vue`
- `frontend/src/views/shift/ShiftCenter.vue`
- `frontend/src/views/shift/ShiftDetail.vue`
- `frontend/src/views/energy/EnergyCenter.vue`
- `frontend/src/views/master/AliasMapping.vue`
- `frontend/src/views/master/Employee.vue`
- `frontend/src/views/master/Equipment.vue`
- `frontend/src/views/master/MachineWizard.vue`
- `frontend/src/views/master/ShiftConfig.vue`
- `frontend/src/views/master/Team.vue`
- `frontend/src/views/master/UserManagement.vue`
- `frontend/src/views/master/Workshop.vue`
- `frontend/src/views/master/WorkshopTemplateConfig.vue`
- `frontend/src/views/master/YieldRateDeprecationMap.vue`
  - Apply shared cards, tables, filters, action bars, empty states, and status treatments.

### Modify Mobile Entry Family

- `frontend/src/views/mobile/MobileEntry.vue`
- `frontend/src/views/mobile/DynamicEntryForm.vue`
- `frontend/src/views/mobile/ShiftReportForm.vue`
- `frontend/src/views/entry/EntryDrafts.vue`
- `frontend/src/views/mobile/OCRCapture.vue`
- `frontend/src/views/mobile/ShiftReportHistory.vue`
- `frontend/src/views/mobile/ReminderList.vue`
- `frontend/src/views/mobile/AttendanceConfirm.vue`
  - Apply mobile Xintai brand language, stronger touch targets, tighter hierarchy.
  - Do not introduce factory-map complexity into worker entry.

## Validation Commands

Run after each major batch:

```powershell
Set-Location frontend
npm run build
```

Run after broad page changes:

```powershell
Set-Location frontend
npx playwright test --workers=1
```

When using local browser preview:

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1
```

Visual checks:

- Desktop: login, `/manage/overview`, `/manage/factory`, `/manage/ai`, reports, quality, reconciliation, master data.
- Mobile width 375px: `/entry`, dynamic report form, drafts, OCR, history.
- Check no button text overflows, no overlapping controls, no blank map/AI surfaces.

---

### Task 1: Upgrade Spec To Wide Frontend Refactor

**Files:**
- Modify: `docs/superpowers/specs/2026-04-29-industrial-ai-frontend-redesign-design.md`

- [ ] **Step 1: Confirm the spec says wide visual refactor**

Run:

```powershell
rg -n "大面积视觉返工|frontend-only|opus 4.7|Wide page-level rollout" docs/superpowers/specs/2026-04-29-industrial-ai-frontend-redesign-design.md
```

Expected: all terms are present.

- [ ] **Step 2: Commit spec update**

```powershell
git add docs/superpowers/specs/2026-04-29-industrial-ai-frontend-redesign-design.md
git commit -m "docs: 升级前端大面积视觉重构规格"
```

Expected: commit succeeds.

### Task 2: Establish Industrial AI Tokens

**Files:**
- Modify: `frontend/src/design/xt-tokens.css`
- Modify: `frontend/src/design/xt-base.css`
- Modify: `frontend/src/design/industrial.css`
- Modify: `frontend/src/design/xt-motion.css`
- Modify: `frontend/src/design/theme.css`

- [ ] **Step 1: Snapshot current visual debt**

Run:

```powershell
rg -n "gradient|backdrop-filter|transition: all|letter-spacing: -|box-shadow|radial-gradient" frontend/src/design frontend/src/views frontend/src/components
```

Expected: list of current debt and intentional candidates.

- [ ] **Step 2: Define palette and surface tokens**

In `xt-tokens.css`, update or add tokens for:

- page canvas: cold off-white, not beige.
- panel surfaces: white and slight blue-gray steps.
- text: graphite primary, muted steel secondary.
- accent: industrial blue.
- energy accent: small copper/furnace tone.
- shadows: low, crisp, layered.
- radii: 4px, 6px, 8px, 12px, pill.
- motion: 120ms, 180ms, 260ms, `cubic-bezier(0.16, 1, 0.3, 1)`.

- [ ] **Step 3: Add reduced-motion and interaction base rules**

In `xt-base.css` and `industrial.css`, ensure:

- `@media (prefers-reduced-motion: reduce)` disables scan/thinking loops.
- interactive controls use explicit transition properties, not `transition: all`.
- panels and tables have visible surface separation.

- [ ] **Step 4: Run frontend build**

```powershell
Set-Location frontend
npm run build
```

Expected: build passes.

- [ ] **Step 5: Commit foundation tokens**

```powershell
git add frontend/src/design/xt-tokens.css frontend/src/design/xt-base.css frontend/src/design/industrial.css frontend/src/design/xt-motion.css frontend/src/design/theme.css
git commit -m "style: 建立工业 AI 前端视觉 token"
```

### Task 3: Rebuild Xintai Logo And Shared XT Components

**Files:**
- Modify: `frontend/src/components/xt/XtLogo.vue`
- Create: `frontend/src/components/xt/XtFactoryMap.vue`
- Create: `frontend/src/components/xt/XtExecutionRail.vue`
- Create: `frontend/src/components/xt/XtAiThinking.vue`
- Create: `frontend/src/components/xt/XtAiActionCard.vue`
- Modify: `frontend/src/components/xt/index.js`
- Modify: `frontend/src/components/xt/XtCard.vue`
- Modify: `frontend/src/components/xt/XtKpi.vue`
- Modify: `frontend/src/components/xt/XtTable.vue`
- Modify: `frontend/src/components/xt/XtPageHeader.vue`
- Modify: `frontend/src/components/xt/XtActionBar.vue`
- Modify: `frontend/src/components/xt/XtSearch.vue`
- Modify: `frontend/src/components/xt/XtEmpty.vue`
- Modify: `frontend/src/components/xt/XtStatus.vue`

- [ ] **Step 1: Upgrade `XtLogo.vue`**

Keep current props `variant` and `color`. Replace the simple hex mark with a more styled SVG mark combining:

- aluminum ingot geometry.
- inner furnace/copper cell.
- batch-flow line.
- AI scan node.

Expected: no call sites need prop changes.

- [ ] **Step 2: Add `XtFactoryMap.vue`**

Component contract:

- `lines: Array`
- `nodes: Array`
- `alerts: Array`
- `activeKey: String`
- `compact: Boolean`

Render a presentational map only. Do not import API modules or stores.

- [ ] **Step 3: Add `XtExecutionRail.vue`**

Component contract:

- `steps: Array`
- `activeIndex: Number`
- `compact: Boolean`

Default labels must be Chinese: `发现`, `判断`, `执行`, `留痕`, `发布`.

- [ ] **Step 4: Add `XtAiThinking.vue`**

Component contract:

- `streaming: Boolean`
- `toolCalls: Array`
- `lastError: String`

When `streaming` is true, show phases: `读取现场`, `核对规则`, `推演影响`, `生成动作`.

- [ ] **Step 5: Add `XtAiActionCard.vue`**

Render compact action state cards for tool calls or suggested actions. Keep them display-only unless parent passes an existing click handler.

- [ ] **Step 6: Export new components**

Modify `frontend/src/components/xt/index.js`.

- [ ] **Step 7: Restyle shared XT primitives**

Update shared card/table/KPI/page header/action/search/empty/status components to use new tokens and explicit transitions.

- [ ] **Step 8: Build**

```powershell
Set-Location frontend
npm run build
```

Expected: build passes.

- [ ] **Step 9: Commit shared component pass**

```powershell
git add frontend/src/components/xt frontend/src/design
git commit -m "style: 重塑鑫泰品牌与共享组件"
```

### Task 4: Rebuild Login And Application Shells

**Files:**
- Modify: `frontend/src/views/Login.vue`
- Modify: `frontend/src/layout/ManageShell.vue`
- Modify: `frontend/src/layout/EntryShell.vue`
- Modify: `frontend/src/layout/AppShell.vue`

- [ ] **Step 1: Rebuild login first screen**

In `Login.vue`:

- Use `XtLogo`.
- Add a factory-map preview, not a marketing hero.
- Keep role selection and username/password behavior unchanged.
- Keep DingTalk and QR login pending states unchanged.

- [ ] **Step 2: Rebuild `ManageShell.vue`**

In `ManageShell.vue`:

- Replace single-character mark with `XtLogo`.
- Make sidebar feel like an industrial command rail.
- Keep `manageNavGroups(auth)` and route behavior unchanged.
- Keep Ctrl-K search behavior unchanged.

- [ ] **Step 3: Align `EntryShell.vue`**

Use a lightweight `XtLogo` brand mark, preserve mobile topbar/tabbar layout and all route behavior.

- [ ] **Step 4: Align `AppShell.vue`**

Only align legacy shell visuals. Do not change navigation logic.

- [ ] **Step 5: Browser visual check**

Run dev server:

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1
```

Check:

- `/login`
- `/manage/overview`
- `/entry`

Expected: no layout overlap at desktop and 375px widths.

- [ ] **Step 6: Build and commit**

```powershell
Set-Location frontend
npm run build
git add src/views/Login.vue src/layout/ManageShell.vue src/layout/EntryShell.vue src/layout/AppShell.vue
git commit -m "style: 重塑登录与应用外壳"
```

### Task 5: Rebuild Management Overview Into Factory War Map

**Files:**
- Modify: `frontend/src/views/review/OverviewCenter.vue`
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue`
- Use: `frontend/src/components/xt/XtFactoryMap.vue`
- Use: `frontend/src/components/xt/XtExecutionRail.vue`

- [ ] **Step 1: Map existing data to view models**

In `OverviewCenter.vue`, derive:

- `factoryMapLines` from existing production lines/runtime trace.
- `factoryMapAlerts` from `exception_lane`.
- `executionSteps` from delivery, exception, reconciliation, and report status data.

Do not add new API calls.

- [ ] **Step 2: Replace first-screen hierarchy**

Make the first visual block:

- center/left: `XtFactoryMap`
- right: AI manager sidecar
- bottom: `XtExecutionRail`

Keep date picker and refresh action.

- [ ] **Step 3: Preserve existing navigation**

Keep `go(routeName)` behavior and quick entries.

- [ ] **Step 4: Align `FactoryDirector.vue`**

Bring factory dashboard hero and runtime sections into the same factory-map language. Do not remove existing details hidden behind expansion.

- [ ] **Step 5: Build and visual check**

```powershell
Set-Location frontend
npm run build
```

Check:

- `/manage/overview`
- `/manage/factory`

Expected: first screen reads as Xintai industrial AI command surface, not generic cards.

- [ ] **Step 6: Commit overview/factory pass**

```powershell
git add src/views/review/OverviewCenter.vue src/views/dashboard/FactoryDirector.vue src/components/xt
git commit -m "style: 重构全厂作战地图总览"
```

### Task 6: Enrich AI Workstation Without Losing Simple Chat

**Files:**
- Modify: `frontend/src/views/ai/AiWorkstation.vue`
- Modify: `frontend/src/views/ai/AiChatMessage.vue`
- Modify: `frontend/src/views/ai/AiConversationList.vue`
- Use: `frontend/src/components/xt/XtAiThinking.vue`
- Use: `frontend/src/components/xt/XtAiActionCard.vue`

- [ ] **Step 1: Keep the simple path**

Confirm these still exist:

- conversation list.
- message stream.
- textarea composer.
- send/stop buttons.

- [ ] **Step 2: Add thinking state**

Render `XtAiThinking` when:

- `store.streaming` is true.
- `store.loadingMessages` is true.
- message tool calls are running.

- [ ] **Step 3: Upgrade tool call display**

In `AiChatMessage.vue`, keep details/pre fallback, but add richer visible state rows for tool calls.

- [ ] **Step 4: Add action cards**

Render `XtAiActionCard` under assistant messages when tool call data exists. Keep action execution display-only unless an existing handler exists.

- [ ] **Step 5: Improve composer**

Make composer feel like a command input while preserving Enter-to-send and disabled logic.

- [ ] **Step 6: Build and visual check**

```powershell
Set-Location frontend
npm run build
```

Check `/manage/ai`.

Expected:

- AI Workstation still feels like a minimal Q&A assistant.
- Thinking state is richer than a spinner.
- Tool/action states do not push layout around violently.

- [ ] **Step 7: Commit AI workstation pass**

```powershell
git add src/views/ai src/components/xt/XtAiThinking.vue src/components/xt/XtAiActionCard.vue
git commit -m "style: 丰富 AI 工作台问答与思考状态"
```

### Task 7: Wide Management Page Visual Pass

**Files:**
- Modify: `frontend/src/views/reports/ReportList.vue`
- Modify: `frontend/src/views/reports/ReportDetail.vue`
- Modify: `frontend/src/views/quality/QualityCenter.vue`
- Modify: `frontend/src/views/quality/QualityDetail.vue`
- Modify: `frontend/src/views/reconciliation/ReconciliationCenter.vue`
- Modify: `frontend/src/views/reconciliation/ReconciliationDetail.vue`
- Modify: `frontend/src/views/attendance/AttendanceOverview.vue`
- Modify: `frontend/src/views/attendance/AttendanceDetail.vue`
- Modify: `frontend/src/views/attendance/ExceptionList.vue`
- Modify: `frontend/src/views/imports/FileImport.vue`
- Modify: `frontend/src/views/imports/ImportHistory.vue`
- Modify: `frontend/src/views/shift/ShiftCenter.vue`
- Modify: `frontend/src/views/shift/ShiftDetail.vue`
- Modify: `frontend/src/views/energy/EnergyCenter.vue`
- Modify: `frontend/src/views/master/AliasMapping.vue`
- Modify: `frontend/src/views/master/Employee.vue`
- Modify: `frontend/src/views/master/Equipment.vue`
- Modify: `frontend/src/views/master/MachineWizard.vue`
- Modify: `frontend/src/views/master/ShiftConfig.vue`
- Modify: `frontend/src/views/master/Team.vue`
- Modify: `frontend/src/views/master/UserManagement.vue`
- Modify: `frontend/src/views/master/Workshop.vue`
- Modify: `frontend/src/views/master/WorkshopTemplateConfig.vue`
- Modify: `frontend/src/views/master/YieldRateDeprecationMap.vue`

- [ ] **Step 1: Normalize page headers**

Use the same page-header density, action alignment, date/filter spacing, and status badge style.

- [ ] **Step 2: Normalize tables**

Apply shared table treatment:

- tabular numbers.
- subtle row separators.
- compact but readable column padding.
- action buttons with consistent icon/text rhythm.

- [ ] **Step 3: Normalize cards and empty states**

Replace generic panels with surfaces that use the new token hierarchy.

- [ ] **Step 4: Fix obvious old text smells**

Where user-facing copy still suggests old manual reviewer/statistician main flow, adjust labels to exception handling or operational observation without changing permissions.

- [ ] **Step 5: Build**

```powershell
Set-Location frontend
npm run build
```

Expected: build passes.

- [ ] **Step 6: Browser smoke check**

Check:

- `/manage/reports`
- `/manage/quality`
- `/manage/reconciliation`
- `/manage/attendance`
- `/manage/imports`
- `/manage/shift`
- `/manage/master`

Expected: pages feel like one product family.

- [ ] **Step 7: Commit management page pass**

```powershell
git add src/views/reports src/views/quality src/views/reconciliation src/views/attendance src/views/imports src/views/shift src/views/energy src/views/master
git commit -m "style: 统一管理端核心页面视觉"
```

### Task 8: Wide Mobile Entry Visual Pass

**Files:**
- Modify: `frontend/src/views/mobile/MobileEntry.vue`
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`
- Modify: `frontend/src/views/mobile/ShiftReportForm.vue`
- Modify: `frontend/src/views/entry/EntryDrafts.vue`
- Modify: `frontend/src/views/mobile/OCRCapture.vue`
- Modify: `frontend/src/views/mobile/ShiftReportHistory.vue`
- Modify: `frontend/src/views/mobile/ReminderList.vue`
- Modify: `frontend/src/views/mobile/AttendanceConfirm.vue`
- Modify: `frontend/src/components/mobile/MobileSwipeWorkspace.vue`

- [ ] **Step 1: Preserve worker-first constraints**

Before changing visuals, confirm:

- buttons remain at least 48px high where they are primary worker actions.
- body text remains at least 16px on key form paths.
- no new complex factory map appears in `/entry`.

- [ ] **Step 2: Apply lightweight brand**

Use the new logo/brand language in top sections, status strips, and major action areas.

- [ ] **Step 3: Improve form rhythm**

Tighten section spacing, button hierarchy, sticky action bars, draft/history cards, OCR capture state.

- [ ] **Step 4: Remove expensive mobile visual patterns**

Remove or replace lingering `backdrop-filter`, heavy gradients, or permanent hover states.

- [ ] **Step 5: Build and mobile check**

```powershell
Set-Location frontend
npm run build
```

Browser check at 375px:

- `/entry`
- `/entry/report`
- `/entry/drafts`
- `/entry/ocr/2026-04-29/1`
- `/entry/history`
- `/entry/attendance`

Expected: no overflow, no overlapping bottom nav/action bar, low cognitive load preserved.

- [ ] **Step 6: Commit mobile pass**

```powershell
git add src/views/mobile src/views/entry src/components/mobile
git commit -m "style: 重塑移动填报端质感"
```

### Task 9: Cleanup, Full Verification, And Visual QA

**Files:**
- Modify as needed only where prior tasks left obvious visual debt.

- [ ] **Step 1: Search for banned patterns**

```powershell
rg -n "transition: all|backdrop-filter|purple|linear-gradient\\(.*blue|radial-gradient|letter-spacing: -" frontend/src
```

Expected: no unintentional banned patterns remain. Any remaining result must be justified by component context.

- [ ] **Step 2: Frontend build**

```powershell
Set-Location frontend
npm run build
```

Expected: build passes.

- [ ] **Step 3: E2E suite**

```powershell
Set-Location frontend
npx playwright test --workers=1
```

Expected: tests pass. If failures are visual-selector drift, fix tests only when behavior is unchanged and selectors are still meaningful.

- [ ] **Step 4: Browser visual pass**

Check desktop:

- `/login`
- `/manage/overview`
- `/manage/factory`
- `/manage/ai`
- `/manage/reports`
- `/manage/quality`
- `/manage/reconciliation`
- `/manage/imports`
- `/manage/master`

Check mobile width:

- `/entry`
- `/entry/report`
- `/entry/drafts`

- [ ] **Step 5: Commit cleanup**

```powershell
git add frontend/src
git commit -m "style: 收敛前端视觉重构细节"
```

- [ ] **Step 6: Final status**

```powershell
git status --short --branch
git log --oneline -8
```

Expected: only intended commits, clean working tree unless user has unrelated changes.

## Rollback Strategy

Each task commits a coherent batch. If a batch fails visually or functionally:

1. Identify the last good commit.
2. Revert only the failing style batch.
3. Keep earlier passing batches.

No database or backend state is touched, so rollback is Git-only.
