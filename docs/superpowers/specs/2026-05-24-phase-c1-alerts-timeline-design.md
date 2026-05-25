# Phase C-1 · 异常 tab 单列时间轴 · 设计文档

**日期**：2026-05-24
**作者**：xt（讨论） / Claude（成文）
**状态**：待用户复核
**前置**：Phase A + B 已合（`codex/owner-three-tab-management-skeleton`，31 commits 已 push 待 PR）
**范围**：异常 tab 视觉重做；车间下钻视觉留到 Phase C-2

---

## 1. 背景

Phase B 把今日 + 生产 tab 画完了。异常 tab 仍是老 `AlertsPage` 用 `?surface=` 切三个全屏 surface（`AnomalyReview` / `QualityCenter` / `ReconciliationCenter`）。老板一进异常 tab 看到的是某个工作台，不是"今天到底出了什么事"的全景。

Phase C-1 把异常 tab 改成**单列混流时间轴**，按时间倒序混合所有域的事件，老板从上到下扫完。卡片只看不动，点击跳老 surface 处理。

车间详情下钻视觉重做（`FactoryCommandShell` + 6 个屏）量级大、独立可解，拆到 Phase C-2 单独立 spec。

## 2. 数据底（已摸完）

异常事件目前分散在三个接口：

| 域 | 接口 | 取数路径 |
|---|---|---|
| 生产 / 填报 | `GET /api/v1/dashboard/factory-director?target_date=YYYY-MM-DD` | `exception_lane.recent_items[]` / `returned_items[]` / `reminder_items[]` |
| 质检 | `GET /api/quality/issues?target_date=YYYY-MM-DD` | 数组 |
| 对账 | `GET /api/reconciliation/items?target_date=YYYY-MM-DD&status=open` | 数组 |

**Phase B 单 API 原则破例**：异常 tab 是消息中心语义，必须事件全口径覆盖，前端 `Promise.allSettled` 三接口聚合是有意为之。后端聚合接口属独立后端轮，不阻塞本轮。

**字段结构**（`backend/app/schemas/dashboard.py:130-145`）：

`exception_lane.recent_items` / `returned_items` / `reminder_items` 类型为 `list[dict[str, Any]] | None`，单条结构后端 prose 拼好。质检/对账两接口在前端 api 模块封装（`api/quality.js`、`api/reconciliation.js`），返回项规范化由前端归一化函数承担。

## 3. 架构

```
TodayPage 要紧事卡 ─→ /manage/alerts?domain=production
                          ↓
                    AlertsPage.vue (整页重写)
                          ├── DateSwitcher (复用 Phase B)
                          ├── DomainFilterChips (新)
                          ├── 汇总条 (一句话)
                          └── EventTimeline → EventCard × N (新)
                                  ↑
                          useAlertsTimeline (新 composable)
                                  ↓ Promise.allSettled
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
     factory-director       /quality/issues   /reconciliation/items
     (recent / returned     (前端 api 已有)    (前端 api 已有)
      / reminder)
```

**关键决策**：

- 老 `AlertsPage` 的 `?surface=` 切组件逻辑作废，但**老 surface 文件 `AnomalyReview` / `QualityCenter` / `ReconciliationCenter` 保留**，作为详细处理工作台
- 新建 `/manage/alerts/legacy?surface=...` 路由承载老 surface
- 老 `?surface=anomaly` query 自动 redirect 到 `?domain=production` 等，兼容 Phase B 链接
- 三接口任一失败 → 该域插占位卡，其它域照常显示（容错隔离）
- 整页只看，不写。点击卡片跳 legacy 路由，写操作仍由老 surface 承担

## 4. 组件清单

新建文件：

| 文件 | 职责 | 接口 |
|---|---|---|
| `composables/useAlertsTimeline.js` | 三接口聚合 + 归一化 + 排序 + 域过滤 | `useAlertsTimeline()` → `{ targetDate, domains, events, filteredEvents, domainCounts, loading, lastError, freshnessStatus, load(), stepDate(±1) }` |
| `components/manage/_alertEventNormalize.js` | 纯函数：原始数据 → `AlertEvent[]` | 导出 `normalizeFactoryDirector(payload, date)` / `normalizeQuality(items, date)` / `normalizeReconciliation(items, date)` |
| `components/manage/DomainFilterChips.vue` | 顶部域过滤芯片（多选 + "全部"互斥） | props: `{ modelValue, counts }`；emit: `update:modelValue` |
| `components/manage/EventTimeline.vue` | 时间倒序事件列表 + 空态 + 汇总条 | props: `{ events, totalCount, openCount, targetDate }` |
| `components/manage/EventCard.vue` | 单条紧凑卡片：时间 + 域标签 + 一句话 + → | props: `{ event }`；click → `router.push(event.detailRoute)` |

