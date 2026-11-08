# 数据中枢总计划 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每天 10:00 自动发出完整、可追溯的 127 项日报；全部前端页面重新设计为简约大气的统一风格；人工只确认机器不知道的事。

**Architecture:** 不换技术栈，不新建门户和第二套日报。Vue 3 + Element Plus 不变，后端主链不变。七条工作线分开推进：数据和页面互不阻塞，但每条线内一次只做一个闭环。本文是总图和前端基础的实施步骤，其他工作线有各自的子计划。

**Tech Stack:** Vue 3、Vite、Element Plus、ECharts、Playwright、node:test；FastAPI、SQLAlchemy、PostgreSQL、pytest。

---

## 1. 这份计划依据什么

| 优先级 | 来源 | 地位 |
|---:|---|---|
| 1 | 负责人 2026-11-08 指令：所有页面重新设计，简约大气上档次 | 最新要求 |
| 2 | `docs/superpowers/specs/2026-11-08-system-overhaul-design.md` | 已批准的改造设计 |
| 3 | `docs/superpowers/specs/2026-08-14-statistics-free-operations-spec.md` | 总目标和验收门槛 |
| 4 | `docs/product-direction.md`、`docs/software-minus-agent-plus-prd.md`、`docs/system-design-direction.md`、`docs/agent-operating-guide.md` | 封档方向 |
| 5 | `AGENTS.md` | 硬规则和前端规则 |
| 6 | `docs/superpowers/specs/2026-09-07-management-dashboard-performance-design.md`、`docs/superpowers/reports/2026-09-14-multidisciplinary-review.md` | 性能和设计审查 |
| 7 | `docs/known-gaps-and-todos.md`、`docs/superpowers/` 其他历史文档 | 只作线索，以当前代码和生产为准 |

**与旧文档的差异：** 2026-09-14 的审查选择「先修误导性结果，不全面换视觉」，当时那几个 P0 已修完。现在负责人明确要求全面重做，以本计划为准。但重做视觉不能补上日报数据：常态缺的 89 项仍要现场提供，所以工作线 B 不因前端工作而暂停。

## 2. 不可突破的边界

- 127 项分母不减；缺数显示缺，不估算，不用历史值或 `0` 代替。
- MES 只读；`D:\输出skill` 只作比对；RAG 不提供实时数字。
- 产品名是 `鑫泰铝业 数据中枢`，不叫 MES。Hermes 对业务用户的身份是 `鑫泰铝业智能大脑`。
- 前端不新增 `description`、`explanation`、`helperText`、`tooltip`、`note`、`rationale` 这类属性，不加解释文案和营销文案。
- 保护 `/entry`、`/manage/today`、`/manage/live`、`/manage/production`、`/manage/coils` 路由。旧地址继续跳转。
- 改页面只改呈现，不改接口语义、权限、业务日期、来源和 trace。
- 写生产库先备份留 trace；`gh pr merge` 要负责人明确批准；第一次真实发钉钉先过目。
- Hermes 的两个定时任务由负责人决定保持运行，不暂停、不改回。

## 3. 总览

```text
A 现场恢复 ──┐
B 日报闭环 ──┼──> F 去统计切换
D Hermes 证据 ┘
C 前端重设计 ──> E 后端减量（靠新页面的访问数据判断）
G 工程底座：贯穿全程
```

| 线 | 目标 | 子计划 | 现状 |
|---|---|---|---|
| A 现场恢复 | 现场能重新扫码 | `2026-11-08-system-overhaul-s0-s1.md` Task 2 | 等现场贴码 |
| B 日报闭环 | 自动取得率 ≥ 80%，再到 95% | 同上 Task 1、3–8 | PR #120 待合并 |
| C 前端重设计 | 38 个页面统一重做 | 本文第 4–6 节 | 未开始 |
| D Hermes 证据 | 20 问真实验收，回答有来源和 trace | 第 8 节 | 代码在，真实验收未确认 |
| E 后端减量 | 冻结再合并未使用的服务 | 第 9 节 | 未开始 |
| F 去统计切换 | 7 日影子验收后停止人工统计 | 第 10 节 | 未开始 |
| G 工程底座 | 恢复 CI，测试可信 | 第 7 节 | Actions 被账单锁定 |

## 4. 前端设计语言

