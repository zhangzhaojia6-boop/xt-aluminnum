# 页面、接口、数据表链路覆盖审计

日期：2026-06-11

范围：管理端页面、前端 API 模块、后端路由、服务层、数据库模型、测试覆盖。

## 1. 小白版结论

系统现在最大的问题不是“没有接口”，而是“页面、接口、数据表之间缺一张总账”。有些页面已经接到真实业务数据，有些页面是预留或旧入口，有些接口很重要但没有独立页面入口。后续如果要清理页面、删除接口、改大屏，必须先看这张链路总账，避免误删还在用的东西。

一句话：先把“哪个页面读哪个接口，接口背后读哪些表”搞清楚，再动代码。

## 2. 总体证据

### 2.1 后端路由已全部挂载

`backend/app/main.py` 第 291 到 325 行挂载了主要接口：

| 路由前缀 | 主要用途 |
| --- | --- |
| `/api/v1/auth` | 登录、刷新、当前用户 |
| `/api/v1/users` | 用户和权限 |
| `/api/v1/master` | 车间、机列、班次、别名 |
| `/api/v1/dashboard` | 日报、趋势、管理端历史指标 |
| `/api/v1/attendance` | 考勤预留/确认 |
| `/api/v1/production` | 班次产量、导入兼容、审核 |
| `/api/v1/mobile` | 手机填报端 |
| `/api/v1/reports` | 报表生成和发布 |
| `/api/v1/mes` | MES 同步、扩展数据、补录就绪 |
| `/api/v1/factory-command` | 卷级、工厂指挥、库存去向 |
| `/api/v1/energy` | 能耗 |
| `/api/v1/inventory` | 库存出入 |
| `/api/v1/contracts` | 合同 |
| `/api/v1/quality` | 质量异常 |
| `/api/v1/reconciliation` | 差异核对 |
| `/api/v1/ai`、`/api/v1/assistant` | AI 助手 |
| `/api/v1/realtime`、`/api/v1/aggregation/*` | 实时流和实时聚合 |

说明：接口面很完整，不能用“没入口”直接判断接口无用。

### 2.2 前端 API 模块数量

`frontend/src/api` 当前有 24 个 API 模块。核心模块：

| 模块 | 主要页面 |
| --- | --- |
| `realtime.js` | `/manage/live`、`/manage/fill-details`、`/manage/workshop-dashboard` |
| `dashboard.js` | `/manage/today`、日报/趋势 |
| `energy.js` | `/manage/energy` |
| `factory-command.js` | 未来 `/manage/coils`、库存去向、工厂指挥 |
| `mes.js` | `/manage/admin/settings`、车间看板 MES 明细 |
| `master.js` | 基础资料、别名、规则、二维码 |
| `users.js` | 账号权限、钉钉同步 |
| `mobile.js` | 手机填报、按卷补录 |
| `attendance.js` | 考勤预留、考勤详情 |
| `reports.js` | 报表中心 |

### 2.3 服务层体量

关键服务文件行数：

| 服务 | 行数 | 风险 |
| --- | ---: | --- |
| `backend/app/services/realtime_service.py` | 2457 | 实时大屏、填报明细、缺报、车间看板都依赖，改动必须 TDD |
| `backend/app/services/factory_command_service.py` | 1609 | 卷级线索、库存去向、工厂指挥依赖，适合拆清 DTO |
| `backend/app/services/mes_sync_service.py` | 1383 | MES 同步核心链路，不能随便改 |
| `backend/app/services/energy_service.py` | 682 | 能耗和吨耗口径依赖，后续物联网接入要从这里进 |
| `backend/app/services/mobile_mes_supplement_service.py` | 433 | 手机端 MES 待补录核心 |
| `backend/app/services/mes_fill_gap_service.py` | 366 | MES 有记录但填报缺失的差异识别 |

## 3. 核心页面到接口映射

### 3.1 实时调度墙 `/manage/live`

前端：

