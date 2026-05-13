# 数据中枢当前部署状态

更新时间：2026-05-13 10:13:30 +08:00

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
- 管理端未显示当前测试填报的直接原因已复核：生产库 `work_order_entries` 仍为 `draft=156`、`mobile_shift_reports` 为 `draft=3`，`ShiftProductionData` 仅有 `mobile_coil_agg/voided=28`；线上当前代码已包含 `entry_status='submitted'` 和 `_aggregate_coil_to_shift()`，旧 draft 测试卷需重新提交或走带 dry-run 的人工提升门禁，不能静默转正式产量。
- 普通移动班次报表同步管理端数据时也会读取机列绑定：同车间绑定账号写入 `ShiftProductionData.equipment_id`，已有同机列聚合行时保持未绑定汇总，避免覆盖卷级聚合。
- 工厂指挥 `machine-lines` API 响应模型已保留 `machine_binding_status`，管理端不再只依赖 service 内部 dict 才能识别未绑定机列。
- 外部联通 readiness 已显式提示钉钉人员绑定缺口：`DINGTALK_ENABLED=true` 但 active 用户/员工没有 `dingtalk_user_id` 时返回 `DINGTALK_NO_BOUND_USERS` warning，避免把 token 可用误判为通知送达。
- MES 同步批内重复投影已收口：`mes_follow_cards` / `mes_dispatch` 按投影后的 `coil_id` 去重，新建 `MesCoilSnapshot` 后立即 `flush`，避免同一事务内重复落库触发唯一键冲突。
- MES MVC 会话恢复已增强：表格查询若被会话过期打回登录页，会清理 cookie/token 后重新登录并重放请求；二次仍返回登录页才报错，避免短期 session 过期让同步长期卡住。
- MES 投影同步已隔离非数据库单源失败：`sync_mes_projection()` 中 crafts/devices/follow_cards/dispatch/wip_total/stock/machine_lines 单步执行，单个外部接口失败返回该源 `failed` stats，已成功 upsert 的来源继续保留；数据库错误仍向上抛出，避免掩盖事务异常。
- 历史 `每日产量` 工作簿已接入只读 canonical 预览：`综合报表` 会输出显式吨单位、车间标签向下继承、日/月投料产出废料合计，并把超过 `10000t` 的日产量标为疑似 kg 口径，不写入数据库。
- 历史 `每日产量` 真实报表已进入生产 import staging：生产备份 `backups/pre-daily-production-import-20260506-210602.dump` 校验通过后，将 `D:\鑫泰报表\5.5\鑫泰每日产量5月.xls` 转换为临时 `.xlsx` 并写入 `ImportBatch id=1`、`batch_no=IMP-20260506130735-d4f557`；`ShiftProductionData` 写入增量为 0。
- 历史 `每日产量` 映射门禁已接入只读预览：生产 `ImportBatch id=1` 共 16 行，`ready_rows=7`、`needs_equipment_mapping_rows=0`、`unresolved_rows=9`，高置信行映射到 `ZD`、`ZR2`、`ZR3`、`RZ/RZ-XC`、`RZ/RZ-ZJ`、`LZ2050/LZ2050-1`、`JQ`；未推断 `冷轧/1650`、`冷轧/1850`、`精整/剪子`、`精整/纵剪`、`拉矫/拉矫`、`拉矫/分切`、`退火炉/拉矫`、`在线退火/新厂北线`、`在线退火/园区北线`，`ShiftProductionData` 仍为 28 行，`shift_rows_delta=0`。
- 历史 `每日产量` 5.5 报表已按锁定报告日重跑暂存：生产备份 `backups/pre-daily-production-locked-staging-20260507-1515.dump` 经 `pg_restore -l` 校验后，使用同一上传 `.xlsx` 写入 `ImportBatch id=2`、`batch_no=IMP-DAILY-LOCKED-20260507151631472379`，`business_date=2026-05-05`，`daily_output_tons=1935.649t`，映射 `16/16 ready`，其中 `equipment_bound_rows=11`、`workshop_only_rows=5`；旧 `id=1` 保留为历史旧表头批次，最新管理端预览应以 `id=2` 为准，`ShiftProductionData` 写入增量仍为 0。
- 4 月 30 日每日产量已找到可用替代表并提升正式事实：源文件为 `D:\鑫泰报表\输出skill\2026-4-30_主表完整字段填充.xls`，只读转换为 `.xlsx` 后按锁定报告日 `2026-04-30` dry-run 通过；表头仍写 `2026-04-22`，记录为 `stale_workbook_report_date` warning。写库前备份 `/srv/aluminum-bypass/backups/pre-daily-production-promote-20260430-20260513-084441.dump` 并通过 `pg_restore -l` 校验；生产 `ImportBatch id=32` 提升正式事实 `14` 行，`input=2388.531t`、`output=2345.849t`、`scrap=111.682t`，厂级看板服务层返回 `today_total_output=2345.85t`、`total_energy=194186.6`、`energy_per_ton=82.77881483420288`；转换源已移入 `/srv/aluminum-bypass/backups/import_sources/daily-production-20260430-20260513-0844/xintai-daily-production-2026-04-30-filled.xlsx` 留档，服务器 Git 工作区保持干净。
- 管理端导入历史已接入 `GET /api/v1/imports/daily-production/mapping-preview` 只读接口和“每日产量/映射门禁”卡片，展示已匹配、待机列、未解析数量与未解析标签；该视图只读，不会写入或修正 `ShiftProductionData`。
- 映射门禁未解析行已增加只读候选主数据提示：候选只从 active `workshops/equipment` 生成并在管理端显示为 `车间 ...` / `机列 ...`，不改变 `DAILY_PRODUCTION_MAPPING_RULES`，不写正式产量事实表；生产主数据核对显示 `冷轧/1650`、`冷轧/1850` 暂无直接 active 机列，精整/拉矫/在线退火相关行仍需人工确认候选。
- 管理端实时态势已增加“填报接入”只读条：`overall_progress` 输出 `formal_entry_count`、`draft_entry_count`、`total_entry_count`，班次单元格输出 `draft_count`；未绑定机列/班次的 draft 测试也会计入 `草稿待提交`，但不进入正式产量；前端显示 `已进入正式`、`草稿待提交`、`缺报班次`。
- 管理端实时聚合已支持“填报事实 + MES 归属”配对：当天填报卡号命中 MES 投影行时，即使 MES 快照没有业务日期，也会保留填报端重量/状态，只用 MES 的车间、机列、班次补齐缺失归属；卡号比较会容忍中文“一”/全角横线等操作员录入变体，移动端扫码查 MES 与 MVC 按卡查询也使用同一配对键，避免入口侧漏掉可绑定卷。
- 填报端提交链路已支持按现场卷标识绑定外部流转线索：现场录入 `R3-9216-2` 这类 `material_code` 时，会兜底匹配外部快照的 `tracking_card_no/material_code/batch_no/coil_id/qr_code`，并在新提交的 `extra_payload` 写入 `flow` 与 `mes_reference`；该能力只补充流转上下文，不覆盖操作员填报重量。
- 管理端 `异常与补录` 的 `待归属` 首屏会先读取实时活跃业务日，再拉取待归属卷级填报；当浏览器日期晚于最新填报日时，页面不再默认落到无数据的当天，而是显示最近上传业务日的缺机列/缺班次草稿。
- 管理端 `异常与补录/待归属` 已增加只读归属线索：接口返回录入账号、外部 MES 卡号命中数、MES 机列、同车间候选机列数量；前端表格显示 `录入来源` 与 `归属线索`，用于区分正常主操填报、无账号脚本/测试草稿和待人工确认机列，不直接改生产数据。
- 管理端 `异常与补录/待归属` 已接入人工确认后的绑定入账动作：管理者逐条触发 `promote_draft_entry` 后，草稿填报会绑定确认机列、提升为 `submitted`，并复用现有 `_aggregate_coil_to_shift()` 生成 `mobile_coil_agg`；多机列候选或缺班次时仍要求人工先明确归属，不做静默批量提升。
- 管理端 `异常与补录/待归属` 已支持多候选机列选择：待归属接口返回 `machine_candidates[{machine_id,machine_name}]`，前端在精整等多机列车间显示 `选择机列` 下拉，选定后才允许 `绑定入账`，避免把同车间多台机列误归到默认候选。
- 主数据已新增只读工艺业务矩阵：`GET /api/v1/master/process-business-map` 输出 `分厂/厂区 -> 车间 -> 机列 -> 工艺业务`，并在 `docs/process-business-map.md` 记录当前口径；`1650/1850`、新厂/园区在线退火拆分、`JZ2` 具体机列职责仍标为待确认，不静默写成已确认事实。
- systemd 部署脚本已改为 `npm ci --include=dev` 后再构建前端，避免生产环境清空 `node_modules` 后因 `vite` 被省略导致部署中断。
- 管理端待补产出重量人工补正入口已上线：`main@7a3a9f0` 新增 `PATCH /api/v1/aggregation/live/missing-output/{entry_id}`，仅允许补正式卷级填报中历史空产出记录，复用工单更新权限、审计、成材率重算和事件链路；管理端“待补产出重量”样例行提供“补重量”弹窗，提交后刷新实时聚合。
- 管理端 `异常与补录` 已接入“待补重量”队列：页面读取实时聚合 `data_quality.missing_output_weight`，把正式卷级填报中缺产出重量的记录列为补录任务，并复用同一个受控补正弹窗处理。
- 管理端 `异常与补录/待归属` 已接入“草稿待归属分布”热力图和只读绑定线索条：复用 `PendingAssignmentHeatmap` 和 `pendingAssignment.items`，按车间/班次展示待绑定草稿卷分布，并区分外部 MES 命中、唯一候选可入账、多候选待选择、缺班次阻断；该视图只读，不改变待归属草稿不进正式产量的边界。

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

