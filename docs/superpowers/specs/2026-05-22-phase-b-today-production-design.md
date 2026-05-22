# Phase B · 今日 + 生产 内容填充 · 设计文档

**日期**：2026-05-22
**作者**：xt（讨论） / Claude（成文）
**状态**：待用户复核
**前置**：Phase A 骨架已落（`codex/owner-three-tab-management-skeleton`，9 commits）
**范围**：今日 tab + 生产 tab 的视觉内容；异常 tab 不动

---

## 1. 背景

Phase A 把管理端骨架收拢到 3 tab（今日 / 生产 / 异常），路由、抽屉、redirect 全跑通。但今日 tab 现在是空的占位，生产 tab 还是嵌的旧 FactoryOverview。本轮把"老板每天进系统看到什么"这件事画完。

异常 tab 保持现 AlertsPage 的 surface 切换不动，等 Phase C 改单列时间轴。

## 2. 数据底（已摸完）

唯一 API：`GET /api/v1/dashboard/factory-director?target_date=YYYY-MM-DD`。今日和生产共用，**不调第二个**——避免数字对不上。

可用字段（详见 `backend/app/schemas/dashboard.py:481-502`）：

- `leader_summary.summary_text` —— 拼好的一句话长文本
- `leader_metrics.{total_output_weight, energy_per_ton, yield_rate, contract_weight, total_attendance, anomaly_total}`
- `history_digest.month_archive.{total_output, shipment_weight, contract_weight, energy_per_ton}` —— 月累
- `analysis_handoff.trend.{current_output, yesterday_output, output_delta_vs_yesterday, seven_day_average_output}`
- `management_estimate.{estimated_revenue, estimated_cost, estimated_margin, energy_cost, labor_cost, remaining_weight, assumptions}`
- `production_lane[]` —— 各车间今日产量 + target_value（**= 过去一月日均**，不是计划目标）+ delta_vs_yesterday
- `exception_lane.{production_exception_count, reconciliation_open_count, unreported_shift_count, mobile_exception_count, recent_items[], returned_items[], reminder_items[]}`

**后端字段不存在的、本轮不做**：达成率、班次进度（夜/早/晚）、月同比、附件下载。理由：没有计划目标系统、没有班次粒度、没有附件 API。不造假指标。

## 3. 今日 tab（默认页）

`/manage/today`（路由 Phase A 已锁，不改），`TodayPage.vue` 替换 OverviewCenter 嵌套，重新画。

**默认 target_date = 昨日**。理由：5/19 的产量要 5/20 早 8 点接力线推完才齐；老板上午进系统，"今日"如果默认今天会全是 0 和半天数据。日期切换允许前后翻，往后翻到当天通常会显示"数据未完成"。页面标题 = `{target_date} 日报`（例 "5月19日 日报"）。

### 3.1 布局（自上而下）

1. **头部**：日期前/后箭头 + 当前日期显示 + 刷新按钮 + 同步状态指示（绿/黄/红，从 `analysis_handoff.freshness` 来）
2. **5 数概览条**：5 张数字卡一排，电脑横排、手机两行 3+2
3. **车间分布条形图**：横向条形图，今日产量+月累两组，按今日产量降序
4. **今日要紧事**：固定 3 个坑位（生产/对账/填报）
5. **成本一行**：估算合计 + 口径标记
6. **完整正文（折叠）**：默认折起，展开 = `leader_summary.summary_text` 整段（不前端切段）

### 3.2 5 数定义

| # | 标题 | 数据 | 公式 |
|---|---|---|---|
| 1 | 日产量 | `leader_metrics.total_output_weight` | 单位 吨，2 位小数 |
| 2 | 比昨日 | `analysis_handoff.trend.output_delta_vs_yesterday` | 单位 吨，正绿负橙，箭头 ↑↓ |
| 3 | 日吨成本 | `management_estimate.estimated_cost / leader_metrics.total_output_weight` | 单位 元/吨，0 位小数；total_output 为 0 时显 — |
| 4 | 月累产量 | `history_digest.month_archive.total_output` | 单位 吨，0 位小数 |
| 5 | 估算毛利 | `management_estimate.estimated_margin` | 单位 万元，1 位小数；estimate_ready=false 时灰显 |

