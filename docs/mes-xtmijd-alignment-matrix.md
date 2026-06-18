# 数据中枢和 MES 指标对齐矩阵

日期：2026-06-18

`鑫泰铝业 数据中枢` 不是 MES。它读取外部 MES 的只读数据，先同步成本地 `mes_*` 投影表，再给 `/manage/*` 页面使用。

共同业务时间：

```text
每天 07:30 到次日 07:30
```

例子：`2026-06-18` 业务日是 `2026-06-18 07:30` 到 `2026-06-19 07:30`，月累计从 `2026-06-01 07:30` 算到目标业务日结束。

## 三条主事实

| 事实 | 外部 MES/WMS 来源 | 本地投影 | 前端来源标签 | 不能混用的点 |
|---|---|---|---|---|
| 投料量 | `MES_Product.FeedingWeight` | `mes_coil_snapshots.feeding_weight` | `MES投料` | 不能用 `MES_Feeding`，当天没有事实记录 |
| 包装量 | `MES_ProductProcessRecord.EndWeight`，过滤 `Process=包装` | `mes_workshop_process_records.output_weight_tons` | `包装工序` | 不能只看精整，要看全厂包装工序 |
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
| `/api/v1/dashboard/mes-factory-production-reconciliation` | 对账接口，返回投料、包装、入库、成品率、来源表、来源字段、车间拆分和 MES 首页已知数字差异 |
| `factory_feeding_daily_input` | 日投料量 |
| `factory_feeding_month_to_date_input` | 月累计投料量 |
| `factory_packaging_daily_output` | 日全厂包装量 |
| `factory_packaging_month_to_date_output` | 月累计全厂包装量 |
| `factory_finished_inbound_daily_output` | 日成品入库量 |
| `factory_finished_inbound_month_to_date_output` | 月累计成品入库量 |
| `daily_yield_rate` | 日全厂成品率 |
| `month_yield_rate` | 月全厂成品率 |
| `yield_rate_source` | 固定为 `mes_feeding_to_finished_inbound` |

## 页面映射

| 数据中枢页面 | 页面要表达的业务 | 对齐方式 |
|---|---|---|
| `/manage/live` | 管理实时大屏 | 顶部卡片展示投料量、全厂包装、成品入库、全厂成品率，来源标签分别是 `MES投料`、`包装工序`、`成品入库`、`投料入库` |
| `/manage/today` | 日报工作台 | 日累计和月累计都使用同一套全厂事实；包装和入库分开展示 |
| `/manage/workshop-dashboard` | 车间看板 | 车间明细按车间过滤；全厂头部指标复用同一套全厂事实 |
| `/manage/production` | 生产分析 | 可以保留质检/历史成品率参考，但主成品率用投料到入库 |
| `/manage/coils` | 卷级线索 | 当前车间、当前工序、随行卡来自 `MES_Product`；工序历史来自 `MES_ProductProcessRecord` |
| `/manage/energy` | 能耗中心 | 吨耗分母若使用包装量，来源必须标成 `包装工序` |
| `/manage/fill-details` | 人工填报明细 | 人工填报只叫人工填报，不混称为 MES 投料、包装或入库 |

## 2026-06-18 对账要求

| 项 | 目标 |
|---|---|
| 日投料 | 数据中枢对 `MES_Product.FeedingWeight` 的业务日汇总应能对上 MES 首页 `427.0t` |
| MES 首页包装 | 精整包装口径应能解释 MES 首页 `66.1t` |
| 全厂包装 | 必须包含精整、园区精整、拉矫车间等所有 `Process=包装` 的工序 |
| 月投料差异 | 当前本地口径 `6380.0t` 与 MES 首页 `6524.0t` 差 `144.0t`，对账接口必须返回 `feeding_month_to_date_delta=-144.0` |

## 小白版理解

以后大屏上的“全厂成品率”只看两件事：

```text
投进去多少料
最后入库多少成品
```

中间“包装了多少”仍然重要，但它是包装工序产量，不等于成品入库量。原来的 `yield_matrix_lane` 还保留，但只做质检或历史参考，不再当全厂主数字。
