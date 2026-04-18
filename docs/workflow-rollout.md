# Workflow Rollout

## Step 1 - Runtime Skeleton (2026-04-04)

### Completed Items
- Added backend feature flags `WORKFLOW_ENABLED`, `WECOM_BOT_ENABLED`, and `WECOM_APP_ENABLED`, all defaulting to `false`.
- Added WeCom config placeholders for the first rollout skeleton: `WECOM_BOT_WEBHOOK_URL`, `WECOM_CORP_ID`, `WECOM_AGENT_ID`, and `WECOM_APP_SECRET`.
- Extended runtime validation so channel flags cannot be enabled without the workflow master switch or their minimum required credentials.
- Kept existing frontend entry points, current workflow event names, and all outbound behavior unchanged in this step.
- Aligned the root `.env.example`, `backend/.env.example`, `scripts/generate_env.py`, and `docker-compose.yml` with the new disabled-by-default toggles.

### Changed Files
- `backend/app/config.py`
- `backend/tests/test_runtime_config.py`
- `backend/tests/test_generate_env_script.py`
- `scripts/generate_env.py`
- `.env.example`
- `backend/.env.example`
- `docker-compose.yml`

### Findings
- Docker Compose reads the root `.env`, so the root `.env.example` is the source-of-truth template for local deployment.
- `backend/.env.example` is still useful as a backend-only reference; it should stay aligned with the root example to avoid split-brain setup.
- The repository already has `backend/app/adapters/`, which is the safest landing zone for later outbound workflow adapters.

### Recommended Publisher / Adapter Placement
- `backend/app/adapters/workflow/base.py`
- `backend/app/adapters/workflow/null_publisher.py`
- `backend/app/adapters/wecom/group_bot.py`
- `backend/app/adapters/wecom/app_channel.py`
- `backend/app/services/workflow_dispatcher.py`
- `backend/app/services/workflow_registry.py`

### Rollback
- Immediate rollback: keep `WORKFLOW_ENABLED=false`, `WECOM_BOT_ENABLED=false`, and `WECOM_APP_ENABLED=false`. With all flags off, this step stays dormant.
- Config rollback: remove or ignore the new WeCom env keys; they are optional while the flags remain disabled.
- Code rollback: revert the files listed in "Changed Files" if the project needs to return to a pre-skeleton state.

### Open Risks
- This step only adds config skeleton and guardrails; no real publisher, retry queue, or dead-letter handling exists yet.
- The WeCom app channel fields are intentionally minimal. Anything beyond bot webhook URL plus basic app credentials must wait for confirmed tenant requirements.
- No admin UI or runtime diagnostics page exists yet for these flags, so rollout visibility still depends on env inspection and logs.

### Next Step
- Add a workflow dispatcher layer on top of the existing `event_bus` and `workflow_events`, starting with a `NullPublisher` so routing is observable before any real outbound delivery is enabled.

### Verification Commands
- `python -m pytest tests/test_runtime_config.py tests/test_generate_env_script.py tests/test_workflow_events.py tests/test_report_workflow_events.py tests/test_event_bus.py tests/test_event_bus_persistence.py`
- `npm run build`
- `docker compose up -d --build backend nginx`
- `docker compose ps`

## Step 2 - Workflow Dispatcher Skeleton (2026-04-04)

### Completed Items
- Added a workflow adapter package with publisher interface, adapter registry, and `NullWorkflowPublisher`.
- Added a unified workflow dispatcher that reads `payload.workflow_event` from existing realtime events and routes supported events through one dispatcher entry.
- Wired `InMemoryEventBus` and `DatabaseEventBus` to invoke the dispatcher after realtime events are stored, without changing current business service call sites.
- Added dispatch history, idempotency guard for successfully dispatched realtime events, plus retry/dead-letter placeholder interfaces for later rollout stages.
- Kept outbound delivery disabled in practice: with `WORKFLOW_ENABLED=false`, the dispatcher records `workflow_disabled`; with `WORKFLOW_ENABLED=true`, the registry currently resolves only the null publisher.