一句话：**白纸、品牌蓝、大数字、细分隔线。** 与门户网站同一品牌。靠留白和字号建立层级，不靠卡片、渐变、阴影和发光。

| 项目 | 规定 |
|---|---|
| 底色 | 页面白 `#FFFFFF`；次级区 `#F7F8FA`。取消深色 HUD、网格、发光 |
| 品牌色 | `#003890`，只用于主操作、当前导航、链接 |
| 文字 | 主 `#111827`，次 `#4B5563`，弱 `#6B7280` |
| 线 | `#E5E7EB` 1px 分隔。不用阴影做层次 |
| 状态色 | 只表示状态：`confirmed` 绿 `#1F7A4D`，`candidate` 蓝 `#003890`，`missing` 灰 `#6B7280`，`conflict` 橙 `#A8660B`，错误 红 `#B3261E` |
| 字体 | `"PingFang SC","Microsoft YaHei",system-ui,sans-serif`，不加载外部字体；数字用 `tabular-nums` |
| 字号 | 12、14、16、20、28、40、56。页面标题 28，主数字 40–56，正文 14 |
| 间距 | 4 的倍数；区块之间 40 |
| 圆角 | 控件 4px；不用大圆角卡片 |
| 动效 | 只有 150ms 状态过渡；遵守 `prefers-reduced-motion` |
| 图表 | 单系列品牌蓝，对比系列用灰；无背景网格重线、无渐变；直接标注，少用图例 |
| 数字 | 每个关键数字旁有状态和来源入口；缺失显示「暂无可信数据」，不显示 0 |

手机端（`/entry`）：单列，主按钮固定底部，触控区 ≥ 44px，一屏一件事。

管理端（`/manage`）：左侧窄导航 + 内容最大宽 1440px；一屏先结论，再明细。

## 5. 全部页面处理清单

共 38 个页面组件，外加 3 个外壳。合并后保留 31 个页面。被合并的路由继续跳转，不让旧链接失效。

| 批次 | 页面 | 路由 | 处理 |
|---|---|---|---|
| W1 | `Login.vue` | `/login` | 重做 |
| W1 | `EntryShell.vue`、`ManageShell.vue`、`AppShell.vue` | 外壳 | 重做；导航收到 5 个一级入口，其余进设置抽屉 |
| W2 | `mobile/MobileEntry.vue` | `/entry`、`/entry/profile` | 重做 |
| W2 | `mobile/UnifiedEntryForm.vue` | `/entry/fill` | 重做，并实现只显示目标字段 |
| W2 | `mobile/ShiftReportForm.vue` | `/entry/report/:d/:s` | 重做 |
| W2 | `mobile/CoilEntryWorkbench.vue` | `/entry/coil/:d/:s` | 重做 |
| W2 | `mobile/ConsumableEntry.vue` | `/entry/consumables` | 重做 |
| W2 | `mobile/OCRCapture.vue` | `/entry/ocr/:d/:s` | 重做 |
| W2 | `mobile/AttendanceConfirm.vue` | `/entry/attendance` | 重做 |
| W2 | `mobile/ShiftReportHistory.vue` | `/entry/history` | 重做 |
| W2 | `entry/EntryDrafts.vue` | `/entry/drafts` | 重做 |
| W3 | `manage/today/TodayPage.vue` | `/manage/today` | 重做为大仪表盘 |
| W3 | `reports/ReportList.vue` | `/manage/reports` | 并入今日页的历史 |
| W3 | `manage/live/LiveDashboardPage.vue` | `/manage/live` | 重做；取消深色大屏 |
| W3 | `manage/production/ProductionPage.vue` | `/manage/production` | 重做 |
| W3 | `manage/coils/CoilTracePage.vue` | `/manage/coils` | 重做 |
| W3 | `manage/alerts/AlertsPage.vue` | `/manage/alerts` | 重做 |
| W3 | `reconciliation/ReconciliationDetail.vue` | `/manage/reconciliation/detail/:id` | 并入异常详情 |
| W3 | `quality/QualityDetail.vue` | `/manage/quality/detail/:id` | 并入异常详情 |
| W4 | `manage/workshop-dashboard/WorkshopDashboardPage.vue` | `/manage/workshop-dashboard` | 重做 |
| W4 | `manage/fill-details/FillDetailsPage.vue` | `/manage/fill-details` | 重做 |
| W4 | `energy/EnergyCenter.vue` | `/manage/energy` | 重做 |
| W4 | `attendance/AttendanceOverview.vue` | `/manage/attendance` | 重做 |
| W4 | `inventory/InventoryCenter.vue` | `/manage/inventory` | 重做 |
| W4 | `factory-command/DestinationScreen.vue` | `/manage/factory/destinations` | 并入库存 |
| W4 | `contracts/ContractsCenter.vue` | `/manage/contracts` | 重做 |
| W4 | `ai/AiWorkstation.vue` | `/manage/ai-assistant` | 重做；先定 PR #83 |
| W5 | `master/Workshop.vue` | `/manage/master` | 重做为基础资料页 |
| W5 | `master/AliasMapping.vue` | `/manage/alias` | 并入基础资料 |
| W5 | `master/MesTerminalBinding.vue` | `/manage/mes-terminal-bindings` | 并入基础资料 |
| W5 | `master/UserManagement.vue` | `/manage/admin/users` | 重做 |
| W5 | `master/RuleConfigCenter.vue` | `/manage/admin/rules` | 重做 |
| W5 | `master/QRCodePrint.vue` | `/manage/admin/qr-print` | 重做 |
| W5 | `manage/admin/SystemSettingsPage.vue` | `/manage/admin/settings` | 重做 |
| W5 | `manage/admin/AgentManagementPage.vue` | `/manage/admin/agents` | 重做 |
| W5 | `manage/channels/CommunicationChannelsPage.vue` | `/manage/channels` | 并入通讯治理 |
| W5 | `review/GovernanceCenter.vue` | `/manage/admin/governance` | 重做 |
| W5 | `manage/rag/RagKnowledgePage.vue` | `/manage/rag` | 重做 |
| W5 | `manage/mapping-reconciliation/MappingReconciliationPage.vue` | `/manage/mapping-reconciliation` | 重做 |

