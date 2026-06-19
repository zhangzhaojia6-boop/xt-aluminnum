# MES 到数据中枢再到 Hermes 的事实地图

日期：2026-06-19

本文只做事实地图，不写任何真实凭据、账号或连接配置。

小白版一句话：MES SQL Server 是外部只读源；数据中枢先把它同步成本地 `mes_*` 表，页面、API、Hermes 日报都读本地表，不在用户打开页面或 Hermes 回答时直接查 MES SQL Server。

## 状态说明

| 状态 | 含义 |
|---|---|
| `已证实` | 已被本仓库文档、后端代码、前端代码或模型字段直接证明。 |
| `候选` | 表名、字段名或页面方向已经有证据，但还没有完成同级别字段对账或页面实测。 |
| `待浏览器/SQL复核` | 需要登录 MES 页面、跑只读 SQL 或拿真实业务日继续核对，不能当最终口径。 |

## 阅读边界

- 已读取：`README.md`、`docs/mes-page-table-mapping.md`、`docs/mes-xintaily-full-page-table-audit.md`、`docs/mes-xtmijd-alignment-matrix.md`、`docs/superpowers/plans/2026-06-04-mes-sqlserver-direct-connection-office-hours.md`、`docs/system-understanding-consolidated-2026-06-14.md`、`docs/audits/output-skill-data-mapping-baseline.md`、`docs/audits/template-daily-report-outputskill-baseline.md`。
- 已读取代码：`backend/app/core/business_time.py`、`backend/app/adapters/sqlserver_mes_adapter.py`、`backend/app/services/mes_sync_service.py`、`backend/app/services/report/mes_factory_production_fact.py`、`backend/app/services/report/mes_factory_packaging_fact.py`、`backend/app/services/report/mes_workshop_machine_reconciliation.py`、`backend/app/services/report/template_daily_fact_sources.py`、`backend/app/services/report/template_daily_report.py`、`backend/app/services/report/output_skill_report_parser.py`、`backend/app/routers/dashboard.py`、`backend/app/routers/mes.py`、`frontend/src/router/index.js`、`frontend/src/api/*.js`、`frontend/src/views/manage/workshop-dashboard/WorkshopDashboardPage.vue`。
- 指定的 `docs/longterm-ai-skill-system-spec.md` 在当前 worktree 未找到；本文件没有引用不存在文件里的结论。

## 业务时间

| 口径 | 时间窗口 | 状态 | 证据 |
|---|---|---|---|
| 普通生产车间 | `07:50-07:50` | `已证实` | `backend/app/core/business_time.py` 中 `PRODUCTION_BUSINESS_DAY_START = 07:50`；MES 对齐文档也写明默认 `07:50` 到次日 `07:50`。 |
| 铸二、铸三、热轧 | `10:00-10:00` | `已证实` | `BILLET_PRODUCTION_BUSINESS_DAY_START = 10:00`，`BILLET_BUSINESS_TIME_WORKSHOPS = {'铸二','铸三','热轧'}`。 |
| 内勤/一日汇总 | `09:30` 起算 | `已证实` | `OWNER_DAILY_BUSINESS_DAY_START = 09:30`，移动端也展示每日一录按 `09:30` 归属。 |
| 内勤迟报参考 | `10:00` | `已证实` | `OWNER_DAILY_LATE_CUTOFF = 10:00`。 |
| 旧文档里的 `07:30` | 历史口径或日报调度口径 | `待浏览器/SQL复核` | 旧总理解文档、部分 RAG 静态文本、日报任务仍出现 `07:30`；MES 字段对齐以当前 `business_time.py` 和 2026-06-18 MES 对齐文档为准。 |

## 架构决定

