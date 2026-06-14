# MES 数据到管理端生产看板链路理解记录（2026-06-14）

## 本轮范围

本轮继续补齐 `鑫泰铝业 数据中枢` 的系统理解，只读检查代码、接口和现有文档，不改生产数据，不改业务代码。

这份文档专门回答一个问题：

```text
外部 MES 里的数据，怎样进入数据中枢，又怎样显示到管理端生产页面？
```

一句话结论：

```text
外部 MES SQL Server -> 数据中枢本地 mes_* 投影表 -> 后端业务服务统一加工 -> 管理端页面读取后端接口展示。
```

前端页面不直接连接 MES 数据库。这样做的好处是安全、稳定，也方便把 MES、人工填报和算法结果分层展示。

## 四层数据链路

### 第一层：外部 MES 源数据

当前 SQL Server 直连适配器在：

```text
backend/app/adapters/sqlserver_mes_adapter.py
```

核心类：

```text
SqlServerMesAdapter
```

它是只读适配器，代码里明确写着：读取 SQL Server 后，管理端页面仍然读数据中枢自己的 `mes_*` 本地投影表。

常见外部表和用途：

| 外部 MES 表 | 数据中枢理解 | 主要用途 |
|---|---|---|
| `MES_Product` | 卷材 / 随行卡 / 当前工艺 / 当前车间 | 卷级线索、在制状态、工艺路线 |
| `MES_ProductProcessRecord` | 工序过站记录 | 上机量、下机量、设备、工人、工序时间 |
| `WMS_InStockDetail` | 入库 / 包装入库记录 | 包装产量、日报最终产量主口径 |
| `MES_Feeding` | 坯料 / 投料记录 | 热轧、铸轧、坯料输入参考 |
| `WMS_Stock` | 库存记录 | 库存和在制参考 |
| `MES_Device` | MES 设备 / PC / 机列线索 | PC 与机列映射、设备别名治理 |

### 第二层：数据中枢本地投影表

同步服务在：

```text
backend/app/services/mes_sync_service.py
```

关键函数：

```text
sync_mes_projection()
sync_mes_stock_records()
sync_mes_workshop_process_records()
```

常见本地表：

| 本地表 | 含义 | 主要页面 |
|---|---|---|
| `mes_coil_snapshots` | 每卷当前状态快照 | `/manage/coils`、调度大屏 |
| `mes_workshop_process_records` | 工序过站记录 | 生产分析、过站参考、工序流转 |
| `mes_stock_records` | MES/WMS 入库投影 | 日报包装产量、全厂最终产量 |
| `mes_material_records` | 坯料 / 投料投影 | 坯料输入、热轧/铸轧参考 |
| `mes_yield_records` | 成品率相关投影 | 成品率和算法对照 |
| `mes_wip_total_snapshots` | 当前在制汇总快照 | 调度大屏、生产分析 |
| `mes_daily_wip_snapshots` | 按日留档的在制快照 | 日报、趋势分析 |
| `mes_reference_items` | 设备、工艺、字典类参考 | 设置、映射、治理 |
| `mes_machine_line_snapshots` | MES 设备/机列线索 | PC 到机列映射 |
| `mes_sync_cursors` / `mes_sync_run_logs` | 同步游标和运行日志 | 同步健康检查 |

简单理解：

```text
外部 MES 是原始账本，本地 mes_* 表是数据中枢拿来做看板和算法的“投影副本”。
```

## 管理端页面怎么取数

### `/manage/live` 实时大屏

前端页面：

```text
frontend/src/views/manage/live/LiveDashboardPage.vue
```

主要接口：

```text
GET /api/v1/aggregation/live
GET /api/v1/realtime/stream
```

后端服务：

```text
backend/app/services/realtime_service.py
build_live_aggregation()
```

它会合并三类数据：

| 类型 | 来源 | 页面用途 |
|---|---|---|
| MES 数据 | `mes_coil_snapshots`、`mes_workshop_process_records`、`mes_stock_records` | 卷材流转、包装产量、工序状态 |
| 人工填报 | `work_order_entries`、`mobile_shift_reports`、`machine_energy_records` | 补录、能耗、异常、责任人 |
| 主数据 | 车间、机列、班次、用户、别名映射 | 权限过滤、机列归属、车间归属 |

实时大屏的全厂关键字段：