顺序理由：登录和外壳每个人都看得到；现场恢复扫码后最先用到 `/entry`；管理层主线其次；后台最后。

已发现没有路由引用的文件，W6 核实后清理：`views/reports/LiveDashboard.vue`（4029 行）、`views/mobile/MobileBottomNav.vue`。

**每个页面的完成标准（都要满足）：**

1. 视觉符合第 4 节，页面里没有硬编码的颜色和深色样式。
2. 接口调用、权限、业务日期、来源、trace 行为和重做前一致。
3. 加载中、空数据、接口失败、缺失事实四种状态都看过。
4. 手机宽度 375、桌面宽度 1440 截图检查，无横向滚动；管理页另查 768。
5. `@axe-core/playwright` 无严重问题。
6. 关键页面首屏 3 秒内出现结论（`/entry/fill` 3 秒可填写）。
7. 相关 node 测试和 Playwright 通过。只允许更新断言旧布局的测试，断言数据、权限、状态的测试不能改。

## 6. 前端基础实施（W0–W1 第一步）

W2–W5 每批开工前先写该批的子计划，因为要先读完那批页面的代码才能写出准确的步骤。

### Task 1: 记录重做前的基线

**Files:**
- Create: `frontend/e2e/visual-baseline.spec.js`

- [ ] **Step 1: 记录测试基线**

Run: `cd frontend && npm test 2>&1 | tail -n 12`
Expected: 776 项全部通过（2026-11-08 基线，构建产物 2.9M）。后续以此为基线。

- [ ] **Step 2: 写截图基线**

```js
import { test } from '@playwright/test'

const PAGES = ['/login', '/manage/today', '/manage/live', '/manage/production', '/manage/coils', '/manage/alerts']

for (const path of PAGES) {
  for (const [label, width, height] of [['desktop', 1440, 900], ['mobile', 375, 812]]) {
    test(`baseline ${path} ${label}`, async ({ page }) => {
      await page.setViewportSize({ width, height })
      await page.goto(path)
      await page.waitForLoadState('networkidle')
      const name = path.replaceAll('/', '_') || 'root'
      await page.screenshot({ path: `test-results/baseline/${name}-${label}.png`, fullPage: true })
    })
  }
}
```

- [ ] **Step 3: 运行并保存**