### Changed Files
- `backend/app/adapters/workflow/base.py`
- `backend/app/adapters/workflow/null_publisher.py`
- `backend/app/adapters/workflow/registry.py`
- `backend/app/adapters/workflow/__init__.py`
- `backend/app/core/workflow_dispatcher.py`
- `backend/app/core/event_bus.py`
- `backend/tests/test_workflow_dispatcher.py`

### Findings
- The safest dispatcher location is `backend/app/core/workflow_dispatcher.py`, not `backend/app/services/workflow_dispatcher.py`. The `app.services` package eagerly imports many services in `__init__.py`, which would create avoidable import coupling from `event_bus`.
- Existing business services already emit the needed contract through `event_bus.publish(...payload.workflow_event...)`, so centralizing the dispatcher behind the event bus avoids touching those services again in this step.
- The dispatcher can now observe all five standard workflow events: `entry_saved`, `entry_submitted`, `attendance_confirmed`, `report_reviewed`, and `report_published`.

### Rollback
- Runtime rollback: keep `WORKFLOW_ENABLED=false` and the dispatcher will remain dormant for delivery while leaving realtime events untouched.
- Code rollback: revert the files listed in "Changed Files" to remove the dispatcher skeleton and restore event bus publish behavior to persistence-only.
- Adapter rollback: future adapters can be removed independently as long as the registry still falls back to an empty list or the null publisher.

### Open Risks
- Dispatch history is currently in-memory only. It is observable in-process and testable, but not yet queryable from an API or persisted across restarts.
- Retry and dead-letter are placeholder interfaces only. They do not yet enqueue work or store failed deliveries.
- The registry currently resolves only the null publisher. Real channel fan-out, per-channel enablement, signing, and retry policy still need later steps.

### Next Step
- Add the first real channel adapter for enterprise WeCom group bot delivery, behind feature flags and dry-run mode, while keeping workflow events as the single contract input.

### Verification Commands
- `python -m pytest tests/test_workflow_dispatcher.py tests/test_event_bus.py tests/test_event_bus_persistence.py tests/test_production_realtime.py tests/test_realtime_routes.py tests/test_realtime_service.py tests/test_work_order_realtime.py tests/test_report_export.py tests/test_report_generation.py tests/test_report_publish_flow.py tests/test_report_service_delivery_status.py tests/test_report_workflow_events.py`

## Step 3 - WeCom Group Bot Channel (2026-04-04)

### Completed Items
- Added the first real workflow delivery adapter: `WeComGroupBotPublisher`.
- Added group bot routing for three target types: team, workshop, and management.
- Added feature-flag and dry-run support for the WeCom bot channel, with dry-run returning observable dispatch results without sending network traffic.
- Centralized message rendering inside the adapter so business semantics are derived from `workflow_event`, not reassembled across services.
- Added HTTP timeout, non-2xx, and business-error handling with log + failure propagation back to the dispatcher.
- Extended runtime config, env templates, env generation script, and Docker Compose env passthrough for the new WeCom bot settings.

### Changed Files
- `backend/app/config.py`
- `backend/app/adapters/workflow/registry.py`
- `backend/app/adapters/wecom/group_bot.py`
- `backend/app/adapters/wecom/__init__.py`
- `backend/app/core/workflow_dispatcher.py`
- `backend/tests/test_runtime_config.py`
- `backend/tests/test_generate_env_script.py`
- `backend/tests/test_wecom_group_bot.py`
- `scripts/generate_env.py`
- `.env.example`
- `backend/.env.example`
- `docker-compose.yml`

### Findings
- The current workflow contract already supports a clean first real channel for `report_reviewed`, `attendance_confirmed`, and `report_published`; these now map to the bot’s “审核完成 / 日报发布” templates without touching business services.
- The current standard events do not yet contain a dedicated reminder event. To avoid inventing business semantics, the adapter only renders the “催报” template when `workflow_event.payload.reminder_reason` is explicitly present.
- Target resolution is config-driven: team and workshop routes come from JSON webhook maps, management can use a dedicated management webhook, and `WECOM_BOT_WEBHOOK_URL` remains the fallback default.
- The implementation assumes the standard enterprise WeCom group bot incoming-webhook JSON contract for text messages. This should be tenant-verified before enabling non-dry-run delivery in production.

