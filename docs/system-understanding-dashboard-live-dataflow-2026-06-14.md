# 管理端核心看板与实时调度数据链路理解记录（2026-06-14）

## 本轮范围

本轮继续做 `鑫泰铝业 数据中枢` 的系统理解留档，只读检查代码和线上接口，不改生产数据，不改业务代码。

重点页面：

- `/manage/today`：昨日报表 / 工厂总览。
- `/manage/production`：生产分析。
- `/manage/live`：实时动态生产流转大屏。
- `/manage/coils`：卷级线索。
- `/manage/fill-details`：人工填报和补录明细。

## 前端入口链路

### `/manage/today` 和 `/manage/production`

两个页面共用：

```text
frontend/src/composables/useDashboardSnapshot.js
```

它会并发读取三类接口：

```text
GET /api/v1/dashboard/factory-director
GET /api/v1/dashboard/daily-production
GET /api/v1/factory-command/overview
```

前端主显示优先级：

- 全厂包装产量：优先 `daily_overview.plant_output.daily_output`。
- 全厂入库产量：优先 `daily_overview.plant_output.finished_inbound_output`。
- 车间产量概览：优先 `daily_overview.workshop_output`。
- 调度/在制/流转参考：会补充读取 `factory-command/overview`。

### `/manage/live`

实时大屏读取：

```text
GET /api/v1/aggregation/live
GET /api/v1/aggregation/live/active-date
GET /api/v1/aggregation/live/fill-details
GET /api/v1/aggregation/live/detail
GET /api/v1/realtime/stream
```

页面有两套刷新机制：

- SSE 实时流正常时，用事件补丁更新局部卡片。
- 实时流未打开时，每 30 秒读取一次快照兜底。

对应前端文件：

```text
frontend/src/views/manage/live/LiveDashboardPage.vue
frontend/src/composables/useRealtimeStream.js
frontend/src/api/realtime.js
```

## 后端数据来源

### 日报主口径

后端入口：

```text
backend/app/routers/dashboard.py
GET /api/v1/dashboard/daily-production
```

核心服务：

```text
backend/app/services/report/daily_overview_builder.py
build_daily_production_overview()
```

关键字段：

| 页面字段 | 后端字段 | 来源 |
|---|---|---|
| 包装产量 | `plant_output.daily_output` | 优先 `mes_stock_records`，缺失时回退 `mes_workshop_process_records` |
| 全厂入库产量 | `plant_output.finished_inbound_output` | 成品库内勤 `work_order_entries(entry_type='owner_daily')` |
| 在制料 | `wip_distribution` | `mes_daily_wip_snapshots` |
| 车间产量概览 | `workshop_output` | 主操手机填报 / 工序下机量 |
| 成品率 | `yield_rates` | MES 成品率记录和算法聚合 |
| 合同吨数 | `contracts` | 合同投影服务 |
| 能耗 | `energy` | 能耗汇总服务 |

### MES 包装产量规则

`daily_overview_builder` 的主逻辑：

```text
_query_mes_packaging_output_with_source_by_date()
```

它先查：

```text
mes_stock_records
```

只有当对应业务日没有库存/入库投影时，才回退：

```text
mes_workshop_process_records
```

这点很重要：页面上的“包装产量”不是内勤填报，也不是车间下机量。

### 实时调度链路

后端入口：

```text
backend/app/routers/realtime.py
GET /api/v1/aggregation/live
```

核心服务：

```text
backend/app/services/realtime_service.py
build_live_aggregation()
```

它会合并：

- `work_order_entries`：手机端主操、内勤补录。
- `mobile_shift_reports`：手机端班次填报。
- `machine_energy_records`：电工能耗填报。
- `mes_workshop_process_records`：MES 工序投影。
- `mes_stock_records`：MES 包装/入库投影。
- 车间、机列、班次主数据。

最后通过：

```text
_inject_factory_packaging_output()
```

把全厂包装产量和全厂入库产量注入实时大屏：

- `factory_total.packaging_output`
- `factory_total.daily_output`
- `factory_total.finished_inbound_output`
- `factory_total.daily_output_source`
- `factory_total.finished_inbound_source`

### 调度概览链路

后端入口：

```text
backend/app/routers/factory_command.py
GET /api/v1/factory-command/overview
```

核心服务：

```text
backend/app/services/factory_command_service.py
build_overview()
```

优先级：

1. 优先尝试实时聚合 `build_live_aggregation()`。
2. 如果实时聚合不可用，再读 `mes_coil_snapshots`、`mes_workshop_process_records` 等 MES 投影。
3. 如果 MES 投影不可用，再用本地填报 `ShiftProductionData` / `MobileShiftReport` 兜底。

