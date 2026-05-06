# 数据中枢当前部署状态

更新时间：2026-05-06 20:22:00 +08:00

## 1. 仓库状态

- 仓库：`https://github.com/zhangzhaojia6-boop/xt-aluminnum.git`
- 当前主线：`main`
- 当前记录基准：当前 `main` HEAD
- 本地与远端状态以 `git status --short --branch` 和 `git rev-parse --short origin/main` 为准
- PR 状态：`#1 fix: 收口管理占位路由与就绪配置阻断` 已合并并关闭
- 推荐服务器目录：`/srv/aluminum-bypass`
- 推荐部署命令：

```bash
cd /srv/aluminum-bypass
./scripts/deploy_systemd_host.sh --pull http://8.140.218.13
```

## 2. 当前产品口径

产品名称统一使用：`鑫泰铝业 数据中枢`。

用户入口：

- `/entry`：岗位填报端。
- `/entry/fill`：机台主操统一按卷填报。
- `/manage`：管理入口。
- `/manage/factory`：工厂驾驶舱。
- `/manage/admin/settings`：管理配置入口。

兼容入口：

- `/mobile` 会重定向到 `/entry`。
- `/review/*` 会重定向到 `/manage/*`。
- `/manage/admin`、`/admin`、`/admin/overview` 会重定向到 `/manage/admin/settings`。

已收口事项：

- 旧管理占位路由已移除。
- 主路径不再暴露“改造中”“待迁移”等占位文案。
- PR review 反馈的扫码取旧 MES 快照问题已修复：重复 QR 取最新快照，缺少 `mes_coil_snapshots` 表时仍可回退设备二维码。
- 管理端已上线卷级实时填报可见性：`pending + mobile_coil_agg` 作为 `卷级直录` 待确认流入展示，正式已确认日报口径不被普通 `pending` 数据污染。
- 工厂指挥中心已上线混合来源消费：MES 投影已存在时，`overview`、`workshops`、`machine-lines` 仍会叠加当天 `mobile_coil_agg` 本地卷级直录，来源标为 `mixed`。
- 按卷填报链路已改为读取 `equipment.bound_user_id` 机列绑定：绑定账号新增卷记录会写入 `WorkOrderEntry.machine_id`，并按 `equipment_id` 生成 `mobile_coil_agg` 聚合行；本轮未对生产历史未绑定聚合行做回填。
- 按卷填报提交口径已收紧：`/mobile/coil-entry` 新增记录写为 `submitted`，`mobile_coil_agg` 只聚合 `submitted/verified/approved` 卷明细；重算时没有合格源卷会 void 旧聚合，draft 历史卷不再进入管理端实时产量。
- 生产库历史 draft-only 聚合已修正：先创建并校验 `/srv/aluminum-bypass/backups/pre-void-mobile-coil-agg-20260506-203651.dump`，再将 2026-05-01 至 2026-05-06 共 28 行来源卷全为 draft 的 `mobile_coil_agg` 置为 `voided`，源卷明细未删除；复验 `active_mobile_coil_agg=0`、`draft_only_candidate_count=0`。
- 普通移动班次报表同步管理端数据时也会读取机列绑定：同车间绑定账号写入 `ShiftProductionData.equipment_id`，已有同机列聚合行时保持未绑定汇总，避免覆盖卷级聚合。
- 工厂指挥 `machine-lines` API 响应模型已保留 `machine_binding_status`，管理端不再只依赖 service 内部 dict 才能识别未绑定机列。
- 外部联通 readiness 已显式提示钉钉人员绑定缺口：`DINGTALK_ENABLED=true` 但 active 用户/员工没有 `dingtalk_user_id` 时返回 `DINGTALK_NO_BOUND_USERS` warning，避免把 token 可用误判为通知送达。
- MES 同步批内重复投影已收口：`mes_follow_cards` / `mes_dispatch` 按投影后的 `coil_id` 去重，新建 `MesCoilSnapshot` 后立即 `flush`，避免同一事务内重复落库触发唯一键冲突。
- MES MVC 会话恢复已增强：表格查询若被会话过期打回登录页，会清理 cookie/token 后重新登录并重放请求；二次仍返回登录页才报错，避免短期 session 过期让同步长期卡住。
- 历史 `每日产量` 工作簿已接入只读 canonical 预览：`综合报表` 会输出显式吨单位、车间标签向下继承、日/月投料产出废料合计，并把超过 `10000t` 的日产量标为疑似 kg 口径，不写入数据库。
- 历史 `每日产量` 真实报表已进入生产 import staging：生产备份 `backups/pre-daily-production-import-20260506-210602.dump` 校验通过后，将 `D:\鑫泰报表\5.5\鑫泰每日产量5月.xls` 转换为临时 `.xlsx` 并写入 `ImportBatch id=1`、`batch_no=IMP-20260506130735-d4f557`；`ShiftProductionData` 写入增量为 0。