### Rollback
- Runtime rollback: keep `WECOM_BOT_ENABLED=false`, or keep `WECOM_BOT_DRY_RUN=true` to observe message assembly without real outbound delivery.
- Config rollback: remove or ignore the new WeCom bot env keys; the dispatcher will continue using `NullWorkflowPublisher`.
- Code rollback: revert the files listed in "Changed Files" to remove the real WeCom channel while preserving the dispatcher skeleton.

### Open Risks
- Reminder delivery is template-ready but not rule-ready. A dedicated reminder workflow event or rule layer still needs to be added before “催报” can be used safely in production.
- Webhook routing is env-driven and in-memory; there is not yet a UI or runtime inspection endpoint for validating which target map entry matched a given event.
- The adapter currently uses plain text messages only. If the tenant requires markdown, mentions, or rate-limit shaping, those should be added in later steps behind tests.

### Next Step
- Add workflow rules on top of the dispatcher so events map intentionally to touchpoints, especially for reminder scenarios, and persist dispatch outcomes for retry / dead-letter visibility.

### Verification Commands
- `python -m pytest tests/test_runtime_config.py tests/test_generate_env_script.py tests/test_wecom_group_bot.py tests/test_workflow_dispatcher.py tests/test_event_bus.py tests/test_event_bus_persistence.py tests/test_production_realtime.py tests/test_realtime_routes.py tests/test_realtime_service.py tests/test_work_order_realtime.py tests/test_report_export.py tests/test_report_generation.py tests/test_report_publish_flow.py tests/test_report_service_delivery_status.py tests/test_report_workflow_events.py`
- `docker compose up -d --build backend`
- `docker compose ps`

## Step 4 - 状态一致性与企业微信账号映射稳定性 (2026-04-06)

### Completed Items
- 梳理并固化移动端与生产数据状态字段使用边界：`MobileShiftReport.report_status`、`ShiftProductionData.data_status`、`DailyReport.status`。
- 补充状态一致性定向测试，覆盖“提交后自动确认”和“提交后自动退回”两条主链路。
- 新增企业微信账号映射服务，支持精确匹配、大小写不敏感匹配、冲突检测、停用账号识别。
- `wecom/login` 路由接入统一映射服务，403 返回现场可读中文原因（未绑定、停用、映射冲突、账号无效）。
- 新增试点账号批量检查脚本，支持文本清单输入和 JSON 输出；数据库不可用时返回中文硬错误。

### Changed Files
- `backend/app/services/wecom_mapping_service.py`
- `backend/app/routers/wecom.py`
- `backend/app/agents/validator.py`
- `backend/scripts/check_wecom_account_mapping.py`
- `backend/tests/test_mobile_status_consistency.py`
- `backend/tests/test_wecom_mapping_service.py`
- `backend/tests/test_wecom_login_route.py`

### Open Risks
- 批量账号检查脚本依赖数据库连通性；在本地无数据库凭据时会直接失败（已返回可读中文错误，非静默）。
- 当前映射仍建立在既有字段（`username`/`dingtalk_user_id`）上，若现场存在历史脏数据，需先跑批量脚本清理冲突。

### Next Step
- 进入“异常闭环最小可用”前，先完成试点账号清单跑批并清零冲突账号，再进行现场演练。

### Verification Commands
- `python -m pytest tests/test_mobile_status_consistency.py tests/test_wecom_mapping_service.py tests/test_wecom_login_route.py -q`
- `python -m pytest -q`
- `python scripts/check_wecom_account_mapping.py --help`
- `python scripts/check_wecom_account_mapping.py --input <账号清单文件> --json`

## Step 5 - 现场运行可用性优化 (2026-04-06)

