# 鑫泰铝业 数据中枢运行链路增量地图（2026-06-14）

## 1. 本轮目的

这份文档补充 `docs/system-understanding-2026-06-14.md`，重点记录当前代码和云端真实运行环境中的接口、页面、数据库、外部连接状态。

本轮只做只读理解和记录，不改业务逻辑。

## 2. 当前代码状态

- 当前本地提交：`7b9157ec3b2e5b66df3176c659398ad4a222743a`
- 当前分支：`main`
- 本地仓库状态：干净，已对齐 `origin/main`
- CodeGraph 索引：
  - 文件：1031
  - 代码节点：15536
  - 关系边：31835
  - 后端：Python 592 个文件
  - 前端：Vue 176 个文件、JavaScript 254 个文件

## 3. understand 图谱状态

项目存在 `.understand-anything/.understandignore`，按 understand skill 规则，重建图谱前必须先确认忽略规则。

当前没有擅自重建全量图谱。

原因：

- 忽略文件会决定哪些代码、文档、测试、产物进入图谱。
- 如果未经确认直接重建，可能遗漏用户希望纳入理解的文件。
- 所以本轮改用 CodeGraph、源码静态读取和云端只读查询补充理解。

## 4. 后端路由覆盖面

后端主入口在 `backend/app/main.py`，核心 API 前缀是 `/api/v1`。

已确认注册的主要路由模块：

- `/auth`：登录、刷新、当前用户、二维码登录、退出。
- `/users`：用户列表、创建、更新、删除、重置密码、同步钉钉用户。
- `/master`：车间、班组、员工、设备、别名、MES 终端绑定、班次配置。
- `/dashboard`：厂长看板、车间主任看板、统计看板、日报产量。
- `/factory-command`：生产调度总览、车间、机列、卷材、卷级流转、成本收益、去向。
- `/mobile`：手机端初始化、当前班次、扫码查找、填报保存提交、历史、提醒、按卷录入、内勤日报。
- `/work-orders`：随行卡工单、工序录入、补录审批。
- `/mes`：MES 导入、同步状态、同步记录、补录准备度、扩展工序/库存/物料/在制/参考数据。
- `/energy`：能耗导入和能耗汇总。
- `/production`：班次产量、异常、审核、确认、驳回、作废。
- `/realtime`：实时流、生产大屏聚合、填报明细、缺报导出、MES 缺口。
- `/reports`：日报生成、列表、审核、发布、运行日报流水线、最终确认、推钉钉、导出。
- `/attendance`：排班、打卡、考勤处理、异常、补录、汇总。
- `/quality`：质量检查、质量问题处理。
- `/reconciliation`：数据差异生成、列表、确认、忽略、纠正。
- `/ai` 和 `/assistant`：AI 会话、消息、智能问答、简报、关注项、能力探测。
- `/agent-management`：智能体治理概览和知识问答。
- `/dingtalk`：钉钉登录和 H5 登录。
- `/notifications`：通知和未读数。
- `/executive`：经营看板、铝价、加工费、成本策略。
- `/inventory`、`/contracts`、`/consumables`：库存、合同、耗材。
- `/rule-configs`：规则配置。
- `/telemetry`：前端错误和性能上报。
- `/export`：统一导出。

## 5. 前端页面和接口覆盖面

前端核心页面仍以 `/manage` 和 `/entry` 两套入口为主。

管理端核心页面：

- `/manage/live`：生产实时大屏。
- `/manage/today`：昨日日报。
- `/manage/production`：生产分析。
- `/manage/coils`：卷级线索。
- `/manage/fill-details`：人工填报明细。
- `/manage/energy`：能源中心。
- `/manage/workshop-dashboard`：车间主任看板。
- `/manage/alerts`：异常中心。
- `/manage/admin/settings`：系统设置。
- `/manage/admin/users`：用户管理。
- `/manage/admin/governance`：权限与治理。
- `/manage/master`：主数据中心。
- `/manage/alias`：别名映射。
- `/manage/mes-terminal-bindings`：MES 终端绑定。
- `/manage/ai-assistant`：AI 助手。

手机端核心页面：

- `/entry`：手机端首页。
- `/entry/fill`：统一填报。
- `/entry/consumables`：辅材填报。
- `/entry/report/:businessDate/:shiftId`：快速填报。
- `/entry/coil/:businessDate/:shiftId`：按卷录入。
- `/entry/ocr/:businessDate/:shiftId`：OCR 录入。
- `/entry/attendance`：异常补录。
- `/entry/history`：历史记录。
- `/entry/drafts`：草稿箱。

前端 API 文件包括：

