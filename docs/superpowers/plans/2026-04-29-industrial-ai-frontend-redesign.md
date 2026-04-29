# 鑫泰铝业 数据中枢工业 AI 前端重构实施计划

> **执行约束:** 执行本计划时必须使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans。每一步用 checkbox（`- [ ]`）跟踪状态。

**目标:** 把前端改成能支撑试跑的工业 AI 数据中枢，而不是通用后台模板。系统名称统一为 `鑫泰铝业 数据中枢`，桌面端要有高密度工厂控制面、AI 总管侧栏、执行轨道和更完整的思考状态；移动端保留低负担填报，同时沿用同一套鑫泰品牌语言。

**架构:** 这是 frontend-only 的大面积视觉与信息架构重构。先建立设计 token 和可复用 XT 组件，再改登录、外壳、总览、AI、移动端和业务页面。路由、API 契约、权限、后端行为不变。

**UI/IA 升级:** 这次不只是换皮。页面动手前先补信息架构治理：命令式导航、模块入口版式、车间工艺图形、字段分层和冗余展示清理。

**技术栈:** Vue 3.5、Vite 8、Element Plus 2.8、Pinia、现有 scoped CSS 和 `frontend/src/design/*` token。不新增 npm 依赖。

---

## 范围与边界

这份计划会触碰超过 8 个前端文件。原因很明确：当前前端太像通用后台，用户要求做大面积视觉返工。

产品命名：

- 产品和系统的标准名称是 `鑫泰铝业 数据中枢`。
- UI、spec、plan、文档和面向用户的文案都用 `数据中枢` 表达产品身份。
- 不要把产品叫作 `MES` 系统。`MES` 只能作为外部生产系统、数据源、集成适配器或边界说明出现。

全局视觉语言：

- 高密度工业账本界面：紧凑页头、细分隔线、等宽数字、状态胶囊和动作轨道。
- Stripe 式精密感：冷白界面、低圆角、冷中性画布、工业蓝点缀和克制阴影。
- 轻量三维工业图形：等距产线、铝锭堆、设备块、批次流转轨和有层次的 AI 中枢。
- 功能模块图形：每个正式中心都要有业务化小图形，不再用通用图标卡片凑数。
- 车间工艺图形：铸锭、热轧、冷轧、拉矫、精整、剪切、在线退火、成品库和跨车间流转要有不同图形。
- AI 总管侧栏：预测、判断、调度、发布和问答入口要像职业经理人在控场，不像装饰性聊天框。
- 其他页面沿用这套语言，但不要机械复制总览页结构。

信息架构：

- 命令式导航：一级只保留总览、工厂、填报、AI、管理；长路由标题在导航里用短名，页面内保留正式全称。
- 模块入口：每个正式中心固定呈现模块编号、业务图形、3 个关键指标、当前状态和一个主动作。
- 车间页面：按工艺图形区分车间，并保持车间 -> 工序 -> 批次 -> 报告的事实链。
- 字段排版：字段分为主字段、辅助字段、审计/来源字段；大面积 `el-descriptions` 平铺改成结论、指标、交付、异常、审计区。
- 冗余清理：首屏删掉重复解释和重复字段，但不删后端字段，不改 API 数据。

动效语言：

- 工厂/数据流扫光：产线、执行轨和数据链路上用很轻的移动高光。
- AI 总管脉冲：思考和分析状态用克制的中枢脉冲，不用普通 spinner。
- 三段思考条：用紧凑动效表现读取数据、核对规则、生成动作。
- 三维深度脉冲：等距产线和 AI 中枢只做很轻的 z-depth 变化。
- 状态卡进入：预测、判断、动作卡使用小幅 `opacity + translateY` 入场。
- 执行推进：从催办到校验、汇总、发布，状态胶囊和轨道节点按进度点亮。
- 所有动效必须遵守 `prefers-reduced-motion`，并避免 `transition: all`。

不得触碰：

- 后端文件。
- API 契约。
- Auth、JWT、权限、角色、排班、设备绑定、外部 MES/生产系统同步。
- readyz、hard gate、AI 校验、workflow dispatcher、审计日志逻辑。
- npm 依赖或 Vite 配置。
- 为了解决字段冗余，不得改后端字段、数据库结构或 API payload。只能改前端分组、命名、排序和折叠呈现。

质量底线：

