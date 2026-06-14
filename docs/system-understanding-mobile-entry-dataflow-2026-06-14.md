# 手机填报端数据链路理解记录（2026-06-14）

## 结论摘要

本轮只读理解范围是 `鑫泰铝业 数据中枢` 的手机填报端：`/entry` 路由、固定填报模板、移动端 API、后端保存服务、数据库落表、角色权限和业务时间。

当前链路不是“手机端直接写 MES”。手机端写入本系统本地数据库：

- 主操逐卷填报：写入 `work_order_entries`，`entry_type = mobile_coil`。
- 电工班次填报：写入 `mobile_shift_reports`，机台明细另写 `machine_energy_records`。
- 内勤/专项每日一录：写入 `work_order_entries`，`entry_type = owner_daily`，具体字段放在 `extra_payload`。
- 车间主任：是管理查看角色，不是手机填报角色。

线上生产库只读抽查证实：这些表里都有近期真实记录，不只是代码里有功能。

## 前端入口

手机端主路由在 `frontend/src/router/index.js`：

- `/entry`：手机端首页。
- `/entry/fill`：当前统一填报页 `UnifiedEntryForm`。
- `/entry/report/:businessDate/:shiftId`：旧快速填报页，仍作为兼容入口保留。
- `/entry/coil/:businessDate/:shiftId`：逐卷录入工作台。
- `/entry/history`：历史填报记录页。

前端移动端 API 在 `frontend/src/api/mobile.js`：

- `GET /mobile/bootstrap`：取当前用户入口信息。
- `GET /mobile/current-shift`：取当前业务日、班次、车间、机台上下文。
- `GET /mobile/entry-fields`：按角色取固定模板字段。
- `POST /mobile/report/save` 和 `POST /mobile/report/submit`：班次类填报保存与提交。
- `POST /mobile/coil-entry`：主操逐卷提交。
- `GET /mobile/owner-daily/{business_date}` 和 `POST /mobile/owner-daily`：每日一录读取和保存。
- `GET /mobile/report/history`：历史记录。

`UnifiedEntryForm` 根据后端返回的 `mode` 和 `submit_target` 决定提交方式：

- `submit_target = coil_entry`：调用 `createCoilEntry()`。
- `submit_target = owner_daily`：调用 `saveOwnerDailyEntry()`。
- 其他情况：先 `saveMobileReport()`，再 `submitMobileReport()`。

## 角色到落表映射

| 角色 | 前端模式 | 后端接口 | 主要落表 | 说明 |
|---|---|---|---|---|
| `machine_operator` 主操 | `per_coil` | `POST /mobile/coil-entry` | `work_order_entries` | `entry_type = mobile_coil`，按卷记录随行卡、投料、下机、废料、机台等 |
| `energy_stat` 车间电工 | `per_shift` | `POST /mobile/report/save` + `/submit` | `mobile_shift_reports` + `machine_energy_records` | 总电/总气写班次汇总，机台明细写 `machine_energy_records` |
| `consumable_stat` 生产内勤 | `owner_daily` | `POST /mobile/owner-daily` | `work_order_entries` | `entry_type = owner_daily`，字段放 `extra_payload` |
| `quality_owner`、`planning_owner`、`energy_chief`、`storage_owner` 等专项岗 | `owner_daily` | `POST /mobile/owner-daily` | `work_order_entries` | 一日一录，按人和日期生成虚拟 `OWNER-角色-用户-日期` 工单号 |
| `workshop_director` 车间主任 | 管理端查看 | 管理端接口 | 不参与手机填报 | `is_manager = true`，只能看对应车间看板 |

## 后端保存逻辑

后端移动端路由在 `backend/app/routers/mobile.py`。

`/mobile/entry-fields` 会根据 `ROLE_FIELD_MAPPING` 给每个角色发固定字段：

- 主操使用模板里的 `entry_fields`，并强制加 `tracking_card_no`。
- 电工使用模板里 `role_write` 包含 `energy_stat` 的字段。
- 生产内勤使用模板里 `role_write` 包含 `consumable_stat` 的字段。
- 质检、计划、总电工、成品库、园区剪切、回收、大修等使用各自每日一录字段。

