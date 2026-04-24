# API 体系分层规范（Lane 2: api-system）

> 目标：把 `aluminum-bypass` 当前后端路由/服务，收敛为“长期 AI 产品体系”下可继续施工的 API 分层规范。
> 
> brownfield 证据来源：`backend/app/main.py`、`backend/app/routers/*.py`、`backend/app/services/mobile_report_service.py`、`report_service.py`、`attendance_confirm_service.py`、`production_service.py`、`mobile_reminder_service.py`、`config_readiness_service.py`、`pilot_metrics_service.py`、`pilot_observability_service.py`、`backend/app/core/health.py`、`workflow_dispatcher.py`。

## 1. 现状结论

当前 API 已经自然分成 4 个正式层，再加 1 个横切访问层：

1. **身份与权限横切层**
   - 入口：`/api/v1/auth/*`、`/api/v1/wecom/*`
   - 约束：`backend/app/core/permissions.py`
   - 作用：不承载业务事实，只负责“谁能进、能看什么、能改什么”。

2. **生产主流程 API**
   - 当前核心：`/api/v1/mobile/*`、`/api/v1/attendance/*`、`/api/v1/work-orders/*`
   - 特征：面向工人/班长/现场设备，写入一手业务事实，再由 Agent/服务自动联动。

3. **观察与驾驶舱 API**
   - 当前核心：`/api/v1/dashboard/*`、`/api/v1/reports` 读接口、`/api/v1/realtime/*`
   - 特征：只读聚合、领导视图、现场观察，不应反向变成主流程写入口。

4. **管理与主数据 API**
   - 当前核心：`/api/v1/master/*`、`/api/v1/users/*`、`/api/v1/imports/*`、`/api/v1/mes/*`、`/api/v1/energy/*`、`/api/v1/reconciliation/*`、`/api/v1/quality/*`
   - 特征：配置、导入、修正、治理、异常闭环，不直接替代一线填报主链路。

5. **readiness / health / observability API**
   - 当前核心：顶层 `/healthz`、`/readyz`
   - 辅助能力：`config_readiness_service.py`、`pilot_metrics_service.py`、`pilot_observability_service.py`
   - 特征：服务是否可运行、可试点、可继续放量；它们是“系统面”，不是业务面。

**API 总原则**：
- 工人/班长写事实；Agent 做校验/汇总/推送；管理者主要读聚合结果；管理员负责配置与兜底。
- 旧 reviewer / reviewed / confirmed_only / include_reviewed 语义只允许留在兼容层，不再定义为长期主口径。
- `event_bus` / `workflow_dispatcher` / agents 是**内部自动化边界**，不是对前端或第三方直接开放的公共写 API。

## 2. 正式 API 分层

### 2.1 横切层：身份、权限、入口

**正式职责**
- 统一用户/设备/企业微信进入系统。
- 统一作用域校验，而不是在业务路由里散落判断。

**当前证据**
- `backend/app/routers/auth.py`：账号登录、扫码登录、`/me`
- `backend/app/routers/dingtalk.py`：当前默认身份入口
- `backend/app/routers/wecom.py`：企业微信兼容登录、JS-SDK 签名
- `backend/app/core/permissions.py`：mobile / reviewer / manager / admin 几类作用域入口

**规范定义**
- 身份入口保留多通道：账号密码、扫码机台、钉钉优先，企业微信兼容保留。
- 权限判断必须下沉到 `core/permissions.py` 这一类横切层，不允许业务服务各写一套。
- 钉钉/企业微信登录都属于“身份入口”，不是管理 API，也不是生产主流程 API。

### 2.2 L1：生产主流程 API（正式主口径）

**正式职责**
- 接收一手业务输入。
- 允许“保存、提交、补正、异常回退再提交”。
- 写入后由系统自动校验、自动同步、自动汇总，不引入人工审核中继岗位。

**当前 canonical 入口**
- `mobile.py`
  - `/api/v1/mobile/bootstrap`
  - `/api/v1/mobile/current-shift`
  - `/api/v1/mobile/report/{business_date}/{shift_id}`
  - `/api/v1/mobile/report/save`
  - `/api/v1/mobile/report/submit`
  - `/api/v1/mobile/report/upload-photo`
- `attendance.py`
  - `/api/v1/attendance/draft`
  - `/api/v1/attendance/confirm`
  - `/api/v1/attendance/anomalies`
  - `/api/v1/attendance/summary`
- `work_orders.py`
  - `/api/v1/work-orders/*`
  - `/api/v1/work-orders/{id}/entries`
  - `/api/v1/work-orders/entries/{id}/submit`