| 文件 | 读取 |
| --- | --- |
| `frontend/src/views/manage/live/LiveDashboardPage.vue` | `fetchLiveActiveDate`、`fetchLiveAggregation`、`fetchLiveCellDetail`、`fetchLiveFillDetails` |

后端：

| 接口 | 服务 |
| --- | --- |
| `/aggregation/live` | `realtime_service.build_live_aggregation` |
| `/aggregation/live/detail` | `realtime_service.build_live_cell_detail` |
| `/aggregation/live/fill-details` | `realtime_service.build_fill_detail_ledger` |
| `/realtime/stream` | `event_bus` 实时事件 |

主要表：

| 表 | 用途 |
| --- | --- |
| `mobile_shift_reports` | 手机填报主记录 |
| `shift_production_data` | 班次产量聚合 |
| `work_order_entries` | 补录和工单明细 |
| `machine_energy_records` | 机列能耗明细 |
| `mes_coil_snapshots` | MES 卷快照 |
| `attendance_*` | 缺报和人员状态 |

风险：这个页面是全系统最核心页面之一，不能只靠视觉测试，必须有字段契约测试保护。

### 3.2 昨日报表 `/manage/today`

前端：

| 文件 | 读取 |
| --- | --- |
| `frontend/src/views/manage/today/TodayPage.vue` | `fetchTimeseries`、`fetchLiveAggregation`、`fetchUsersPage` |

后端：

| 接口 | 服务 |
| --- | --- |
| `/dashboard/timeseries` | 日报趋势 |
| `/aggregation/live` | 当日/昨日核心口径 |
| `/users/` | 责任人和人员数据 |

风险：日报页同时读历史指标和实时聚合，必须统一业务日口径，否则会出现“今天、昨天、MES 在制料”对不上的问题。

### 3.3 生产分析 `/manage/production`

前端：

| 文件 | 读取 |
| --- | --- |
| `frontend/src/views/manage/production/ProductionPage.vue` | 通过页面内部组件和管理端工具读取生产聚合 |

后端：

| 接口 | 服务 |
| --- | --- |
| `/aggregation/live` | 实时生产聚合 |
| `/dashboard/daily-production` | 日产量 |
| `/aggregation/pass-count/*` | 冷轧道次/班次道次 |

风险：生产分析页要和日报页分工，不应重复显示同一堆指标。它更适合做车间/工序/机列分析。

### 3.4 填报明细 `/manage/fill-details`

前端：

| 文件 | 读取 |
| --- | --- |
| `frontend/src/views/manage/fill-details/FillDetailsPage.vue` | `fetchDailyProduction`、`fetchLiveAggregation`、`fetchLiveFillDetails`、`fetchMesFillGaps`、`exportMissingReportExcel`、`fetchWorkshops` |

后端：

| 接口 | 服务 |
| --- | --- |
| `/dashboard/daily-production` | 旧日报口径 |
| `/aggregation/live/fill-details` | 填报明细 |
| `/aggregation/live/mes-fill-gaps` | MES 和填报差异 |
| `/aggregation/live/missing-report-export` | 缺报导出 |

主要表：

| 表 | 用途 |
| --- | --- |
| `mobile_shift_reports` | 主操/电工等填报 |
| `work_order_entries` | 补录 |
| `mes_workshop_process_records` | MES 工序记录 |

风险：它应该展示“人工填报明细”，不要继续承担卷级线索主页面职责。

### 3.5 能耗中心 `/manage/energy`

前端：

| 文件 | 读取 |
| --- | --- |
| `frontend/src/views/energy/EnergyCenter.vue` | `fetchEnergySummary` |

后端：

| 接口 | 服务 |
| --- | --- |
| `/energy/summary` | `energy_service.get_energy_summary` |

主要表：

| 表 | 用途 |
| --- | --- |
| `energy_import_records` | 历史导入能耗 |
| `machine_energy_records` | 机列能耗明细 |
| `mobile_shift_reports` | 电工/主操填报能耗 |
| `work_order_entries` | 内勤/专项能耗 |
| `daily_consumable_logs` | 包装入库分母 |