## 3. 默认部署形态

默认使用 Docker Compose：

```text
nginx 容器: 80/443
backend 容器: 8000
db 容器: PostgreSQL 15
```

核心文件：

- `docker-compose.yml`
- `docker-compose.prod.yml`
- `nginx/nginx.conf`
- `scripts/deploy_trial.sh`
- `scripts/check_trial_stack.sh`
- `scripts/go_live_gate.sh`
- `scripts/launch_cloud_trial.sh`
- `scripts/backup_db.sh`
- `scripts/restore_db.sh`

生产机必须自备：

- `.env`
- `ssl/cert.pem`
- `ssl/key.pem`

不要把 `.env`、证书、密钥、数据库备份提交到 Git。

当前 ECS 真实运行形态仍是历史 systemd 托管：

```text
公网 80/443
  -> 宿主机 nginx
  -> aluminum-bypass.service: 127.0.0.1:8000
  -> 宿主机 PostgreSQL
```

当前 ECS 已按 systemd 形态完成本轮更新；Docker Compose 仍是后续统一部署形态，但切换前不要直接抢占宿主机 80/443 端口。

## 4. 本地验证记录

在当前 `main` HEAD 上已完成代码与路由文档回归验证：

- `python -m pytest backend/tests -q`：714 passed，124 deselected，31 warnings
- `python -m pytest backend/tests/test_coil_entry_auto_calc.py -q`：6 passed
- `python -m pytest backend/tests/test_coil_entry_auto_calc.py backend/tests/test_realtime_service.py backend/tests/test_factory_command_service.py backend/tests/test_workshop_reporting_status.py -q`：32 passed
- `python -m pytest backend/tests/test_daily_production_canonical_service.py backend/tests/test_legacy_data_profile_service.py -q`：23 passed
- `python -m pytest backend/tests/test_import_service_daily_production.py backend/tests/test_daily_production_canonical_service.py -q`：8 passed
- `python -m pytest backend/tests/test_dingtalk_cli.py backend/tests/test_statistics_module_ready_script.py backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_current_deploy_state_tracks_current_head_and_validation_evidence backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_exec_plan_tracks_phase_progress_without_hiding_external_gates -q`：17 passed
- `python -m pytest backend/tests/test_mobile_shift_report_machine_binding.py backend/tests/test_coil_entry_auto_calc.py backend/tests/test_factory_command_service.py backend/tests/test_realtime_service.py -q`：31 passed
- `python -m pytest backend/tests/test_mobile_shift_report_machine_binding.py backend/tests/test_factory_command_routes.py backend/tests/test_factory_command_service.py backend/tests/test_realtime_service.py -q`：36 passed
- `python -m pytest backend/tests/test_aggregator_agent.py -q`：7 passed
- `python -m pytest backend/tests/test_mes_sync_service.py backend/tests/test_mes_mvc_preflight_script.py -q`：11 passed
- `python -m pytest backend/tests/test_mes_sync_service.py backend/tests/test_mes_mvc_preflight_script.py backend/tests/test_mvc_mes_adapter.py -q`：17 passed
- `python -m pytest backend/tests/test_factory_command_service.py -q`：20 passed
- `python -m pytest backend/tests/test_reconciliation_granularity.py -q`：3 passed
- `python -m pytest backend/tests/test_report_service_contract_lane.py backend/tests/test_realtime_service.py backend/tests/test_factory_command_service.py backend/tests/test_owner_entry_projection_fallbacks.py backend/tests/test_workshop_reporting_status.py -q`：40 passed
- `python -m pytest backend/tests -m frontend_contract -q`：124 passed，675 deselected
- `npm --prefix frontend test`：119 passed
- `npm --prefix frontend run build`：通过
- `git diff --check`：通过

此前在 `main@b029db8` 上已完成部署闸门与容器可用性验证：

- `npm --prefix frontend run e2e -- e2e/admin-surface.spec.js --grep "admin surface is separate"`：1 passed
- `docker compose config --quiet`：通过
- `curl -k https://127.0.0.1/readyz`：HTTP 200
- `bash scripts/go_live_gate.sh https://example.invalid --dry-run --require-external`：正确显示 `GATE_EXTERNAL`
- `bash scripts/launch_cloud_trial.sh https://example.invalid --dry-run --require-external --pull`：正确透传 `--require-external`

`main@9130fb3` 之后，主线继续完成 workflow 状态措辞、中心页真实路由、未使用 mock、排班闸门时区、成本历史契约和 canonical 中心导航路径收口；当前文档以当前 `main` HEAD 为准。