- `python -m pytest backend/tests/test_statistics_module_ready_script.py backend/tests/test_dashboard_routes.py::test_external_readiness_dashboard_route_exposes_hard_issues backend/tests/test_quick_cloud_trial_docs_and_ops.py -q`：51 passed，1 deselected
- `python -m pytest backend/tests/test_statistics_module_ready_script.py backend/tests/test_dashboard_routes.py::test_external_readiness_dashboard_route_exposes_hard_issues backend/tests/test_quick_cloud_trial_docs_and_ops.py -q`：52 passed，1 deselected
- `git diff --check`：通过，仅 Windows LF -> CRLF 提示
- 本轮部署：`main@798bc0f` 已通过 `./scripts/deploy_systemd_host.sh --pull http://8.140.218.13` 上线；服务器 `main...origin/main` 干净，`aluminum-bypass.service` 与 `nginx.service` 均为 active。
- 生产缺失输入清单复验：`python scripts/check_statistics_module_ready.py --missing-inputs` 输出 `LLM/AI 摘要增强`、`应用连接外发`、`钉钉真实人员触达` 三行，列为 `用途 | 所在位置 | 缺失字段 | 影响范围 | 建议取值`，没有回显任何真实密钥值。
- 本轮部署：`main@19dbd5b` 已通过 `./scripts/deploy_systemd_host.sh --pull http://8.140.218.13` 上线；服务器 `main...origin/main` 干净，`aluminum-bypass.service` 与 `nginx.service` 均为 active。
- 生产 `/readyz` 复验：`status=ready`，`database/uploads/equipment_binding/schedule/pipeline=ok`，`mes_sync.last_run_status=success`、`fetched_count=50`、`upserted_count=50`。
- 生产 readiness 新命令复验：`python scripts/check_statistics_module_ready.py --json --check-live-aggregation` 返回预期 exit `2`，hard issues 仍为 `LLM_DISABLED`、`APP_CONNECTION_DISABLED`，warning 仍为 `DINGTALK_NO_BOUND_USERS`；实时聚合只读探针为 `live_aggregation_ok=true`，`live_aggregation_business_date=2026-05-12`，`live_aggregation_date_source=recent_upload`，`live_aggregation_data_source=mixed`，`live_aggregation_total_entry_count=38`，`live_aggregation_formal_entry_count=38`，`live_aggregation_draft_entry_count=0`，`live_aggregation_mes_row_count=23`，`live_aggregation_mes_match_count=24`，`live_aggregation_bound_to_machine_count=24`，`live_aggregation_pending_assignment_count=0`。
- `python -m pytest backend/tests -q`：794 passed，124 deselected，39 warnings
- `npm --prefix frontend test`：126 passed
- `npm --prefix frontend run build`：通过，保留既有 Vite 大 chunk warning
- `git diff --check`：通过，仅 Windows LF -> CRLF 提示
- 本轮部署：`main@688073b` 已通过 `./scripts/deploy_systemd_host.sh --pull http://8.140.218.13` 上线；`aluminum-bypass.service` 与 `nginx.service` 均为 active/running。
- 生产复验：公网 `/readyz` 返回 `status=ready`，`database/uploads/equipment_binding/schedule/pipeline=ok`，`mes_sync.last_run_status=success`、`fetched_count=50`、`upserted_count=50`。
- 生产只读聚合复验：`2026-05-12` 仍为 `data_source=mixed`，`factory_output=281.12t`，`data_quality.missing_output_weight.entry_count=6`；样例仍为 `entry_id=297 / S-2-062-1 / 铸三车间 / 2#机 / 小夜 / output_weight=null`，确认未自动改写真实历史重量。
- 生产路由与产物复验：内网 OpenAPI 已包含 `PATCH /api/v1/aggregation/live/missing-output/{entry_id}`；前端 dist 已包含 `aggregation/live/missing-output`、`补产出重量`、`补重量` 和 `live-missing-output-dialog`。
- 本地补录工作台复验：`npm --prefix frontend test -- reviewTaskCenter.test.js` 返回 126 passed；`npm --prefix frontend run build` 通过。Playwright mock 探针确认 `/manage/entry-center?tab=missingOutput&desktop=1` 在 390px 下显示 `待补重量`、`S-2-062-1` 和 2 个 `补重量` 按钮，补正弹窗宽度 366px，页面横向溢出为 0。
- `python -m pytest backend/tests -q`：723 passed，124 deselected，31 warnings
- `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q`：35 passed，1 deselected
- `python -m pytest backend/tests/test_coil_entry_auto_calc.py -q`：6 passed
- `python -m pytest backend/tests/test_coil_entry_auto_calc.py backend/tests/test_realtime_service.py backend/tests/test_factory_command_service.py backend/tests/test_workshop_reporting_status.py -q`：32 passed
- `python -m pytest backend/tests/test_daily_production_canonical_service.py backend/tests/test_legacy_data_profile_service.py -q`：23 passed
- `python -m pytest backend/tests/test_import_service_daily_production.py backend/tests/test_daily_production_canonical_service.py -q`：8 passed
- `python -m pytest backend/tests/test_daily_production_mapping_service.py -q`：2 passed
- `python -m pytest backend/tests/test_dingtalk_cli.py backend/tests/test_statistics_module_ready_script.py backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_current_deploy_state_tracks_current_head_and_validation_evidence backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_exec_plan_tracks_phase_progress_without_hiding_external_gates -q`：17 passed
- `python -m pytest backend/tests/test_mobile_shift_report_machine_binding.py backend/tests/test_coil_entry_auto_calc.py backend/tests/test_factory_command_service.py backend/tests/test_realtime_service.py -q`：31 passed
- `python -m pytest backend/tests/test_mobile_shift_report_machine_binding.py backend/tests/test_factory_command_routes.py backend/tests/test_factory_command_service.py backend/tests/test_realtime_service.py -q`：36 passed
- `python -m pytest backend/tests/test_aggregator_agent.py -q`：7 passed
- `python -m pytest backend/tests/test_mes_sync_service.py backend/tests/test_mes_mvc_preflight_script.py -q`：11 passed
- `python -m pytest backend/tests/test_mes_sync_service.py backend/tests/test_mes_mvc_preflight_script.py backend/tests/test_mvc_mes_adapter.py -q`：19 passed
- `python -m pytest backend/tests/test_factory_command_service.py -q`：20 passed
- `python -m pytest backend/tests/test_reconciliation_granularity.py -q`：3 passed
- `python -m pytest backend/tests/test_realtime_service.py backend/tests/test_realtime_service_contract.py -q`：9 passed
- `python -m pytest backend/tests/test_report_service_contract_lane.py backend/tests/test_realtime_service.py backend/tests/test_factory_command_service.py backend/tests/test_owner_entry_projection_fallbacks.py backend/tests/test_workshop_reporting_status.py -q`：40 passed
- `python -m pytest backend/tests/test_real_master_data.py backend/tests/test_realtime_service.py backend/tests/test_master_pagination.py backend/tests/test_report_service_contract_lane.py -q`：30 passed
- `python -m pytest backend/tests -q`：746 passed，124 deselected，31 warnings
- `python -m pytest backend/tests -m frontend_contract -q`：124 passed，675 deselected
- `npm --prefix frontend test`：124 passed
- `npm --prefix frontend run build`：通过
- `git diff --check HEAD~1..HEAD`：通过
- `./scripts/deploy_systemd_host.sh --pull http://8.140.218.13`：当前 `main` 已部署，公网 `/readyz` 返回 ready，`mes_sync last_run_status=success`、`fetched_count=50`、`upserted_count=50`、`active_workshop_count=12`、`active_equipment_count=140`
- 生产主数据核验：`seed_real_master_data()` 幂等后 `virtual_role_qr_active 96 -> 96`、`virtual_role_qr_bound 96 -> 96`；`ZXTF-1..4` 均为 `running`，QR 为 `XT-ZXTF-*`；`mes_mvc` active alias 共 17 条，`2050车间 -> LZ2050`、`热轧 -> RZ`、`拉矫车间 -> JZ`、`园区精整 -> JQ`、`新厂在线车间/园区在线车间 -> ZXTF`。
- 生产路由核验：`GET /api/v1/master/process-business-map` 未登录返回 `403`，确认路由已上线且受管理端鉴权保护；`aluminum-bypass.service` 与 `nginx.service` 均为 active/running。

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

