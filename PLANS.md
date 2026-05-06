# Execution Plan (ExecPlan)

> This is a living document. Codex updates it as tasks progress.
> Use this file to plan complex features before implementation.

## Current Plan: 数据中枢优化三阶段（MES MVC 已接入）

### Goal
把现有"手填 + 投影骨架 + 5 个确定性 agent + 钉钉占位"这套自洽闭环打磨到极致。不等 MES，先把现状跑通、跑顺、跑快。

### Design Decisions
- Agent 维持确定性执行器形态，不引入 LLM 自由代理
- 工人入口收敛到钉钉 H5（先真打通免登录），企业微信用户消息通道整体下线
- 保留 `adapters/wecom/group_bot.py` 作为输出 publisher lane
- 工厂指挥中心优先显示 MES 投影，并在 MES 已有投影时叠加当天 `mobile_coil_agg` 卷级直录；MES 投影为空时回退到 `ShiftProductionData` 聚合（不白屏）
- 校验阈值按车间维度可配置，`thresholds.py` 降级为 fallback
- AI 助手从"摘要展示"升级为"建议 + 一键调 agent"
- 三阶段必须串行推进，前一阶段 success criteria 不达标不进下一阶段

### Phases

**Phase 1 · 地基清理**（代码闭环已验证）
详见 `docs/superpowers/plans/2026-05-03-phase1-foundation-cleanup.md`
- Task 1: Pytest 收集与回归全绿
- Task 2: Readyz 硬阻断降级（空绑定、空排班 → warning）
- Task 3: 拆除企业微信用户消息路径（保留群机器人 publisher）
- Task 4: 工厂指挥中心 7 屏回退到手填口径

**Phase 2 · 自动化闭环**（代码闭环已验证）
详见 `docs/superpowers/plans/2026-05-03-phase2-automation-closure.md`
- Task 1: 规则阈值按车间可配置（DB 存 + 热加载）
- Task 2: AI 助手异常"建议→一键处置"回环
- Task 3: 班长一屏（排班/出勤/已报/退回/催报 五象限）

**Phase 3 · 工人入口升级**（代码闭环已验证；MES MVC 已连通；钉钉/Workflow/LLM/应用连接待现场凭证/UAT）
详见 `docs/superpowers/plans/2026-05-03-phase3-worker-entry-upgrade.md`
- Task 1: 钉钉 H5 免登录闭环 + 工作通知真实发送
- Task 2: 扫码即填（本地 `coil_snapshots` 登记替代 MES 投影）

### 阶段进度审计（2026-05-06）

- Phase 1 代码闭环：readyz warning 语义、企业微信用户消息路径下线、工厂指挥中心手填回退、后端回归均已有自动化覆盖。
- Phase 2 代码闭环：规则阈值按车间配置、AI 助手建议到 agent 一键处置、班长一屏均已有后端和前端自动化覆盖。
- Phase 3 代码闭环：钉钉 H5 登录服务、钉钉通讯录同步入口、扫码带出与锁字段校验均已有后端和前端自动化覆盖。
- MES MVC 联通阻塞已解除：生产预检 `login.status=success`，one-shot 同步 `coil_snapshots fetched=50 upserted=50`，`mes_coil_snapshots_count=52`。
- 管理端工厂指挥中心已验证混合来源：生产 `overview_source=mixed`，当天卷级直录原始 `raw_mobile_coil_agg_output_kg=120460.0`，管理口径 `overview_total_output=120.46`，`machine_lines_len=56`，`unbound_machine_lines_len=5`。
- 机列绑定贯通到管理端：普通移动班次报表会把同车间绑定账号写入 `ShiftProductionData.equipment_id`，工厂指挥 `machine-lines` API 响应模型保留 `machine_binding_status`，生产回滚事务探针 `mobile_shift_report_binding_ok=true`。
- 对账服务已验证卷级吨口径：生产 `reconciliation_output_total_tons=120.46`，`production_vs_mes` 与 `energy_vs_production` 不再把 `mobile_coil_agg` raw kg 当吨比较。
- 自动汇总 Agent 已验证卷级吨口径：confirmed `mobile_coil_agg` 行进入自动日报/老板摘要前先折吨，生产代码探针 `aggregator_output_tons=250.0`、`aggregator_input_tons=260.0`。
- 内部 workflow 开关已启用：生产 `WORKFLOW_ENABLED=true`，当前由 `NullWorkflowPublisher` 接收事件，不触发外部机器人或应用连接外发。
- 钉钉应用配置已启用并完成 token 预检：`DINGTALK_ENABLED=true`，`token_received=true`；但当前生产库仍无绑定钉钉用户，通知送达需要现场绑定与 UAT。
- 钉钉通讯录同步阻塞已定位：生产只读拉部门用户返回缺少 `qyapi_get_department_member` 权限，需要先在钉钉开放平台给应用开通通讯录成员读取权限。
- 钉钉通讯录权限已具备可重复只读诊断：`scripts/dingtalk_cli.py contacts --department-id 1 --json` 返回 `missing_scope=qyapi_get_department_member`，不会写用户表或回显成员明细。
- 外部联通 readiness 已显式返回 `DINGTALK_NO_BOUND_USERS` warning：`active_dingtalk_user_count=0`、`active_dingtalk_employee_count=0`。
- 历史 `每日产量` 工作簿已具备只读 dry-run 预览：综合日报表按吨单位映射日/月投料、产出、废料，车间标签向下继承，并拦截 `10000t` 以上疑似 kg 口径异常，暂不写库。
- 外部联通仍未完全完成：`LLM_DISABLED`、`APP_CONNECTION_DISABLED` 仍是正式完全体阻塞。
- 真实钉钉客户端免登录、通讯录成员读取权限、工作通知送达、Workflow/LLM/应用连接 API、MES 持续同步监控和正式域名仍需现场凭证与 UAT。