班次类保存由 `backend/app/services/mobile_report/lifecycle.py::save_or_submit_report()` 完成：

- 先检查必须是手机填报用户。
- 每日一录角色会被拒绝走班次接口，避免写错表。
- 电工只写能耗字段；非电工写产量、出勤、异常等字段。
- 如果提交了 `machine_energy_records`，会先汇总到 `mobile_shift_reports.electricity_daily/gas_daily`，再把明细写入 `machine_energy_records`。
- 非电工提交后会同步到 `shift_production_data`，用于后续汇总和校验。

主操逐卷保存由 `backend/app/services/mobile_report/summary.py::create_coil_entry()` 完成：

- 先校验投料量必须大于 0。
- 根据随行卡号找或创建 `work_orders`。
- 根据扫码机台账号找绑定机台和所在车间。
- 写入 `work_order_entries`，`entry_type = mobile_coil`。
- 如果未填废料但有投料和下机，会按 `投料 - 下机 - 套筒 - 切边 - 托盘` 自动算废料。
- 保存后聚合到班次维度。

每日一录保存由 `backend/app/services/mobile_report/summary.py::save_owner_daily_entry()` 完成：

- 只允许 `OWNER_DAILY_ROLES` 内的角色。
- 根据当前时间按 09:30 切业务日。
- 创建或复用虚拟工单号 `OWNER-角色-用户ID-业务日`。
- 写入 `work_order_entries`，`entry_type = owner_daily`。
- 具体字段整体放在 `extra_payload`。

## 业务时间口径

后端口径在 `backend/app/core/business_time.py`：

- 生产业务日：07:30 到次日 07:30。
- 内勤/专项每日一录：09:30 到次日 09:30。

前端口径在 `frontend/src/utils/shiftClock.js`：

- 长白班：07:30-15:30。
- 小夜班：15:30-23:30。
- 大夜班：23:30-次日 07:30。
- 生产业务日锚点：07:30。
- 每日一录锚点：09:30。

前后端当前口径是一致的。

## 线上只读证据

生产服务器 `/srv/aluminum-bypass` 当前仓库和服务可用。本轮只读查询没有修改生产数据。

活跃账号数量抽查：

- `machine_operator = 47`
- `energy_stat = 16`
- `consumable_stat = 16`
- `workshop_director = 15`
- `energy_chief / quality_owner / planning_owner / storage_owner / shipment_outflow_owner / recovery_owner / overhaul_owner` 各有账号。

近期真实数据抽查：

- `mobile_shift_reports` 有 2026-06-14 的铸轧二、铸轧三电工提交记录。
- `machine_energy_records` 有 2026-06-14 的铸轧二、铸轧三机台气耗明细。
- `work_order_entries` 有 2026-06-14 的主操逐卷记录，包含剪切、淬火、热轧、铸轧三等车间。
- `work_order_entries` 有 2026-06-13 的每日一录记录，包含成品库、拉矫、新厂在线退火、质量内勤等。

这说明三条链路在生产库中都有真实数据。

## 已发现风险

1. `/entry/history` 后端历史接口当前主要返回 `mobile_shift_reports` 和主操 `mobile_coil` 记录；每日一录 `owner_daily` 记录虽然有 schema 和前端标签，但后端 `list_report_history()` 没有把每日一录统一并入历史列表。每日一录在 `/entry/fill` 当前页能加载当天记录，但“历史页看整日每日一录”可能不完整。
2. `ShiftReportHistory.vue` 的 `advancedRoleBuckets` 没有包含 `consumable_stat`。如果历史接口后续返回生产内勤每日记录，详情跳转可能走旧的 `mobile-report-form`，而不是统一填报页。
3. `save_owner_daily_entry()` 会按当前时间强制校正业务日，这对防止填错日期有帮助，但如果现场需要补更早日期，需要专门的补录/审核入口，不应直接复用普通每日一录入口。
4. `work_order_entries` 的 `owner_daily` 数据把字段放在 `extra_payload`，灵活但不如独立字段直观；后续做报表时必须通过统一字段字典读取，避免某个页面漏读或错读。