**统一事件类型**（`_alertEventNormalize.js` 顶部 JSDoc）：

```js
/**
 * @typedef {Object} AlertEvent
 * @property {string} id              // 跨域唯一：`${domain}:${rawId}`
 * @property {'production'|'quality'|'reconciliation'|'reporting'} domain
 * @property {string} occurredAt      // ISO 字符串，前端按此排序
 * @property {string} summary         // 一句话："1 车间早班产量异常 -2.4%"
 * @property {string} detailRoute     // '/manage/alerts/legacy?surface=...'
 * @property {'open'|'resolved'|null} status
 * @property {boolean} [isFallback]   // true = 容错占位卡
 */
```

**改写文件**：

| 文件 | 改动 |
|---|---|
| `views/manage/alerts/AlertsPage.vue` | 整页重写。从切组件改为时间轴渲染。`?surface=` 兼容 redirect 到 `?domain=` |
| `router/index.js` | 加 `/manage/alerts/legacy` 路由承载老 surface；`?surface=anomaly\|quality\|reconciliation` query 在 navigation guard 里 redirect 到 `?domain=production\|quality\|reconciliation` |
| `views/manage/today/TodayPage.vue` | `KeyEventList` 跳转 query 从 `?surface=` 改为 `?domain=` |
| `e2e/helpers/review-mocks.js` | 增量补 `quality_issues` / `reconciliation_items` mock，与 factory-director mock 同 mock body |

**保留不动**：`views/attendance/AnomalyReview.vue` / `views/quality/QualityCenter.vue` / `views/reconciliation/ReconciliationCenter.vue`。

**域 → 颜色 token**：

| 域 | 文字色 token | 背景色 |
|---|---|---|
| production | `--xt-color-warning` | `color-mix(in srgb, var(--xt-color-warning) 12%, transparent)` |
| quality | `--xt-color-danger` | `color-mix(in srgb, var(--xt-color-danger) 12%, transparent)` |
| reconciliation | `--xt-color-accent` | `color-mix(in srgb, var(--xt-color-accent) 12%, transparent)` |
| reporting | `--xt-text-muted` | `var(--xt-bg-panel-soft)` |

## 5. 数据流：三接口归一化

**字段映射**（`_alertEventNormalize.js`）：

| 域 | 来源 | 单条字段映射 |
|---|---|---|
| 生产 | `exception_lane.recent_items[]` | `id`=`production:${row.id ?? row.shift_id ?? idx}`<br>`occurredAt`=`row.occurred_at \|\| row.created_at \|\| target_date+'T00:00:00'`<br>`summary`=`row.summary \|\| 拼接(workshop+shift+desc)`<br>`detailRoute`=`/manage/alerts/legacy?surface=anomaly`<br>`status`=`row.status === 'resolved' ? 'resolved' : 'open'` |
| 填报 | `returned_items[]` + `reminder_items[]` | `domain`='reporting'，`detailRoute`=`/manage/alerts/legacy?surface=anomaly` |
| 质检 | `/api/quality/issues` 数组 | `domain`='quality'，`detailRoute`=`/manage/alerts/legacy?surface=quality` |
| 对账 | `/api/reconciliation/items` 数组 | `domain`='reconciliation'，`detailRoute`=`/manage/alerts/legacy?surface=reconciliation` |

**域归属规则**（避免 recent_items 与 returned/reminder 在填报场景重叠）：

`exception_lane.recent_items[]` 一律归 `production` 域；`returned_items[]` + `reminder_items[]` 一律归 `reporting` 域。后端如同时把同一异常塞进 recent + returned，前端按 `id` 去重时优先保留 `reporting` 域条目（更接近老板视角）。

**字段缺失兜底**：

- `occurredAt` 缺失：`target_date + 'T00:00:00'`，排序落到当日最早
- `summary` 缺失：拼 `${workshop_name} ${shift_label} ${event_type}`，缺哪段跳哪段
- `id` 缺失：`${domain}:${index}`（仅作 Vue key，不参与 detailRoute）
- 数组为 null/undefined：当作空数组，不抛错

**排序规则**：`occurredAt` 倒序（最近的最上面）。同一秒按 domain 字典序稳定排序，确保跨刷新顺序一致。

**容错隔离**（`useAlertsTimeline.load`）：