- 把用户原话“像opus 4.7在Claude code编码设计前端一样，参考其设计前端多好看，你gpt5.5设计的前端太难看了”作为前端质量约束。
- 避免通用 GPT 风格仪表盘。
- 每个批次完成前都要做桌面端和移动端浏览器检查。
- 丰富 AI 工作台的思考、工具和动作状态，但不能破坏极简问答路径。

## 数据流

多个视觉组件会消费展示状态，但数据流必须保持单向:

```text
Existing API/store/mock data
  -> page component computed view models
  -> page-local presentation grouping
  -> XtFactoryMap / XtExecutionRail / XtAiThinking / XtModuleTile / XtFieldGroup
  -> display only, or existing authorized UI actions
```

共享视觉组件不能直接调用 API。

## 文件结构

### 新建或替换

- `frontend/src/components/xt/XtFactoryMap.vue`
  - Reusable factory war-map visual for management overview and factory dashboard.
  - Props only: lines, nodes, alerts, activeKey, compact.
  - No API calls.
  - Includes the subtle factory/data flow sweep from the locked visual direction.
  - Includes lightweight isometric depth for factory decks, machine blocks, and aluminum ingot stacks.

- `frontend/src/components/xt/XtExecutionRail.vue`
  - Reusable “发现 → 判断 → 执行 → 留痕 → 发布” rail.
  - Props only: steps, activeIndex, compact.
  - No API calls.
  - Includes execution progression motion through rail steps and state capsules.

- `frontend/src/components/xt/XtAiThinking.vue`
  - AI thinking/tool/action state component for AI Workstation.
  - Props only: streaming, toolCalls, lastError.
  - Implements AI manager pulse and three-stage thinking bars.
  - Must support `prefers-reduced-motion`.

- `frontend/src/components/xt/XtAiActionCard.vue`
  - Compact action card rendered under AI answers when tool calls or suggested actions exist.
  - No direct execution unless the existing page already has an authorized handler.

- `frontend/src/components/xt/XtModuleGlyph.vue`
  - Reusable functional-module graphic.
  - Props only: moduleId, variant, status.
  - Variants: overview, entry, factory, ingestion, review, report, quality, cost, brain, ops, governance, master.
  - No API calls.

- `frontend/src/components/xt/XtWorkshopGlyph.vue`
  - Reusable workshop/process graphic.
  - Props only: workshopType, active, compact.
  - Types: casting, hot_roll, cold_roll, leveling, finishing, shearing, online_annealing, inventory, cross_workshop_flow.
  - No API calls.

- `frontend/src/components/xt/XtModuleTile.vue`
  - Reusable formal-center module tile.
  - Props only: module, metrics, status, actionLabel, compact.
  - Uses `XtModuleGlyph`.
  - No API calls.

- `frontend/src/components/xt/XtFieldGroup.vue`
  - Reusable field presentation group for detail pages and forms.
  - Props only: title, tier, items, collapsed.
  - Tiers: primary, supporting, audit.
  - No API calls and no hidden data mutation.

### 修改基础层

- `frontend/src/config/navigation.js`
  - Add short navigation labels and command-rail grouping for manage shell.
  - Keep route names, access rules, and redirects unchanged.

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
  - Upgrade logo from generic hex mark to stylized Xintai aluminum/furnace/batch-flow mark with subtle isometric depth.

- `frontend/src/components/xt/XtModuleGlyph.vue`
- `frontend/src/components/xt/XtWorkshopGlyph.vue`
  - Add the functional module and workshop process graphic systems.

- `frontend/src/components/xt/XtModuleTile.vue`
- `frontend/src/components/xt/XtFieldGroup.vue`
  - Add the formal module layout and field grouping primitives.

- `frontend/src/components/xt/XtCard.vue`
- `frontend/src/components/xt/XtKpi.vue`
- `frontend/src/components/xt/XtTable.vue`
- `frontend/src/components/xt/XtPageHeader.vue`
- `frontend/src/components/xt/XtActionBar.vue`
- `frontend/src/components/xt/XtSearch.vue`
- `frontend/src/components/xt/XtEmpty.vue`
- `frontend/src/components/xt/XtStatus.vue`
  - Bring shared components into the new surface vocabulary.

### 修改外壳与入口

- `frontend/src/views/Login.vue`
  - Rebuild first screen with brand mark, factory-map preview, and precise login panel.

- `frontend/src/layout/ManageShell.vue`
  - Apply new logo, command-bar density, side navigation, topbar, and elevated workspace surfaces.