- `auth.js`
- `dashboard.js`
- `factory-command.js`
- `mobile.js`
- `mes.js`
- `realtime.js`
- `energy.js`
- `production.js`
- `master.js`
- `users.js`
- `reports.js`
- `attendance.js`
- `quality.js`
- `reconciliation.js`
- `ai-assistant.js`
- `assistant.js`
- `agent-management.js`
- `dingtalk.js`
- `executive.js`
- `consumables.js`
- `telemetry.js`
- `user-preferences.js`

## 6. 数据库模型覆盖面

本地模型定义确认共有 90 张表。

云端生产库按模型表只读统计，也确认有 90 张表可访问。

这说明：

- 代码模型和生产库主体结构是对齐的。
- 当前不是“代码里有模型但生产库完全缺表”的状态。
- 但字段级口径仍需要按具体页面继续查，不应只凭表存在判断业务正确。

## 7. 生产库关键数据量

云端只读统计显示，当前真实数据不是空库。

与生产/MES/填报最相关的数据量：

- `mes_coil_snapshots`：1395 条。
- `mes_workshop_process_records`：2066 条。
- `mes_stock_records`：1498 条。
- `mes_material_records`：268 条。
- `mes_yield_records`：329 条。
- `mes_machine_line_snapshots`：100 条。
- `mes_reference_items`：452 条。
- `mes_daily_wip_snapshots`：120 条。
- `work_orders`：2037 条。
- `work_order_entries`：2761 条。
- `mobile_shift_reports`：189 条。
- `machine_energy_records`：27 条。
- `energy_import_records`：337 条。
- `daily_consumable_logs`：1 条。
- `shift_production_data`：91 条。
- `realtime_events`：11950 条。
- `mobile_reminder_records`：4346 条。
- `audit_logs`：3943 条。
- `users`：112 条。
- `equipment`：185 条。
- `workshops`：25 条。

业务含义：

- MES 投影表已经有较多数据，适合继续作为前端生产主数据的核心来源。
- 人工填报表也有数据，但相对 MES 规模更小，适合做补录、对照、异常说明。
- 能耗机台记录有 27 条，仍需继续盯住能耗链路是否足以支撑报表。
- `workshops` 有 25 条，但业务活跃生产车间口径是 13 个，所以页面筛选必须走活跃车间规则，不能直接把数据库全部车间都展示出来。

## 8. 外部连接状态

线上 `/readyz` 当前状态：

- 总状态：`ready`
- 数据库：`ok`
- 上传目录：`ok`
- 设备绑定：`ok`
- 排班：`ok`
- 日报流水线：`ok`
- MES 同步：`ok`
- IoT 能耗同步：`unconfigured`

MES 状态：

- 适配器：`sqlserver`
- 来源：`mes_projection`
- 状态：`fresh`
- 最近同步状态：`success`
- `sync_freshness_seconds` 约 1 到 2 秒级。

生产环境配置边界：

- `APP_ENV=production`
- `MES_ADAPTER=sqlserver`
- `MES_SQLSERVER_HOST=47.92.251.37`
- `MES_SQLSERVER_DATABASE=XTAL`
- `MES_SQLSERVER_USERNAME=screen`
- `DINGTALK_ENABLED=true`
- `WORKFLOW_ENABLED=true`
- `LLM_ENABLED=true`
- `IOT_ENERGY_ADAPTER` 未配置。

说明：

- MES 直连 SQL Server 当前已经是线上主链路。
- 物联网能耗数据库尚未接入，所以 `iot_energy_sync=unconfigured` 是预期状态。
- 钉钉、工作流、LLM 已在生产配置中启用，但是否所有实际推送流程都闭环，还需要继续按真实人员和群测试。

## 9. 管理员登录问题的系统理解

本轮前置修复确认了一个重要运维风险：

旧逻辑中，已有 `admin` 用户如果输入云端 `INIT_ADMIN_PASSWORD`，后端会把数据库里的 admin 密码覆盖回初始化密码。

这会造成用户感知上的“密码突然变了”。

当前已修复：

- 已有 admin 用户只能用数据库里的真实密码登录。
- 初始化密码只用于 admin 不存在时创建初始账号。
- 真正要重置 admin 密码，必须显式运行重置脚本或部署脚本传入 `ADMIN_LOGIN_PASSWORD`。

当前线上验证：

- `admin` 管理员账号登录成功；文档不保存明文密码。
- 云端初始化密码登录失败，不再覆盖真实密码。

## 10. 页面、API、表之间的主链路

可以把当前系统理解成这几条主链路：

### 10.1 管理端大屏链路

`/manage/live`

前端：

- `frontend/src/views/manage/live/LiveDashboardPage.vue`
- `frontend/src/api/realtime.js`

后端：

- `/api/v1/aggregation/live`
- `/api/v1/aggregation/live/detail`
- `/api/v1/aggregation/live/fill-details`
- `/api/v1/aggregation/live/missing-report-export`
- `/api/v1/realtime/stream`