风险：后续接物联网库时，不能让前端直连；应进入本地影子表，再由 `energy_service` 统一输出。

### 3.6 各车间看板 `/manage/workshop-dashboard`

前端：

| 文件 | 读取 |
| --- | --- |
| `frontend/src/views/manage/workshop-dashboard/WorkshopDashboardPage.vue` | `fetchWorkshopDashboard`、实时聚合、MES 工序、MES 在制、缺报导出 |

后端：

| 接口 | 服务 |
| --- | --- |
| `/dashboard/workshop-director` | 车间看板 |
| `/aggregation/live` | 实时聚合 |
| `/mes/extended/workshop-process-records` | MES 工序 |
| `/mes/extended/material-records` | MES 在制/材料 |

风险：车间主任权限必须严格按车间隔离，不能看到其他车间数据。

### 3.7 系统设置 `/manage/admin/settings`

前端：

| 文件 | 读取 |
| --- | --- |
| `frontend/src/views/manage/admin/SystemSettingsPage.vue` | `fetchMesSupplementReadiness` |

后端：

| 接口 | 服务 |
| --- | --- |
| `/mes/supplement-readiness` | `mes_supplement_readiness_service` |

风险：这里最适合放“PC/WAN/一体机待绑定终端清单”，但不能复用普通别名表硬做复杂绑定。

### 3.8 账号权限 `/manage/admin/users`

前端：

| 文件 | 读取 |
| --- | --- |
| `frontend/src/views/master/UserManagement.vue` | `fetchUsersPage`、`createUser`、`updateUser`、`deleteUser`、`resetUserPassword`、`syncDingtalkUsers` |

后端：

| 接口 | 服务 |
| --- | --- |
| `/users/` | 用户列表和增删改 |
| `/users/sync-dingtalk` | 钉钉同步 |

风险：钉钉同步接口还存在，但目前不是主业务链路。建议保留接口权限保护，但前端弱化或放进“预留能力”。

## 4. 弱业务页面与风险

### 4.1 合同页 `/manage/contracts`

现状：页面直接调用 `/contracts/summary` 和 `/contracts/export`。

风险：

1. 直接调用 API，不利于统一契约测试。
2. 合同指标如果和生产日报不同步，会干扰管理层判断。
3. 如果口径不稳，应先降级为二级入口。

建议：先迁移到 `frontend/src/api/contracts.js` 或统一 API 模块，再决定是否保留主入口。

### 4.2 库存页 `/manage/inventory`

现状：页面直接调用 `/inventory/summary` 和 `/inventory/export`。

风险：

1. 和卷级线索、库存去向页面职责重叠。
2. 当前更适合合并到 `/manage/coils` 的库存/去向筛选。

建议：先合并到卷级线索，不直接删除接口。

### 4.3 报表中心 `/manage/reports`

现状：读取 `/reports`。

风险：和 `/manage/today` 的日报职责重叠。

建议：作为 `/manage/today` 的历史报告抽屉或导出区域，不作为主导航。

### 4.4 考勤预留 `/manage/attendance`

现状：页面标题就是“考勤预留”，同时已有考勤接口和详情页。

风险：放在主导航会让用户以为考勤已正式接入。

建议：钉钉打通前降级到系统预留；详情页只从异常或考勤上下文进入。

## 5. 测试覆盖现状

### 5.1 后端测试

已有大量相关测试，例如：

| 领域 | 测试 |
| --- | --- |
| 实时聚合 | `test_realtime_service.py`、`test_realtime_routes.py`、`test_realtime_service_contract.py` |
| 能耗 | `test_energy_summary.py`、`test_energy_import.py` |
| MES | `test_mes_sync_service.py`、`test_mes_api_contract.py`、`test_mes_supplement_readiness_service.py` |
| 工厂指挥/卷级 | `test_factory_command_service.py`、`test_factory_command_routes.py` |
| 手机填报 | `test_mobile_routes.py`、`test_mobile_mes_pending_supplements.py`、`test_mobile_shift_report_machine_binding.py` |
| 合同/库存 | `test_inventory_contract_routes.py`、`test_contract_*` |
| 用户权限 | `test_users_routes.py`、`test_users_dingtalk_sync.py` |