- `frontend/src/layout/EntryShell.vue`
  - Apply lightweight mobile brand language without adding map complexity.

- `frontend/src/layout/AppShell.vue`
  - Keep compatibility shell visually aligned for legacy routes that still import `AppShell`.

### 修改核心页面

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

### 修改管理页面族

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

### 修改移动填报页面族

- `frontend/src/views/mobile/MobileEntry.vue`
- `frontend/src/views/mobile/DynamicEntryForm.vue`
- `frontend/src/views/mobile/ShiftReportForm.vue`
- `frontend/src/views/entry/EntryDrafts.vue`
- `frontend/src/views/mobile/OCRCapture.vue`
- `frontend/src/views/mobile/ShiftReportHistory.vue`
- `frontend/src/views/mobile/ReminderList.vue`
- `frontend/src/views/mobile/AttendanceConfirm.vue`
  - Apply mobile Xintai brand language, stronger touch targets, tighter hierarchy.
  - 不要把工厂地图的复杂度带进工人填报端。

## 验证命令

每个主要批次后运行:

```powershell
Set-Location frontend
npm run build
```

跨页面改动后运行:

```powershell
Set-Location frontend
npx playwright test --workers=1
```

本地浏览器预览:

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1
```

视觉检查:

- Desktop: login, `/manage/overview`, `/manage/factory`, `/manage/ai`, reports, quality, reconciliation, master data.
- Mobile width 375px: `/entry`, dynamic report form, drafts, OCR, history.
- Check no button text overflows, no overlapping controls, no blank map/AI surfaces.

---

### Task 1: 升级规格为大面积前端重构

**Files:**
- Modify: `docs/superpowers/specs/2026-04-29-industrial-ai-frontend-redesign-design.md`

- [ ] **Step 1: Confirm the spec says wide visual refactor**

运行:

```powershell
rg -n "大面积视觉返工|frontend-only|opus 4.7|UI/IA 双层重构|字段排版与冗余治理|导航栏排版层|功能模块排版层" docs/superpowers/specs/2026-04-29-industrial-ai-frontend-redesign-design.md
```

预期: 所有关键词都能搜到。

- [ ] **Step 2: Commit spec update**

```powershell
git add docs/superpowers/specs/2026-04-29-industrial-ai-frontend-redesign-design.md
git commit -m "docs: 升级前端大面积视觉重构规格"
```

预期: commit 成功。

### Task 2: 建立工业 AI 设计 Token

**Files:**
- Modify: `frontend/src/design/xt-tokens.css`
- Modify: `frontend/src/design/xt-base.css`
- Modify: `frontend/src/design/industrial.css`
- Modify: `frontend/src/design/xt-motion.css`
- Modify: `frontend/src/design/theme.css`

- [ ] **Step 1: Snapshot current visual debt**

运行:

```powershell
rg -n "gradient|backdrop-filter|transition: all|letter-spacing: -|box-shadow|radial-gradient" frontend/src/design frontend/src/views frontend/src/components
```

预期: 列出当前视觉债务和需要保留的候选项。

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

预期: build 通过。

- [ ] **Step 5: Commit foundation tokens**

```powershell
git add frontend/src/design/xt-tokens.css frontend/src/design/xt-base.css frontend/src/design/industrial.css frontend/src/design/xt-motion.css frontend/src/design/theme.css
git commit -m "style: 建立工业 AI 前端视觉 token"
```

### Task 3: 重塑鑫泰 Logo 与共享 XT 组件

**Files:**
- Modify: `frontend/src/components/xt/XtLogo.vue`
- Create/modify: `frontend/src/components/xt/XtFactoryMap.vue`
- Create/modify: `frontend/src/components/xt/XtExecutionRail.vue`
- Create/modify: `frontend/src/components/xt/XtAiThinking.vue`
- Create/modify: `frontend/src/components/xt/XtAiActionCard.vue`
- Create: `frontend/src/components/xt/XtModuleGlyph.vue`
- Create: `frontend/src/components/xt/XtWorkshopGlyph.vue`
- Create: `frontend/src/components/xt/XtModuleTile.vue`
- Create: `frontend/src/components/xt/XtFieldGroup.vue`
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

预期: 不需要修改调用方 props。

- [ ] **Step 2: Add `XtFactoryMap.vue`**

组件契约:

- `lines: Array`
- `nodes: Array`
- `alerts: Array`
- `activeKey: String`
- `compact: Boolean`

只渲染展示地图。不要导入 API 模块或 store。

- [ ] **Step 3: Add `XtExecutionRail.vue`**

组件契约:

- `steps: Array`
- `activeIndex: Number`
- `compact: Boolean`

Default labels must be Chinese: `发现`, `判断`, `执行`, `留痕`, `发布`.

- [ ] **Step 4: Add `XtAiThinking.vue`**

组件契约:

- `streaming: Boolean`
- `toolCalls: Array`
- `lastError: String`

When `streaming` is true, show phases: `读取现场`, `核对规则`, `推演影响`, `生成动作`.

- [ ] **Step 5: Add `XtAiActionCard.vue`**

Render compact action state cards for tool calls or suggested actions. Keep them display-only unless parent passes an existing click handler.

- [ ] **Step 6: Add `XtModuleGlyph.vue`**

组件契约:

- `moduleId: String`
- `variant: String`
- `status: String`
- `compact: Boolean`

Render one purpose-built mini graphic per formal center:

- overview / factory: flow map and nodes.
- entry: stacked direct-entry form and batch line.
- ingestion: source ring and mapping lines.
- review / quality: triage list and alert block.
- report: delivery rail.
- cost: matrix / stack bars.
- brain: AI hub / thinking bars.
- ops / governance / master: matrix, policy boundary, template stack.

- [ ] **Step 7: Add `XtWorkshopGlyph.vue`**

组件契约:

- `workshopType: String`
- `active: Boolean`
- `compact: Boolean`

Render distinct workshop/process graphics:

- casting: furnace, casting node, ingot flow.
- hot_roll: heated slab, rollers, shearing.
- cold_roll: coil and roller pair.
- leveling: washing / leveling / annealing line.
- finishing / shearing: cut rails and packaging.
- online_annealing: continuous annealing line.
- inventory: stacked ingots / warehouse blocks.
- cross_workshop_flow: batch-number fact chain.

- [ ] **Step 8: Add `XtModuleTile.vue`**

组件契约:

- `module: Object`
- `metrics: Array`
- `status: String`
- `actionLabel: String`
- `compact: Boolean`

Render fixed module anatomy:

- module number.
- short title.
- `XtModuleGlyph`.
- exactly 3 metric cells when data exists.
- status capsule.
- one primary action.

- [ ] **Step 9: Add `XtFieldGroup.vue`**

组件契约:

- `title: String`
- `tier: String`
- `items: Array`
- `collapsed: Boolean`

Tiers:

- primary: visible by default and visually strongest.
- supporting: grouped by business meaning and may be collapsed.
- audit: collapsed by default and placed near page bottom.

移动端不要隐藏工人必填字段。填报表单可以用步骤或分区承载，但不能把必填项塞进很小的折叠区。

- [ ] **Step 10: Export new components**

Modify `frontend/src/components/xt/index.js`.

- [ ] **Step 11: Restyle shared XT primitives**

Update shared card/table/KPI/page header/action/search/empty/status components to use new tokens and explicit transitions.

- [ ] **Step 12: Build**

```powershell
Set-Location frontend
npm run build
```

预期: build 通过。

- [ ] **Step 13: Commit shared component pass**

```powershell
git add frontend/src/components/xt frontend/src/design
git commit -m "style: 重塑鑫泰品牌与共享组件"
```

### Task 4: 重构登录页与应用外壳

**Files:**
- Modify: `frontend/src/config/navigation.js`
- Modify: `frontend/src/views/Login.vue`
- Modify: `frontend/src/layout/ManageShell.vue`
- Modify: `frontend/src/layout/EntryShell.vue`
- Modify: `frontend/src/layout/AppShell.vue`

- [ ] **Step 1: Add command navigation short labels**

In `frontend/src/config/navigation.js`, add display metadata without changing route names or access:

- `shortLabel` for long labels.
- `commandGroup` for first-level groups: 总览, 工厂, 填报, AI, 管理.
- `secondaryGroup` for expanded grouping.

Navigation text rules:

- first-level rail uses only short labels or glyphs.
- long labels such as `数据接入与字段映射中心` become `数据接入` in navigation.
- page title still shows the full formal name.
- legacy/compatible entries stay out of first-level rail.

- [ ] **Step 2: Rebuild login first screen**

In `Login.vue`:

- Use `XtLogo`.
- Add a factory-map preview, not a marketing hero.
- Keep role selection and username/password behavior unchanged.
- Keep DingTalk and QR login pending states unchanged.

- [ ] **Step 3: Rebuild `ManageShell.vue`**

In `ManageShell.vue`:

- Replace single-character mark with `XtLogo`.
- Make sidebar feel like a data-hub command rail.
- Use `shortLabel` / `commandGroup` where available.
- Keep `manageNavGroups(auth)` and route behavior unchanged.
- Keep Ctrl-K search behavior unchanged.

- [ ] **Step 4: Align `EntryShell.vue`**

Use a lightweight `XtLogo` brand mark, preserve mobile topbar/tabbar layout and all route behavior.

- [ ] **Step 5: Align `AppShell.vue`**

只对齐旧外壳视觉，不改导航逻辑。

- [ ] **Step 6: Browser visual check**

Run dev server:

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1
```