**正式边界**
- 主流程只写“原始事实对象”：班次填报、考勤确认、工单条目。
- 主流程不能让管理者用 dashboard/report API 反向补录生产事实。
- 主流程提交后，自动化链路由内部服务承担：
  - `mobile_report_service.save_or_submit_report()` -> `_sync_to_shift_production()` -> `validator_agent.execute()`
  - `attendance_confirm_service.submit_confirmation()` -> `event_bus.publish('attendance_confirmed', ...)`
  - `work_order_service.submit_entry()` -> `event_bus.publish('entry_submitted', ...)`

### 2.3 L2：观察与驾驶舱 API（正式读面）

**正式职责**
- 聚合主流程结果给班长、车间主任、厂长、管理层。
- 只读、限流、按 scope 读。
- 可以暴露异常、上报率、可交付状态，但不能反向承接主流程编辑。

**当前 canonical 入口**
- `dashboard.py`
  - `/api/v1/dashboard/factory-director`
  - `/api/v1/dashboard/workshop-director`
  - `/api/v1/dashboard/statistics`
  - `/api/v1/dashboard/delivery-status`
- `reports.py`
  - `GET /api/v1/reports`
  - `GET /api/v1/reports/{report_id}`
  - `GET /api/v1/reports/{report_id}/export`
- `realtime.py`
  - `/api/v1/realtime/stream`
  - `/api/v1/aggregation/live`
  - `/api/v1/aggregation/live/detail`

**正式边界**
- Dashboard / report 默认是读模型，不是状态推进器。
- 领导口径统一读取 canonical 主链路结果：`report_service` 已把 `generated_scope` 统一收敛到 `auto_confirmed`。
- `delivery-status` 属于“业务交付观察面”，不是系统 readiness probe。

### 2.4 L3：管理与主数据 API（正式治理面）

**正式职责**
- 维护主数据、账号、模板、设备、班次、导入、核对、质量治理。
- 负责修配置、修映射、做例外处理，但不替代工人/班长主流程。

**当前 canonical 入口**
- `master.py`：workshops / teams / employees / equipment / shift-configs / aliases / workshop-templates
- `users.py`：用户 CRUD、重置密码
- `imports.py`、`mes.py`、`energy.py`：导入/集成入口
- `reconciliation.py`：核对项生成与处理
- `quality.py`：质量问题运行、忽略、关闭

**正式边界**
- 管理面写的是“配置事实”和“治理状态”，不是“生产事实”。
- 例如：设备绑定、账号归属、班次配置是管理面；班次产量提交不是管理面。
- 管理面接口原则上要求 admin / reviewer / ops 身份，不直接给普通移动用户暴露。

### 2.5 L4：readiness / health / observability API（正式系统面）

**正式职责**
- 给负载均衡、运维、试点负责人回答三件事：
  1. 服务活没活着
  2. 当前是否 ready
  3. 为什么不 ready / 运行质量怎么样

**当前证据**
- `backend/app/main.py`
  - `/health`
  - `/healthz`
  - `/readyz`
- `backend/app/core/health.py`
  - `build_liveness_payload()`
  - `build_readiness_payload()`
  - `inspect_pipeline_readiness()`
- `config_readiness_service.py`：主数据/排班/账号绑定 readiness
- `pilot_metrics_service.py`：试点复盘指标
- `pilot_observability_service.py`：运行日志埋点

**正式放置规则**
- `/healthz`：平台级 liveness，保留在顶层，不放 `/api/v1/`。
- `/readyz`：平台级 readiness，保留在顶层，不放 `/api/v1/`。
- `pilot_metrics`、`dispatch history`、`异常复盘` 这类**给人看的运维观察接口**，长期应放到**认证后的 `/api/v1/system/*` 或 `/api/v1/ops/*`**，不要塞进 dashboard，也不要混进 `/readyz`。
- `readyz` 只回答“是否可继续进入主链路/调度”，不能变成大而全的管理报表。

## 3. 对象体系与读写归属