| 决定 | 状态 | 说明 |
|---|---|---|
| 页面不直查 MES SQL Server | `已证实` | 前端只调用 `/api/v1/...`；后端页面接口读本地业务库和 `mes_*` 投影。 |
| Hermes 不在回答或日报生成时直查 MES SQL Server | `已证实` | Hermes 日报走 `TemplateDailyFacts`、`daily_reports`、RAG 历史归档；事实来自本地投影和本地业务表。 |
| SQL Server 只用于 adapter/sync/audit/read-through | `已证实` | `SqlServerMesAdapter` 只允许固定 `SELECT`；`mes_sync_service` 把结果写入本地投影；审计脚本只读；read-through 只能作为受控后端读取，不给页面直接绕过本地投影。 |
| 外部凭据不入代码、文档、日志 | `已证实` | SQL Server 方案文档明确禁止写真实凭据；代码有敏感字段过滤和错误脱敏。 |

标准链路：

```text
MES 页面/MVC 证据 + SQL Server 只读表
  -> SqlServerMesAdapter
  -> mes_sync_service
  -> 本地 mes_* 投影表
  -> FastAPI /api/v1 接口
  -> Vue 管理端/移动端
  -> Hermes 日报事实包 / RAG 历史 / 输出 skill 对齐
```

## 总事实地图