正式试用闸门复验时应使用带实时聚合只读探针的命令，避免只看配置而漏掉管理端实时数据服务是否可计算：

```bash
python scripts/check_statistics_module_ready.py --json --check-live-aggregation
```

缺少现场输入时，可直接输出按 `用途 | 所在位置 | 缺失字段 | 影响范围 | 建议取值` 组织的清单：

```bash
python scripts/check_statistics_module_ready.py --missing-inputs
```

2026-05-13 线上复验结论：

- `hard_gate_passed=false`、`module_usable=false`、`external_connection_enabled=false`
- 已通过的基础项：`local_runnable=true`、`runtime_valid=true`、`database_ok=true`
- 已通过的业务底座：`workflow_enabled=true`、`auto_publish_enabled=true`、`auto_push_enabled=true`
- 外部 MES 当前可用：`mes_adapter=mvc`、`mes_ready=true`
- 正式外发仍缺：`llm_enabled=false`、`llm_model_ref_set=false`、`app_connection_enabled=false`、`app_connection_push_mode=disabled`
- 实时聚合只读探针用于返回 `live_aggregation_business_date`、`live_aggregation_data_source`、`live_aggregation_total_entry_count`、`live_aggregation_mes_row_count` 与 `live_aggregation_bound_to_machine_count`；当天无填报不等于探针失败，只有服务异常才进入 `LIVE_AGGREGATION_UNAVAILABLE`
- 钉钉应用已启用但未绑定真实人员：`warning_issues=DINGTALK_NO_BOUND_USERS`、`active_dingtalk_user_count=0`、`active_dingtalk_employee_count=0`

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
AUTO_PUBLISH_ENABLED=true
AUTO_PUSH_ENABLED=true
LLM_ENABLED=true
LLM_API_BASE=...
LLM_API_KEY=...
LLM_MODEL=...
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