| 对象 | 当前系统主存储/服务 | canonical 写入口 | canonical 读入口 | 说明 |
| --- | --- | --- | --- | --- |
| User / Session | `auth.py`、`dingtalk.py`、`wecom.py`、`users.py` | `/api/v1/auth/*`、`/api/v1/dingtalk/login`、`/api/v1/users/*` | `/api/v1/auth/me` | 身份对象，不承载业务产量事实 |
| Workshop / Team / Equipment / ShiftConfig | `master.py`、`equipment_service.py` | `/api/v1/master/*` | `/api/v1/master/*`、bootstrap | 主数据对象 |
| AttendanceSchedule | `attendance.py`、`config_readiness_service.py` | 导入/排班导入 | attendance read / readyz | 应报清单基础对象 |
| MobileShiftReport | `mobile_report_service.py` | `/api/v1/mobile/report/save|submit|upload-photo` | mobile detail/history、dashboard 汇总 | 现场主填报对象 |
| ShiftProductionData | `_sync_to_shift_production()`、`production_service.py` | 不直接给领导端写；由 mobile / import / ops 例外入口写入 | dashboard / reports / production read | 生产聚合事实对象 |
| ShiftAttendanceConfirmation | `attendance_confirm_service.py` | `/api/v1/attendance/confirm` | `/api/v1/attendance/*` | 考勤确认对象 |
| WorkOrder / WorkOrderEntry | `work_order_service.py` | `/api/v1/work-orders/*` | `/api/v1/work-orders/*` | 跟踪卡/工单链路对象 |
| MobileReminderRecord | `mobile_reminder_service.py` | 自动调度 + `/api/v1/mobile/reminders/run`（例外） | reminders list / exception lane | 提醒与闭环对象，不是主生产对象 |
| DailyReport | `report_service.py`、`aggregator.py` | 调度自动生成；手动 generate/publish 为兼容/运营入口 | `/api/v1/reports*`、dashboard | 领导视图对象 |
| DataReconciliationItem / DataQualityIssue | `reconciliation.py`、`quality.py` | 管理治理入口 | dashboard delivery / reports finalize | 治理对象 |
| RealtimeEvent / workflow_event | `event_bus.py`、`workflow_dispatcher.py` | 只能由内部服务发布 | realtime stream、未来 ops 观察接口 | 内部自动化对象，不直接开放外部写入 |
| Readiness Snapshot / Pilot Metrics | `health.py`、`config_readiness_service.py`、`pilot_metrics_service.py` | 只由系统计算 | `/readyz`、未来 `/api/v1/system/*` | 系统面对象 |

## 4. 读写边界规范

### 4.1 生产事实只允许从主流程进入
- `MobileShiftReport` 是现场一手录入对象。
- `ShiftProductionData` 是领导口径与驾驶舱口径的生产事实对象，但其正常来源应是：
  1. 移动填报同步
  2. 导入/MES
  3. 极少数管理例外修正
- Dashboard / Reports / Realtime 不得承担“补录生产事实”的职责。

### 4.2 观察层只读，不推进主状态
- `dashboard.py` 和 `realtime.py` 只能做读模型。
- `reports.py` 的列表、详情、导出是读模型；写动作只允许作为兼容或运营兜底入口存在。

### 4.3 管理层只能改配置/治理/例外，不重建人工审核主链
- `master.py`、`users.py`、`quality.py`、`reconciliation.py` 的写动作属于治理面。
- `production.py` 的 `review/confirm/reject/void` 不应再被定义为日常主链路，而应降级为兼容/异常处置面。
- `reports.py` 的 `review/publish/finalize/run-daily-pipeline` 同理：允许保留，但不应作为长期默认流程入口。

### 4.4 内部自动化边界必须内聚，不外露
- `event_bus.publish(...)`、`workflow_dispatcher`、agent 定时任务是服务内部联动面。
- 前端或第三方不得直接提交 workflow event。
- 如未来需要运维观察 dispatcher 状态，只开放只读 API，不开放手工篡改事件总线的公共接口。

## 5. canonical 与 compatibility surface 划分

### 5.1 canonical surface（长期保留并继续增强）

| 面 | canonical surface |
| --- | --- |
| 身份入口 | `/api/v1/auth/login`、`/api/v1/auth/me`、`/api/v1/auth/qr-login`、`/api/v1/dingtalk/login` |
| 主流程 | `/api/v1/mobile/report/save`、`/api/v1/mobile/report/submit`、`/api/v1/mobile/current-shift`、`/api/v1/attendance/confirm`、`/api/v1/work-orders/*` |
| 观察面 | `/api/v1/dashboard/factory-director`、`/api/v1/dashboard/workshop-director`、`/api/v1/dashboard/statistics`、`/api/v1/dashboard/delivery-status`、`GET /api/v1/reports*`、`/api/v1/realtime/stream` |
| 管理面 | `/api/v1/master/workshops|teams|employees|equipment|shift-configs|workshop-templates`、`/api/v1/users/*`、`/api/v1/imports/*`、`/api/v1/mes/import`、`/api/v1/reconciliation/*`、`/api/v1/quality/*` |
| 系统面 | `/healthz`、`/readyz` |

### 5.2 compatibility surface（保留但不再做主设计中心）