| 字段 | 业务意思 |
|---|---|
| `factory_total.packaging_output` | MES 包装产量 |
| `factory_total.daily_output` | 当前主产量口径，等同 MES 包装产量 |
| `factory_total.finished_inbound_output` | 成品库内勤填报的全厂入库量 |
| `factory_total.daily_output_source` | 主产量来源，一般应是 `mes_stock_records` |
| `factory_total.finished_inbound_source` | 入库填报来源，一般是 `storage_owner_daily_entry` |

重点：实时大屏不是只靠手工填报，也不是直接读 MES 源库；它读的是后端聚合后的结果。

### `/manage/today` 昨日报表

前端页面：

```text
frontend/src/views/manage/today/TodayPage.vue
frontend/src/composables/useDashboardSnapshot.js
```

主要接口：

```text
GET /api/v1/dashboard/factory-director
GET /api/v1/dashboard/daily-production
GET /api/v1/factory-command/overview
```

核心日报服务：

```text
backend/app/services/report/daily_overview_builder.py
build_daily_production_overview()
```

日报主产量规则：

```text
优先 mes_stock_records 的包装/入库产量；
如果当天没有 mes_stock_records，再回退 mes_workshop_process_records 的包装工序产量。
```

页面上需要区分两个字段：

| 页面中文 | 后端字段 | 数据来源 | 是否主口径 |
|---|---|---|---|
| 包装产量 | `plant_output.daily_output` / `plant_output.packaging_output` | MES 主数据 | 是 |
| 全厂入库产量 | `plant_output.finished_inbound_output` | 成品库内勤每日一录 | 否，是对照 |

所以“包装产量”和“全厂入库产量”不是一回事。

### `/manage/production` 生产分析

前端页面：

```text
frontend/src/views/manage/production/ProductionPage.vue
```

这个页面和 `/manage/today` 共用 `useDashboardSnapshot()`，但更偏向生产分析、排行、趋势、产量构成。

需要特别注意：

```text
包装产量 = 最终产量主口径；
过站下机参考 = 各工序流转量，不等于全厂最终产量。
```

如果页面把过站下机量当成最终产量，数字会被放大；如果把最终包装产量当成所有车间产量，又会看不到工序流转情况。

### `/manage/coils` 卷级线索

前端页面：

```text
frontend/src/views/manage/coils/CoilTracePage.vue
```

主要接口：

```text
GET /api/v1/factory-command/coils
GET /api/v1/factory-command/coils/{coil_key}/flow
```

核心服务：

```text
backend/app/services/factory_command_service.py
```

它主要读 `mes_coil_snapshots`，并尝试用 `mes_workshop_process_records` 补充最新上机量、下机量、自动废料等线索。

页面的定位是：

```text
看每一卷现在在哪里、走过什么工艺、有没有匹配到具体机列、是否需要人工补录。
```

它不是人工填报明细页。

### `/manage/fill-details` 填报明细

这个页面原则上只看人工填报和补录：

```text
主操、电工、内勤等人工录入记录。
```

MES 自动投影数据不应该混进这个页面，否则用户会分不清“人填的”和“系统抓的”。

## 线上只读证据

本轮已验证过线上接口，目标业务日为 `2026-06-13`。

### MES 同步状态

```text
GET /api/v1/mes/sync-status
```

关键结果：

| 字段 | 结果 |
|---|---|
| adapter | `sqlserver` |
| source | `mes_projection` |
| status | `fresh` |
| last_run_status | `success` |
| lag_seconds | `0.0` |

结论：线上已经有 SQL Server 直连投影链路在跑，不是只靠旧 MVC 抓取。

### 日报产量接口

```text
GET /api/v1/dashboard/daily-production?target_date=2026-06-13
```

关键结果：

| 字段 | 值 |
|---|---:|
| `plant_output.basis` | `mes_packaging_output` |
| `plant_output.basis_label` | `包装产量` |
| `plant_output.daily_output_source` | `mes_stock_records` |
| `plant_output.finished_inbound_source` | `storage_owner_daily_entry` |
| `plant_output.daily_output` | `241.91` 吨 |
| `plant_output.finished_inbound_output` | `246.38` 吨 |
| `plant_output.business_day_start` | `07:30` |

结论：日报页主产量来自 MES 入库投影，成品库内勤填报作为对照值存在。

### 实时大屏接口

```text
GET /api/v1/aggregation/live?business_date=2026-06-13
```

关键结果：

| 字段 | 值 |
|---|---:|
| `factory_total.packaging_output` | `241.91` 吨 |
| `factory_total.daily_output` | `241.91` 吨 |
| `factory_total.finished_inbound_output` | `246.38` 吨 |
| `factory_total.daily_output_source` | `mes_stock_records` |
| `factory_total.finished_inbound_source` | `storage_owner_daily_entry` |