## 下一步建议

- 修复 `/entry/history`：把 `owner_daily` 每日一录记录并入历史接口，并让 `consumable_stat` 详情进入 `/entry/fill`。
- 给 `owner_daily` 历史增加回归测试：生产内勤、成品库、总电工都能按业务日查到整日记录。
- 给 `machine_energy_records` 增加“有机台明细时班次总能耗等于明细汇总”的测试。
- 给 `/mobile/entry-fields` 增加角色字段快照测试，防止以后模板字段被误删或误分配。

## 本轮复核补充（2026-06-14 下午）

这次补充只做代码阅读、线上只读接口烟测和浏览器只读验证，没有提交生产填报数据。

### 权限边界再确认

- 管理员 `admin` 能登录管理端，但在生产环境不是手机填报用户。
- 管理员访问 `GET /api/v1/mobile/bootstrap` 返回 403，这是正确行为，不是接口坏了。
- 管理员访问 `GET /api/v1/mobile/report/history` 返回 403，也是正确行为。
- 管理员访问 `/entry` 前端会被带回 `/manage/admin/settings`，说明前端和后端都在阻止管理员误进手机填报端。
- 车间主任看板接口 `GET /api/v1/dashboard/workshop-director` 可读，管理员全局查看时 `workshop_id = null`，车间主任实际登录时会被 `assert_manager_dashboard_access()` 限制在自己的车间。

### 线上只读接口证据

线上 `GET /api/v1/users/?limit=500&is_active=true` 只读抽查显示：

- 启用主操 `machine_operator`：47 个。
- 启用电工 `energy_stat`：16 个。
- 启用内勤/辅材 `consumable_stat`：16 个。
- 启用车间主任 `workshop_director`：15 个。
- 启用移动/专项角色总数：86 个。
- 有机台绑定的启用账号：101 个。

这里的 `15` 是包含回收、成品库等更宽管理/部门口径，不等于“13 个活跃生产车间”。以后讨论车间数量时必须先说明口径。

### 车间看板前端证据

浏览器只读打开 `/manage/workshop-dashboard` 正常，无控制台红错、无请求失败。页面展示：

- 车间看板。
- 机列填报明细。
- 电工填报明细。
- MES 外部数据、人工填报、算法数据三类来源标识。
- 缺报导出入口。
- 更宽口径车间筛选项：铸锭分厂、铸轧二、铸轧三、热轧、三条冷轧、精整、剪切、拉矫、回收、成品库、新厂在线退火、园区在线退火、淬火车间等。

### 保存链路再确认

- `backend/app/services/mobile_report/lifecycle.py::save_or_submit_report()` 是班次填报主保存逻辑。
- 电工提交 `machine_energy_records` 时，会先把明细汇总到 `mobile_shift_reports.electricity_daily/gas_daily`，再写入 `machine_energy_records`。
- `backend/app/services/mobile_report/summary.py::create_coil_entry()` 是主操逐卷保存逻辑，写 `work_order_entries`，`entry_type = mobile_coil`。
- `backend/app/services/mobile_report/summary.py::save_owner_daily_entry()` 是每日一录保存逻辑，写 `work_order_entries`，`entry_type = owner_daily`。
- `mobile_report_service.py` 本身只是兼容转发文件，真实实现已经拆到 `backend/app/services/mobile_report/` 文件夹。

### 仍需后续处理的风险

- `/entry/history` 当前只明确合并班次记录和主操逐卷记录；每日一录 `owner_daily` 还需要继续补进历史页闭环。
- 车间看板显示的是 15 个更宽口径选项；如果某些页面只要 13 个活跃生产车间，必须使用独立的活跃生产车间口径，不能直接复用这里的管理筛选。
- 线上只读烟测证明页面可打开、权限能拦截，但没有替代真实手机端账号的逐角色提交测试。