Run: `cd frontend && npx playwright test e2e/visual-baseline.spec.js`
Expected: `test-results/baseline/` 下生成 12 张图。需要登录的页面若跳回登录页，改用 `e2e/helpers/review-mocks.js` 的现有登录模拟，再运行一次。

- [ ] **Step 4: 提交**

```bash
git add frontend/e2e/visual-baseline.spec.js
git commit -m "test: 记录前端重做前的页面基线"
```

### Task 2: 换设计令牌

**Files:**
- Modify: `frontend/src/design/xt-tokens.css`
- Modify: `frontend/src/design/theme.css`
- Test: `frontend/tests/design-tokens.test.js`

保留现有变量名，只改值，这样所有页面立刻跟随，不用逐个改引用。

- [ ] **Step 1: 写失败测试**

```js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const tokens = readFileSync(new URL('../src/design/xt-tokens.css', import.meta.url), 'utf8')

test('brand and paper tokens follow the design language', () => {
  assert.match(tokens, /--xt-primary:\s*#003890/)
  assert.match(tokens, /--xt-bg-page:\s*#ffffff/i)
  assert.match(tokens, /--xt-border:\s*#e5e7eb/i)
})

test('dark command tokens are gone', () => {
  assert.doesNotMatch(tokens, /--xt-command-blue-canvas/)
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && node --test tests/design-tokens.test.js`
Expected: FAIL，`--xt-primary` 还是 `oklch(51% 0.17 255)`。

- [ ] **Step 3: 改令牌值**

在 `frontend/src/design/xt-tokens.css` 的 `:root` 中改为：

```css
--xt-primary: #003890;
--xt-primary-hover: #002f78;
--xt-primary-active: #002660;
--xt-primary-light: #e6ebf4;
--xt-primary-soft: #f2f5fa;
--xt-bg-page: #ffffff;
--xt-bg-shell: #ffffff;
--xt-bg-panel: #ffffff;
--xt-bg-panel-soft: #f7f8fa;
--xt-bg-panel-muted: #f7f8fa;
--xt-text: #111827;
--xt-text-secondary: #4b5563;
--xt-text-muted: #6b7280;
--xt-border: #e5e7eb;
--xt-success: #1f7a4d;
--xt-warning: #a8660b;
--xt-danger: #b3261e;
--xt-info: #003890;
```

删除 `--xt-command-blue-canvas`、`--xt-command-blue-panel`、`--xt-command-blue-line`、`--xt-command-blue-cyan`、`--xt-command-blue-green`、`--xt-command-blue-amber`，并用下面的命令找到还在用它们的地方，把背景改成 `var(--xt-bg-page)`、线改成 `var(--xt-border)`、文字改成 `var(--xt-text)`。

Run: `grep -rn "xt-command-blue" frontend/src`
Expected: 改完后无输出。

- [ ] **Step 4: 把 Element Plus 主色接到令牌**

在 `frontend/src/design/theme.css` 的 `:root` 中加入（已有同名变量则替换）：

```css
--el-color-primary: var(--xt-primary);
--el-color-primary-dark-2: var(--xt-primary-active);
--el-color-primary-light-3: #4d74b1;
--el-color-primary-light-5: #809cc8;
--el-color-primary-light-7: #b3c3de;
--el-color-primary-light-8: #ccd7e9;
--el-color-primary-light-9: var(--xt-primary-light);
--el-border-radius-base: 4px;
--el-font-family: "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
```

- [ ] **Step 5: 验证**

Run: `cd frontend && node --test tests/design-tokens.test.js && npm run build`
Expected: 测试通过，构建成功。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/design frontend/tests/design-tokens.test.js
git commit -m "style: 设计令牌换成白纸和品牌蓝"
```

### Task 3: 统一的数字组件

**Files:**
- Create: `frontend/src/components/xt/XtMetric.vue`
- Test: `frontend/tests/xt-metric.test.js`

所有页面的关键数字都用它，保证缺失不会显示成 0。

- [ ] **Step 1: 写失败测试**

```js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/components/xt/XtMetric.vue', import.meta.url), 'utf8')

test('XtMetric shows missing facts as text, never zero', () => {
  assert.match(source, /暂无可信数据/)
  assert.match(source, /value === null \|\| value === undefined \|\| value === ''/)
})

test('XtMetric exposes the four fact states', () => {
  for (const state of ['confirmed', 'candidate', 'missing', 'conflict']) {
    assert.match(source, new RegExp(state))
  }
})