数字卡不点击。生产 tab 也是厂级合计 + 车间排名表，没有"日产量对应的子页面"可跳；强加点击会落到没意义的滚动锚点。Phase C 重做生产下钻时再考虑信任锚点。

### 3.3 车间分布条形图

- 数据源：`production_lane[]`
- 横向条，每个 workshop 一行，两组（今日 / 月累）
- 排序：今日产量降序
- 颜色：今日 = `--xt-color-accent`，月累 = `--xt-color-muted`
- ECharts，bar series，复用现有 `frontend/src/components/charts/` 模式
- 高度：电脑 360px 固定，手机 240px

### 3.4 今日要紧事

固定 3 个坑位（不是 top N、不是排序）：

| 坑位 | 触发 | 卡片标题 | 跳转 |
|---|---|---|---|
| 1 生产 | `production_exception_count > 0` | "生产异常 N 件" | `/manage/alerts?surface=anomaly` |
| 2 对账 | `reconciliation_open_count > 0` | "对账未结 N 条" | `/manage/alerts?surface=reconciliation` |
| 3 填报 | `unreported_shift_count > 0` | "未填报班次 N 个" | `/manage/alerts?surface=anomaly` |

各坑位独立判断：count = 0 时该卡显灰底"无"，不参与排序。3 个全 0 时区域整体不渲染（不要硬塞"今日无要紧事"占位）。

### 3.5 成本一行

`management_estimate.estimated_cost` 是合计估算，**后端没有拆电+气**——`assumptions` 里只有单价不是用量。to boss.md 里的"电费 14.00 万、气费 18.77 万"是 prose 字符串不是结构化字段。

展示：

```
今日估算成本 X.XX 万   口径：估算
```

不做"展开看电费气费"——后端没数据。Phase C 如要拆，需后端 `management_estimate` 加 `electricity_cost_value` / `gas_cost_value` 字段。

### 3.6 折叠正文

`<details>` 元素，summary 写"完整日报正文"。展开后单段 `<p>` 渲染 `leader_summary.summary_text`。**不切段**——后端拼好的就是一句话，前端按句号切会切错。to boss.md 那种 5 段是人手拼的，不是系统出的。Phase C 再考虑后端结构化输出。

## 4. 生产 tab

`/manage/production`，`ProductionPage.vue` 替换 FactoryOverview 嵌套，重新画**首屏**。下钻层（车间详情 / 机台 / 卷）保持现有 FactoryCommandShell 系列不动——本轮范围之外。

### 4.1 布局

1. **头部**：日期切换 + 刷新（与今日 tab 同款组件复用）
2. **厂级 5 数**
3. **车间排名表**

### 4.2 厂级 5 数

| # | 标题 | 数据 |
|---|---|---|
| 1 | 已产 | `leader_metrics.total_output_weight` |
| 2 | 比昨日 | `analysis_handoff.trend.output_delta_vs_yesterday` |
| 3 | 估算毛利 | `management_estimate.estimated_margin` |
| 4 | 合同缺口 | `management_estimate.remaining_weight` |
| 5 | 日吨能耗 | `leader_metrics.energy_per_ton` |

### 4.3 车间排名表

数据源：`production_lane[]`，按 `total_output` 降序。

列：

| 列 | 字段 | 说明 |
|---|---|---|
| 车间 | `workshop_name` | 点击进车间详情（旧路由 `/manage/production/workshop/:id`，本轮不重画详情）|
| 今日产量 | `total_output` | 单位 吨 |
| 比昨日 | `delta_vs_yesterday` | 正绿负橙 |
| 月均参照 | `target_value` | 灰字小号，加注"月均"，**不叫"目标"或"达成"**；null 时显 — |