本地 Docker 状态：

- `db`：healthy
- `backend`：healthy
- `nginx`：running

## 5. 当前 readyz 与配置闸门

生产 `/readyz` 已通过，返回的关键状态：

- `database=ok`
- `uploads=ok`
- `equipment_binding=ok`
- `schedule=ok`
- `pipeline=ok`
- `mes_sync=idle`
- `mes_sync.configured=true`
- `mes_sync.last_run_status=success`
- `mes_sync.fetched_count=50`
- `mes_sync.upserted_count=50`

`python scripts/check_statistics_module_ready.py --json` 仍然是预期 hard fail。原因不是数据库、MES 或代码阻断，而是其余正式外部联通尚未配置真实值：

- `LLM_DISABLED`
- `APP_CONNECTION_DISABLED`

正式联通前可先生成不回显现有密钥的 `.env` 填写模板：

```bash
python scripts/check_statistics_module_ready.py --env-template
```

正式联通前必须在服务器 `.env` 写入真实值：

```dotenv
MES_ADAPTER=mvc
MES_MVC_BASE_URL=...
MES_MVC_USERNAME=...
MES_MVC_PASSWORD=...
WORKFLOW_ENABLED=true
DINGTALK_ENABLED=true
DINGTALK_CORP_ID=...
DINGTALK_APP_KEY=...
DINGTALK_APP_SECRET=...
DINGTALK_AGENT_ID=...
APP_CONNECTION_ENABLED=true
APP_CONNECTION_PUSH_MODE=enabled
APP_CONNECTION_API_BASE=...
APP_CONNECTION_API_KEY=...
```

如果现场使用 REST 形式的外部 MES，则改为：

```dotenv
MES_ADAPTER=rest_api
MES_API_BASE=...
MES_API_KEY=...
```

## 6. 远端与 Vercel 探测记录

最近一次 ECS 修复验证：2026-05-06 20:22 左右。