| MES 页面/业务 | 状态 | SQL Server 表字段 | 本地投影 | API | 前端页面 | Hermes / 输出 skill 字段 |
|---|---|---|---|---|---|---|
| 在制料：调度管理 / 生产车间实时查询 `/Dispatch/Index`、在制料统计 | `已证实` 字段链路；重量单位仍 `待浏览器/SQL复核` | `MES_Product.CurrentWorkShop`、`CurrentProcess`、`FeedingWeight`，在制过滤排除 `InStockDate`、`DeliveryDate`、空车间、空工序 | `mes_wip_total_snapshots.workshop_name/process_name/doing_count/doing_weight_tons/snapshot_at/source_payload`；日快照 `mes_daily_wip_snapshots.business_date/workshop_name/process_name/coil_count/material_weight_tons/feeding_weight_tons` | `GET /api/v1/mes/extended/wip-total-snapshots`；`GET /api/v1/dashboard/daily-production`；`GET /api/v1/dashboard/workshop-director` | `/manage/workshop-dashboard` 的在制料明细；`/manage/today` 和 `/manage/live` 的在制分布 | `wip_total`、`wip_1650_2050_cold`、`wip_1850_cold`、`wip_milling`、`wip_anneal_total`、`wip_new_north`、`wip_new_south`、`wip_park_anneal`、`wip_finishing_total`、`wip_straightening`、`wip_finishing`、`wip_park_finishing`、`wip_hot_plate_shearing`、`wip_coating` |
| 投料管理：计划管理 / 投料管理 `/Feeding/Index` | `已证实` | `MES_Product.FeedingWeight`、`CreateDate`、`CurrentWorkShop` | `mes_coil_snapshots.feeding_weight/business_date/event_time/current_workshop/source_payload.metadata.CreateDate` | `GET /api/v1/dashboard/mes-factory-production-reconciliation` 返回 `factory_feeding_daily_input`、`factory_feeding_month_to_date_input`；`GET /api/v1/dashboard/daily-production` | `/manage/workshop-dashboard` KPI `全厂投料`；`/manage/today` 日报卡片；`/manage/live` 实时头部 | 投料本身不是模板正文直接字段；用于 `daily_yield_rate/monthly_yield_rate` 的事实来源候选和对账字段 |
| 随行卡管理：计划管理 / 随行卡管理 `/FollowCard/Index` | `已证实` 本地字段；MES 页面列仍 `待浏览器/SQL复核` | 主表 `MES_Product`；随行卡优先 `MaterialCode`，兼容 `TrackingCardNo/FollowCardNo/CardNo/BatchNumber`；还包含 `Customer/CustomerSimple`、`Alloy`、`Specification`、`CurrentWorkShop`、`CurrentProcess`、`NextWorkShop`、`NextProcess`、`ProcessRoute` | `mes_coil_snapshots.tracking_card_no/material_code/batch_no/contract_no/customer_alias/alloy_grade/spec_display/current_workshop/current_process/next_workshop/next_process/process_route_text`；流转事件 `coil_flow_events` | `GET /api/v1/factory-command/coils`；`GET /api/v1/factory-command/coils/{coil_key}/flow`；`GET /api/v1/mobile/coil-flow-suggestion`；`GET /api/v1/work-orders/{tracking_card_no}` | `/manage/coils` 卷级线索；`/entry/coil` 按卷录入辅助 | 日报模板不直接打印随行卡；输出 skill 对齐可用卷号、合同、客户、机台、工序作对账维度 |
| 车间报表：车间生产管理 / 车间报表 `/Report/ProductionWorkshopReport` | `已证实` | `MES_ProductProcessRecord.WorkShop`、`Process`、`DeviceName`、`BeginWeight`、`EndWeight`、`EndDatetime`、`Worker`、`BatchNumber` | `mes_workshop_process_records.workshop_name/process_name/device_name/input_weight_tons/output_weight_tons/end_time/business_date/worker_name/batch_no` | `GET /api/v1/dashboard/mes-workshop-machine-reconciliation`；`GET /api/v1/mes/extended/workshop-process-records`；`GET /api/v1/dashboard/daily-production` | `/manage/workshop-dashboard` 车间投料量、车间下机量、机台明细；`/manage/production`；`/manage/today` | 车间产量字段：`cold_1650_daily/month`、`cold_1850_daily/month`、`cold_2050_daily/month`、`online_anneal_daily/month`、`straightening_daily/month`、`finishing_daily/month`、`shearing_daily/month`、`coating_daily/month`；道次字段：`*_pass_daily/month` |
| 包装录入：包装管理 / 包装录入 `/Pack/Index` | `已证实` | `MES_ProductProcessRecord.Process = 包装`、`EndWeight`、`EndDatetime`、`WorkShop` | `mes_workshop_process_records.output_weight_tons/end_time/business_date/process_name/workshop_name`，过滤工序名包含 `包装` | `GET /api/v1/dashboard/mes-factory-production-reconciliation`；`GET /api/v1/dashboard/mes-home-reconciliation`；`GET /api/v1/dashboard/daily-production` | `/manage/workshop-dashboard` KPI `全厂包装`；`/manage/today` 包装/总产量；`/manage/production` | `total_output_daily`、`total_output_month`、`total_output_delta` 的 MES 包装产量来源；输出 skill 中“车间总产量日合计/月累计”对齐目标 |
| 成品调拨单：包装管理 / 成品调拨单 `/Allocation/Index` | `候选`，当前已有后端对照口径 | 候选 `WMS_InStockDetail.NetWeight/CreateDate/AllocationDate/FromDepartment/ToDepartment`、`WMS_OutStockDetail.NetWeight/CreateDate/DeliveryCode`、`WMS_Stock` | `mes_stock_records.source_path in ('sqlserver:stock_records','sqlserver:delivery_stock_records')`，字段 `net_weight_tons/business_date/source_payload.FromDepartment/ToDepartment` | `GET /api/v1/dashboard/mes-factory-production-reconciliation` 的 `packaging_fact.finished_transfer_day`；`GET /api/v1/mes/extended/stock-records` | `/manage/today`、`/manage/production` 可作为包装流转对照；具体展示位置 `待浏览器/SQL复核` | 不直接替代入库字段；可作为 `finished_inbound_daily/month` 的对照候选，不能和包装工序、成品入库混成一个数 |
| 成品库出入库：成品库 / 库存查询 `/Stock/Index` | 入库 `已证实`；出库 `候选` | 入库：`WMS_InStock.TotalNetWeight/InStockDate`、`WMS_InStockDetail.NetWeight/CreateDate`；出库候选：`MES_DeliveryDetail.NetWeight/OperateDate`、`WMS_OutStockDetail.NetWeight/CreateDate/DeliveryCode` | `mes_stock_records.source_path='sqlserver:stock_header_records'` 或 `sqlserver:stock_records`，字段 `net_weight_tons/in_stock_date/business_date/status_name`；出库兜底也落 `mes_stock_records` | `GET /api/v1/dashboard/mes-factory-production-reconciliation` 返回 `factory_finished_inbound_daily_output`、`factory_finished_inbound_month_to_date_output`；`GET /api/v1/mes/extended/stock-records` | `/manage/workshop-dashboard` KPI `成品入库`；`/manage/today` 入库成品；`/manage/production` | `finished_inbound_daily`、`finished_inbound_month`；输出 skill 正文“入库成品日合计/月累计” |
| 坯料明细：坯料管理 / 坯料明细 `/Material/Index` | `已证实` | `MES_Material.Weight`、`ProductionDate`、`WorkShopRolling/PWorkShop/WorkShop`、`MaterialCode`、`Alloy`、`Specification`、`StatusName`；状态包含 `已使用`、`未使用` | `mes_material_records.material_code/workshop_name/line_name/alloy_grade/spec_display/weight_tons/production_date/business_date/status_name` | `GET /api/v1/mes/extended/material-records`；`GET /api/v1/dashboard/mes-workshop-machine-reconciliation` 的坯料车间 source_mapping；`GET /api/v1/dashboard/daily-production` | 坯料车间日报/生产分析；具体页面明细展示 `待浏览器/SQL复核` | `hot_roll_daily/month`、`cast_2_daily/month`、`cast_3_daily/month` 可从 `mes_material_records` 填补；业务时间用 `10:00-10:00` |
| 前世今生：前世今生 `/Archives/Index` | 本地追溯 `已证实`；MES 原页面字段 `候选` | 候选串联 `MES_Product`、`MES_ProductProcessRecord`、`WMS_InStockDetail`、`WMS_Stock` | `mes_coil_snapshots` + `mes_workshop_process_records` + `mes_stock_records` + `coil_flow_events` | `GET /api/v1/factory-command/coils`；`GET /api/v1/factory-command/coils/{coil_key}/flow` | `/manage/coils` 卷级线索，可看当前车间/工序、上一道/下一道、入库/调拨/交付状态 | 日报不直接打印；Hermes/RAG 可把它作为卷级追溯事实。缺某段时标缺口，不能补假数据 |
| Hermes 日报事实包 | `已证实` | 不直接读 SQL Server；只读本地投影和业务表 | `TemplateDailyFacts.target_date/wip_date/values/sources/missing_fields/conflicts`；最终进入 `daily_reports.report_data.template_daily_report` 和 `final_text_summary` | `GET /api/v1/reports/template-daily/preview`；后台 `generate_daily_reports()`；RAG 归档 `archive_latest_daily_report_to_rag()` | `/manage/today` 日报工作台；Hermes 钉钉/日报推送链路 | `REQUIRED_FIELDS` 全量字段，分组为 opening、workshop_output、manual_supplement、wip、energy、contract_input、yield、cost |
| 输出 skill 样本 | `已证实` 为验证源；全量真实匹配率仍 `待浏览器/SQL复核` | 不作为运行时 SQL 源；只读参考文件结构和脱敏样本 | 系统侧拉平本地 `mes_*`、`work_order_entries`、`machine_energy_records`、`daily_reports` 等 | `GET /api/v1/mapping-reconciliation/sources`；`POST /api/v1/mapping-reconciliation/run`；`GET /api/v1/mapping-reconciliation/runs/{id}`；`GET /api/v1/mapping-reconciliation/runs/{id}/differences` | `/manage/mapping-reconciliation` 输出 skill 对齐 | `output_skill_report_parser.py` 把日报正文解析成模板字段；`D:\输出skill` 只做校验目标，不反向改生产数据 |