**不染色，不显达成率百分比**——target_value 是月均不是计划，染色阈值（0.7? 0.8?）没业务依据；做了就是 AI 假规则。Phase C 如要染色，需要业务先定"低于什么算落后"。

**target_value 可能全空**：`backend/app/services/report/lane_builders.py:61` 路径直接给 `None`，只有 `mobile_report/lifecycle.py` 路径才有值。spec 实现要默认 null 不抛错。

### 4.4 时间维度

Phase B 只做"日"——和今日 tab 共用同一个 `DateSwitcher`（前/后箭头 + 当前日期）。**不放周/月切换按钮**——后端没有周/月聚合 API，灰显占位是 dead UI。Phase C 做趋势页时一起加。

## 5. 共用组件

`frontend/src/components/manage/`（新）：

- `KpiBar.vue` —— 5 数概览条，props: `{ items: KpiItem[] }`，KpiItem = `{ key, label, value, unit, hint, status, onClick }`
- `WorkshopBarChart.vue` —— 横向条形图，props: `{ rows: WorkshopRow[] }`
- `KeyEventList.vue` —— 要紧事卡片列表，props: `{ items: KeyEvent[], maxCount }`
- `CostLine.vue` —— 成本一行，props: `{ estimate: ManagementEstimate }`
- `DateSwitcher.vue` —— 头部日期切换，props: `{ modelValue, onRefresh }`

所有组件用 `--xt-*` token，不写硬编码颜色/间距。

## 6. 异常 tab

**不动**。AlertsPage 维持现 surface 切换。Phase C 单列时间轴时一起重做。

## 7. 设计原则

- **共用一个 API** —— 今日和生产都打 `/dashboard/factory-director`，确保数字一致
- **数据没有就不做** —— 达成率/班次条/月同比 全不做，不造假指标
- **prose 整段丢出** —— 不前端切段
- **下钻不重画** —— 车间详情/机台/卷继续用现有 FactoryCommandShell
- **token 强制** —— 所有新组件用 `--xt-*`
- **YAGNI** —— 不做附件区、不做自定义日期、不做导出

## 8. 不在范围

- 异常 tab 重画（Phase C）
- 车间详情/机台/卷下钻视觉重做（Phase C 或更晚）
- 后端字段新增（plan_target、班次粒度、附件 API）
- 编辑者工作台（独立轮）
- 操作端整顿（独立轮）

## 9. 验收

- `/manage/today` 默认进入"昨日日报"，标题显当前 target_date
- 显示 5 数 + 车间条形图 + 今日要紧事 + 成本一行 + 折叠正文，全部从 `/dashboard/factory-director` 真数据来
- 5 数中数字卡不可点击
- `/manage/production` 显示 5 数 + 车间排名表，与今日 tab 同 API 同数字
- 今日要紧事 3 个坑位独立判断；count = 0 时该卡显灰底"无"；3 个全 0 时区域整体不渲染
- 要紧事卡片 count > 0 时点击 → 跳 `/manage/alerts` 带正确 surface query
- 成本一行只显合计 + "口径：估算"，**不展开拆电气**
- 不出现"达成率"、"班次进度"、"月同比"、"top 3"字样
- 车间排名表 target_value 列标注为"月均"，**不染色**；null 时显 —
- summary_text 整段渲染，不前端切段
- 生产 tab 头部只一个 DateSwitcher，**没有周/月按钮**
- 手机/电脑共用一套组件，按宽度切布局
- 单元测试覆盖 KpiBar / WorkshopBarChart / KeyEventList 数据映射逻辑
- e2e 走通：进 today → 看到 5 数 → 点要紧事跳 alerts → 进 production → 看到车间排名

## 10. 后续

- Phase C：异常 tab 单列时间轴 + 车间详情下钻视觉重做
- Phase D（spec §10 第二轮）：编辑者（总统计）工作台
- Phase E：操作端工人填报整顿
