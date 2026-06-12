# Stitch + image2 前端重构阶段 1：系统理解与数据链路地图

日期：2026-06-12

## 执行保护结论

1. 当前工作分支：`stitch-image2-frontend-redesign-20260612`。
2. 计划基线已提交：`867ff32 docs: add stitch image2 frontend redesign plan`。
3. Stitch MCP 可用，已能读取已有的工业蓝、手机端、调度墙相关 Stitch 项目。
4. CodeGraph 可用，当前索引约 989 个文件。
5. 前端单元测试基线通过：`npm run test`，637 个测试通过。
6. 后端测试收集可用：`python -m pytest --collect-only -q`，收集到 1304 个测试，27 个被默认标记排除。
7. 后端全量 `python -m pytest -q` 在 5 分钟内未完成，暂记为“慢测试基线风险”，后续阶段按受影响链路先跑聚焦测试。

## 页面入口地图

管理端核心入口来自 `frontend/src/router/index.js` 和 `frontend/src/config/manage-navigation.js`。

核心管理页面：

1. `/manage/live`：生产实时调度墙，组件为 `LiveDashboardPage`。
2. `/manage/today`：昨日报表，组件为 `TodayPage`。
3. `/manage/production`：生产分析，组件为 `ProductionPage`。
4. `/manage/workshop-dashboard`：各车间看板，组件为 `WorkshopDashboardPage`。
5. `/manage/coils`：卷级线索，组件为 `CoilTracePage`。
6. `/manage/fill-details`：填报明细，组件为 `FillDetailsPage`。
7. `/manage/energy`：能源中心，组件为 `EnergyCenter`。
8. `/manage/alerts`：异常处理，组件为 `AlertsPage`。
9. `/manage/admin/settings`：系统设置，组件为 `SystemSettingsPage`。
10. `/manage/admin/users`：账号权限，组件为 `UserManagement`。

手机端核心入口：

1. `/entry`：填报端首页。
2. `/entry/fill`：统一填报。
3. `/entry/consumables`：辅材和内勤类填报。
4. `/entry/coil/:businessDate/:shiftId`：按卷录入。
5. `/entry/history`：历史填报。
6. `/entry/drafts`：草稿箱。

已确认的旧入口处理：

1. `/manage/daily-report` 已重定向到 `/manage/today`。
2. `/admin/setting` 已重定向到 `/manage/admin/settings`。
3. `/manage/admin/templates` 已重定向到 `/manage/admin/settings`。
4. `/team-lead` 已重定向到 `/entry`。

## 前端 API 地图

核心前端 API 文件：

1. `frontend/src/api/dashboard.js`：日报、管理概览、累计、对比、趋势、外部就绪状态。
2. `frontend/src/api/realtime.js`：实时调度、填报明细、缺报导出、MES 补录缺口。
3. `frontend/src/api/mes.js`：MES 同步状态、MES 扩展数据、在制料、工序记录。
4. `frontend/src/api/energy.js`：能源汇总。
5. `frontend/src/api/mobile.js`：手机端启动、扫码、填报、历史、MES 待补录。
6. `frontend/src/api/production.js`：旧生产导入和班次生产数据接口，仍需谨慎处理。

## 后端接口地图

后端挂载入口来自 `backend/app/main.py`。

核心后端路由：

1. `/api/v1/dashboard/*`：来自 `backend/app/routers/dashboard.py`。
2. `/api/v1/aggregation/live/*`：来自 `backend/app/routers/realtime.py`。
3. `/api/v1/mes/*`：来自 `backend/app/routers/mes.py`。
4. `/api/v1/energy/*`：来自 `backend/app/routers/energy.py`。
5. `/api/v1/mobile/*`：来自 `backend/app/routers/mobile.py`。
6. `/api/v1/production/*`：来自 `backend/app/routers/production.py`。

健康检查：

1. `/healthz` 可用。
2. `/api/v1/healthz` 可用。
3. `/readyz` 会检查更完整的就绪状态，后续不能把外部 MES 临时失败直接等同为部署失败。

## 数据来源地图

MES 外部数据：