- SSH：`root@8.140.218.13` key 登录可用。
- 远端仓库：`/srv/aluminum-bypass` 已快进到当前 `main` HEAD，`HEAD` 与 `origin/main` 对齐，工作区干净。
- 远端运行形态：宿主机 nginx + `aluminum-bypass.service` + 宿主机 PostgreSQL；`docker compose ps` 当前无运行容器。
- 已用 `./scripts/deploy_systemd_host.sh --pull http://8.140.218.13` 完成 systemd 宿主机部署闭环。
- 本轮已部署 `main@ac48f3b`：MES 同步批内重复投影修复已上线；生产 one-shot 同步返回 `coil_snapshots fetched=50 upserted=50`、`mes_follow_cards fetched=50 upserted=50`、`mes_dispatch fetched=50 upserted=50`，未再触发 `mes_coil_snapshots.coil_id` 唯一键冲突。
- 本轮已部署 `main@f2350d6`：工厂指挥中心在 MES 投影存在时叠加本地 `mobile_coil_agg` 卷级直录，生产探针返回 `overview_source=mixed`、`overview_total_input=149510.0`、`overview_total_output=120460.0`、`overview_today_output=120460.0`、`overview_workshop_summary_len=3`、`machine_lines_len=56`、`unbound_machine_lines_len=5`、`unbound_output_total=120460.0`。
- 本轮已部署 `main@bff456b`：卷级填报 raw kg 已在工厂指挥、实时聚合、日报和能源汇总入口统一折算为吨；生产探针保留 `raw_mobile_coil_agg_output_kg=120460.0`，同时返回 `overview_total_input_tons=149.51`、`overview_total_output_tons=120.46`、`overview_today_output_tons=120.46`、`unbound_output_tons=120.46`、`live_factory_output=120.46`。
- 本轮已部署 `main@182508f`：对账服务 `production_vs_mes` 与 `energy_vs_production` 的生产侧产量改为按 `mobile_coil_agg` raw kg 折吨后分组；生产只读探针返回 `reconciliation_output_total_tons=120.46`，正产量行为 `JZ/NIGHT=37.25`、`LZ2050/DAY=9.1`、`LZ2050/NIGHT=74.11`。
- 本轮已部署 `main@fd96768`：自动汇总 Agent 生成日报/老板摘要时不再用 SQL raw sum，confirmed `mobile_coil_agg` 行会先折吨再写入 `total_output_weight`、`total_input_weight` 和车间明细；生产代码探针返回 `aggregator_output_tons=250.0`、`aggregator_input_tons=260.0`。
- 本轮已部署 `main@1a1139c`：普通移动班次报表同步到管理端时保留同车间机列绑定，工厂指挥 `machine-lines` API 响应模型保留 `machine_binding_status`；生产回滚事务探针返回 `schema_preserves_machine_binding_status=true`、`checked_equipment_id=12`、`rollback_mobile_shift_report_equipment_id=12`、`mobile_shift_report_binding_ok=true`。
- 本轮已拉取 `main@8678dc7`：新增 `scripts/dingtalk_cli.py contacts --department-id 1 --json` 只读诊断；生产运行返回 `ok=false`、`configured=true`、`department_access=false`、`dry_run_only=true`、`missing_scope=qyapi_get_department_member`，可重复验证钉钉通讯录权限阻塞且不写用户表。
- 本轮已部署 `main@180d84d`：外部联通 readiness 新增钉钉人员绑定 warning；生产 `scripts/check_statistics_module_ready.py --json` 返回 `warning_issues=DINGTALK_NO_BOUND_USERS`、`active_dingtalk_user_count=0`、`active_dingtalk_employee_count=0`，同时 hard issue 仍为 `LLM_DISABLED,APP_CONNECTION_DISABLED`。
- 本轮已部署 `main@f137662`：外部联通 readiness 支持 `--check-dingtalk-contacts`；生产复验返回 `hard_issues=LLM_DISABLED,APP_CONNECTION_DISABLED`、`warning_issues=DINGTALK_NO_BOUND_USERS,DINGTALK_CONTACTS_PERMISSION_MISSING`、`dingtalk_department_access=false`、`dingtalk_contacts_missing_scope=qyapi_get_department_member`。
- 本轮已部署 `main@d5da2ca`：历史 `每日产量` 工作簿只读 canonical 预览与日期误判修复已上线；生产 synthetic parser 返回 `valid_business_date=2026-05-03`、`valid_daily_output_tons=60.38`、`valid_quality_status=ready`，无日期样本返回 `missing_business_date=null`、`missing_quality_status=blocked`，确认普通小数 `1.14` 不会再被当作日期。
- 生产 MES MVC 预检已通过：`adapter=mvc`、`mvc_configured=true`、`missing_env=[]`、`login_page.status=reachable`、`token_present=true`、`login.status=success`。
- 生产库 MES 投影已落库：`mes_coil_snapshots_count=52`，`mes_machine_line_snapshots_count=50`，最新 `coil_snapshots` 同步日志为 `status=success`、`fetched_count=50`、`upserted_count=50`、`error_message=null`。
- 生产内部 workflow 开关已启用：备份 `backend/.env` 到忽略目录 `backups/.env.workflow-backup-20260506-170534` 后仅修改 `WORKFLOW_ENABLED=true`；`WECOM_BOT_ENABLED=false`、`DINGTALK_ENABLED=false`、`APP_CONNECTION_ENABLED=false`，当前只由 `NullWorkflowPublisher` 接收 workflow 事件，不会触发外部机器人或应用连接外发。
- 生产钉钉配置已启用：备份 `backend/.env` 到忽略目录 `backups/.env.dingtalk-backup-20260506-171247` 后仅修改 `DINGTALK_ENABLED=true`；`scripts/dingtalk_cli.py token --json` 返回 `ok=true`、`configured=true`、`token_received=true`、`token_length=32`。当前生产库 `active_users_with_dingtalk_id=0`、`active_employees_with_dingtalk_id=0`，所以还不能宣称工作通知已送达。
- 生产只读拉取钉钉部门用户失败：接口返回缺少 `qyapi_get_department_member` 权限；当前阻塞在钉钉开放平台给应用开通通讯录成员读取权限，不是本系统数据库或同步代码未运行。
- 该权限阻塞现在可用 `PYTHONPATH=. .venv/bin/python scripts/dingtalk_cli.py contacts --department-id 1 --json` 在生产机复验；命令只输出统计和权限状态，不回显成员姓名、手机号、userid 或 token。
- 本轮已部署 `main@6e1bfb4`：管理端实时态势第一屏新增“班次产量节奏”，线上 `LiveDashboard-BvJspizJ.js` / `LiveDashboard-CtQL3H_9.css` 已包含 `班次产量节奏` 和 `live-shift-rhythm`。
- 本轮已部署 `main@54a09e0`：管理端实时态势第一屏新增“卷级直录分布”，线上 `LiveDashboard-CO0mybtJ.js` / `LiveDashboard-BHO0nfza.css` 已包含 `卷级直录分布`、`live-output-distribution` 和 `未绑定`。
- 本轮已部署 `main@47be2a7`：管理端实时态势第一屏新增“未绑定填报归属”，线上 `LiveDashboard-BSehAJcz.js` / `LiveDashboard-DYSwQp49.css` 已包含 `未绑定填报归属`、`live-unbound-fill` 和 `绑定账号`。
- 生产 Playwright 视觉验证已覆盖 `http://8.140.218.13/manage/admin/settings?desktop=1`：桌面 `1440x900` 与手机 `390x844` 均显示“未绑定填报归属”、`120460.00`、`2 个车间`、`3 条机列` 与“绑定账号”，页面无横向溢出；截图留存在本地忽略目录 `frontend/test-results/visual-production/`。
- 本轮已部署 `main@1c00050`：管理端实时态势主聚合接入 `mobile_coil_agg` 卷级直录 fallback，线上 `LiveDashboard-CeSbJ94X.js` 已包含 `卷级直录` 和 `local_shift_data`。
- 本轮已部署 `main@7659225`：管理端实时态势页新增“外部联通闸门”卡，线上 `LiveDashboard-BXTGpXX4.js` / `dashboard-D6EhilfF.js` 已包含 `外部联通闸门`、`接口待返回`、`external-readiness` 和 `hard_issues`。
- 本轮已部署 `main@3e492f8`：管理端外部 MES 状态条显示运行配置缺口，线上 `LiveDashboard-BNcHeouG.js` 已包含 `required_env`、`缺少配置` 和 `MES_MVC_BASE_URL`。
- 本轮已部署 `main@38493da`：管理端车间机列页支持把未绑定 `mobile_coil_agg` 实时填报按车间/班次归入“未绑定机列”，线上 `MachineLineScreen-DL7qgGJc.js` / `MachineLineScreen-FDnJ2hSk.css` 已包含 `未绑定机列`、`machine_binding_status` 和 `fc-line__bar`。
- 本轮已部署 `main@8fc5ce0`：管理端用户管理页支持绑定机列，线上 `UserManagement-CvyvNRYK.js` 已包含 `绑定机列` 和 `bound_machine_id`。
- 本轮已部署 `main@5831bab`：管理端用户管理页支持按机列绑定状态和具体机列筛选账号，线上 `UserManagement-B4GmUedd.js` 已包含 `绑定状态`、`machine_binding` 和 `boundMachineId`；线上 `/api/v1/users/` 探针返回 `machine_binding=bound total=136`、`machine_binding=unbound total=198`、`bound_machine_id=<已绑定机列> total=1`。
- 本轮已部署 `main@3847564`：管理端“未绑定填报归属”面板的“绑定账号”入口会带 `machine_binding=unbound` 进入用户管理，线上 `LiveDashboard-CiAkZ4yu.js` / `UserManagement-97qO9yGl.js` 已包含 `machine_binding` 和 `bound_machine_id`；生产 Playwright 验证桌面 `1440x900` 与手机 `390x844` 均跳到 `/manage/admin/users?machine_binding=unbound&desktop=1`，用户接口请求 `/api/v1/users/?machine_binding=unbound&skip=0&limit=10` 返回 `total=198`，页面无横向溢出。
- 配置前 `main@6c78f84` 曾新增 `backend/scripts/check_mes_mvc_preflight.py`，用于不回显密钥地检查 MES MVC 配置、登录页 token 与可选登录链路；当时 ECS 运行 `PYTHONPATH=. .venv/bin/python scripts/check_mes_mvc_preflight.py --json` 返回 `adapter=null`、`mvc_configured=false`、`missing_env=MES_ADAPTER,MES_MVC_BASE_URL,MES_MVC_USERNAME,MES_MVC_PASSWORD`、`login_page.status=skipped`、`login.status=skipped`。
- 本轮已部署 `main@54ccd7c`：管理端实时态势第一屏新增“机列归属率”动态视图，线上 `LiveDashboard-CCWtW8qw.js` / `LiveDashboard-DxaRmkzM.css` 已包含 `机列归属率`、`live-machine-ownership` 和 `buildMachineOwnershipSummary`；生产 Playwright 验证桌面 `1440x900` 与手机 `390x844` 均显示 `0 已归属 · 3 待归属`、`120460.00`、`3 产出机列`，页面无横向溢出，截图留存在本地忽略目录 `frontend/test-results/visual-production/`。
- 本轮已部署 `main@32be0e2`：管理端实时聚合 API 显式返回 `machine_binding_status`，生产探针确认 `/api/v1/aggregation/live?business_date=2026-05-06` 的 3 条正产量临时机列均带 `machine_binding_status=unbound`，`all_positive_rows_have_binding_status=true`，前端与 AI 分析不再需要从负数 `machine_id` 反推归属状态。
- 本轮已部署 `main@56886c7`：按卷填报创建链路已使用 `equipment.bound_user_id` 写入 `WorkOrderEntry.machine_id`，并按 `equipment_id` 生成未来 `mobile_coil_agg` 聚合行；生产 `readyz` 返回 `status=ready`、`equipment_binding=ok`，只读探针确认既有 `2026-05-06` 聚合行仍为 `bound_rows=0`、`unbound_rows=5`、`unbound_output_kg=120460.0`，本轮未做历史回填。
- 上一轮已部署 `main@793918a`：管理端运维页新增外部 MES 状态条，线上 `LiveDashboard-CqFyBTcQ.js` / `LiveDashboard-WZX7jfx-.css` 已包含 `mes-connection-strip`、`外部 MES` 和 `MES_MVC_BASE_URL`。
- 更新前已创建数据库备份：`backups/systemd-predeploy-20260506-141130.dump`。
- 已执行后端依赖安装、Alembic 迁移、`init_master_data.py`、`init_real_master_data.py`、`create_admin.py`。
- `init_real_master_data.py` 同步默认试点排班后，目标日 `2026-05-06` readyz 统计 `schedule_row_count=195`。
- 已执行前端构建：`VITE_API_BASE_URL=/api/v1 npm run build`。
- 已修复 systemd backend `.env`：`APP_ENV=production`，`INIT_ADMIN_PASSWORD` 使用强密码；不输出真实密钥。
- 已执行 owner 账号绑定修复：`FACTORY-UM`、`FACTORY-IK`、`FACTORY-CT` 绑定到 `CPK`。
- 已验证虚拟角色二维码：`virtual_role_qr_active=96`，`virtual_role_qr_bound=96`。
- `http://8.140.218.13/readyz`：HTTP 200，返回后端 readyz JSON。
- `http://8.140.218.13/manage/admin/settings`：HTTP 200，返回前端 SPA。
- `http://8.140.218.13/manage/factory`：HTTP 200，返回前端 SPA。
- `http://8.140.218.13/manage/factory/machine-lines`：HTTP 200，返回前端 SPA。
- 生产前端资源 `FactoryDirector-CzchESVl.js` 已包含 `review-factory-live-chart`。
- 生产库 `2026-05-06` 卷级填报核对：`mobile_coil_entries=17` 历史明细仍保留；28 行 draft-only `mobile_coil_agg` 已置为 `voided`，当前 `active_mobile_coil_agg=0`、`draft_only_candidate_count=0`。
- 管理端上报状态服务仍保留卷级直录入口语义；draft-only 聚合修正后，工厂指挥服务当前返回 `overview_source=mes_projection`、`factory_command_total_output_tons=0`、`overview_today_output_tons=0`、`overview_workshop_summary_len=0`。
- 工厂指挥服务 `list_machine_lines()` 当前返回 `machine_lines_len=51`，其中 `local_source_line_count=0`；历史未绑定 draft 测试行不再作为 `local_shift_data` 机列进入管理端实时产量。
- 管理端实时态势 `/api/v1/aggregation/live?business_date=2026-05-06` 当前服务探针返回 `data_source=work_order_runtime`、`factory_output=0.0`、`positive_live_cell_count=0`，不再显示历史 draft-only 临时机列产量。
- 管理端班次节奏在无 submitted/verified/approved 卷级直录时不再展示历史 draft-only 产量节奏。
- 对账服务仍保留卷级 kg 折吨代码路径；生产 draft-only 聚合置为 `voided` 后，历史 `120460.0kg -> 120.46t` 只作为已验证过的折吨行为证据，不再作为当前活动产量。
- 自动汇总 Agent 的部署探针使用 synthetic confirmed `mobile_coil_agg` 行验证代码路径：`250000.0kg -> aggregator_output_tons=250.0`、`260000.0kg -> aggregator_input_tons=260.0`；未在生产库触发自动日报生成或写入新日报。
- ECS 到外部 MES 登录入口 `https://mes.xintaily.com/Login/Index` 网络可达：HTTP 200，`remote_ip=47.92.251.37`，`ssl_verify=0`，`time_total=0.767825s`；当前 MES 未联通不是服务器网络不可达。
- 2026-05-06 14:50 左右刷新 MES 前置核对时：ECS 到 `https://mes.xintaily.com/Login/Index` 返回 HTTP 200，耗时约 `0.268s`；当时生产运行配置中 `MES_ADAPTER` 等效为 `null`，`MES_MVC_BASE_URL`、`MES_MVC_USERNAME`、`MES_MVC_PASSWORD` 仍为空，阻塞在生产 MES 运行配置缺失。
- 2026-05-06 16:55 左右生产 MES 已切到 MVC 配置并完成同步：`MES_ADAPTER=mvc`、`mes_ready=true`、`coil_snapshots fetched=50 upserted=50`、`mes_coil_snapshots_count=50`。
- 线上部署代码的 `/api/v1/dashboard/external-readiness` 同源检查仍返回 `hard_gate_passed=False`、`module_usable=False`、`external_connection_enabled=False`，但 `MES_UNCONFIGURED`、`WORKFLOW_DISABLED` 与 `DINGTALK_DISABLED` 已解除；当前 `hard_issue_codes=LLM_DISABLED,APP_CONNECTION_DISABLED`，并通过 `DINGTALK_NO_BOUND_USERS` warning 标出当前生产库 `active_dingtalk_user_count=0`、`active_dingtalk_employee_count=0`。
- 钉钉人员绑定阻塞已定位到外部应用权限：需要在钉钉开放平台给当前应用开通 `qyapi_get_department_member` 后，才能执行通讯录同步并让 H5 免登/工作通知命中真实人员。
- `/readyz` 关键状态：
  - `environment=production`
  - `database=ok`
  - `uploads=ok`
  - `equipment_binding=ok`
  - `schedule=ok`
  - `pipeline=ok`
  - `hard_gate_passed=true`
  - `mes_sync=idle`
  - `mes_sync.configured=true`
  - `mes_sync.last_run_status=success`
  - `mes_sync.fetched_count=50`
  - `mes_sync.upserted_count=50`
  - `mes_sync.action_required=none`
  - `workflow_enabled=true`
  - `dingtalk_enabled=true`
  - `active_mobile_user_count=329`
  - `active_workshop_count=12`
  - `active_equipment_count=136`

