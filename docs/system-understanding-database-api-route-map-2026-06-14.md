# 数据库、后端接口、前端路由映射理解记录（2026-06-14）

## 本轮范围

本轮继续补齐 `鑫泰铝业 数据中枢` 的系统理解，只读检查当前代码和线上入口，不改业务代码，不改生产数据。

目标是用小白也能看懂的话讲清：

```text
用户点某个前端页面 -> 前端调用哪个接口 -> 后端服务读写哪些表 -> 页面最终显示什么。
```

## 当前结构总览

当前代码重新抽取结果：

| 项目 | 当前数量 | 证据来源 |
|---|---:|---|
| 后端 FastAPI 路由 | 246 | `backend/app/main.py` 加载后的 `app.routes` |
| SQLAlchemy 数据表 | 90 | `backend/app/models/base.py` 的 `Base.metadata.tables` |
| 前端 API 调用点 | 166 | `frontend/src/api/*.js` 静态抽取 |
| 前端路由字面量 | 147 | `frontend/src/router/index.js` 静态抽取 |
| 前端重定向规则 | 103 | `frontend/src/router/index.js` 静态抽取 |

简单理解：

```text
后端是 FastAPI；
数据库表由 SQLAlchemy 模型定义；
前端是 Vue；
页面路由集中在 frontend/src/router/index.js；
前端请求统一从 frontend/src/api/*.js 发到 /api/v1/*。
```

## 后端入口和接口分组

后端主入口：

```text
backend/app/main.py
```

它负责：

- 创建 FastAPI 应用。
- 注册跨域、异常处理、上传目录。
- 注册全部业务路由。
- 启动定时任务，比如日报汇总、提醒、AI 简报、成本快照。
- 提供 `/healthz`、`/readyz` 和 `/api/v1/healthz`、`/api/v1/readyz`。

接口数量较多的分组：

| 接口分组 | 数量 | 主要用途 |
|---|---:|---|
| `master` | 35 | 车间、机列、班次、别名、MES 终端绑定 |
| `ai` | 21 | AI 助手、会话、简报、关注项 |
| `mobile` | 19 | 手机填报、班次、历史、补录、扫码辅助 |
| `attendance` | 15 | 考勤导入、统计、异常、审核 |
| `executive` | 12 | 经营成本、加工费、铝价、利润快照 |
| `dashboard` | 11 | 今日/日报/统计/管理看板 |
| `mes` | 11 | MES 同步状态、扩展数据、补录准备 |
| `aggregation` | 10 | 实时大屏、填报明细、缺报、异常 |
| `reports` | 9 | 日报生成、审核、发布、导出 |
| `production` | 8 | 旧生产班次数据、异常、审核 |
| `factory-command` | 7 | 调度、卷级线索、车间/机列/库存去向 |
| `users` | 7 | 用户管理、重置密码、钉钉同步 |
| `work-orders` | 7 | 随行卡补录、工单和补录内容 |

## 数据库表按业务分组

### 主数据和权限

| 表 | 作用 |
|---|---|
| `users` | 登录账号、角色、权限范围 |
| `workshops` | 车间 |
| `equipment` | 机列、二维码、绑定账号 |
| `teams` | 班组 |
| `employees` | 员工 |
| `shift_configs` | 班次配置 |
| `master_code_aliases` | 别名映射 |
| `mes_terminal_bindings` | MES 终端 / PC / 机列绑定 |
| `audit_logs` | 操作审计 |

这组表决定：

```text
谁能登录、能看到哪个页面、哪个机列属于哪个车间、MES 设备名怎样映射到真实机列。
```

### 手机填报和人工补录

| 表 | 作用 |
|---|---|
| `mobile_shift_reports` | 主操等班次填报 |
| `machine_energy_records` | 电工能耗填报 |
| `work_orders` | 随行卡补录主记录 |
| `work_order_entries` | 补录字段明细、内勤每日一录 |
| `daily_consumable_logs` | 内勤辅材/专项每日记录 |
| `field_amendments` | 字段修正审核 |
| `mobile_reminder_records` | 缺报提醒 |

这组表决定：

```text
手机端填了什么、谁填的、什么时候填的、是否补录、是否审核。
```

### MES 本地投影

| 表 | 作用 |
|---|---|
| `mes_coil_snapshots` | 每卷当前状态 |
| `mes_workshop_process_records` | 工序过站记录 |
| `mes_stock_records` | 包装/入库记录 |
| `mes_material_records` | 坯料/投料记录 |
| `mes_yield_records` | 成品率相关记录 |
| `mes_wip_total_snapshots` | 当前在制汇总 |
| `mes_daily_wip_snapshots` | 每日留档在制 |
| `mes_reference_items` | MES 字典和参考项 |
| `mes_machine_line_snapshots` | MES 设备/机列线索 |
| `coil_flow_events` | 卷流转事件 |
| `mes_sync_cursors` | MES 同步游标 |
| `mes_sync_run_logs` | MES 同步运行日志 |