## 关键本地投影字段

### `mes_coil_snapshots`

状态：`已证实`

用途：卷级主事实、投料、随行卡、当前工序、前世今生主干。

关键字段：

| 本地字段 | 外部候选字段 | 用途 |
|---|---|---|
| `coil_id`、`mes_product_id` | `MES_Product.Id/ProductId` | 卷材唯一键和去重。 |
| `tracking_card_no`、`material_code` | `MaterialCode`，兼容随行卡别名字段 | 随行卡查询、扫码/手输辅助。 |
| `batch_no` | `PBatchNumber/BatchNumber/BatchNo` | 批号追溯、工序记录关联。 |
| `contract_no` | `ContractCode/ContractNo` | 合同和日报辅助。 |
| `customer_alias` | `CustomerSimple/Customer/CustomerName` | 客户说明和检索。 |
| `alloy_grade` | `Alloy` | 合金。 |
| `spec_display/spec_thickness/spec_width/spec_length` | `Specification/SpecThickness/SpecWidth/SpecLength` | 规格。 |
| `feeding_weight` | `FeedingWeight` | 投料量。 |
| `current_workshop/current_process` | `CurrentWorkShop/CurrentProcess` | 当前在制位置。 |
| `next_workshop/next_process` | `NextWorkShop/NextProcess` | 下一道工序。 |
| `process_route_text` | `ProcessRoute` | 工艺路线。 |
| `in_stock_date/delivery_date/allocation_date` | 同名日期字段 | 判断入库、出库、调拨状态。 |
| `business_date/event_time/updated_from_mes_at/last_seen_from_mes_at` | `OperateDate/CreateDate/InStockDate` 等 | 业务日归属和同步新鲜度。 |