普通移动班报机列绑定修复部署证据（2026-05-06 19:41）：

- 本地验证：新增 `backend/tests/test_mobile_shift_report_machine_binding.py` 覆盖同车间绑定、跨车间忽略、与 `mobile_coil_agg` 同机列唯一键不冲突；`python -m pytest backend/tests/test_mobile_shift_report_machine_binding.py backend/tests/test_coil_entry_auto_calc.py backend/tests/test_factory_command_service.py backend/tests/test_realtime_service.py -q` 返回 `31 passed`。
- 后端全量：`python -m pytest backend/tests -q` 返回 `697 passed, 124 deselected, 31 warnings`。
- 已部署提交：`1a1139c fix: 保留机列归属到管理端数据`，服务器 `git rev-parse HEAD` 为 `1a1139cd11ffdb5c56ac4a0d9f869e9614909626`，`main...origin/main` 干净。
- 部署后 `/readyz` 返回 `status=ready`、`equipment_binding=ok`、`pipeline=ok`、`mes_sync.last_run_status=success`、`mes_sync.fetched_count=50`、`mes_sync.upserted_count=50`。
- 服务器代码确认包含普通班报 `get_bound_machine_for_user()` 写入逻辑、`conflicting_query` 唯一键防护，以及 `FactoryMachineLineOut.machine_binding_status` 响应字段。
- 生产库只读探针：`mobile: total=0, active=0, bound=0, unbound=0`；`mobile_coil_agg: total=28, active=28, bound=0, unbound=28`；`duplicate_active_machine_keys=0`。当前没有历史普通班报可回填，本修复只影响后续提交链路。