### 5.2 前端测试

前端已有大量单测和 e2e，例如：

| 领域 | 测试 |
| --- | --- |
| 管理端实时/日报/生产 | `manageLivePhase2.test.js`、`manageTodayPage.test.js`、`manageProductionPage.test.js` |
| 能耗 | `energyCenterDesign.test.js`、`manage-energy.spec.js` |
| 异常 | `manageAlertsPage.test.js`、`manage-alerts-timeline.spec.js` |
| 设置/用户/主数据 | `systemSettingsPage.test.js`、`userManagementDesign.test.js`、`manage-shell.spec.js` |
| 合同/库存 | `contractsCenterDesign.test.js`、`inventoryCenterDesign.test.js`、对应 e2e |
| 手机填报 | `coilEntryWorkbench.scan.test.js`、`mobile-shift-report.spec.js`、`mobile-scan-entry.spec.js` |

缺口：还没有正式 `/manage/coils` 页面测试，也缺统一状态语言的跨页面测试。

## 6. 关键风险分级

### P1：缺页面-接口-表字段统一契约

影响：后端有数，前端可能显示 0、空、暂无可信数据。

建议：给 `live/today/production/fill-details/energy/coils` 建立字段契约测试。

### P1：`/manage/coils` 缺正式页面

影响：MES 卷级数据已有，但用户没有清晰入口查某卷料。

建议：新增页面，并接入现有 `factory-command` 卷接口。

### P1：实时服务过大，改动容易牵一发动全身

影响：`realtime_service.py` 2457 行，多个页面依赖。

建议：任何改实时聚合都先写测试，再小步改。

### P2：合同和库存页面直接调用 API

影响：错误处理、超时、权限和测试不统一。

建议：迁移到 API 模块后再决定是否主导航保留。

### P2：钉钉、导入、模板、考勤预留仍有接口或页面痕迹

影响：用户可能误点旧能力，开发者可能误以为仍是主线。

建议：保留兼容和权限保护，前端明确降级到预留或设置区。

## 7. 推荐下一步

### 第一阶段：字段契约补强

1. `/aggregation/live` 输出字段要覆盖实时页、日报页、生产页。
2. `/energy/summary` 要明确系统采集、人工填报、分母缺失。
3. `/factory-command/coils` 要补齐卷级线索字段。
4. `/mes/supplement-readiness` 要输出 PC/WAN 待绑定清单。

### 第二阶段：新增 `/manage/coils`

1. 新增路由和导航。
2. 接 `fetchFactoryCommandCoils` 和 `fetchFactoryCommandCoilFlow`。
3. 先做搜索、列表、详情抽屉。
4. 加单测和 e2e。

### 第三阶段：页面合并灰度

1. 库存并入卷级线索。
2. 报表并入昨日报表。
3. 考勤预留移出主导航。
4. 合同页降级为二级入口，等口径稳定后再提升。

## 8. 五视角评分

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.7 | 找到了“页面多但业务主线不够集中”的根因 |
| 工程 | 9.8 | 接口、服务、模型、测试链路都已定位，可安全施工 |
| 设计 | 9.6 | 下一步能把用户路径收敛到卷级、调度、异常、能耗 |
| 安全 | 9.7 | 保留权限边界，旧接口不直接删，外部数据不前端直连 |
| 真实用户 | 9.7 | 能减少找页面、看空页面、看错 0 的困惑 |

综合：9.7/10。

## 9. 结论

现在不建议继续盲目重构页面。更稳的路线是：

1. 先补页面-接口-字段契约测试。
2. 再新增 `/manage/coils`。
3. 再统一核心页面状态语言。
4. 最后灰度合并弱业务页面。

这能最大程度保证业务逻辑不乱、前端不空、用户能一眼找到真正要看的数据。