所以它适合做“调度观察”和“卷级流转参考”，不应该直接替代日报最终包装产量。

## 线上只读证据

验证日期：`2026-06-13`

管理员接口登录：

```text
POST /api/v1/auth/login -> 200
```

接口返回摘要：

| 接口 | 状态 | 关键证据 |
|---|---:|---|
| `/dashboard/factory-director` | 200 | `today_total_output=241.91`，`total_output_basis=mes_packaging_output` |
| `/dashboard/daily-production` | 200 | `plant_output.daily_output=241.91`，`daily_output_source=mes_stock_records` |
| `/dashboard/daily-production` | 200 | `plant_output.finished_inbound_output=246.38`，`finished_inbound_source=storage_owner_daily_entry` |
| `/factory-command/overview` | 200 | `source=mixed`，`today_output_tons=1618.55`，`output_basis=live_aggregation` |
| `/aggregation/live` | 200 | `factory_total.packaging_output=241.91`，`factory_total.finished_inbound_output=246.38` |
| `/aggregation/live` | 200 | `workshops=13`，`mes_sync_status.adapter=sqlserver`，`last_run_status=success` |
| `/dashboard/timeseries` | 200 | 返回 3 条时间序列数据 |
| `/factory-command/coils` | 200 | 返回卷级字段：随行卡号、批号、规格、MES 上/下机、自动废料线索 |

页面静态入口只读烟测：

```text
/manage/live -> 200
/manage/today -> 200
/manage/production -> 200
/manage/coils -> 200
/manage/fill-details -> 200
/manage/energy -> 200
```

## 测试证据

前端测试：

```text
npm test --prefix frontend -- manageDashboardSnapshot manageDailyReportSurface manageLivePhase2 manageProductionPage manageLiveProcessFlow
```

实际该命令跑完了当前前端测试集：

```text
665 passed
```

后端定向测试：

```text
python -m pytest -q backend/tests/test_daily_overview_mes_packaging.py backend/tests/test_daily_overview_chain.py::test_daily_overview_exposes_plant_output_basis_and_plant_cost backend/tests/test_realtime_service.py::test_inject_factory_packaging_output_uses_mes_as_live_main_metric backend/tests/test_report_service_contract_lane.py::test_yesterday_shift_breakdown_uses_mes_packaging_as_factory_output
```

结果：

```text
7 passed
```

## 当前明确结论

- `包装产量` 当前是 MES 主数据口径，线上来自 `mes_stock_records`。
- `全厂入库产量` 当前是成品库内勤填报口径，来源是 `storage_owner_daily_entry`。
- `/manage/live` 会同时展示 MES 包装产量和内勤入库填报，二者没有在后端混成一个字段。
- `/manage/today` 和 `/manage/production` 都以 `useDashboardSnapshot()` 为主要数据入口。
- `/manage/live` 的大屏不是单纯轮询，它有 SSE 实时流，断开时 30 秒快照兜底。
- 线上 MES 同步状态当前显示 `adapter=sqlserver`、`last_run_status=success`，说明线上已不是只依赖旧 MVC 抓取的状态。

## 仍需后续重点盯的风险

### 风险 1：生产分析页过站下机参考仍可能被 0 覆盖

线上 `/dashboard/factory-director` 当前返回：

```text
process_total_output=0.0
```

而 `ProductionPage.vue` 的 `productionSourceOverview` 目前优先使用：

```text
snapshot.data.value.process_total_output
```

如果这个字段存在但为 0，前端可能不会回退到 `daily_overview.workshop_output` 或 `factory-command/overview` 的工序流转数据。

这和前一份日报/生产分析链路文档中的风险一致，后续修复时应把“0 且车间明细有值”的情况视为可回退。

### 风险 2：实时调度和日报的“产量”不是同一个业务概念

线上同一天：

```text
日报包装产量：241.91 吨
调度实时总输出：1618.55 吨
```

这不是接口冲突，而是两个不同口径：

- `241.91`：MES 包装/入库方向的最终产量。
- `1618.55`：实时聚合里的工序流转总输出。

前端必须持续显示来源标签，避免用户把“工序流转量”误当“全厂最终产量”。

### 风险 3：完整浏览器深测还没覆盖所有交互

本轮做了接口只读验证、页面静态入口验证、自动测试验证。还没有逐按钮、逐筛选、逐抽屉、逐移动端流程做完整浏览器深测。

因此本轮结论只能说“核心数据链路和接口返回已验证”，不能说“全站所有功能已深测完成”。