本轮核验命令：

- `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q`：35 passed，1 deselected
- `python -m pytest backend/tests/test_aggregator_agent.py -q`：7 passed
- `python -m pytest backend/tests/test_reconciliation_granularity.py -q`：3 passed
- `python -m pytest backend/tests -q`：708 passed，124 deselected，31 warnings
- `python -m pytest backend/tests/test_daily_production_canonical_service.py backend/tests/test_legacy_data_profile_service.py -q`：23 passed
- `python -m pytest backend/tests/test_dingtalk_cli.py backend/tests/test_statistics_module_ready_script.py backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_current_deploy_state_tracks_current_head_and_validation_evidence backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_exec_plan_tracks_phase_progress_without_hiding_external_gates -q`：17 passed
- `python -m pytest backend/tests/test_mobile_shift_report_machine_binding.py backend/tests/test_coil_entry_auto_calc.py backend/tests/test_factory_command_service.py backend/tests/test_realtime_service.py -q`：31 passed
- `python -m pytest backend/tests/test_mobile_shift_report_machine_binding.py backend/tests/test_factory_command_routes.py backend/tests/test_factory_command_service.py backend/tests/test_realtime_service.py -q`：36 passed
- `npm --prefix frontend test`：119 passed
- `npm --prefix frontend run build`：通过
- `bash -n scripts/deploy_systemd_host.sh`：通过
- `git diff --check`：通过（仅 Windows CRLF 提示）

### Files to Modify
按阶段查看对应 plan 文件。

### Completion Criteria
- [x] Phase 1 代码闭环已验证
- [x] Phase 2 代码闭环已验证
- [x] Phase 3 代码闭环已验证
- [ ] 真实外部联通闸门通过
- [ ] 试点车间一周，工人-班长-管理者三端零人工中转运转

### Notes
- MES MVC、内部 workflow 和钉钉 token 已完成生产验证；正式完全体前仍需持续同步监控、钉钉通讯录成员读取权限、真实钉钉用户绑定/UAT、LLM/应用连接 API 与正式域名联通。
- 不把本地测试通过误写成现场 UAT 完成；现场 UAT 需要目标车间、真实账号、真实钉钉客户端和正式域名证据。
- 星标项全部在这三个 phase 里；非星标项（一键代提、双录校验、reminder 智能化等）作为 backlog 不列入

---

## Plan Template

When starting a new plan, replace the "Current Plan" section with:

```markdown
## Current Plan: [Feature Name]

### Goal
What we're building and why.

### Design Decisions
Key architectural choices and trade-offs.

### Tasks
- [ ] Task 1 — description
- [ ] Task 2 — description
- [ ] Task 3 — description

### Files to Modify
- `path/to/file.py` — what changes
- `path/to/component.vue` — what changes

### Completion Criteria
- [ ] Tests pass
- [ ] Build succeeds
- [ ] Migration works
- [ ] Manually verified

### Notes
Discoveries, blockers, or context gathered during implementation.
```

## Completed Plans

_Archive finished plans here with date and summary._