### `mes_workshop_process_records`

状态：`已证实`

用途：车间报表、机台上机/下机、包装工序、车间产量、道次。

| 本地字段 | SQL Server 字段 | 用途 |
|---|---|---|
| `workshop_name` | `WorkShop/Workshop/WorkShopName` | 车间。 |
| `process_name` | `Process/ProcessName/WorkShopProcess` | 工序。 |
| `device_name` | `DeviceName/Device/MachineName` | 机台。 |
| `input_weight_kg/input_weight_tons` | `BeginWeight/InputWeight/UpWeight` | 上机量/车间投料量。 |
| `output_weight_kg/output_weight_tons` | `EndWeight/OutputWeight/CalcWeight` | 下机量/包装量/过程产量。 |
| `end_time` | `EndDatetime/CalcDatetime/StrOperateDate` | 工序完成时间。 |
| `business_date` | 由 `end_time` 加业务日规则计算 | 日报、看板和对账。 |

### `mes_stock_records`

状态：入库 `已证实`，出库/调拨细分 `候选`

用途：成品入库、成品调拨、发货兜底。

| 本地字段 | SQL Server 字段 | 用途 |
|---|---|---|
| `source_path` | `sqlserver:stock_header_records/stock_records/delivery_stock_records` | 区分入库表头、入库明细、出库兜底。 |
| `net_weight_kg/net_weight_tons` | `TotalNetWeight/NetWeight/InStockNetWeight` | 入库或出库净重。 |
| `gross_weight_kg/gross_weight_tons` | `TotalGrossWeight/GrossWeight` | 毛重参考。 |
| `in_stock_date` | `InStockDate/CreateDate/AllocationDate/OperateDate` | 入库或流转时间。 |
| `business_date` | 由时间字段加业务日规则计算 | 日报归属。 |
| `source_payload.FromDepartment/ToDepartment` | 同名部门字段 | 成品调拨单过滤和对照。 |

### `mes_material_records`

状态：`已证实`

用途：铸二、铸三、热轧等坯料产量。

| 本地字段 | SQL Server 字段 | 用途 |
|---|---|---|
| `material_code` | `MaterialCode/MaterialAutoCode` | 坯料编号。 |
| `workshop_name` | `WorkShopRolling/PWorkShop/WorkShop` | 坯料来源车间。 |
| `weight_kg/weight_tons` | `Weight/MaterialWeight` | 坯料重量。 |
| `production_date` | `ProductionDate/StrProductionDate` | 坯料生产时间。 |
| `business_date` | 按车间业务时间计算 | 日报归属，铸二/铸三/热轧走 `10:00-10:00`。 |
| `status_name` | `StatusName/Status` | 当前包含 `已使用`、`未使用`。 |

