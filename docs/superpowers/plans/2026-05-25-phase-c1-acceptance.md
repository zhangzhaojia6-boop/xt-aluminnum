# Phase C-1 验收 + 清理记录

**日期**：2026-05-25
**分支**：`codex/phase-c1-alerts-timeline`
**HEAD**：`caf8580`
**spec**：`docs/superpowers/specs/2026-05-24-phase-c1-alerts-timeline-design.md`
**plan**：`docs/superpowers/plans/2026-05-24-phase-c1-alerts-timeline.md`

## 1. 测试结果

- 单测：`npm test` → **355/355 PASS**（Phase B 基线 311 + Phase C-1 新增 44）
  - 6 个新测试文件：`manageAlertEventNormalize.test.js`、`manageAlertsTimeline.test.js`、`manageEventCard.test.js`、`manageDomainFilterChips.test.js`、`manageEventTimeline.test.js`、`manageAlertsPage.test.js`
- e2e（chromium，本地 reuseServers）：**92/92 PASS，3 skipped，0 fail**
  - 新增 `manage-alerts-timeline.spec.js`：5/5
  - Phase A+B 三个核心 spec 全绿（`manage-shell` 5/5、`manage-today-production` 3/3、`owner-three-tab-skeleton` 4/4）

## 2. spec §8 验收逐条核验

| # | 验收项 | 状态 | 证据 |
|---|---|---|---|
| 1 | `/manage/alerts` 默认进入 = 昨日，DateSwitcher 复用 Phase B | ✅ | `useAlertsTimeline.js:37` `dayjs(now).subtract(1, 'day')`；`AlertsPage.vue:5` `<DateSwitcher>` 同款组件 |
| 2 | 顶部域过滤芯片：`[全部] [生产 N] [质检 N] [对账 N] [填报 N]`，全部互斥、其他多选 | ✅ | `DomainFilterChips.vue:25-30` 4 域 + 全部；`toggle()` push/filter，`clearDomains()` emit `[]` |
| 3 | `?surface=` 旧 query 自动 redirect 到 `?domain=` | ✅ | `AlertsPage.vue:40` `SURFACE_TO_DOMAIN`；`onMounted()` 读旧 query → `syncRouteFromDomains()` 写新 query；e2e `owner-three-tab-skeleton.spec.js:40-41` 跑 `/manage/quality` 落到 `?domain=quality` |
| 4 | 时间轴单列，按 `occurredAt` 倒序；同秒按 domain 字典序稳定 | ✅ | `_alertEventNormalize.js:79-82` `mergeAndSort` |
| 5 | 卡片紧凑版：`时间 + 域标签 + 一句话 + →`，整卡 hover 可点击 | ✅ | `EventCard.vue:1-15` grid 4 列 + `@click="emit('open')"`；`:hover` 变背景 |
| 6 | 卡片点击 → 跳 `/manage/alerts/legacy?surface=...` | ✅ | `EventTimeline.vue:39-41` `router.push(event.detailRoute)`；`_alertEventNormalize.js:1-3` legacy URL 常量；e2e `manage-alerts-timeline.spec.js:52-56` |
| 7 | 三接口 `Promise.allSettled` 隔离容错；任一失败 → 占位卡 + 黄色 freshness | ✅ | `useAlertsTimeline.js:62-87` `allSettled`；`fallbackCard()`；`freshnessStatus` 1-2 失败 = yellow；e2e `manage-alerts-timeline.spec.js:46-50` 单接口失败用例 |
| 8 | 全部失败 → 红色状态点 | ✅ | `useAlertsTimeline.js:120-123` `fails >= 3 → red`（4 域失败计数，覆盖三接口） |
| 9 | 域过滤芯片 count 来自全量 events（不随过滤变化） | ✅ | `useAlertsTimeline.js:105-112` `domainCounts` 遍历 `events.value`，与 `filteredEvents` 解耦 |
| 10 | count = 0 的芯片仍可点（点了显空列表 + "当日无此类异常"） | ✅ | `DomainFilterChips.vue:18` 不禁用；`EventTimeline.vue:9` 空态 `<p>当日无异常</p>` |
| 11 | 整页空 events → 居中"当日无异常"灰字，无图标 | ✅ | `EventTimeline.vue:9` `<p class="xt-event-timeline__empty">当日无异常</p>`；样式 `text-align: center; color: var(--xt-text-muted)` |
| 12 | 汇总条："X 月 X 日 共 N 件，未结 M"；M=0 时换"全部已处理" | ✅ | `EventTimeline.vue:5-7` 三态文案 |
| 13 | 域芯片色映射：生产=warning / 质检=danger / 对账=accent / 填报=muted；`color-mix()` 不写 rgba | ✅ | `EventCard.vue:56-59` 四 `.pill-*` 全部 `color-mix(in srgb, ...)`；样式块零 hex（单测 `manageEventCard.test.js` 也校验） |
| 14 | 老 surface 通过 legacy 路由仍可访问，文件不动 | ✅ | `router/index.js` `alerts/legacy` 路由 + `AlertsPage.legacy.vue` 薄壳；`AnomalyReview/QualityCenter/ReconciliationCenter` 文件零改动 |
| 15 | TodayPage 要紧事 3 卡跳转 query 从 `?surface=` 改为 `?domain=` | ✅ | `_keyEvents.js:1-5` `SLOTS[i].domain`；`KeyEventList.vue:21` `query: { domain: item.domain }`；e2e `manage-today-production.spec.js:21` 验证 `domain=reconciliation` |
| 16 | 不出现"处理 / 忽略 / 备注"等动作按钮；写操作仍由老 surface 承担 | ✅ | `AlertsPage.vue` / `EventTimeline.vue` / `EventCard.vue` 全部只渲染 `→`；无 `<button>` 动作 |
| 17 | 手机/电脑共用一套组件，<720px 时过滤芯片横滚不换行 | ✅ | `DomainFilterChips.vue:50-55` `flex-wrap: nowrap; overflow-x: auto` |
| 18 | 单测 ≥ 现 311/311 baseline + 6 新文件覆盖单组件 + composable | ✅ | 355/355 PASS（baseline 311 + 新增 44 across 6 files） |
| 19 | e2e 5 项全过；与 Phase A+B 12 项基线一起回归 | ✅ | 新增 5/5 + 整轮 92/92（Phase A+B 12 基线含其中） |