域名链路诊断：

- `xtmijd.com` 当前只返回 SOA，无 A 记录，不能作为可访问域名使用。
- `www.xtmijd.com` 已解析到 `8.140.218.13`。
- 从服务器本机用 SNI 验证 `xtmijd.com:443 -> 127.0.0.1` 和 `xtmijd.com:443 -> 8.140.218.13`，`/readyz` 均为 HTTP 200，说明 nginx HTTPS server、证书文件和后端反代链路可用。
- 从本机公网访问 `http://www.xtmijd.com/readyz` 返回阿里云 `Server: Beaver` 的 `Non-compliance ICP Filing` 403 页面。
- 从本机公网访问 `https://www.xtmijd.com/readyz` 在 TLS 握手阶段 connection reset。

结论：HTTPS 域名链路当前阻塞在域名备案/接入合规层，不是应用 readyz、nginx upstream 或后端代码问题。本轮公网正向证据以 `http://8.140.218.13/readyz` 为准；正式对外域名需要完成 ICP 备案/接入或换用已备案域名。

外部正式联通闸门仍未完全通过，`python scripts/check_statistics_module_ready.py --json` 当前 hard fail 为：

- `LLM_DISABLED`
- `APP_CONNECTION_DISABLED`

Vercel 主线探测：

- 最近一次可确认正向记录仍是 2026-05-05 12:47 左右：`/`、`/entry`、`/manage/admin` 返回前端挂载页，`/readyz` 返回前端 SPA shell 而不是后端 readyz JSON。
- 2026-05-06 08:07 左右从本机探测 `xt-aluminnum.vercel.app:443` TCP 不通，`curl -4 https://xt-aluminnum.vercel.app/` 连接超时；因此本轮不把 Vercel 作为当前可达证据。