Check:

- `/login`
- `/manage/overview`
- `/entry`

预期: 桌面和 375px 宽度下都没有布局重叠。

- [ ] **Step 7: Build and commit**

```powershell
Set-Location frontend
npm run build
git add src/config/navigation.js src/views/Login.vue src/layout/ManageShell.vue src/layout/EntryShell.vue src/layout/AppShell.vue
git commit -m "style: 重塑登录与应用外壳"
```

### Task 5: 把管理总览改成全厂作战地图

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

不要新增 API 调用。

- [ ] **Step 2: Replace first-screen hierarchy**

Make the first visual block:

- center/left: `XtFactoryMap`
- right: AI manager sidecar
- bottom: `XtExecutionRail`

Keep date picker and refresh action.

- [ ] **Step 3: Preserve existing navigation**

Keep `go(routeName)` behavior and quick entries.

- [ ] **Step 4: Align `FactoryDirector.vue`**

把工厂看板首屏和运行区统一到工厂地图语言。不要删除原来折叠区里的细节。

- [ ] **Step 5: Build and visual check**

```powershell
Set-Location frontend
npm run build
```

Check:

- `/manage/overview`
- `/manage/factory`

预期: 首屏像鑫泰工业 AI 指挥界面，不像通用卡片后台。

- [ ] **Step 6: Commit overview/factory pass**