### Completed Items
- 增加试点运行关键可观测日志：提交、自动校验、自动确认/退回、汇总、推送。
- 增加试点复盘指标输出能力：TTR、上报率、退回率、差异率。
- 增加两个降级开关：
  - `AUTO_PUBLISH_ENABLED`：控制自动发布日报
  - `AUTO_PUSH_ENABLED`：控制自动推送消息
- 调度任务增加 `max_instances=1 + coalesce=true`，降低重复执行风险。
- 新增最小试点 SOP 文档，覆盖入口、登录失败、退回处理、当班未报处理。

### Changed Files
- `backend/app/config.py`
- `backend/app/services/pilot_observability_service.py`
- `backend/app/services/pilot_metrics_service.py`
- `backend/app/services/mobile_report_service.py`
- `backend/app/agents/validator.py`
- `backend/app/agents/aggregator.py`
- `backend/app/agents/reporter.py`
- `backend/app/agents/reminder.py`
- `backend/app/main.py`
- `backend/scripts/check_pilot_metrics.py`
- `backend/tests/test_runtime_config.py`
- `backend/tests/test_generate_env_script.py`
- `backend/tests/test_aggregator_agent.py`
- `backend/tests/test_reporter_agent.py`
- `backend/tests/test_pilot_metrics_service.py`
- `.env.example`
- `backend/.env.example`
- `docker-compose.yml`
- `scripts/generate_env.py`
- `docs/pilot-sop-minimal.md`

### Open Risks
- `AUTO_PUSH_ENABLED=false` 时会停止推送动作，但日志仍会记录“已执行推送流程”的审计决策，这是有意保留的可追溯行为。
- 指标中的 TTR 当前按“创建到提交”计算，若现场后续定义为“班末到提交”，需再补排班结束时间口径。

### Next Step
- 在试点环境跑 3-7 天，按 `check_pilot_metrics.py` 日更复盘，并根据日志热点决定是否进入异常闭环强化阶段。

### Verification Commands
- `python -m pytest tests/test_aggregator_agent.py tests/test_reporter_agent.py tests/test_pilot_metrics_service.py tests/test_runtime_config.py tests/test_generate_env_script.py -q`
- `python -m pytest -q`
- `python scripts/check_pilot_metrics.py --help`

## Step 6 - 最小异常闭环 (2026-04-06)

### Completed Items
- 新增最小异常类型字典（5类）：产出>投入、班次缺报、能耗异常波动、出勤异常、跨班次跳变。
- 新增异常检测服务，输出当日异常清单与摘要，优先复用现有模型与排班/填报数据。
- 将异常摘要接入日报汇总结果，确保驾驶舱/日报文本可直接看到异常概况。
- 将异常摘要接入日报推送文案，管理层在消息触达时同步看到异常总数与摘要。
- 新增试点异常检查脚本，支持按日期/车间输出异常清单。
- 新增异常处理最小 SOP 文档。

### Changed Files
- `backend/app/core/anomaly_types.py`
- `backend/app/services/anomaly_detection_service.py`
- `backend/scripts/check_pilot_anomalies.py`
- `backend/app/agents/aggregator.py`
- `backend/app/agents/reporter.py`
- `backend/tests/test_anomaly_detection_service.py`
- `backend/tests/test_aggregator_agent.py`
- `backend/tests/test_reporter_agent.py`
- `docs/pilot-anomaly-sop-minimal.md`

### Open Risks
- 当前异常清单以“发现与触达”优先，未新增复杂处置流转状态；仍依赖班组按 SOP 修复后复跑确认。
- 能耗异常与跨班次跳变阈值目前为固定阈值，后续可按车间工艺差异细化。

### Next Step
- 在试点周内每日复跑异常脚本并记录 Top 异常类型，确认是否需要进入“异常处置台”增强。

### Verification Commands
- `python -m pytest tests/test_anomaly_detection_service.py tests/test_aggregator_agent.py tests/test_reporter_agent.py tests/test_pilot_metrics_service.py tests/test_runtime_config.py tests/test_generate_env_script.py -q`
- `python -m pytest -q`
- `python scripts/check_pilot_anomalies.py --help`