最近一次 ECS 修复验证：2026-05-06 23:16 左右。

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
- 本轮已部署 `main@cc22abd`：MES 投影同步已隔离单源失败，`sync_mes_projection` 逐来源返回 `success/failed`；SQLAlchemy/事务错误仍向上抛出让整轮回滚。生产重启后 `http://8.140.218.13/readyz` 与 `127.0.0.1:8000/readyz` 均返回 200，`mes_sync.configured=true`、`mes_sync.last_run_status=success`、`mes_sync.fetched_count=50`、`mes_sync.upserted_count=50`，服务进程 `aluminum-bypass.service` 为 active。
- 本轮已部署 `main@1aa32bf`：历史 `每日产量` 映射预览已上线；生产只读预览 `ImportBatch id=1` 返回 `total_rows=16`、`ready_rows=7`、`needs_equipment_mapping_rows=0`、`unresolved_rows=9`，未推断标签保持 blocked，复验 `shift_rows_delta=0`。
- 本轮已部署 `main@c880265`：包含管理端“填报接入”只读条、导入历史映射候选提示、未绑定草稿入口计数，以及 systemd 前端构建稳定性修复；前端构建脚本已改为 `node node_modules/vite/bin/vite.js build --configLoader native`，不再依赖 ECS 上 `npm ci` 是否生成 `.bin/vite`。
- 公网 `/readyz` 返回 ready，`mes_sync last_run_status=success`、`fetched_count=50`、`upserted_count=50`；线上资源包含 `填报接入`、`草稿待提交`、`candidate_workshops`、`candidate_equipment`。
- 管理端实时聚合已修正未绑定草稿入口计数，公网 `/api/v1/aggregation/live?business_date=2026-05-06` 返回 `status_code=200`、`data_source=work_order_runtime`、`formal_entry_count=0`、`draft_entry_count=17`、`total_entry_count=17`；生产只读探针确认 17 条 `work_order_entries` 均缺 `machine_id` 或 `shift_id`，所以会显示在“填报接入”总数，不进入机列产量吨数。
- 本轮已部署 `main@e97f5ee`：管理端实时态势新增“车间填报接入”三段图和“草稿待归属”汇总；线上 `LiveDashboard-0fQW5w4R.js` / `LiveDashboard-BwV9nvGm.css` 已包含 `fill-workshop-flow`、`车间填报接入` 和 `pending_assignment` 消费逻辑。
- 生产只读聚合探针返回 `data_source=work_order_runtime`、`formal_entry_count=0`、`draft_entry_count=17`、`total_entry_count=17`、`factory_output=0.0`；`pending_assignment.entry_count=17`、`draft_entry_count=17`、`missing_machine_count=17`、`missing_shift_count=0`、`workshop_count=3`、`shift_count=3`、`input=149.51`、`output=120.46`。当前车间填报接入分布为 `铸三车间 0/4/4`、`2050冷轧车间 0/9/9`、`精整车间 0/4/4`（格式：正式/草稿/总卷数）。
- 本轮已部署 `main@3dff735`：`异常与补录` 新增 `待归属` 页签，后端新增 `GET /api/v1/aggregation/live/pending-assignment` 只读接口；接口复用实时聚合权限边界，只列出缺 `machine_id` 或 `shift_id` 的卷级填报，不会提交、归属或提升草稿。
- 生产只读接口探针返回 `pending_assignment_endpoint_status=200`、`pending_total=17`、`draft_entry_count=17`、`missing_machine_count=17`、`missing_shift_count=0`、`input=149.51`、`output=120.46`、`scrap=18.05`；分布为 `2050冷轧车间=9`、`精整车间=4`、`铸三车间=4`。当前实时聚合 `factory_total.output=29.85` 来自 5 条 `submitted/bound` 卷级记录，待归属草稿的 `120.46t` 仍只作为待归属压力展示，不进入正式产量总数。
- 部署后公网 `/readyz` 返回 `status=ready`，`mes_sync.configured=true`、`mes_sync.last_run_status=success`、`fetched_count=50`、`upserted_count=50`；正式 readiness 仍只剩 `LLM_DISABLED`、`APP_CONNECTION_DISABLED` hard issues 和 `DINGTALK_NO_BOUND_USERS` warning，`mes_adapter=mvc`、`mes_ready=true`。
- 2026-05-07 08:50 左右跨业务日巡检发现 `/readyz` 被 `SCHEDULE_EMPTY` 阻断：目标日 `2026-05-07` 的 `schedule_row_count=0`，但 `mes_sync.last_run_status=success`、`fetched_count=50`、`upserted_count=50`，确认阻塞不是 MES。
- 已在生产机执行 `PYTHONPATH=. .venv/bin/python scripts/init_real_master_data.py`，返回 `default pilot schedule synced: 195`；复验 `/readyz` 返回 `status=ready`、`target_date=2026-05-07`、`schedule_row_count=195`、`pipeline=ok`、`mes_sync.last_run_status=success`。
- 跨业务日排班补种方案已收口为后端启动与定时任务：lifespan 启动时先执行一次 `seed_default_pilot_schedule()`，APScheduler 使用 `DEFAULT_TIMEZONE=Asia/Shanghai` 并每天 `00:05` 注册 `default_schedule_seed`，不在 `/readyz` 中写库，不改变 MES 同步或生产事实表。
- 本轮已部署 `main@e031e6d`：远端工作区 `main...origin/main` 干净；部署后公网 `/readyz` 返回 `status=ready`、`target_date=2026-05-07`、`schedule_row_count=195`、`mes_sync.last_run_status=success`、`fetched_count=50`、`upserted_count=50`；启动日志未出现 `Default pilot schedule seed failed` 或 traceback。
- 本轮已部署 `main@0b7532d`：管理端实时态势新增 `外部联通明细` 只读动态图条，线上 `LiveDashboard-DjJo6Sq3.css` / `LiveDashboard-BNOu-Le9.js` 已包含 `external-readiness-lanes`、`LLM 摘要`、`应用连接` 和 `钉钉人员`；生产 `/api/v1/dashboard/external-readiness` 返回 `hard_codes=LLM_DISABLED,APP_CONNECTION_DISABLED`、`warning_codes=DINGTALK_NO_BOUND_USERS`、`mes_ready=true`，公网 `/readyz` 仍为 ready。
- 生产只读探针确认当前 `每日产量` 映射候选：`total_rows=16`、`ready_rows=7`、`unresolved_rows=9`、`candidate_rows=9`；填报侧现状仍是 `work_order_entries draft=156`、`mobile_shift_reports draft=3`、`mobile_coil_agg/voided=28`，所以当前测试填报未进入正式管理产量的根因仍是草稿态未提交，不是 MES 或管理端接口断链；未绑定 draft 也会进入管理端 `草稿待提交` 可见性口径。
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
- 本轮已部署 `main@99e36d9`：填报卷标识与外部流转线索绑定补丁已上线；公网 `/readyz` 返回 `status=ready`、`hard_gate_passed=true`、`mes_sync.last_run_status=success`、`fetched_count=50`、`upserted_count=50`。生产只读探针确认 `R3-9216-2` 以 `coil_identifier` 命中外部快照，`material_code=R3-9216-2`、`tracking_card_no=26RA03782`，后端提交 payload 构造会补 `current_workshop=2050车间`、`current_process=冷轧`、`next_workshop=新厂在线车间`、`next_process=北线退火` 和 `mes_reference`；当前 2026-05-12 管理端实时聚合为 `data_source=mixed`、`total_entry_count=35`、`input=319.08t`、`output=274.27t`、`scrap=19.9t`，工厂指挥 `overview_today_output_tons=274.27`。
- 本轮已部署 `main@586b636`：新增安全补录命令 `backend/scripts/enrich_mobile_coil_flow_context.py`，默认 dry-run，只在显式 `--apply` 时为已提交卷级填报补 `extra_payload.flow/mes_reference`，不改重量、状态、机列或班次。生产先 dry-run 确认 `2026-05-12 scanned=35/candidates=17/updated=0`，再创建并校验备份 `backups/pre-flow-enrichment-20260513-043519.dump`，随后执行 `--apply` 更新 17 条；复验 dry-run 返回 `candidate_count=0`、`skipped_existing_flow_count=17`，`R3-9216-2` 样例已带 `2050车间/冷轧 -> 新厂在线车间/北线退火` 与 `tracking_card_no=26RA03782`，管理端实时聚合保持 `data_source=mixed`、`total_entry_count=35`、`output=274.27t`，公网 `/readyz` 仍为 ready。
- 本轮已部署 `main@34154f3`：卷级填报后端新增重量完整性门禁，与移动端表单一致要求 `input_weight > 0`、`output_weight > 0` 且 `output_weight <= input_weight`；生产探针用真实服务代码验证缺 `output_weight` 返回 `422/output_weight_required`、产出大于投入返回 `422/output_weight_exceeds_input`，且 `work_order_entries` 与 `work_orders` 计数保持不变，公网 `/readyz` 仍为 ready。既有 6 条 2026-05-12 铸三车间空产出历史记录未自动回填，需后续在管理端作为数据质量/人工补正项处理。
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
- 管理端 `异常与补录/待归属` 已改为跟随 `/api/v1/aggregation/live/active-date` 返回的实时活跃业务日；本地验证 `npm --prefix frontend test` 为 124 passed，`npm --prefix frontend run build` 通过，文档门禁单测通过。
- 管理端 `异常与补录/待归属` 已补充只读根因线索，本地 `python -m pytest backend/tests/test_realtime_service.py backend/tests/test_realtime_routes.py -q` 返回 23 passed，`npm --prefix frontend test` 返回 124 passed；当前生产 17 条待归属的核心根因仍是 `created_by_user_id=null` 且本地外部 MES 卡号未命中。
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
- 生产只读映射预览：`batch_id=1`，`total_rows=16`，`ready_rows=7`，`needs_equipment_mapping_rows=0`，`unresolved_rows=9`；已匹配 `铸锭/->ZD/`、`铸轧/铸二->ZR2/`、`铸轧/铸三->ZR3/`、`热轧/铣床->RZ/RZ-XC`、`热轧/热轧->RZ/RZ-ZJ`、`冷轧/2050->LZ2050/LZ2050-1`、`园区剪切/->JQ/`；未推断 `冷轧/1650`、`冷轧/1850`、`精整/剪子`、`精整/纵剪`、`拉矫/拉矫`、`拉矫/分切`、`退火炉/拉矫`、`在线退火/新厂北线`、`在线退火/园区北线`；复验 `shift_rows_delta=0`。
- 2026-05-07 已新增显式锁定报告日 staging 写入：`scripts/dry_run_daily_production_import.py --write-staging` 默认先跑同一硬门禁，失败会回滚；本轮本地测试 `python -m pytest backend/tests -q` 为 `768 passed, 124 deselected, 32 warnings`，`npm test` 为 `124 pass`，`npm run build` 通过。
- 生产锁定日期重跑：`backups/pre-daily-production-locked-staging-20260507-1515.dump`，`pg_restore -l` 输出 701 行；`ImportBatch id=2`，`source_type=daily_production_report_locked`，`business_date=2026-05-05`，`quality_status=warning` 仅因表头仍写 `2026-05-03`，`total_rows=1`，`success_rows=1`，`failed_rows=0`，`preview total_rows=16`、`ready_rows=16`、`needs_equipment_mapping_rows=0`、`unresolved_rows=0`，`ShiftProductionData` 未新增正式事实行。
- 2026-05-07 已把 2026-05-05 锁定批次提升为正式生产事实：先备份 `backups/pre-daily-production-promote-20260507-165000.dump` 并通过 `pg_restore -l` 校验，再将 `ImportBatch id=2` 写入 `ShiftProductionData`；结果为 `15` 行、`daily_production_report`、`confirmed`，产量合计 `1935.649t`。生产 HTTP 复验：`GET /api/v1/dashboard/factory-director?target_date=2026-05-05` 返回 `today_total_output=1935.65`，`GET /api/v1/dashboard/workshop-director?target_date=2026-05-05&workshop_id=<LZ2050>` 返回 `85.13t`。
- 2026-05-07 已继续把 2026-05-01 至 2026-05-04 的每日产量真实报表提升为正式生产事实：服务器缺 `xlrd`，未新增生产依赖，改用本地只读转换出的 `.xlsx` 上传到 `/srv/aluminum-bypass/import_sources/daily-production/` 后解析；写库前备份 `backups/pre-daily-production-promote-5-1-5-4-20260507-170602.dump` 并通过 `pg_restore -l` 校验。新批次为 `ImportBatch id=3..6`，预检均无阻断，提升结果分别为 `2026-05-01: 14 rows / 2238.785t`、`2026-05-02: 16 rows / 2230.978t`、`2026-05-03: 16 rows / 2237.241t`、`2026-05-04: 15 rows / 2632.562t`；生产 HTTP 复验厂级看板分别返回 `2238.79`、`2230.98`、`2237.24`、`2632.56`。
- 2026-05-07 已补齐 4 月旧表映射：`拉矫/横剪 -> JZ-HJ1`、`拉矫/产量 -> JZ` 车间级、`在线退火/新厂南线 -> ZXTF-2`。本地全量验证 `python -m pytest backend/tests -q` 返回 `773 passed, 124 deselected, 32 warnings`，提交 `15f0667 fix: 补齐四月每日产量旧表映射` 已部署到 ECS，服务器 `tests/test_daily_production_mapping_service.py` 返回 `4 passed`。
- 2026-05-07 已把 4 月可通过门禁的 9 天每日产量报表提升为正式生产事实：写库前备份 `backups/pre-daily-production-promote-april-20260507-172235.dump` 并通过 `pg_restore -l` 校验；上传转换源已移入 `backups/import_sources/daily-production-april-20260507-1722/` 保留。新批次为 `ImportBatch id=7..15`，结果为 `2026-04-20: 15 rows / 2282.833t`、`2026-04-21: 16 rows / 1771.415t`、`2026-04-23: 13 rows / 1994.820t`、`2026-04-24: 12 rows / 1572.276t`、`2026-04-25: 14 rows / 2894.256t`、`2026-04-26: 15 rows / 2052.452t`、`2026-04-27: 14 rows / 2072.124t`、`2026-04-28: 14 rows / 2311.268t`、`2026-04-29: 14 rows / 2052.489t`；生产 HTTP 复验这些日期的 `factory-director` 均为 200 且返回对应吨数。
- 当前正式每日产量事实覆盖 `2026-04-20`、`2026-04-21`、`2026-04-23` 至 `2026-04-30`、`2026-05-01` 至 `2026-05-05`，共 `217` 行，均为 `data_source=daily_production_report` 且非 `voided`。其中 `ImportBatch id=1` 是早期未锁定报告日的历史暂存批次，因把 5.5 文件表头误识别为 `2026-05-03`，仅保留审计用途，不应作为管理端最新预览或正式事实来源。
- 2026-05-07 已新增真实每日能耗/气耗入库门禁：`scripts/dry_run_energy_import.py` 只读取 `各车间能耗统计表` 与 `各车间天然气用量统计表` 的用量口径，显式跳过抄表页、合计项和未建主数据的辅助项；本地全量验证 `python -m pytest backend/tests -q` 返回 `775 passed, 124 deselected, 32 warnings`，提交 `b9e9620 feat: 支持真实能耗日报入库` 已部署到 ECS，服务器 `tests/test_dry_run_energy_import_script.py` 返回 `2 passed`。
- 2026-05-07 已把 2026-05-01 至 2026-05-05 的真实能耗/气耗表写入正式 `energy_import_records`：服务器仍未新增 `xlrd`，改用本地只读转换的 `.xlsx` 上传解析；写库前备份 `backups/pre-daily-energy-promote-20260507-174300.dump` 并通过部署脚本 `pg_restore -l` 校验，转换源已移入 `backups/import_sources/daily-energy-20260507-1743/`。新批次为 `ImportBatch id=16..20`，正式能耗行分别为 `2026-05-01: 21 rows / 电 124945.7 kWh / 气 50281.0 m3`、`2026-05-02: 22 rows / 电 129754.5 kWh / 气 49396.0 m3`、`2026-05-03: 22 rows / 电 120596.0 kWh / 气 48223.0 m3`、`2026-05-04: 22 rows / 电 137814.8 kWh / 气 50045.0 m3`、`2026-05-05: 20 rows / 电 97353.5 kWh / 气 43130.0 m3`。
- 生产服务层复验：`energy_service.summarize_energy_for_date` 对 2026-05-01 至 2026-05-05 均返回对应电/气合计，`build_factory_dashboard(2026-05-05)` 返回 `today_total_output=1935.65`、`total_energy=140483.5`、`energy_per_ton=72.57694964324628`、`energy_lane_count=10`，确认管理端厂级看板可读到正式能耗记录。
- 2026-05-07 已修正 26 日气耗识别：气耗表标题 `26年4月/5月` 不再被误识别为 26 日数据行；本地全量验证 `python -m pytest backend/tests -q` 返回 `776 passed, 124 deselected, 32 warnings`，提交 `35dc17b fix: 修正能耗日报26日气耗识别` 已部署到 ECS，服务器 `tests/test_dry_run_energy_import_script.py` 返回 `3 passed`。
- 2026-05-07 已把 2026-04-20 至 2026-04-30 的真实能耗/气耗表写入正式 `energy_import_records`：写库前备份 `backups/pre-daily-energy-promote-april-20260507-1804.dump` 并通过部署脚本 `pg_restore -l` 校验，转换源已移入 `backups/import_sources/daily-energy-april-20260507-1804/`。新批次为 `ImportBatch id=21..31`，正式能耗行合计 `230` 条；生产复验显示 `2026-04-20..2026-04-30` 均返回 10 个车间聚合行，其中 `2026-04-26` 已恢复为 `电 122852.0 kWh / 气 49221.0 m3`。
- 生产服务层复验：`build_factory_dashboard(2026-04-26)` 返回 `today_total_output=2052.45`、`total_energy=172073.0`、`energy_per_ton=83.83777062752259`、`energy_lane_count=10`，确认 4 月正式能耗记录已经进入管理端厂级看板口径。