```js
const [fdResult, qResult, rResult] = await Promise.allSettled([...])
// 每个域独立判断 fulfilled / rejected
// 任一 rejected → events 头部塞一条 isFallback=true 的占位 AlertEvent:
//   { domain, summary: '加载失败，点击查看老页', detailRoute, isFallback: true }
// 其它域照常显示
```

**freshnessStatus**：

- 三接口全成 → `green`
- 至少一个失败 → `yellow`（DateSwitcher 同步状态点显示黄色）
- 全部失败 → `red` + 整页"三个数据源都加载失败"占位

**domainCounts**：未应用 domain 过滤前的全量计数。芯片显示 `生产 4`、`质检 2` 等。

**域过滤**：纯前端 computed。`domains.length === 0` 视为"全部"。

## 6. 视觉规范

**整页骨架**：

```
┌─ 异常 ──────────────────────────────────────┐
│  ← 5月19日 →   [刷新]    🟢 同步             │
│  [全部 12]  [生产 4]  [质检 2]  [对账 3]  [填报 3]
├──────────────────────────────────────────────┤
│  5 月 19 日 共 12 件，未结 3                  │
├──────────────────────────────────────────────┤
│  10:23  [生产]  1 车间早班产量异常 -2.4%   →│
│  09:50  [对账]  3 笔过磅与系统差异          →│
│  08:15  [填报]  1 车间晚班 未填报           →│
└──────────────────────────────────────────────┘
```

**EventCard 单卡布局**（高度桌面 56px / 手机 64px）：

```
┌────────────────────────────────────────┐
│ 10:23  [生产]  1车间早班产量异常 -2.4%  →│
└────────────────────────────────────────┘
  ↑       ↑      ↑                       ↑
  时间    域芯片  一句话(truncate)        箭头
  60px    56px   1fr                     24px
```

整卡 hover/click，不要内嵌按钮。`cursor: pointer`，hover `background: var(--xt-bg-panel-soft)`，active `transform: scale(0.995)`。

**域芯片样式**（小号 pill）：

```css
.xt-domain-pill {
  padding: 1px var(--xt-space-2);
  border-radius: var(--xt-radius-pill);
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0;
}
```

颜色按 §4 表中域 → token 映射使用 `color-mix()`，不写 rgba 字面量。

**DomainFilterChips**：

- "全部"是逻辑芯片：选中时清空 `domains[]`；选中其他芯片时自动取消"全部"
- 选中态：`background: var(--xt-color-accent); color: white;`
- 未选态：`background: var(--xt-bg-panel-soft); color: var(--xt-text-secondary);`
- count = 0 的芯片显灰底但仍可点击（点了就空列表 + 当日无此类异常）
- 高度 28px，间距 `var(--xt-space-2)`

**汇总条**：`{月}月{日}日 共 {totalCount} 件，未结 {openCount}`。`未结 0` 时换 "全部已处理" 灰字。

**空态**：events 为空 → 居中一行灰字 `当日无异常`。无图标无插画——产线场景，不需要"庆祝"动效。

**列表分隔**：事件之间 `border-bottom: 1px solid var(--xt-border)`。最后一条不画线。整列表外层 `var(--xt-radius-md)` + `var(--xt-border)` + `var(--xt-bg-panel)`，与今日 tab 排名表同款。

**响应式断点**：

- ≥720px：DateSwitcher 与 DomainFilterChips 同行（DateSwitcher 居左，过滤芯片居右）
- <720px：两行，DateSwitcher 在上，过滤芯片横滚（`overflow-x: auto`，不换行）
- 卡片始终单列。手机时间列 50px，桌面 60px

**容错占位卡**：

某域接口失败时，列表头部插一条特殊 EventCard：`background: color-mix(in srgb, var(--xt-color-warning) 8%, var(--xt-bg-panel))`，文案 `[质检] 加载失败 → 点击查看`，跳老 surface。

**token 强制**：所有新组件 0 hex / 0 rgba 字面量。`color-mix()` 调浅色透明背景，比硬编码 `rgba(...)` 更可主题化。

## 7. 测试

**单元测试**（`node --test`，源串断言模式，与 Phase B 一致）：