主要数据：

- `realtime_events`
- `mes_*` 投影表
- `mobile_shift_reports`
- `work_order_entries`
- `machine_energy_records`

### 10.2 日报和生产分析链路

`/manage/today`、`/manage/production`

前端：

- `frontend/src/views/manage/TodayPage.vue`
- `frontend/src/views/manage/ProductionPage.vue`
- `frontend/src/composables/useDashboardSnapshot.js`
- `frontend/src/api/dashboard.js`
- `frontend/src/api/factory-command.js`

后端：

- `/api/v1/dashboard/factory-director`
- `/api/v1/dashboard/daily-production`
- `/api/v1/factory-command/overview`

主要数据：

- `mes_stock_records`
- `mes_workshop_process_records`
- `mes_daily_wip_snapshots`
- `mobile_shift_reports`
- `daily_consumable_logs`
- `machine_energy_records`
- `daily_reports`

### 10.3 卷级线索链路

`/manage/coils`

前端：

- `frontend/src/views/manage/coils/CoilTracePage.vue`
- `frontend/src/api/factory-command.js`

后端：

- `/api/v1/factory-command/coils`
- `/api/v1/factory-command/coils/{coil_key}/flow`
- `/api/v1/mes/extended/*`

主要数据：

- `mes_coil_snapshots`
- `coil_flow_events`
- `mes_workshop_process_records`
- `mes_material_records`
- `work_orders`
- `work_order_entries`

### 10.4 手机填报链路

`/entry/fill`、`/entry/report/*`、`/entry/coil/*`、`/entry/history`

前端：

- `frontend/src/views/mobile/UnifiedEntryForm.vue`
- `frontend/src/views/mobile/ShiftReportForm.vue`
- `frontend/src/views/mobile/CoilEntryWorkbench.vue`
- `frontend/src/views/mobile/ShiftReportHistory.vue`
- `frontend/src/api/mobile.js`

后端：

- `/api/v1/mobile/bootstrap`
- `/api/v1/mobile/current-shift`
- `/api/v1/mobile/report/save`
- `/api/v1/mobile/report/submit`
- `/api/v1/mobile/report/history`
- `/api/v1/mobile/coil-entry`
- `/api/v1/mobile/owner-daily`
- `/api/v1/work-orders/*`

主要数据：

- `mobile_shift_reports`
- `work_orders`
- `work_order_entries`
- `machine_energy_records`
- `daily_consumable_logs`
- `quality_issue_log`

### 10.5 主数据和配置链路

`/manage/admin/settings`、`/manage/admin/users`、`/manage/master`、`/manage/alias`、`/manage/mes-terminal-bindings`

前端：

- `frontend/src/views/manage/admin/SystemSettingsPage.vue`
- `frontend/src/views/manage/admin/UserManagement.vue`
- `frontend/src/views/admin/Workshop.vue`
- `frontend/src/views/admin/AliasMapping.vue`
- `frontend/src/views/admin/MesTerminalBinding.vue`

后端：

- `/api/v1/master/*`
- `/api/v1/users/*`
- `/api/v1/rule-configs`

主要数据：

- `users`
- `workshops`
- `teams`
- `equipment`
- `master_code_aliases`
- `mes_terminal_bindings`
- `rule_configs`
- `workshop_template_configs`

## 11. 当前仍需继续 QA 的范围

这轮还不能宣称“每一个功能、每一个角色都体验完成”。

后续需要继续逐项 QA：

- 管理员：所有管理端主页面、配置、用户、主数据、规则、导出。
- 车间主任：只能看本车间看板，不能看其他车间。
- 主操：扫码进入、填报、按卷补录、历史查询。
- 电工：能耗填报、历史查询、管理端能耗映射。
- 内勤/成品库：日报补录、包装入库/成品库口径。
- 铸锭、铸二、铸三、热轧、淬火车间：无一体机补录流程。
- AI 助手：问答、简报、关注项、治理审批。
- 钉钉：登录、主动汇报、指定人员审核、失败留痕。
- 导出：缺报 Excel、日报、能耗、库存/合同导出。

## 12. 本轮结论

当前系统不是空壳，云端已经有真实 MES、填报、工单、实时事件和审计数据。

最关键的系统边界已经更清楚：

- MES SQL Server 是外部只读源。
- 本系统管理端读本地 `mes_*` 投影表，不直接读外部 MES。
- 人工填报数据应作为补录和异常审核，不能和 MES 主数据混成一个来源。
- 13 个活跃生产车间规则必须覆盖前端筛选、后端接口和统计口径。
- 管理员密码不会再被初始化密码自动覆盖，这是运维安全上的一个重要修复。

下一步建议：