结论：Vercel 当前只能作为前端静态部署证据，不能证明后端、数据库、外部 MES、钉钉或应用连接 API 已正式联通。ECS 当前后端、数据库、填报排班和 nginx 基础路由已恢复到 ready；正式完全体仍取决于域名备案/接入、外部 MES、Workflow、LLM、钉钉和应用连接 API 的真实配置与验收。

## 7. 一条命令更新上线

服务器 SSH 用户认证可用后执行：

```bash
cd /srv/aluminum-bypass
./scripts/deploy_systemd_host.sh --pull http://8.140.218.13
```

如果后续切回 Docker Compose 统一部署形态，并且 AI 已正式配置后希望一起检查：

```bash
./scripts/launch_cloud_trial.sh https://你的域名 --pull
```

如果 MES、钉钉和应用连接 API 已填入真实配置，正式上线时必须加外部联通闸门：

```bash
./scripts/deploy_systemd_host.sh --pull --require-external https://你的域名
```

上线后必须确认：

```bash
cd /srv/aluminum-bypass
systemctl is-active aluminum-bypass
systemctl is-active nginx
curl -fsS http://8.140.218.13/healthz
curl -fsS http://8.140.218.13/readyz
cd backend
.venv/bin/python scripts/check_statistics_module_ready.py --json
```