```powershell
git add src/views/review/OverviewCenter.vue src/views/dashboard/FactoryDirector.vue src/components/xt
git commit -m "style: 重构全厂作战地图总览"
```

### Task 6: 丰富 AI 工作台，同时保留极简问答

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

预期:

- AI Workstation still feels like a minimal Q&A assistant.
- Thinking state is richer than a spinner.
- Tool/action states do not push layout around violently.

- [ ] **Step 7: Commit AI workstation pass**

```powershell
git add src/views/ai src/components/xt/XtAiThinking.vue src/components/xt/XtAiActionCard.vue
git commit -m "style: 丰富 AI 工作台问答与思考状态"
```

### Task 7: 管理端页面族视觉统一

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
- Use: `frontend/src/components/xt/XtModuleTile.vue`
- Use: `frontend/src/components/xt/XtModuleGlyph.vue`
- Use: `frontend/src/components/xt/XtWorkshopGlyph.vue`

- [ ] **Step 1: Normalize page headers**

Use the same page-header density, action alignment, date/filter spacing, and status badge style.

- [ ] **Step 2: Normalize module entrance layout**

For formal-center overview pages and module grids, use the module anatomy:

- module number.
- short title.
- functional glyph.
- 3 key metrics where available.
- current status capsule.
- one primary action.

Avoid generic repeated cards that only differ by title.

- [ ] **Step 3: Apply workshop graphics where relevant**

Use `XtWorkshopGlyph` on:

- `/manage/factory`
- `/manage/workshop`
- main-data workshop/template pages.
- mobile current-shift summary where space allows.

Map workshop/process types to glyphs without adding API calls.

- [ ] **Step 4: Normalize tables**

Apply shared table treatment:

- tabular numbers.
- subtle row separators.
- compact but readable column padding.
- action buttons with consistent icon/text rhythm.

- [ ] **Step 5: Normalize cards and empty states**

Replace generic panels with surfaces that use the new token hierarchy.

- [ ] **Step 6: Fix obvious old text smells**

Where user-facing copy still suggests old manual reviewer/statistician main flow, adjust labels to exception handling or operational observation without changing permissions.

- [ ] **Step 7: Build**

```powershell
Set-Location frontend
npm run build
```

预期: build 通过。

- [ ] **Step 8: Browser smoke check**

Check:

- `/manage/reports`
- `/manage/quality`
- `/manage/reconciliation`
- `/manage/attendance`
- `/manage/imports`
- `/manage/shift`
- `/manage/master`

预期: 页面看起来属于同一套产品。

- [ ] **Step 9: Commit management page pass**

```powershell
git add src/views/reports src/views/quality src/views/reconciliation src/views/attendance src/views/imports src/views/shift src/views/energy src/views/master
git commit -m "style: 统一管理端核心页面视觉"
```

### Task 7A: 字段排版与冗余展示治理

**Files:**
- Modify: `frontend/src/views/reports/ReportDetail.vue`
- Modify: `frontend/src/views/quality/QualityDetail.vue`
- Modify: `frontend/src/views/reconciliation/ReconciliationDetail.vue`
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`
- Modify: `frontend/src/views/mobile/ShiftReportForm.vue`
- Use: `frontend/src/components/xt/XtFieldGroup.vue`

- [ ] **Step 1: Define page-local field groups**

For each page, derive view-model arrays from existing loaded data:

- `primaryFields`: decision-critical fields shown immediately.
- `supportingFields`: context fields grouped by business meaning.
- `auditFields`: id/source/time/confirmation/fallback fields collapsed by default.

No backend field, schema, or API payload changes.

- [ ] **Step 2: Refactor `ReportDetail.vue` field layout**

Replace broad `el-descriptions` grids with:

- conclusion block.
- core metrics block.
- delivery/publication block.
- quality/anomaly block.
- audit/source block collapsed by default.

Keep all previously visible data reachable.

- [ ] **Step 3: Refactor quality and reconciliation details**

Apply the same tiering:

- primary: status, object, severity/result, owner/action.
- supporting: context, related report/workshop, business explanation.
- audit: ids, timestamps, source, fallback state.

- [ ] **Step 4: Refactor mobile entry field rhythm**

In `DynamicEntryForm.vue` and `ShiftReportForm.vue`:

- first screen shows only task identity and required main fields.
- optional补录,线索,审计 fields move to explicit section/page.
- required fields remain visible or reachable through the normal step flow, not buried behind tiny disclosures.
- helper copy is shortened; no repeated explanations on every section.

- [ ] **Step 5: Build and visual check**

```powershell
Set-Location frontend
npm run build
```

Check:

- `/manage/reports/detail/:id` using an existing report id.
- `/manage/quality/detail/:id` if data exists.
- `/manage/reconciliation/detail/:id` if data exists.
- 375px mobile entry flow.

预期: 首屏不再被平铺字段网格占满，所有字段仍然可达。

- [ ] **Step 6: Commit field governance pass**

```powershell
git add src/views/reports/ReportDetail.vue src/views/quality/QualityDetail.vue src/views/reconciliation/ReconciliationDetail.vue src/views/mobile/DynamicEntryForm.vue src/views/mobile/ShiftReportForm.vue src/components/xt/XtFieldGroup.vue
git commit -m "style: 治理字段排版与冗余展示"
```

### Task 8: 移动填报端视觉统一

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

预期: 不溢出，底部导航和操作栏不重叠，填报负担不增加。

- [ ] **Step 6: Commit mobile pass**

```powershell
git add src/views/mobile src/views/entry src/components/mobile
git commit -m "style: 重塑移动填报端质感"
```

### Task 9: 清理、全量验证与视觉 QA

**Files:**
- Modify as needed only where prior tasks left obvious visual debt.

- [ ] **Step 1: Search for banned patterns**

```powershell
rg -n "transition: all|backdrop-filter|purple|linear-gradient\\(.*blue|radial-gradient|letter-spacing: -" frontend/src
```

预期: 没有非预期禁用模式。仍然保留的结果必须能从组件场景解释。

- [ ] **Step 2: Frontend build**

```powershell
Set-Location frontend
npm run build
```

预期: build 通过。

- [ ] **Step 3: E2E suite**

```powershell
Set-Location frontend
npx playwright test --workers=1
```

预期: 测试通过。如果失败来自视觉选择器漂移，只能在行为不变且选择器仍有意义时修测试。

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

预期: 只包含计划内提交。除非用户有无关改动，否则工作区干净。

## 回滚策略

Each task commits a coherent batch. If a batch fails visually or functionally:

1. Identify the last good commit.
2. Revert only the failing style batch.
3. Keep earlier passing batches.

No database or backend state is touched, so rollback is Git-only.