1. 用户确认 `.understandignore` 后，重建 understand 图谱。
2. 用真实角色账号逐页 QA。
3. 重点核对 MES 主数据如何逐步替代内勤统计岗。
4. 继续补齐物联网能耗库接入后的能耗链路。

## 13. 追加复核：健康检查、部署和外部访问边界

时间：2026-06-14 13:40

本轮继续按只读方式复核运行链路，重点回答“页面能打开但登录提示连接失败时，应该先查哪里”。

### 13.1 后端健康检查分层

后端在 `backend/app/main.py` 同时提供四个健康入口：

- `/healthz`
- `/api/v1/healthz`
- `/readyz`
- `/api/v1/readyz`

通俗理解：

- `healthz` 只回答“程序还活着吗”，主要检查应用本身。
- `readyz` 回答“系统能不能进入主业务链路”，会额外检查数据库、上传目录、日报流水线门禁、MES 同步状态和物联网能耗同步状态。

代码证据：

- `backend/app/main.py` 注册顶层和 `/api/v1` 两套健康路由。
- `backend/app/core/health.py` 的 `build_liveness_payload()` 只返回 `app=ok`。
- `backend/app/core/health.py` 的 `build_readiness_payload()` 会检查 database、uploads、pipeline、mes_sync、iot_energy_sync。

### 13.2 readyz 不等于所有外部系统都已正式接入

当前代码语义中，外部数据源异常不一定会把整个应用判成不可用：

- MES 未配置、迁移缺失、同步 stale 或同步失败，会反映到 `checks.mes_sync` 和 `details.mes_sync`，但应用仍可能返回 `status=ready`。
- 物联网能耗未配置会显示 `iot_energy_sync=unconfigured`，这是“尚未接入”的状态，不等于后端程序坏了。
- 真正阻断 `readyz` 的是数据库、上传目录或自动日报硬门禁失败。

这套设计的好处是：外部系统短暂异常时，管理端和手机填报端不至于整站不可用；坏处是排查时不能只看 HTTP 200，要继续看 `checks` 和 `details`。

### 13.3 前端 API 访问路径

前端统一 API 客户端在 `frontend/src/api/index.js`：

- 默认 `VITE_API_BASE_URL=/api/v1`
- 生产前端会用同域相对路径请求 `/api/v1/...`
- 请求超时文案是“请求超时，服务器响应太慢，请稍后重试”
- 真正没连到后端时，文案是“连接服务器失败，请检查网络、代理或稍后重试”

因此，用户看到“连接服务器失败”时，含义通常是：浏览器请求没有拿到后端响应。它和“账号或密码不正确”不是一类问题。

### 13.4 Nginx 和部署脚本链路

生产 Nginx 配置在 `nginx/nginx.conf`：

- `/api/` 代理到后端 `http://backend:8000/api/`
- `/healthz` 代理到后端 `/healthz`
- `/readyz` 代理到后端 `/readyz`
- `/api/v1/realtime/stream` 单独关闭缓冲，支持实时流
- 其他页面路径走前端 `index.html`

systemd 部署脚本在 `scripts/deploy_systemd_host.sh`：

- 先备份数据库并校验备份。
- 执行后端迁移和主数据初始化。
- 默认不重置管理员密码；只有传入 `ADMIN_LOGIN_PASSWORD` 时才显式重置。
- 前端构建时默认写入 `VITE_API_BASE_URL=/api/v1`。
- 重启服务后等待 `/readyz` 返回 HTTP 200 且 `hard_gate_passed=true`。

### 13.5 线上只读探测结果

本轮只读探测结果：

- `https://xtmijd.com/api/v1/healthz`：HTTP 200。
- `https://xtmijd.com/api/v1/readyz`：HTTP 200，`status=ready`。
- `https://xtmijd.com/healthz`：HTTP 200。
- `https://xtmijd.com/readyz`：HTTP 200，`status=ready`。
- `https://www.xtmijd.com/api/v1/healthz`：连接失败。

结论：

- 当前无 `www` 的正式域名健康检查正常。
- 带 `www` 的域名不可作为登录入口。
- 如果用户从 `www.xtmijd.com`、代理环境、旧缓存或错误收藏入口进入，前端可能显示“连接服务器失败”。

### 13.6 本轮验证命令结果

- `python -m pytest -q backend/tests/test_health.py backend/tests/test_nginx_https_config.py`：`17 passed`。
- `npm test --prefix frontend -- --run frontend/tests/apiErrorMessages.test.js frontend/tests/manageRouteRedirects.test.js`：实际触发当前前端测试集，`666 passed`。

边界说明：

- 本轮没有登录后逐按钮做全站浏览器 QA。
- 本轮没有修改生产配置、Nginx、DNS 或数据库。
- 本轮只证明健康检查、Nginx 配置断言、前端错误文案和当前无 `www` 域名可达性，不代表所有外部服务业务动作都完成实测。