| 当前兼容面 | 证据 | 处理原则 |
| --- | --- | --- |
| `/api/v1/dashboard/factory`、`/api/v1/dashboard/workshop` | `dashboard.py` 中 alias 路由 | 只做别名兼容；文档与前端新调用统一到 `*-director` |
| `/api/v1/master/shifts` | `master.py` 中 `list_shifts_compat()` | 只读兼容；正式名统一 `shift-configs` |
| `confirmed_only` / `include_reviewed` 请求参数 | `schemas/reports.py` 仍允许；`report_service._normalize_scope()` 已统一到 `auto_confirmed` | 输入兼容保留，输出与存储统一 canonical `auto_confirmed` |
| `/api/v1/reports/{id}/review`、`/publish`、`/finalize`、`/run-daily-pipeline` | `reports.py` + `report_service.py` | 降级为运营/例外/灰度兜底入口，不再定义为默认日报主链 |
| `/api/v1/production/shift-data/{id}/review|confirm|reject|void` | `production.py` | 降级为例外处置面，不作为主流程日常入口 |
| `/health` | `main.py` | 视为简单兼容探活；正式平台探针统一 `healthz/readyz` |

### 5.3 当前最重要的兼容债务
- `aggregator.py` 仍以 `REPORT_SERVICE_SCOPE = "confirmed_only"` 调用 `_generate_production_report()`，但 `report_service` 内部已规范化到 `auto_confirmed`。这说明**服务层 canonical 已先行，调用面命名仍残留旧语义**。
- `schemas/reports.py` 的默认 `scope` 仍是 `confirmed_only` / `include_reviewed`，与长期 API 口径不一致。
- Dashboard 与 report 写接口仍保留 reviewer 思维入口，应继续从“主入口”降为“例外入口”。

## 6. readiness / health / observability 的正式放置

### 6.1 平台探针（对机器）
- `GET /healthz`
  - 只回答进程与基础活性。
  - 用于 nginx / LB / k8s / compose 级探活。
- `GET /readyz`
  - 只回答“此刻是否允许调度和放量”。
  - 当前已接入数据库、上传目录、`AUTO_PIPELINE_REQUIRE_READY`、`inspect_pilot_config()`。

### 6.2 运维观察面（对人）
长期应该新增认证后的统一入口，例如：
- `GET /api/v1/system/readiness`
- `GET /api/v1/system/pilot-metrics`
- `GET /api/v1/system/workflow-dispatch`
- `GET /api/v1/system/anomalies/summary`

**放置规则**
- 这类接口属于系统/运维面，不应放在 `dashboard/*`，否则业务驾驶舱和运维驾驶舱会混层。
- 这类接口也不应塞进 `/readyz`，否则 readiness probe 会变成人工诊断大杂烩。
- `pilot_observability_service.py` 当前只有日志埋点，没有 API；长期应由只读 ops API 暴露“摘要”，不要直接暴露原始日志流。

### 6.3 业务可交付状态（对管理者）
- `dashboard/delivery-status` 继续保留在业务观察层。
- 它回答的是“日报交付是否齐备”，不是“系统是否 ready”。
- 因此它与 `/readyz` 并列存在，而不是合并。

## 7. 下一阶段 API 施工顺序（只列 lane 相关）

1. **先收口文档与 OpenAPI 口径**
   - 把 canonical surface 与 compatibility surface 在接口文档中明确标识。
2. **再收口 scope 默认值**
   - 报表/日报相关 schema 默认值改为 `auto_confirmed`，兼容旧值但不再默认旧值。
3. **再把人工 review/publish 入口降级为 exception/ops 入口**
   - 文案、前端调用、权限都不再把它们当主链。
4. **最后新增认证后的 system/ops 观察 API**
   - 把 pilot metrics、dispatcher history、异常摘要从脚本/日志，提升为正式运维读面。

## 8. 本 lane 的定稿结论

`aluminum-bypass` 的长期 API 体系，不应再被理解成“若干 CRUD 路由集合”，而应被理解成：

- **横切身份层**：谁进入系统
- **生产主流程层**：谁写一手事实
- **观察驾驶舱层**：谁看结果与异常
- **管理治理层**：谁改配置与兜底
- **系统运维层**：系统是否 ready、为何不 ready、运行质量如何

其中长期主链路只有一条：

**工人/班长提交 -> 系统自动校验/同步 -> Agent 自动汇总/推送 -> 管理层观察**

所有 reviewer / reviewed / confirmed_only / 手工 publish 语义，都只允许作为 compatibility 或 exception surface 继续存在，不能再回到 API 体系中心。