## Step 7 - QA Readiness 与放量检查 (2026-04-06)

### Completed Items
- 补充 QA/readiness 定向验证，覆盖自动确认兼容状态 `auto_confirmed`、`returned_reason` 可执行性、canonical `auto_confirmed` 日报口径，以及配置硬门禁/警告门禁语义。
- 新增试点上线前检查清单，统一预检命令、现场 smoke 步骤、降级开关和放量结论模板。
- 将最小 SOP 与异常 SOP 都挂到同一份 readiness checklist，减少现场值班人员找文档的成本。

### Changed Files
- `backend/tests/test_reminder_agent.py`
- `backend/tests/test_aggregator_agent.py`
- `backend/tests/test_config_readiness_service.py`
- `docs/pilot-readiness-checklist.md`
- `docs/pilot-sop-minimal.md`
- `docs/pilot-anomaly-sop-minimal.md`
- `docs/workflow-rollout.md`

### Rollout Gates
- Gate A：`check_pilot_config.py` 返回 `hard_gate_passed=true`，warning 可登记后放行。
- Gate B：移动填报链路验证通过，自动确认/自动退回/范围隔离均正常。
- Gate C：日报 canonical 口径为 `auto_confirmed`，兼容入参仍接受 `confirmed_only`，且 `AUTO_PUBLISH_ENABLED` / `AUTO_PUSH_ENABLED` 能独立降级。

### Verification Commands
- `python -m pytest tests/test_health.py tests/test_config_readiness_service.py tests/test_validator_agent.py tests/test_mobile_status_consistency.py tests/test_mobile_scope_isolation.py tests/test_reminder_agent.py tests/test_aggregator_agent.py tests/test_report_generation.py tests/test_report_publish_flow.py tests/test_reporter_agent.py tests/test_pilot_metrics_service.py -q`
- `python scripts/check_pilot_config.py --date 2026-04-06 --json`
- `python scripts/check_pilot_metrics.py --date 2026-04-06 --json`
- `python scripts/check_pilot_anomalies.py --date 2026-04-06 --json`

### Next Step
- 先按 `docs/pilot-readiness-checklist.md` 完成一次带记录的试点预检，再决定是否进入现场放量。

## Step 8 - 企业微信单入口收口与文档对齐 (2026-04-08)

### Completed Items
- 将外部口径统一为“企业微信单入口优先”，明确现场唯一移动填报入口为 `/mobile`。
- 明确“保留后端/系统端口”语义：企业微信是当前优先身份入口，但历史 `dingtalk_*` 字段与相关系统端口继续作为兼容结构保留，不在本轮移除。
- README、试点 SOP、readiness checklist 已同步改为单入口口径，避免现场误以为还存在并列工人端主入口。
- 补充了现场 smoke 关注点：进入 `/mobile`、退回后回到同一入口继续处理、登录映射仍兼容历史字段。

### Changed Files
- `README.md`
- `docs/pilot-sop-minimal.md`
- `docs/pilot-readiness-checklist.md`
- `docs/workflow-rollout.md`
- `docs/wecom-single-entry-review-2026-04-08.md`

### Review Notes
- 当前 canonical 业务写入口仍是 `/api/v1/mobile/*`；`/api/v1/wecom/*` 仅承担企业微信身份入口职责。
- 历史 `dingtalk_*` 字段目前仍参与兼容映射与系统集成，不应被现场文案继续描述为默认主入口。
- 若前端仍保留其他工人端落点，只能视为兼容路径，现场培训与 README 不再把它们当成并列主入口。

### Verification Commands
- `cd frontend && npm run build`
- `cd backend && python -m pytest tests/test_mobile_status_consistency.py tests/test_wecom_login_route.py -q`
- 手工检查 `/mobile`：登录、提交、退回后继续处理三个最小场景

### Next Step
- 将前端剩余历史入口文案继续收口到企业微信 `/mobile` 主链路，并在现场试点时只培训这一条路径。