- 2026-05-13 已新增实时聚合数据质量摘要：`/api/v1/aggregation/live` 返回 `data_quality.missing_output_weight`，只统计正式 `mobile_coil` 填报中产出重量为空的记录，并保留最多 10 条带车间、机列、班次、流转卡号的样例。该口径用于管理端显式提示历史“待补产出重量”，不自动猜测或回填真实产量；本地验证 `backend/tests/test_realtime_service.py backend/tests/test_realtime_routes.py backend/tests/test_mobile_submit_with_locked_fields.py` 为 `43 passed`，完整后端测试为 `790 passed, 124 deselected, 38 warnings`，前端构建通过。生产已部署 `main@e9254c2`，`/readyz` 为 ready；HTTP 复验 `business_date=2026-05-12` 返回 `data_source=mixed`、`total_entry_count=36`、`factory_output=281.12t`、`data_quality.missing_output_weight.entry_count=6`，首条样例为 `entry_id=297 / S-2-062-1 / 铸三车间 / 2#机 / 小夜`。管理端 `LiveDashboard.vue` 已接入该字段并显示“待补产出重量”提示带；前端验证 `npm --prefix frontend test -- managementCommandCenter.test.js` 为 `125 passed`，`npm --prefix frontend run build` 通过，Playwright 视觉探针确认 `1366px` 与 `390px` 宽度横向溢出均为 `0`；生产 dist 已确认包含 `待补产出重量` 与 `live-missing-output`。
- 2026-05-13 本地已新增“待补产出重量”受控人工补正闭环：`PATCH /api/v1/aggregation/live/missing-output/{entry_id}` 只允许管理端补正式 `mobile_coil` 且当前产出为空的记录，请求以吨为单位提交 `output_weight` 与 `reason`，服务层转换为 kg 后复用 `work_order_service.update_entry()`，继续走既有审计、权限、成材率重算和事件链路；产出为空、已存在产出、投入缺失、产出大于投入、原因空白均有明确错误。管理端实时页样例行新增 `补重量`，弹窗只收产出重量和补正原因，成功后刷新实时聚合。本地验证：后端路由红绿 `2 passed`，后端服务 + 路由 `12 passed, 1 warning`，关联后端 `46 passed, 1 warning`，前端 `126 passed`，构建通过；Playwright mock 探针确认 1366px/390px 横向溢出均为 `0`，填写 `2.1t` 和“现场复核产出重量”后出现“产出重量已补正”。该能力不自动回填生产 6 条历史记录，需现场提供真实产出后逐条补正。
- 2026-05-13 管理端 `异常与补录/差异` 已接入真实 open 差异清单：页面请求 `/api/v1/reconciliation/items?business_date=<date>&status=open`，逐条展示 `production_vs_mes` 等差异的车间/班次维度、来源对、字段、差异值与风险等级，并提供 `详情` 到 `/manage/reconciliation/detail/:id`、`核对中心` 到 `/manage/reconciliation?business_date=<date>&status=open` 的处理入口；核对中心读取 query 初始化筛选，且强制桌面入口会保留 `desktop=1`。若清单接口失败但 dashboard 仍返回 open count，保留汇总占位。验证：红灯断言后 `npm --prefix frontend test -- reconciliationDispositionValidation.test.js reviewTaskCenter.test.js` 为 `126 passed`，`npm --prefix frontend run build` 通过；390px Playwright mock 探针确认真实差异行 `#77` 可见、包含外部 MES 线索、操作区有 2 个按钮、页面横向溢出为 `0`，点击 `核对中心` 后 URL 为 `/manage/reconciliation?business_date=2026-04-23&status=open&desktop=1`。
- 2026-05-13 管理端 `差异核对中心` 列表已改成业务口径：`production`/`shift_production_data` 显示为 `填报端产量`，`mes`/`mes_export` 显示为 `外部 MES`，来源值和差异值按字段补单位，`XT-ZD-1` 等机列维度保留可读展示；从列表进入详情会保留 `desktop=1`。验证：先写红灯断言后 `npm --prefix frontend test -- reconciliationDispositionValidation.test.js reviewTaskCenter.test.js` 为 `126 passed`，`npm --prefix frontend run build` 通过；390px Playwright mock 探针确认 `填报端产量 / 外部 MES / +15 吨` 可见，列表与详情页横向溢出均为 `0`，详情 URL 为 `/manage/reconciliation/detail/11?desktop=1`。
- 2026-05-13 管理端 `差异详情` 已同步业务口径：来源显示为 `填报端产量` 与 `外部 MES`，机列维度、核对字段、来源值和差异值均为业务标签并带单位；新增 `返回核对中心`，保留 `business_date/status/reconciliation_type/desktop=1` 查询状态。验证：红灯断言后 `npm --prefix frontend test -- reconciliationDispositionValidation.test.js reviewTaskCenter.test.js` 为 `127 passed`，`npm --prefix frontend run build` 通过；390px Playwright mock 探针确认详情页显示 `1175 吨 / 1160 吨 / +15 吨`、不再出现 `生产系统 / MES 系统`，返回后 URL 为 `/manage/reconciliation?business_date=2026-04-23&status=open&desktop=1`。
- 2026-05-13 已将差异核对显示口径收敛到 `frontend/src/utils/reconciliationDisplay.js`：`差异核对中心`、`差异详情`、`异常与补录/差异` 共用同一套来源标签、字段标签、组合维度解析和按字段补单位格式化，避免管理端对填报端产量与外部 MES 机列数据的显示口径分叉。验证：`npm --prefix frontend test -- reconciliationDispositionValidation.test.js reviewTaskCenter.test.js` 为 `128 passed`，`npm --prefix frontend run build` 通过，`PLAYWRIGHT_BASE_URL=http://127.0.0.1:5185 npm --prefix frontend run e2e -- e2e/reconciliation-center.spec.js` 为 `5 passed`。
- 2026-05-13 生产排查确认实时聚合当前活跃业务日为 `2026-05-12`，该日填报端正式记录 `36` 条、非空机列格子 `9` 个、聚合来源 `mixed`；`2026-05-13` 暂无正式/草稿填报记录。外部 MES 卷快照可通过流转卡/材料号匹配填报记录，但当前批次 `machine_code` 全为空；后端已补强 MES 路线机列绑定：当直接机列为空时，用 `current_workshop/current_process/next_workshop/next_process` 解析车间和工艺，只在本车间唯一物理机列或工艺类型唯一匹配时补出机列，多机列歧义保持待归属。验证：`python -m pytest backend/tests/test_realtime_service.py backend/tests/test_realtime_routes.py -q` 为 `37 passed, 1 warning`，`python -m pytest backend/tests -q` 为 `796 passed, 124 deselected, 39 warnings`。
- 2026-05-13 已给 `/api/v1/aggregation/live` 补充管理端可直接展示的实时状态字段：`business_date_context` 返回请求业务日、当前自然业务日、活跃填报业务日、最新填报业务日以及各日期填报记录数，避免 `2026-05-13` 无填报时被误判为管理端没有实时数据；`mes_machine_binding` 返回外部 MES 行数、已解析机列数、路线推断数、上游机列码缺失数、填报记录匹配数、已绑机列数和待归属机列数。该切片不改变聚合重量口径，只把已有后端判定显式暴露给前端。验证：新增红绿测试覆盖日期上下文和外部 MES 绑定统计，`python -m pytest backend/tests/test_realtime_service.py backend/tests/test_realtime_routes.py -q` 为 `39 passed, 1 warning`，完整后端测试为 `798 passed, 124 deselected, 39 warnings`。生产已部署 `main@c1d176b`，`/readyz` 返回 ready；认证 HTTP 探针 `business_date=2026-05-12` 返回 `business_date_context.current_business_date=2026-05-13`、`current_date_entry_count=0`、`active_business_date=2026-05-12`、`active_date_entry_count=36`，同时返回 `mes_machine_binding.mes_row_count=21`、`route_inferred_machine_count=8`、`upstream_machine_code_missing_count=21`、`fill_entries_with_mes_match=22`、`fill_entries_bound_to_machine=22`。
- 2026-05-13 管理端实时页已接入上述字段，新增 `实时数据日期 / 填报端上传 / 外部 MES 机列绑定` 紧凑状态条，直接显示当前展示日期、今天是否有填报、最近有效填报日、外部 MES 行数、匹配填报数、已绑机列数、路线推断数和上游机列码缺失数。验证：红灯先失败于 `buildLiveRealityStatus` 未导出；实现后 `npm --prefix frontend test -- managementCommandCenter.test.js` 为 `129 passed`，`npm --prefix frontend run build` 通过，`PLAYWRIGHT_BASE_URL=http://127.0.0.1:5185 npm --prefix frontend run e2e -- e2e/admin-surface.spec.js` 为 `10 passed`，覆盖 `1366px` 与 `390px` 无横向溢出。
- 2026-05-13 已修正管理端实时页停留在空白当前日时看不到跨业务日填报的问题：生产只读探针确认当前自然日 `2026-05-13` 无填报，但最近有效上传业务日为 `2026-05-12`，该日 `mobile_coil/submitted=37`、`mobile_coil_agg/pending=9`、实时聚合 `data_source=mixed`、产出 `284.6t`，外部 MES 投影 `23` 行，填报命中 MES `24` 卷且已绑定机列 `24` 卷。前端新增自动实时日期模式：默认跟随最近填报业务日；若页面正在显示当前日且当前日为空，收到其他业务日 `entry_submitted` 事件时自动切到该业务日；用户手动选历史日期后不被实时事件打断。验证：新增 `shouldSwitchToRealtimeBusinessDate` 纯函数测试，`npm --prefix frontend test -- managementCommandCenter.test.js` 为 `131 passed`，`npm --prefix frontend run build` 通过。生产已部署 `main@62beb12`，`aluminum-bypass` 与 `nginx` 均为 active，`/readyz` 为 ready；线上前端资产 `LiveDashboard-DLZmEtSH.js` 与 `LiveDashboard-Dyq2cv9y.css` 已更新。生产 Playwright 复验 `/manage/admin/settings?desktop=1` 在 `1366px` 与 `390px` 均显示 `当前显示 2026-05-12`、`填报端 37 卷`、`匹配填报 24 卷`、`已绑机列 24 卷`、`外部 MES 23 行`，`body/root` 横向溢出均为 `0`；服务层复验返回 `active.business_date=2026-05-12`、`data_source=mixed`、`factory_total.output=284.6`、`fill_entries_with_mes_match=24`、`fill_entries_bound_to_machine=24`。
- 2026-05-13 已完成管理端 10w 级异常产量复验：4.30 真实日报补入后，生产 `ShiftProductionData` 非 `voided` 活跃行 `254`，折吨后 `>=10000t` 的活跃行 `0`，最大折吨单行仍为 `1163.0t`。生产服务探针显示 `2026-05-12` 厂级看板、车间看板和实时聚合均为 `281.12t`，七日走势最大 `355.97t`；`2026-05-13` 当天厂级、车间和实时聚合均为 `0.0t`，对应当天暂无填报。新增回归测试 `test_build_history_digest_converts_mobile_coil_aggregate_kg_to_tons` 锁定历史走势/月累计必须把 `mobile_coil_agg` 原始 kg 折为吨，防止 `/manage/factory` 再出现 kg 当吨的 10w 级显示。

下一道门禁：`2026-04-22` 每日产量文件源表日产量列为空，当前原始表解析结果为 `blocked / rows=0`；`D:\鑫泰报表\输出skill\2026-4-22_日均报表.xls` 不是当前“每日产量综合报表”格式，解析为 `no_daily_production_summary_sheet`。该日 `日报正文.txt` 写明热轧日产 `262t`，但 `日均报表.xls` 的“各工序产量报表”中 `热轧` 行日产量为 `0t`，且表内混有包装/在制类行，所以当前只能作为参考资产，不能作为正式每日产量事实源。后续如需补这一天，必须先找到同日非空综合日报源表或现场确认可用替代表，不能用当前空表或口径冲突表强行入库。

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