## Hermes 日报字段分组

状态：`已证实`

Hermes 日报事实包不是一个单表查询结果，而是：

```text
collect_template_daily_facts()
  -> TemplateDailyFacts.values
  -> validate_template_daily_report_facts()
  -> render_template_daily_report()
  -> daily_reports.report_data.template_daily_report
  -> daily_reports.final_text_summary
```

字段分组：

| 分组 | 代表字段 |
|---|---|
| `opening` | `report_date`、`total_output_daily`、`total_output_delta`、`total_output_month` |
| `workshop_output` | `cast_roll_daily/month`、`hot_roll_daily/month`、`cold_1650_daily/month`、`rolling_daily/month`、`finishing_daily/month` 等 |
| `manual_supplement` | `recovery_daily/month`、`roller_grind_daily/month` |
| `wip` | `wip_total` 及各在制料拆分字段 |
| `energy` | 全厂用电、用气、各车间吨耗字段 |
| `contract_input` | `finished_inbound_daily/month`、`daily_contract_weight`、`cold_roll_input_daily`、`remaining_contract_weight` |
| `yield` | `daily_yield_rate`、`monthly_yield_rate`、`hot_roll_yield_rate`、`cast_roll_yield_rate` |
| `cost` | `electricity_cost_10k`、`gas_cost_10k`、`total_cost_10k`、`cost_per_ton` |

特别说明：

- `D:\输出skill` 是验证目标，不是运行时事实源。
- 输出 skill 正文解析器会把中文日报正文反解析成同一批字段，用来对账。
- `missing_fields` 不为空时，系统应显示缺字段或阻断自动文本，不能让模型猜数。

## 待复核清单

| 项 | 状态 | 需要复核什么 |
|---|---|---|
| 在制料 `doing_weight_tons` 单位 | `待浏览器/SQL复核` | 代码字段名是吨，但 SQL 来源是 `MES_Product.FeedingWeight`；需要用真实 SQL 和 MES 页面确认是 kg 还是吨，避免输出 skill 对账误差。 |
| 成品调拨单精确表 | `待浏览器/SQL复核` | 当前后端用 `WMS_InStockDetail` 和 `WMS_OutStockDetail` 做对照，MES 页面是否还依赖 `WMS_Stock` 需要页面和 SQL 同步确认。 |
| 成品库出库主表 | `候选` | 入库已明确，出库/发货需要确认 `MES_DeliveryDetail`、`WMS_OutStockDetail`、`WMS_Stock` 的主次关系。 |
| 前世今生页面字段 | `候选` | 本地 `/manage/coils` 已能追溯，但 MES `/Archives/Index` 原页面具体接口和字段还需浏览器抓取。 |
| Hermes RAG 静态路线里的 `07:30` | `待浏览器/SQL复核` | `business_time.py` 和新 MES 文档是 `07:50`，但 `hermes_rag_service.build_mes_route_catalog_text()` 仍写 `07:30`，需要后续统一。 |
| 输出 skill 真实全量匹配率 | `待浏览器/SQL复核` | 已有解析和 dry-run 底座，但不能宣称真实全量 95%+ 已完成。 |

## 可直接使用的结论

1. 页面、API、Hermes 的主读取层是本地 `mes_*` 投影，不是 MES SQL Server。
2. SQL Server 的主职责是只读同步、审计、对账和受控 read-through。
3. 投料、包装、入库是三件事：
   - 投料：`MES_Product.FeedingWeight`。
   - 包装：`MES_ProductProcessRecord.EndWeight` 且 `Process=包装`。
   - 入库：`WMS_InStock/WMS_InStockDetail` 的净重和入库时间。
4. 车间/机台报表用 `MES_ProductProcessRecord.BeginWeight/EndWeight/DeviceName/EndDatetime`。
5. 坯料明细用 `MES_Material.Weight/ProductionDate`，铸二、铸三、热轧按 `10:00-10:00`。
6. Hermes 日报只渲染事实包字段；缺字段必须显式暴露，不能让模型补数字。