## 8. 生产环境变量底线

服务器 `.env` 至少确认：

- `APP_ENV=production`
- `POSTGRES_PASSWORD` 已替换强随机值
- `SECRET_KEY` 已替换 32 位以上强随机值
- `INIT_ADMIN_PASSWORD` 已替换 12 位以上强密码
- `CORS_ORIGINS=https://你的域名`
- `VITE_API_BASE_URL=/api/v1`

外部正式联通至少确认：

- MES adapter 已启用并能访问真实外部 MES。
- Workflow 已启用。
- 钉钉应用配置完整。
- 应用连接 API 已启用，且 push mode 为 `enabled`。

## 9. 真实日报导入门禁

2026-05-06 已把 `daily_production_report` 接入现有 `ImportBatch` / `ImportRow` 审计区，作为真实报表进入正式生产事实表前的 dry-run 门禁。

已验证：

- `python -m pytest backend/tests/test_import_service_daily_production.py backend/tests/test_daily_production_canonical_service.py -q`：8 passed。
- `python -m pytest backend/tests/test_import_service_contract_report.py backend/tests/test_import_service_yield_matrix.py -q`：2 passed。
- 本地内存 SQLite 受控导入 `D:\鑫泰报表\5.5\鑫泰每日产量5月.xls`，`import_type=daily_production_report`，`total_rows=1`，`success_rows=1`，`failed_rows=0`。
- 解析结果：`business_date=2026-05-03`，`source_unit=t`，`row_count=16`，`daily_input_tons=1985.674`，`daily_output_tons=1935.649`，`month_to_date_output_tons=11258.775`，`daily_scrap_tons=50.025`，`issues=[]`。
- 同次导入 `shift_production_data_rows=0`，确认该门禁只写导入审计区，不写正式生产事实表。
- 生产写库前备份：`backups/pre-daily-production-import-20260506-210602.dump`，`backup_bytes=401988`，`pg_restore -l` 校验通过。
- 生产环境暂未安装 `xlrd`，本轮未新增依赖；使用本机只读转换出的临时 `.xlsx` 进入生产 staging，源文件仍为 `D:\鑫泰报表\5.5\鑫泰每日产量5月.xls`。
- 生产 staging 批次：`ImportBatch id=1`，`batch_no=IMP-20260506130735-d4f557`，`file_name=xintai-daily-production-2026-05-03.xlsx`，`file_path=uploads/4ee5b77a8566471c84266074fe8969d4.xlsx`，`total_rows=1`，`success_rows=1`，`failed_rows=0`。
- 生产写库复验：首行 `business_date=2026-05-03`，`source_unit=t`，`row_count=16`，`daily_output_tons=1935.649`；`ShiftProductionData` 从 28 到 28，`shift_rows_delta=0`。

下一道门禁：把导入行转为正式生产数据前，必须先做车间/机列映射、班次归属、日累计与月累计口径确认，并继续拦截 `>10000t` 的疑似 kg/t 错配数据。

## 10. 回滚锚点

当前主线回滚锚点：

```bash
git rev-parse --short HEAD
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
./scripts/backup_db.sh
```

代码回滚：

```bash
git checkout <last-good-commit>
TRIAL_BASE_URL=https://你的域名 ./scripts/deploy_trial.sh
```

数据库回滚必须先做备份校验，不要直接覆盖生产库。