结论：实时大屏也能拿到同一套 MES 包装主口径。

### 卷级线索接口

```text
GET /api/v1/factory-command/coils?limit=5
```

已看到字段包括：

```text
随行卡号、批号、客户、合金、规格、当前车间、当前工艺、上一工艺、下一工艺、MES 上机量、MES 下机量、自动废料、机列匹配状态。
```

其中一些记录仍显示 `pending machine binding`，说明 PC/设备到真实机列的映射还没有完全打通。

## 自动测试证据

后端定向测试：

```text
python -m pytest -q backend/tests/test_sqlserver_mes_adapter.py backend/tests/test_mes_sync_service.py backend/tests/test_mes_extended_routes.py backend/tests/test_mes_extended_scope.py backend/tests/test_realtime_service.py backend/tests/test_realtime_routes.py backend/tests/test_report_service_contract_lane.py backend/tests/test_dashboard_routes.py backend/tests/test_factory_command_routes.py backend/tests/test_mobile_mes_pending_supplements.py
```

结果：

```text
150 passed
```

前端测试：

```text
npm test --prefix frontend -- tests/manageCoilsPage.test.js tests/liveDashboardPhase2.test.js tests/useDashboardSnapshot.test.js tests/manageDailyReportSurface.test.js tests/productionPage.test.js tests/todayPage.test.js tests/workshopEnergyLiveRegression.test.js
```

实际跑完当前前端测试集：

```text
665 passed
```

## 当前确认结论

- 前端不直接连 MES SQL Server，只通过后端接口读取数据中枢整理后的结果。
- MES 包装产量当前是管理端生产主口径。
- 成品库内勤填报的入库量仍保留，但应作为对照，不应覆盖 MES 主口径。
- `/manage/fill-details` 应只展示人工填报，不应混入 MES 自动抓取数据。
- `/manage/coils` 是 MES 主数据的卷级线索页，是后续减少人工填报的关键页面。
- `/manage/live`、`/manage/today`、`/manage/production` 都已经接入 MES 包装产量链路，但页面展示侧仍有局部风险。

## 仍需后续盯紧的风险

### 风险 1：`/manage/today` 可能被慢接口拖住首屏

`useDashboardSnapshot()` 当前会同时等待：

```text
/dashboard/factory-director
/dashboard/daily-production
/factory-command/overview
```

线上观察到：

```text
/dashboard/daily-production 约 0.9 秒返回；
/factory-command/overview 约 1.1 秒返回；
/dashboard/factory-director 约 4.7 秒返回，响应体较大。
```

如果前端等所有接口都回来再更新页面，日报主数据可能已经返回了，但页面仍短时间显示“暂无可信数据”。

后续建议：

```text
让 daily-production 先独立渲染日报主卡片；
factory-director 和 factory-command 作为补充数据异步填充。
```

### 风险 2：PC 到机列映射还不够稳

MES 记录里有些设备名是 PC 或一体机名，不是数据中枢里的真实机列名。

影响：

```text
卷级线索能知道卷在哪个车间/工艺，但不一定能稳定定位到哪台机列。
```

后续要补的是：

```text
PC / MES 设备 / 工艺 / 车间 -> 数据中枢机列
```

这张映射表打稳后，才能进一步减少主操补录。

### 风险 3：调度总量和日报最终产量容易被误读

同一天可能出现：

```text
MES 包装产量：241.91 吨
调度/工序流转总量：1618.55 吨
```

这不是谁错了，而是业务口径不同：

| 数字 | 含义 |
|---|---|
| 包装产量 | 最终产量主口径 |
| 工序流转量 | 各工序过站量，可能一卷经过多个工序重复累计 |

页面必须一直保留中文来源标签，不能只写“总产量”。

### 风险 4：坯料/投料记录不能直接当成成品产量

`mes_material_records` 适合做热轧、铸轧、坯料输入参考，但它不是最终成品入库。

如果用它补热轧、铸轧的产量，页面必须写清：

```text
坯料输入参考 / 投料量参考
```

不能写成：

```text
全厂最终产量
```

## 后续理解优先级

建议下一轮继续补这三块：

1. PC / 一体机 / MES 设备 到真实机列的映射规则。
2. 热轧、铸二、铸三、淬火这类没有完整一体机链路的车间如何用 MES 坯料和人工补录并行。
3. 能耗数采数据库接入后，吨耗分母应继续使用 MES 包装产量，不能回退到手工填报产量。
