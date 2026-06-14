# 管理端“昨日报表 / 生产分析”数据链路理解记录（2026-06-14）

## 本轮范围

本轮只做只读理解和 QA，不改生产数据，也不改业务代码。目标是把 `/manage/today` 和 `/manage/production` 两个核心页面的数据来源、字段映射和现存风险讲清楚。

## 页面入口

- `/manage/today`：页面标题是“工厂总览 / 昨日报表”，用于看上一业务日的日报、产量、填报缺口、能耗对照和生产流转。
- `/manage/production`：页面标题是“生产驾驶舱 / 生产分析”，用于看产量 KPI、车间排行、主数据摘要和生产信号。

两个页面都通过 `frontend/src/composables/useDashboardSnapshot.js` 取数。

## 前端取数方式

`useDashboardSnapshot()` 一次并发拉三类接口：

- `/api/v1/dashboard/factory-director`
- `/api/v1/dashboard/daily-production`
- `/api/v1/factory-command/overview`

其中 `/dashboard/daily-production` 的返回会被放入：

```text
snapshot.data.daily_overview
```

因此，日报页的包装产量、全厂入库产量、合同吨数、成品率、车间产量概览，主要都读 `daily_overview`。

## 后端主口径

后端入口：

```text
backend/app/routers/dashboard.py
GET /api/v1/dashboard/daily-production
```

核心生成函数：

```text
backend/app/services/report/daily_overview_builder.py
build_daily_production_overview()
```

关键规则：

- `plant_output.daily_output`：全厂最终包装产量，优先来自 `mes_stock_records`。
- `plant_output.finished_inbound_output`：全厂入库产量，来自成品库内勤 `storage_owner_daily_entry`。
- `workshop_output[].daily_output`：各车间过站/下机参考，不等同于全厂最终产量。
- `energy.total_electricity`：能耗总电，来自能耗汇总。
- `plant_output.energy_per_ton`：总电量除以 MES 包装产量。
- `energy.energy_per_ton`：能耗服务自身口径的吨耗，和页面 KPI 主口径不是同一个字段。

## 线上只读证据

目标日期：`2026-06-13`

接口 `/api/v1/dashboard/daily-production?target_date=2026-06-13` 返回的关键值：

- MES 包装产量：`241.91` 吨
- 全厂入库产量：`246.38` 吨
- 合同吨数：`227` 吨
- 日成品率：`94.57%`
- 能耗总电：`6512` 度
- `plant_output.energy_per_ton`：`26.92`
- `energy.energy_per_ton`：`105.1`

云端数据库同一套后端函数只读核对：

- `mes_stock_records` 包装产量：`241.91` 吨
- `mes_workshop_process_records` 包装工序产量：`234.61` 吨
- 成品库内勤入库产量：`246.38` 吨
- 实际主口径选择：`mes_stock_records`
- 全厂入库来源：`storage_owner_daily_entry`

浏览器实际打开 `/manage/today`：

- 能看到 `包装产量 241.91 吨`
- 能看到 `全厂入库产量 246.38 吨`
- 能看到 `过站下机参考 1,133.95 吨`
- 能看到 `合同吨数 227 吨`
- 能看到 `日成品率 94.57%`
- 页面里仍出现“暂无可信数据”，但当前证据显示主要出现在“电工填报”等对照项，不是主产量卡片。

浏览器实际打开 `/manage/production`：

- 能看到 `包装产量 241.91 吨`
- 能看到 `成品率 94.57%`
- 能看到车间排行。
- “过站下机参考”显示 `0 吨`，这和 `/manage/today` 的 `1,133.95 吨` 不一致。

## 已确认没问题的点

- `包装产量` 当前确实是 MES 主数据，不是内勤填报。
- `全厂入库产量` 当前确实是内勤成品库填报数据，两者没有混成一个字段。
- `/manage/today` 和 `/manage/production` 的主包装产量都能显示真实值。
- 登录后页面能打开，接口返回 200。

## 新发现风险

### 风险 1：生产分析页“过站下机参考”取值不一致

现象：

- `/manage/today` 显示过站下机参考 `1,133.95 吨`
- `/manage/production` 显示过站下机参考 `0 吨`

原因判断：

`frontend/src/views/manage/production/ProductionPage.vue` 的 `productionSourceOverview` 目前优先读：

```text
snapshot.data.process_total_output
```

如果这个字段存在但值为 `0`，前端就不会回退到更可信的车间明细合计。

业务影响：

用户会以为当天没有过站/下机量，但车间排行和日报页明明有数据，容易误判生产状态。

建议修复：

生产分析页的“过站下机参考”应该优先使用 `daily_overview.workshop_output` 的日产量合计，只有车间明细为空时才回退到旧字段。

回归测试点：

- `/manage/production` 的过站下机参考应与 `/manage/today` 的过站下机参考一致。
- 主包装产量仍保持 `plant_output.daily_output`，不能被过站下机量覆盖。

### 风险 2：吨电耗存在两个相近字段，容易误读

现象：

- `plant_output.energy_per_ton = 26.92`
- `energy.energy_per_ton = 105.1`
- 页面 KPI 显示 `26.9 kWh/吨`

原因判断：

前端 KPI 优先使用 `plant_output.energy_per_ton`，这个值是总电量除以 MES 包装产量。`energy.energy_per_ton` 来自能耗服务自己的汇总口径。

业务影响：

如果后续开发人员只看接口摘要，可能以为页面显示错了。实际不是页面丢数据，而是字段口径不同。

建议：

后续应在接口或口径字典里明确两个字段的中文解释，避免同名近义字段造成误接。

## 当前结论

这两个页面的主产量链路整体是通的：MES 包装产量作为主口径，内勤入库作为对照口径。当前最需要后续修复的是 `/manage/production` 的“过站下机参考 0 吨”映射问题，以及吨电耗字段的口径命名说明。