全 19 条通过。

## 3. plan ↔ 现实对齐修补（执行期发现）

实施过程中发现 plan 几处与代码现状偏移，已就近修正：

- **Task 2** ESM 静态 import 失败：`api/quality.js` / `api/reconciliation.js` 用 extensionless `'./index'`，Node `--test` 环境无法解析。改为 lazy `import()` 包装（`useAlertsTimeline.js:18-29`），保留默认行为不变，也使 composable 可注入测试 fake。
- **Task 4** plan 代码用 `#fff` 字面量做 fallback，会被组件单测的"无 hex 颜色"断言挡下。改为 CSS 关键字 `var(--xt-text-on-accent, white)`，语义等价。
- **Task 6** 之后两处旧 e2e 断言（`manage-today-production.spec.js:21` 的 `?surface=reconciliation`、`owner-three-tab-skeleton.spec.js:41` 的 `?surface=quality`）和 `manageRouteRedirects.test.js` 中读 `AlertsPage.vue` 的 5 条断言变成对老 URL/老页的引用——`AlertsPage` 现在挂载时统一改写 query 到 `?domain=`，相关断言已修正：
  - commit `0c700e4`：单测重指 `AlertsPage.legacy.vue`
  - commit `caf8580`：两个 e2e spec 重指 `?domain=`
- **Task 7** plan 写 meta 字段 `{ group: 'manage' }`，但 `router/index.js` 整个文件用的字段是 `zone:`，且每条相邻路由都通过 `...reviewMeta` 展开。改为 `...reviewMeta + title + canonical` 与邻路由一致。
- **Task 8** plan 的"File Structure"标的是 `TodayPage.vue` 写 `?surface=`，但实际查询字符串落在 `KeyEventList.vue:21`，`_keyEvents.js` 里是命名字段 `surface`。重命名 `surface → domain` + 三值映射 `anomaly/reconciliation/anomaly → production/reconciliation/reporting`，组件链路同步。
- **Task 9** plan 假设了 `signInAsManager` 和 `?api/quality/issues` 路径——repo 实际用 `setupReviewSessionAndMocks(page)` 一站式 helper 且后端前缀是 `/api/v1/`。改用现成 helper + 正确前缀，并把 `mockQualityIssues` / `mockReconciliationItems` / `mockQualityFailure` 三个 override helper 加在 `review-mocks.js` 末尾，默认 `reconciliation/items` 也加进 `setupReviewSessionAndMocks` 防止其他 spec 失踪 mock。

## 4. 文件结构汇总（Phase C-1 产出）

新增：