这组表决定：

```text
MES 抓来的卷、工序、包装、入库、在制数据怎样成为管理端主数据。
```

### 报表、异常和质量

| 表 | 作用 |
|---|---|
| `daily_reports` | 日报发布记录 |
| `production_exceptions` | 生产异常 |
| `data_quality_issues` | 数据质量问题 |
| `data_reconciliation_items` | 数据核对差异 |
| `quality_yield_daily` | 质量/成品率日报 |
| `quality_issue_log` | 质量问题日志 |

这组表决定：

```text
日报、异常、数据冲突和质量问题如何被记录、审核、发布。
```

### 能耗和经营成本

| 表 | 作用 |
|---|---|
| `energy_import_records` | 老能耗导入记录 |
| `iot_energy_snapshots` | 物联网能耗快照 |
| `iot_energy_sync_runs` | 物联网能耗同步运行日志 |
| `machine_energy_daily_compare` | 机列能耗对照 |
| `aluminum_price_daily` | 铝价 |
| `processing_fee_rules` | 加工费规则 |
| `cost_daily_result` | 日成本结果 |
| `machine_daily_cost_snapshots` | 机列日成本快照 |
| `machine_daily_profit_snapshots` | 机列日利润快照 |

这组表决定：

```text
吨电耗、吨气耗、成本、利润、加工费和铝价怎样计算。
```

### AI 和外部通讯

| 表 | 作用 |
|---|---|
| `ai_conversations` | AI 会话 |
| `ai_messages` | AI 消息 |
| `ai_briefing_events` | AI 简报 |
| `ai_watchlist_items` | AI 关注项 |
| `agent_profiles` | 多 Agent 配置 |
| `communication_channels` | 通讯渠道 |
| `agent_outbox_messages` | 待发送消息 |
| `external_message_logs` | 外部消息日志 |
| `multimodal_evidence` | 多模态证据 |
| `agent_operation_approvals` | Agent 操作审批 |

这组表决定：

```text
AI 助手、主动汇报、钉钉/外部通讯、审批留痕如何运行。
```

## 核心前端页面到接口和表的映射

### `/manage/live`：生产实时大屏

| 层级 | 位置 |
|---|---|
| 前端页面 | `frontend/src/views/manage/live/LiveDashboardPage.vue` |
| 前端 API | `frontend/src/api/realtime.js` |
| 后端接口 | `/api/v1/aggregation/live`、`/api/v1/realtime/stream` |
| 后端服务 | `backend/app/services/realtime_service.py` |
| 主要表 | `mes_*`、`work_order_entries`、`mobile_shift_reports`、`machine_energy_records`、`equipment`、`workshops` |

页面定位：

```text
实时看全厂生产流转、机列状态、MES 包装产量、内勤入库对照、缺报和异常。
```

### `/manage/today`：昨日日报

| 层级 | 位置 |
|---|---|
| 前端页面 | `frontend/src/views/manage/today/TodayPage.vue` |
| 前端组合器 | `frontend/src/composables/useDashboardSnapshot.js` |
| 后端接口 | `/api/v1/dashboard/daily-production`、`/api/v1/dashboard/factory-director`、`/api/v1/factory-command/overview` |
| 后端服务 | `backend/app/services/report/daily_overview_builder.py` |
| 主要表 | `mes_stock_records`、`mes_workshop_process_records`、`work_order_entries`、`machine_energy_records`、`daily_reports` |

页面定位：

```text
看上一业务日的包装产量、全厂入库对照、成品率、能耗、合同和缺报。
```

### `/manage/production`：生产分析

| 层级 | 位置 |
|---|---|
| 前端页面 | `frontend/src/views/manage/production/ProductionPage.vue` |
| 前端组合器 | `frontend/src/composables/useDashboardSnapshot.js` |
| 后端接口 | `/api/v1/dashboard/daily-production`、`/api/v1/factory-command/overview` |
| 主要表 | `mes_stock_records`、`mes_workshop_process_records`、`mes_wip_total_snapshots`、`mobile_shift_reports` |

页面定位：

```text
分析产量构成、车间排行、在制、成品率、吨耗。这里必须区分包装产量和工序过站量。
```

### `/manage/coils`：卷级线索

| 层级 | 位置 |
|---|---|
| 前端页面 | `frontend/src/views/manage/coils/CoilTracePage.vue` |
| 前端 API | `frontend/src/api/factory-command.js` |
| 后端接口 | `/api/v1/factory-command/coils`、`/api/v1/factory-command/coils/{coil_key}/flow` |
| 后端服务 | `backend/app/services/factory_command_service.py` |
| 主要表 | `mes_coil_snapshots`、`mes_workshop_process_records`、`coil_flow_events`、`mes_terminal_bindings` |

页面定位：

```text
按卷查看随行卡、客户、合金、规格、当前工艺、当前车间、机列匹配和补录状态。
```