1. `mes_coil_snapshots`：卷级快照、随行卡号、工艺路线、当前工序、下一工序、在制状态。
2. `mes_machine_line_snapshots`：MES 侧机列或终端线体。
3. `mes_workshop_process_records`：车间工序产量，包含投入、产出、工序、设备、人员、结束时间、业务日。
4. `mes_stock_records`：成品入库相关数据，核心字段为净重吨数和入库时间。
5. `mes_material_records`：在制料和材料明细。
6. `mes_yield_records`：MES 侧成品率和合同相关数据。
7. `mes_wip_total_snapshots`：MES 在制汇总快照。

人工填报数据：

1. `mobile_shift_reports`：手机端班次填报，保存班次、车间、团队、产量、能耗、异常等。
2. `work_order_entries`：按卷录入，保存随行卡、机台、上机下机重量、规格、废料、能耗、附加字段。
3. `shift_production_data`：班次生产汇总数据，含导入和确认状态。
4. 内勤日汇总类表：例如 `recovery_daily`、`overhaul_daily`、以及通过 owner daily 服务写入的日填报数据。

算法和汇总数据：

1. `backend/app/core/business_time.py` 定义业务日。
2. `backend/app/domain/metric_contracts.py` 定义核心指标口径。
3. `backend/app/services/report/*` 负责日报、驾驶舱、趋势、对比等管理端汇总。
4. `backend/app/services/realtime_service.py` 负责实时调度墙、填报明细、缺报、待分配等。
5. `backend/app/services/energy_service.py` 负责能源汇总。
6. `backend/app/services/mes_extended_service.py` 负责 MES 扩展数据查询。

## 时间口径地图

1. 主操、电工等生产类角色业务日：早上 07:30 开始，每 24 小时一循环。
2. 内勤日填报业务日：早上 09:30 开始，每 24 小时一循环。
3. 管理端默认日报目标日：使用 `last_completed_production_business_date`，即最后一个已完成生产业务日。
4. MES 工序、入库、在制相关记录已带 `business_date` 字段，后续页面必须优先使用此字段而不是前端临时按自然日猜。

## 核心指标口径地图

来自 `backend/app/domain/metric_contracts.py`：

1. 全厂总产量：主口径为 `mes_stock_records.net_weight_tons`，只统计成品入库相关最终工序。
2. 机台用电：主口径为 `machine_energy_records.energy_kwh`，没有机台明细时才退到班次填报电量。
3. 正式成品率：主口径为正式成品率矩阵，运行时投入产出只作为明细兼容。
4. MES 在制卷：主口径为 `mes_coil_snapshots`，要求按业务日、未入库、未发货、仍有当前或下一工序过滤。

## 权限地图

1. 管理端全局页面需要管理员、经理或全局 review 权限。
2. 车间主任使用 `workshop_dashboard` 范围，只能看本车间看板。
3. 实时调度接口会按用户 scope 限制 workshop。
4. MES 扩展数据接口允许管理员、经理、review 角色访问，并按车间范围过滤。
5. 手机端接口使用 mobile 用户权限，当前角色决定可见字段和提交目标。

## 阶段 1 风险清单

1. 后端全量测试耗时过长，后续不能只依赖全量 pytest 作为每阶段反馈，需要“聚焦测试 + 最终长测试”组合。
2. 旧导入接口仍存在但大多返回 410 或重定向，前端重构时不能误把旧导入功能重新做成主入口。
3. `/manage/daily-report` 与 `/manage/today` 已合并为重定向，后续设计要以 `/manage/today` 为主。
4. MES 数据和人工填报数据已经并存，前端必须明确显示来源，不能只显示一个混合数字。
5. 能耗口径存在机台明细优先、班次电量兜底的规则，页面设计不能只写“总电量”。
6. 内勤和生产角色业务日开始时间不同，页面需要标注或至少内部传参正确。
7. 手机端字段由固定模板和角色映射决定，不能让 Stitch 设计稿擅自增删字段。

## 阶段 1 验收结论

阶段 1 达到继续条件：

1. 核心页面入口已列清。
2. 核心前端 API 已列清。
3. 核心后端路由已列清。
4. MES、人工填报、算法汇总、时间口径和权限边界已建立基础地图。
5. 下一阶段可以进入浏览器 QA 基线，不应直接开始大面积改 UI。