| 文件 | 覆盖点 |
|---|---|
| `tests/manageAlertEventNormalize.test.js` | `_alertEventNormalize.js` 三函数：字段映射、缺字段兜底、null 数组容错、id 规则、detailRoute 域映射 |
| `tests/manageAlertsTimeline.test.js` | `useAlertsTimeline.js`：`Promise.allSettled` 容错、`freshnessStatus` 三态、`domainCounts` 计算、域过滤、排序稳定性 |
| `tests/manageDomainFilterChips.test.js` | "全部"芯片互斥、count 显示、token 使用（无 hex）、a11y role |
| `tests/manageEventCard.test.js` | 域芯片色映射、点击 emit、容错占位卡渲染、整卡可点击（非内嵌按钮） |
| `tests/manageEventTimeline.test.js` | 空态文案、汇总条 "未结 0 → 全部已处理"、分隔线规则 |
| `tests/manageAlertsPage.test.js` | `?surface=anomaly` redirect 到 `?domain=production`、整页渲染 5 子组件、不出现 "TODO/暂未/敬请期待"、token 强制 |

**E2E**（`frontend/e2e/manage-alerts-timeline.spec.js`）：

- test 1：今日 → 要紧事"对账未结"→ `/manage/alerts?domain=reconciliation` → 验证对账芯片选中态 + 列表只剩对账事件
- test 2：切换日期 → 列表刷新 → 5 月 18 日有 6 条
- test 3：域过滤芯片多选 → 选生产+对账 → 列表过滤
- test 4：容错占位卡：mock 质检接口 500 → 列表头部出现 `[质检] 加载失败` 占位卡
- test 5：卡片点击 → 跳 `/manage/alerts/legacy?surface=anomaly` → 老 AnomalyReview 渲染

**mock 增量**：`e2e/helpers/review-mocks.js` 补 `quality_issues` / `reconciliation_items`，与 factory-director mock 同 mock body，不删不改老字段（参照 Phase B mock 增量原则）。

## 8. 验收

1. `/manage/alerts` 默认进入 = 昨日，DateSwitcher 复用 Phase B 同款
2. 顶部域过滤芯片：`[全部] [生产 N] [质检 N] [对账 N] [填报 N]`，全部互斥、其他多选
3. `?surface=anomaly|reconciliation|quality` 旧 query 自动 redirect 到 `?domain=production|reconciliation|quality`
4. 时间轴单列，按 `occurredAt` 倒序；同秒按 domain 字典序稳定
5. 卡片紧凑版：`时间 + 域标签 + 一句话 + →`，整卡 hover 可点击
6. 卡片点击 → 跳 `/manage/alerts/legacy?surface=...`
7. 三接口 `Promise.allSettled` 隔离容错；任一失败 → 占位卡 + 黄色 freshness 状态点
8. 全部失败 → 红色状态点 + 整页"三个数据源都加载失败"占位
9. 域过滤芯片 count 来自全量 events（不随过滤变化）
10. count = 0 的芯片仍可点（点了显空列表 + "当日无此类异常"）
11. 整页空 events → 居中"当日无异常"灰字，无图标
12. 汇总条："X 月 X 日 共 N 件，未结 M"；M=0 时换"全部已处理"
13. 域芯片色映射：生产=warning / 质检=danger / 对账=accent / 填报=muted；用 `color-mix()` 不写 rgba
14. 老 surface（AnomalyReview / QualityCenter / ReconciliationCenter）通过 legacy 路由仍可访问，文件不动
15. TodayPage 要紧事 3 卡跳转 query 从 `?surface=` 改为 `?domain=`
16. 不出现"处理 / 忽略 / 备注"等动作按钮；写操作仍由老 surface 承担
17. 手机/电脑共用一套组件，<720px 时过滤芯片横滚不换行
18. 单测 ≥ 现 311/311 baseline + 6 新文件覆盖单组件 + composable
19. e2e 5 项全过；与 Phase A+B 12 项基线一起回归

## 9. 不在范围

- 车间下钻视觉重做（Phase C-2 独立 spec）
- 后端事件聚合接口（把 quality / reconciliation 并进 `factory-director.exception_lane`）→ 独立后端轮，前端聚合是临时方案
- 异常状态写操作（已处理 / 忽略 / 转单 / 加备注）→ 老 surface 已实现，本轮保留
- 跨日"未结"清单视图（"今天累计还有什么没结"）→ Phase D 或更晚
- 异常通知推送（钉钉机器人触发规则）→ 后端独立轮
- 质检/对账接口字段补齐（如 `occurred_at` 缺失字段）→ 后端独立轮，本轮前端兜底
- 老 AlertsPage `?surface=` query 弃用通知 → 不发，redirect 已保证兼容

## 10. 后续

- Phase C-2：车间详情下钻视觉重做（`FactoryCommandShell` + 6 屏整体重画）
- Phase D：编辑者（总统计）工作台
- Phase E：操作端工人填报整顿
- 后端独立轮：`factory-director.exception_lane` 聚合 quality / reconciliation 事件，本 spec 的前端 3 接口拼是临时方案