- `frontend/src/components/manage/_alertEventNormalize.js`
- `frontend/src/composables/useAlertsTimeline.js`
- `frontend/src/components/manage/EventCard.vue`
- `frontend/src/components/manage/DomainFilterChips.vue`
- `frontend/src/components/manage/EventTimeline.vue`
- `frontend/src/views/manage/alerts/AlertsPage.legacy.vue`
- `frontend/tests/manageAlertEventNormalize.test.js`
- `frontend/tests/manageAlertsTimeline.test.js`
- `frontend/tests/manageEventCard.test.js`
- `frontend/tests/manageDomainFilterChips.test.js`
- `frontend/tests/manageEventTimeline.test.js`
- `frontend/tests/manageAlertsPage.test.js`
- `frontend/e2e/manage-alerts-timeline.spec.js`
- `docs/superpowers/specs/2026-05-24-phase-c1-alerts-timeline-design.md`
- `docs/superpowers/plans/2026-05-24-phase-c1-alerts-timeline.md`
- `docs/superpowers/plans/2026-05-25-phase-c1-acceptance.md`（本文件）

整页重写：

- `frontend/src/views/manage/alerts/AlertsPage.vue`

调整：

- `frontend/src/router/index.js` 增 `alerts/legacy` 路由
- `frontend/src/components/manage/_keyEvents.js` 字段 `surface → domain` + 三值重映射
- `frontend/src/components/manage/KeyEventList.vue` link query `surface → domain`
- `frontend/e2e/helpers/review-mocks.js` factory-director payload 扩 `recent_items/returned_items/reminder_items`，加 `reconciliation/items` 默认 mock，加 3 个 override helper
- `frontend/tests/manageKeyEventList.test.js` 同步字段名
- `frontend/tests/manageRouteRedirects.test.js` 重指 legacy 文件
- `frontend/e2e/manage-today-production.spec.js` URL 断言
- `frontend/e2e/owner-three-tab-skeleton.spec.js` URL 断言

## 5. 提交日志（本轮 14 commit）

```
caf8580 test(e2e): update legacy assertions from ?surface= to ?domain=
9ccb275 test(alerts): e2e covering domain filter, fallback card, legacy deep-link
0c700e4 test(alerts): point legacy surface-switch assertions at AlertsPage.legacy.vue
0ee4c16 refactor(today): KeyEvent slot routes use ?domain= for new alerts page
7f81163 feat(alerts): add /manage/alerts/legacy route mounting old surfaces
584743b feat(alerts): rewrite AlertsPage as single-column timeline shell
c44cca2 feat(alerts): EventTimeline summary + empty + ordered list
f239a0a feat(alerts): DomainFilterChips with multi-select toggle
6359530 feat(alerts): EventCard compact card with domain pill
d52e3cf docs(useAlertsTimeline): clarify stepDate ↔ watcher coupling
05c5649 feat(alerts): useAlertsTimeline composable with allSettled
3267647 feat(alerts): _alertEventNormalize for 3-source merge+sort
8c41b40 docs(plans): Phase C-1 alerts timeline implementation plan
```

## 6. 待清理（不在本轮删除）

延续 Phase B 的清理候选清单，本轮未触动：

| 文件 | 引用状态 | 建议 |
|---|---|---|
| `frontend/src/views/review/OverviewCenter.vue` | src/ 零引用；tests/ 仍有 4 处 | Phase C-2 / D 删除 + 同步更新或删除 4 个测试文件 |
| `frontend/src/views/factory-command/FactoryOverview.vue` | src/ 零引用；tests/ 2 处 | Phase C-2 / D 删除 + 更新断言 |

Phase C-1 不动旧 surface 文件（`AnomalyReview` / `QualityCenter` / `ReconciliationCenter` / `AlertsPage.legacy.vue`），因为 §8 验收第 14 条要求 legacy 路由仍可访问。

## 7. 后续

- **PR 与 rebase**：`codex/phase-c1-alerts-timeline` 是从 Phase A+B 分支上长出来的。开 PR 前确认 A+B 已合到 `main`，再 `git fetch origin && git rebase origin/main`，预期冲突点在 `_keyEvents.js` 字段名和 `review-mocks.js` mock 体；其余文件 A+B 没碰过。
- **Phase C-2**：异常 tab 时间轴只是消息中心；下一步车间详情下钻视觉重做（`FactoryCommandShell` + 6 屏）规模大，独立 spec。
- **后端聚合接口**（spec §2 备注）：当前前端 `Promise.allSettled` 三接口聚合是有意为之，后端聚合接口属独立后端轮，不阻塞 C-1 / C-2。
