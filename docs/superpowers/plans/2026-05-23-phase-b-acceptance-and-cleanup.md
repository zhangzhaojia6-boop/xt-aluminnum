# Phase B 验收 + 旧引用清理记录

**日期**：2026-05-23
**分支**：`codex/owner-three-tab-management-skeleton`
**HEAD**：`2d8dcd6`
**spec**：`docs/superpowers/specs/2026-05-22-phase-b-today-production-design.md`
**plan**：`docs/superpowers/plans/2026-05-23-phase-b-today-production-implementation.md`

## 1. 测试结果

- 单测：`npm test` → 311/311 PASS（Phase A 基线 290 + Phase B 新增 21）
- e2e（chromium，本地 reuseServers）：12/12 PASS
  - `manage-shell.spec.js`：5/5
  - `manage-today-production.spec.js`（Task 9 新增）：3/3
  - `owner-three-tab-skeleton.spec.js`：4/4

## 2. spec §9 验收逐条核验

| # | 验收项 | 状态 | 证据 |
|---|---|---|---|
| 1 | `/manage/today` 默认进入"昨日"，标题显当前 target_date | ✅ | `useDashboardSnapshot.js` 默认 `dayjs().subtract(1, 'day')`；`TodayPage.vue:4` `<h1>{{ pageTitle }}</h1>` |
| 2 | 5 数 + 车间条形图 + 要紧事 + 成本一行 + 折叠正文 真数据 | ✅ | `TodayPage.vue` 全部从 `useDashboardSnapshot` computed 取 |
| 3 | 5 数中数字卡不可点击 | ✅ | `KpiBar.vue` 渲染纯 `<div>`，无 `@click` / `<a>` |
| 4 | `/manage/production` 同 API 同数字 | ✅ | `ProductionPage.vue` 也调 `useDashboardSnapshot()` |
| 5 | 要紧事 3 坑独立判断；count=0 灰底；全 0 隐藏 | ✅ | `_keyEvents.js` `buildKeyEvents` + `hasAnyEvent`，`TodayPage.vue` `v-if="hasKeyEvents"` |
| 6 | 要紧事 count>0 点击跳 alerts 带 surface | ✅ | e2e Task 9.1 验证 `/manage/alerts?surface=reconciliation` |
| 7 | 成本一行只显合计 + "口径：估算"，不展开 | ✅ | `CostLine.vue` 无电气拆分逻辑 |
| 8 | 估算金额 ÷10000；要紧事统一 `exception_lane` | ✅ | `TodayPage.vue` margin 计算 `÷10000`；`_keyEvents.js` SLOTS 全部从 `lane[s.field]` 取 |
| 9 | 不出现 "达成率/班次进度/月同比/top 3" | ✅ | e2e Task 9.3 `.toHaveCount(0)` 双 tab |
| 10 | 排名表 target_value 标"月均"，不染色；null → — | ✅ | `ProductionPage.vue` 表头列名 + `null ? '—' : ...`，无 tone class |
| 11 | summary_text 整段渲染，不切段 | ✅ | `TodayPage.vue` `<p>{{ leaderSummary.summary_text }}</p>` 单段 |
| 12 | 生产 tab 头部只 DateSwitcher，无周/月按钮 | ✅ | `ProductionPage.vue` header 仅 DateSwitcher |
| 13 | 手机/电脑共用一套组件 | ✅ | `KpiBar.vue` `@media (max-width: 720px)` 切 3 列 |
| 14 | KpiBar / WorkshopBarChart / KeyEventList 数据映射单测 | ✅ | `tests/manageKpiBar.test.js`、`manageWorkshopBarChart.test.js`、`manageKeyEventList.test.js` |
| 15 | e2e: today→5 数→要紧事→alerts→production→排名表 | ✅ | `manage-today-production.spec.js` |

全 15 条通过。

## 3. spec 内部偏移修补

- WorkshopBarChart 第二系列：spec §3.3 写"今日+月累"，但 `production_lane[]` 没有每车间月累字段。Task 8 评审时发现，commit `960d28a` 改为"今日+月日均"（target_value），与 §4.3 排名表口径对齐。
- ProductionPage 排名表"比昨日"列：实现初稿用 `compare_value`（昨日产量），spec §4.3 写的是 `delta_vs_yesterday`（带符号差值）。commit `9cef80b` 已修。

## 4. 旧引用清理候选（不在本轮删除）

以下文件 **仍存在于 `src/`，但生产代码（src/）已无引用**，仅 tests/ 还在断言。建议 Phase C 清理：

| 文件 | 引用状态 | 建议 |
|---|---|---|
| `frontend/src/views/review/OverviewCenter.vue` | src/ 零引用；tests/ 4 处 | Phase C 删除文件 + 同步更新或删除 `aiAssistantUiContract.test.js`、`managementMigrationCopy.test.js`、`manageRouteRedirects.test.js`、`overviewWipSummary.test.js` |
| `frontend/src/views/factory-command/FactoryOverview.vue` | src/ 零引用（Phase A 已切走）；tests/ 2 处 | Phase C 删除文件 + 更新 `aiAssistantUiContract.test.js`、`factoryCommandScreens.test.js` |
| `frontend/src/composables/useFactoryDashboard.js` | 仅 `views/dashboard/FactoryDirector.vue` 还在用 | 保留：FactoryDirector 是下钻页，本轮范围外 |

清理原则（CLAUDE.md §3）："如果发现无关 dead code，提一下，但不删"。本轮只记录，不动。

## 5. 文件结构汇总（Phase B 产出）

新增：
- `frontend/src/composables/useDashboardSnapshot.js`
- `frontend/src/components/manage/DateSwitcher.vue`
- `frontend/src/components/manage/KpiBar.vue`
- `frontend/src/components/manage/WorkshopBarChart.vue` + `_workshopRows.js`
- `frontend/src/components/manage/KeyEventList.vue` + `_keyEvents.js`
- `frontend/src/components/manage/CostLine.vue`
- 6 个对应单测文件
- `frontend/e2e/manage-today-production.spec.js`

重写：
- `frontend/src/views/manage/today/TodayPage.vue`（占位 → 96 行）
- `frontend/src/views/manage/production/ProductionPage.vue`（占位 → 161 行）

修改：
- `frontend/e2e/helpers/review-mocks.js` — `factory-director` mock body 增量补字段（leader_metrics.total_output_weight、analysis_handoff、management_estimate.remaining_weight、production_lane[]），全部为 additive，未删未改键名

## 6. 不在范围（推到后续）

- 异常 tab 重画 → Phase C
- 车间详情 / 机台 / 卷下钻视觉重做 → Phase C 或更晚
- `OverviewCenter.vue` / `FactoryOverview.vue` 文件级删除 → Phase C
- 后端字段新增（plan_target、班次粒度、附件 API）→ 独立后端轮
- 编辑者工作台 → Phase D
- 操作端工人填报整顿 → Phase E

## 7. 收尾

Phase B 完成。建议下一步：

1. 走 `superpowers:finishing-a-development-branch`，把 `codex/owner-three-tab-management-skeleton` 的 Phase A + B 提 PR 合并。
2. PR 合并后启动 Phase C spec（异常 tab 单列时间轴 + 下钻视觉）。