test('XtMetric does not introduce forbidden props', () => {
  assert.doesNotMatch(source, /description|explanation|helperText|tooltip|rationale/)
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend && node --test tests/xt-metric.test.js`
Expected: FAIL，文件不存在。

- [ ] **Step 3: 实现**

```vue
<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [Number, String], default: null },
  unit: { type: String, default: '' },
  state: { type: String, default: 'confirmed' },
  sourceRoute: { type: String, default: '' }
})

const STATE_LABELS = { confirmed: '已确认', candidate: '待确认', missing: '缺失', conflict: '有冲突' }
const isMissing = computed(() => {
  const value = props.value
  return value === null || value === undefined || value === ''
})
const stateKey = computed(() => (isMissing.value ? 'missing' : props.state))
</script>

<template>
  <div class="xt-metric">
    <div class="xt-metric__label">{{ label }}</div>
    <div v-if="isMissing" class="xt-metric__empty">暂无可信数据</div>
    <div v-else class="xt-metric__value">
      {{ value }}<span v-if="unit" class="xt-metric__unit">{{ unit }}</span>
    </div>
    <component
      :is="sourceRoute ? 'router-link' : 'span'"
      :to="sourceRoute || undefined"
      class="xt-metric__state"
      :class="`is-${stateKey}`"
    >{{ STATE_LABELS[stateKey] }}</component>
  </div>
</template>

<style scoped>
.xt-metric { display: grid; gap: 4px; font-family: var(--el-font-family); }
.xt-metric__label { font-size: 14px; color: var(--xt-text-secondary); }
.xt-metric__value { font-size: 40px; line-height: 1.1; font-weight: 600; color: var(--xt-text); font-variant-numeric: tabular-nums; }
.xt-metric__unit { margin-left: 4px; font-size: 14px; font-weight: 400; color: var(--xt-text-muted); }
.xt-metric__empty { font-size: 16px; line-height: 44px; color: var(--xt-text-muted); }
.xt-metric__state { font-size: 12px; text-decoration: none; }
.is-confirmed { color: var(--xt-success); }
.is-candidate { color: var(--xt-primary); }
.is-missing { color: var(--xt-text-muted); }
.is-conflict { color: var(--xt-warning); }
</style>
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend && node --test tests/xt-metric.test.js`
Expected: 3 项 PASS。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/xt/XtMetric.vue frontend/tests/xt-metric.test.js
git commit -m "feat: 统一的事实数字组件，缺失不显示为 0"
```

### Task 4: 出样给负责人选

**Files:** 无生产改动。

- [ ] **Step 1: 用新令牌重做 `/login` 和 `/manage/today` 首屏，在本地用样本数据运行**

Run: `cd frontend && npm run dev`
Expected: 两页都符合第 4 节。

- [ ] **Step 2: 截桌面和手机图，和 Task 1 的基线并排，交负责人确认风格**

这是整个前端工作的唯一视觉决策点。确认后 W2–W5 按此执行，不再逐页确认；不满意就在这一步改，不进入 W2。

## 7. 工作线 G：工程底座

| 项 | 动作 | 验收 |
|---|---|---|
| CI | 负责人处理 GitHub 账单 | Actions 真正运行 |
| CI 覆盖 | 审查 R8：把前端 node 测试和管理端浏览器测试纳入 CI | 绿灯范围写明 |
| 前端 node 测试 | 2026-11-08 基线 776 项全过；随页面重做，只更新旧布局断言 | 始终全过 |
| 前端发布 | 每批按 AGENTS.md 核对云端构建文件、实际返回的资源、Service Worker | 有证据才说上线 |
| 过时文档 | 更新 README（还写着主操手填、MES 以后接） | 与现状一致 |
| 过时地址 | Hermes 配置里的 `xtmijd.com` 和代码、文档里的旧域名 | `grep` 只剩历史记录 |

## 8. 工作线 D：Hermes 证据

现状来自计划勾选和提交记录，真实情况要先跑才知道：