### `/manage/fill-details`：填报明细

| 层级 | 位置 |
|---|---|
| 前端页面 | `frontend/src/views/manage/fill-details/FillDetailsPage.vue` |
| 前端 API | `frontend/src/api/realtime.js` |
| 后端接口 | `/api/v1/aggregation/live/fill-details`、`/api/v1/aggregation/live/mes-fill-gaps` |
| 主要表 | `work_order_entries`、`mobile_shift_reports`、`machine_energy_records`、`users`、`equipment` |

页面定位：

```text
只看人工填报和补录，不把 MES 自动投影混进“谁填了什么”的明细。
```

### `/entry/*`：手机填报端

| 层级 | 位置 |
|---|---|
| 前端页面 | `frontend/src/views/mobile/*`、`frontend/src/views/entry/*` |
| 前端 API | `frontend/src/api/mobile.js` |
| 后端接口 | `/api/v1/mobile/*`、`/api/v1/work-orders/*`、`/api/v1/ocr/*` |
| 主要表 | `mobile_shift_reports`、`work_orders`、`work_order_entries`、`machine_energy_records`、`daily_consumable_logs` |

页面定位：

```text
主操、电工、内勤等现场角色扫码或登录后填报、补录、查历史。
```

### `/manage/admin/settings` 和 `/manage/admin/users`

| 页面 | 主要接口 | 主要表 |
|---|---|---|
| 系统设置 | `/api/v1/admin/*`、`/api/v1/master/*`、`/api/v1/mes/*` | `system_configs`、`workshops`、`equipment`、`master_code_aliases`、`mes_terminal_bindings` |
| 用户管理 | `/api/v1/users/*` | `users`、`equipment`、`workshops`、`teams` |

页面定位：

```text
配置账号、车间、机列、别名、MES 终端绑定和系统状态。
```

## 前端路由现状

前端路由集中在：

```text
frontend/src/router/index.js
```

核心分区：

| 分区 | 路径 | 用途 |
|---|---|---|
| 登录 | `/login` | 管理端账号密码登录、钉钉登录、二维码入口识别 |
| 手机端 | `/entry/*` | 填报、历史、草稿、OCR、考勤补录 |
| 管理端 | `/manage/*` | 日报、实时、生产、卷级、异常、能耗、设置 |
| 旧管理入口 | `/admin/*`、`/review/*`、`/master/*` | 多数重定向到新 `/manage/*` |
| 旧移动入口 | `/mobile/*`、`/worker`、`/team-lead/*` | 重定向到 `/entry/*` |

当前 `frontend/src/router/index.js` 里有大量重定向，说明系统仍要兼容旧二维码、旧收藏链接、旧菜单路径。后续清理旧页面时不能只看页面是否好看，要先查有没有旧入口依赖。

## 当前已确认断点

### 断点：前端残留 `/auth/workshop-quick-entry`

证据：

```text
frontend/src/api/auth.js
frontend/src/stores/auth.js
```

仍有：

```text
POST /auth/workshop-quick-entry
```

但当前后端 246 个路由中没有：

```text
/api/v1/auth/workshop-quick-entry
```

影响：

```text
如果某个旧页面或旧逻辑调用 workshopQuickEntry，会请求不存在的后端接口。
```

当前判断：

```text
这是一个待清理或待补兼容的断点。本轮只记录，不直接删除，因为还需要确认是否有旧二维码或旧入口依赖。
```

## 本轮线上只读验证

本轮做了只读接口和页面入口验证。

接口验证结果：

| 接口 | 状态 |
|---|---:|
| `/api/v1/auth/me` | 200 |
| `/api/v1/dashboard/daily-production` | 200 |
| `/api/v1/aggregation/live/active-date` | 200 |
| `/api/v1/mes/sync-status` | 200 |
| `/api/v1/factory-command/overview` | 200 |
| `/api/v1/users/?limit=1` | 200 |
| `/api/v1/master/workshops?limit=5` | 200 |

页面入口验证结果：

| 页面 | 状态 |
|---|---:|
| `/login` | 200 |
| `/manage/today` | 200 |
| `/manage/live` | 200 |
| `/manage/production` | 200 |
| `/manage/coils` | 200 |
| `/entry` | 200 |
| `/manage/admin/settings` | 200 |

注意：

```text
这只是入口可访问和接口可返回的只读验证，不等于逐按钮、逐筛选、逐角色完整 QA。
```

## 后续理解优先级

建议后续继续补三张图：

1. `角色 -> 路由权限 -> 可见页面 -> 可调用接口`。
2. `移动端填报字段 -> 后端接口 -> 数据库字段 -> 管理端展示字段`。
3. `外部通讯/钉钉/AI Agent -> 数据库留痕 -> 审批治理 -> 主动汇报`。

这三张图补齐后，系统“谁能做什么、数据去哪儿、页面为什么这么显示”的底座就会更稳。
