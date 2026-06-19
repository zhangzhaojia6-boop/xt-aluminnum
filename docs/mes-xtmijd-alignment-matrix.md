# 数据中枢和 MES 指标对齐矩阵

日期：2026-06-18

`鑫泰铝业 数据中枢` 不是 MES。它读取外部 MES 的只读数据，先同步成本地 `mes_*` 投影表，再给 `/manage/*` 页面使用。

共同业务时间：

```text
默认每天 07:50 到次日 07:50；铸二、铸三、热轧每天 10:00 到次日 10:00
```

例子：普通车间的 `2026-06-18` 业务日是 `2026-06-18 07:50` 到 `2026-06-19 07:50`；热轧的 `2026-06-18` 业务日是 `2026-06-18 10:00` 到 `2026-06-19 10:00`。月累计按各车间自己的业务日窗口累加。

## 三条主事实

| 事实 | 外部 MES/WMS 来源 | 本地投影 | 前端来源标签 | 不能混用的点 |
|---|---|---|---|---|
| 投料量 | `MES_Product.FeedingWeight` | `mes_coil_snapshots.feeding_weight` | `MES投料` | 不能用 `MES_Feeding`，当天没有事实记录；按当前车间业务时间归属 |
| 包装量 | `MES_ProductProcessRecord.EndWeight`，过滤 `Process=包装`；成品调拨单做对照 | `mes_workshop_process_records.output_weight_tons`、`mes_stock_records` | `包装工序` | 包装录入已包装未必已入库，也算包装产量；不能只看精整，要看全厂包装工序 |
| 成品入库量 | `WMS_InStock / WMS_InStockDetail` | `mes_stock_records` | `成品入库` | 不能用包装产量替代入库量 |

全厂成品率主口径：

```text
日成品率 = 日成品入库量 / 日投料量 * 100
月成品率 = 月累计成品入库量 / 月累计投料量 * 100
```

分母是 0 时，后端返回 `null`，前端显示缺数。

## 后端统一出口

| 接口/字段 | 用途 |
|---|---|
| `/api/v1/dashboard/mes-factory-production-reconciliation` | 全厂对账接口，返回投料、包装、入库、成品率、来源表、来源字段和车间拆分；没有真实读取到 MES 首页参考值时，差异字段返回 `null` |
| `/api/v1/dashboard/mes-workshop-machine-reconciliation` | 车间/机台对账接口，返回车间产量、车间下机量、机台下机量、机台绑定状态和来源字段 |
| `factory_feeding_daily_input` | 日投料量 |
| `factory_feeding_month_to_date_input` | 月累计投料量 |
| `factory_packaging_daily_output` | 日全厂包装量 |
| `factory_packaging_month_to_date_output` | 月累计全厂包装量 |
| `factory_finished_inbound_daily_output` | 日成品入库量 |
| `factory_finished_inbound_month_to_date_output` | 月累计成品入库量 |
| `daily_yield_rate` | 日全厂成品率 |
| `month_yield_rate` | 月全厂成品率 |
| `yield_rate_source` | 固定为 `mes_feeding_to_finished_inbound` |

## 车间和机台口径

| 指标 | 含义 | 主要来源 | 数据中枢字段 | 注意 |
|---|---|---|---|---|
| 车间产量 | 车间最终产出口径 | `MES_ProductProcessRecord.EndWeight` 或坯料卷投影 | `production_output`、`total_output` | 冷轧只统计已标记最终工序的重量；没有最终工序标记时不能把过站量当产量 |
| 车间投料量 | 车间报表里的上机重量 | `MES_ProductProcessRecord.BeginWeight` | `workshop_feeding_input`、`machine_input_weight` | 不能从卷当前车间反推 |
| 车间下机量 | 车间所有过站下机重量 | `MES_ProductProcessRecord.EndWeight` | `workshop_down_machine_output`、`process_output`、`mtd_process_output` | 这是过程通过量，不等于最终产量 |
| 机台上机量 | 机台维度的上机重量 | `MES_ProductProcessRecord.DeviceName + BeginWeight` | `machine_input_weight`、`day_total.input` | 本地未匹配机台必须保留为未匹配 |
| 机台下机量 | 机台维度的过站下机重量 | `MES_ProductProcessRecord.DeviceName + EndWeight` | `machine_down_machine_output`、`day_total.output` | 本地未匹配机台必须显示为 `MES未匹配机台` 或 `待归属`，不能猜 |

坯料类车间当前沿用 MES 坯料明细口径：`MES_Material.Weight`，状态包含 `已使用` 和 `未使用`，业务时间为 `10:00-10:00`。接口会在 `source_basis/source_label` 里标出来源，不混称为 `MES_ProductProcessRecord`。

## 批号追溯

`前世今生 / Archives` 是批号追溯入口。数据中枢做同义映射时，一条批号应能串起：`MES_Product` 的合同/随行卡/当前工序，`MES_ProductProcessRecord` 的每道工序上机/下机，`MES_ProductProcessRecord(Process=包装)` 的包装记录，以及 `WMS_InStockDetail/WMS_Stock` 的成品库记录。没有查到某一段时标缺口，不补假数据。

## 页面映射

| 数据中枢页面 | 页面要表达的业务 | 对齐方式 |
|---|---|---|
| `/manage/live` | 管理实时大屏 | 顶部卡片展示投料量、全厂包装、成品入库、全厂成品率；机台矩阵展示机台下机量 |
| `/manage/today` | 日报工作台 | 日累计和月累计都使用同一套全厂事实；包装和入库分开展示 |
| `/manage/workshop-dashboard` | 车间看板 | `今日下机量` 对应 `process_output`，`车间口径产量` 对应 `total_output`，全厂头部指标复用同一套全厂事实 |
| `/manage/production` | 生产分析 | 可以保留质检/历史成品率参考，但主成品率用投料到入库 |
| `/manage/coils` | 卷级线索 | 当前车间、当前工序、随行卡来自 `MES_Product`；工序历史来自 `MES_ProductProcessRecord` |
| `/manage/energy` | 能耗中心 | 吨耗分母若使用包装量，来源必须标成 `包装工序` |
| `/manage/fill-details` | 人工填报明细 | 人工填报只叫人工填报，不混称为 MES 投料、包装或入库 |

## 2026-06-18 对账要求

| 项 | 目标 |
|---|---|
| 日投料 | 数据中枢对 `MES_Product.FeedingWeight` 的业务日汇总应能对上 MES 投料/随行卡页面，同车间同业务时间比较 |
| MES 首页包装 | 精整包装口径应能解释 MES 首页 `66.1t` |
| 全厂包装 | 必须包含精整、园区精整、拉矫车间等所有 `Process=包装` 的工序 |
| 月投料差异 | 只有真实浏览器读到 MES 首页月累计参考值时才计算；当前没有参考值时 `mes_home_reference={}`，`feeding_month_to_date_delta=null` |
| 车间/机台下机 | `/api/v1/dashboard/mes-workshop-machine-reconciliation?target_date=2026-06-18` 返回车间、机台、来源、绑定状态 |

## 小白版理解

以后大屏上的“全厂成品率”只看两件事：

```text
投进去多少料
最后入库多少成品
```

中间“包装了多少”仍然重要，但它是包装工序产量，不等于成品入库量。原来的 `yield_matrix_lane` 还保留，但只做质检或历史参考，不再当全厂主数字。