| 需求 | 来源 | 动作 |
|---|---|---|
| 20 问回答都有结论、来源、状态、trace | 6/27 PRD、6/28 设计 | 用 `backend/app/services/hermes_20_question_acceptance.py` 在生产只读跑一遍，得到真实通过数，再决定修什么 |
| 管理端看得到证据链 | 6/27 PRD 7.5 | 并入 W3 的今日页和异常页 |
| 取证范围和当前日期、权限一致 | 9/14 审查 R4 | 写测试复现后修 |
| 来源状态按独立来源表达 | 9/14 审查 R5 | 并入 W3 今日页 |
| 未来时间不能算新鲜 | 9/14 审查 R6 | 跨原始时间、投影、序列化对照后修 |
| 聊天补录、责任人升级、事后摘要 | 8/14 Task 6 | 工作线 B 达到第一阶段后开始 |
| 网页 AI（PR #83） | 10/31 约定稳定后决定 | 恢复期已过。W4 前读 PR 和 R2–R4，再决定合并或重做 |
| 专业知识不充当实时数字 | 封档方向 | 20 问验收时一并确认 |
| 策略版本化、回放、回滚 | 8/14 第 4.5 节 | 负责人已恢复自我成长任务；排在闭环之后，当前不改它 |
| 系统判定开停机 | 8/14 Task 7 | 不在 127 项内，切换后再做 |

## 9. 工作线 E：后端减量

W3–W5 上线并恢复使用满 14 天后才开始，这时才有访问数据作依据。

- [ ] 用 `frontend` 的 telemetry 和 nginx 日志统计每个接口的真实调用。
- [ ] 候选线索：`/executive`、`/command`、铝价抓取（每天报错）、`/manage/factory/cost` 相关残留、AI mock 兜底（known gaps 第 2 项）。
- [ ] 每项登记到 `docs/datahub-deprecation-register.md`：标记、观察 7–14 天、验证、合并或删除。
- [ ] 不动 `DailyFactBundle`、MES/WMS 只读链路、钉钉证据、Hermes 依赖链、审计、trace；不删生产表。
- [ ] 重型查询继续优化（9/14 R7，9/7 实测接口 5–10 秒）：先测基线，再改，用同一样本对照。

## 10. 工作线 F：去统计切换

前置：B 达到第一阶段（≥ 80%），A 恢复使用，W2 上线。

- [ ] 实现 8/14 Task 9 的 `backend/scripts/run_statistics_free_shadow_gate.py`。
- [ ] 连续 7 个业务日影子运行，统计人员只核对结果。
- [ ] 门槛：适用字段自动取得率、完整率、准确率都 ≥ 95%；关键字段来源和口径正确率 100%；超容差 0；人工抄数、汇总、催报 0 次。
- [ ] 第一次给真实员工发的日报和消息，先给负责人过目。
- [ ] 达标后停止集中统计；未达标回到失败字段所属工作线。

## 11. 执行顺序

| 步 | 内容 | 依赖 |
|---:|---|---|
| 1 | 合并部署 PR #120 | 负责人批准 |
| 2 | 第 6 节 Task 1–4，出样 | 无 |
| 3 | 负责人确认风格 | Task 4 |
| 4 | W1 登录和外壳上线 | 第 3 步 |
| 5 | W2 `/entry` 上线；同时现场贴码（A） | 第 4 步 |
| 6 | 跑 20 问真实验收（D） | 无 |
| 7 | W3 管理主线，接入来源状态和 R5 | 第 4 步 |
| 8 | 能耗表、车间口径陆续接入（B） | 现场 |
| 9 | W4、W5 | 第 7 步 |
| 10 | W6 清理：删除 `xt-hud.css`、`industrial.css`、无引用页面 | W5 上线并观察 14 天 |
| 11 | E 后端减量 | 第 9 步 + 14 天 |
| 12 | F 切换 | B、A、W2 |

每批结束都重新核对生产状态和缺口分布，再决定下一步是否调整。

## 12. 需要负责人和现场提供的

| 事项 | 影响 | 卡在 |
|---|---|---|
| 批准合并 PR #120 | 日报记录 | 第 1 步 |
| 确认第 4 节的风格样稿 | 全部前端 | 第 3 步 |
| 贴新二维码、改钉钉首页地址 | 恢复使用 | 第 5 步 |
| 能源统计员每天发两张表 | 48 项，并影响成本 4 项 | B |
| 各车间产量口径 | 30 项 | B |
| 回收、磨辊、外加工、寄存责任人 | 7 项 | B |
| 处理 GitHub 账单 | CI | G |
