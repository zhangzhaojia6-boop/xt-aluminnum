# 2026-05-12 填报实时数据与外部生产系统绑定审计

## 结论

线上并不是“填报端完全没有写入”。服务器只读探针显示：

- `work_order_entries` 总数：284。
- `mobile_coil` 直录记录：284。
- `mobile_coil_agg` 聚合记录：65。
- 2026-05-12 active date 来源：`recent_upload`，最近填报数：22。
- admin 视角实时聚合：`input=206.68 吨`、`output=169.66 吨`、`scrap=10.72 吨`。

真实断点是：部分填报记录虽然已写入，但 `extra_payload` 为空，没有把外部生产系统的流转线索沉淀到提交记录。现场常填的卷标识如 `R3-9216-2` 是外部快照里的 `material_code`，而原扫码/查找兜底只按 `tracking_card_no` 查，导致这些记录无法在提交时自动带出 `current_process` / `next_process`。

## 根因

- `backend/app/services/scan_lookup_service.py`
  - 原 `_latest_tracking_card_snapshot()` 只匹配 `MesCoilSnapshot.tracking_card_no`。
  - 外部生产系统里部分现场码在 `material_code`，真实批次号在 `tracking_card_no` / `batch_no`。
- `backend/app/services/mobile_report/summary.py`
  - 原 `create_coil_entry()` 只保存前端传入的 `extra_payload.flow`。
  - 当前端没有先拿到或没有带回 flow 时，后端不会在提交时兜底补外部流转上下文。

## 修复

- 新增外部快照标识兜底匹配：
  - `tracking_card_no`
  - `material_code`
  - `batch_no`
  - `coil_id`
  - `qr_code`
- `lookup_qr()` 在 QR 与 tracking card 都未命中时，继续用上述标识匹配，返回 `source='coil_identifier'`。
- `create_coil_entry()` 在提交 payload 没有 `flow` 时，用填报卷标识只读匹配外部快照，并写入：
  - `extra_payload.flow`
  - `extra_payload.mes_reference`
- 锁定字段比较补齐等价规格容忍：`1060.0` 与 `1060`、`1.20×1200×C` 与 `1.2×1200` 不再被误判为篡改。

## 边界

- 不改变正式产量聚合口径。
- 不把未经确认的外部数据直接覆盖操作员填报重量。
- 不放宽锁定字段校验；锁定字段仍按已有 token / snapshot 规则执行。
- 未命中外部快照时继续允许原有填报路径，不阻断现场录入。

## 验证

```powershell
python -m pytest backend/tests/test_scan_lookup_service.py::test_scan_lookup_hits_material_code_when_tracking_card_differs -q
python -m pytest backend/tests/test_mobile_submit_with_locked_fields.py::test_mobile_coil_entry_enriches_flow_from_mes_material_code_match -q
python -m pytest backend/tests/test_scan_lookup_service.py backend/tests/test_mobile_scan_lookup_route.py backend/tests/test_mobile_submit_with_locked_fields.py -q
python -m pytest backend/tests/test_realtime_service.py backend/tests/test_factory_command_service.py -q
python -m pytest backend/tests/test_scan_lookup_service.py backend/tests/test_mobile_scan_lookup_route.py backend/tests/test_mobile_submit_with_locked_fields.py backend/tests/test_realtime_service.py backend/tests/test_factory_command_service.py -q
python -m pytest backend/tests -q
npm --prefix frontend run build
```

结果：

- material code lookup 回归：1 passed。
- 提交流转兜底回归：1 passed。
- 扫码/锁定字段/提交链路：21 passed。
- 实时聚合/工厂指挥服务：44 passed。
- 关联后端总回归：65 passed。
- 完整后端测试：785 passed，124 deselected，38 warnings。
- 前端生产构建：通过；保留既有 Vite 大 chunk warning。

## 生产复验

部署：`main@99e36d9` 已通过 `/srv/aluminum-bypass/scripts/deploy_systemd_host.sh --pull http://8.140.218.13` 上线。

线上只读探针：

- `/readyz`：`status=ready`，`hard_gate_passed=true`，`mes_sync.last_run_status=success`，`fetched_count=50`，`upserted_count=50`。
- `R3-9216-2`：`lookup_qr()` 返回 `source=coil_identifier`，`material_code=R3-9216-2`，`tracking_card_no=26RA03782`。
- 提交 payload 构造：`_build_coil_flow_extra_payload()` 会补 `current_workshop=2050车间`、`current_process=冷轧`、`next_workshop=新厂在线车间`、`next_process=北线退火` 和 `mes_reference`。
- 2026-05-12 admin 视角实时聚合：`data_source=mixed`，`total_entry_count=35`，`input=319.08t`，`output=274.27t`，`scrap=19.9t`。

## 历史记录补录

旧填报记录早于 `main@99e36d9` 提交，不会自动拥有 `extra_payload.flow`。本轮新增只补上下文的安全命令：

```bash
python backend/scripts/enrich_mobile_coil_flow_context.py --business-date 2026-05-12 --json
python backend/scripts/enrich_mobile_coil_flow_context.py --business-date 2026-05-12 --apply --json
```

生产执行顺序：

- dry-run：`scanned_count=35`，`candidate_count=17`，`updated_count=0`。
- 备份：`backups/pre-flow-enrichment-20260513-043519.dump`，已用 `pg_restore -l` 校验。
- apply：`updated_count=17`。
- apply 后 dry-run：`candidate_count=0`，`skipped_existing_flow_count=17`。
- 复验样例 `entry_id=283 / R3-9216-2`：已带 `flow.current_workshop=2050车间`、`flow.current_process=冷轧`、`flow.next_workshop=新厂在线车间`、`flow.next_process=北线退火`、`mes_reference.tracking_card_no=26RA03782`。
- 管理端实时聚合保持 `data_source=mixed`，`total_entry_count=35`，`output=274.27t`；补录没有改变产量事实。

## 重量完整性门禁

只读盘点发现 2026-05-12 仍有 6 条铸三车间卷级填报 `output_weight=null`。这些记录已经是 `submitted` 且有机列/班次，问题不是管理端链路，而是后端旧逻辑允许空产出入库。

本轮修复：

- 后端 `create_coil_entry()` 与移动端表单一致要求 `input_weight > 0`、`output_weight > 0`。
- 若 `output_weight > input_weight`，返回 `422/output_weight_exceeds_input`。
- 生产探针验证缺产出与产出大于投入均不会新增 `work_orders` 或 `work_order_entries`。
- 既有 6 条空产出历史记录未自动回填；真实产量必须由现场人工补正或后续数据质量工作台处理。

## 实时质量摘要

为避免管理端只展示汇总吨数而掩盖历史填报缺口，实时聚合接口新增 `data_quality.missing_output_weight`：

- 只统计正式 `mobile_coil` 填报记录，不统计草稿、外部生产系统投影或班报聚合行。
- 汇总 `entry_count`、投入吨数、废料吨数，并返回最多 10 条样例，包含流转卡号、车间、机列、班次和记录 ID。
- `backend/app/services/realtime_service.py` 保留 `output_weight_missing` 标记，避免数据库空值在聚合前被 `0` 吞掉。
- `LiveAggregationOut` 已开放 `data_quality` 字段，管理端后续可直接展示“待补产出重量”。

本地验证：

```powershell
python -m pytest backend/tests/test_realtime_service.py::test_build_live_aggregation_reports_formal_mobile_entries_missing_output_weight -q
python -m pytest backend/tests/test_realtime_service.py backend/tests/test_realtime_routes.py backend/tests/test_mobile_submit_with_locked_fields.py -q
```

结果：

- 单点 TDD 回归：1 passed。
- 实时聚合 / 实时路由 / 卷级填报重量门禁：43 passed。

生产复验：

- 部署：`main@fffe050` 已通过 `./scripts/deploy_systemd_host.sh --pull http://8.140.218.13` 上线。
- `/readyz`：`status=ready`，`mes_sync.last_run_status=success`。
- HTTP API：`/api/v1/aggregation/live?business_date=2026-05-12` 返回 `data_source=mixed`，`total_entry_count=36`，`factory_output=281.12t`。
- `data_quality.missing_output_weight.entry_count=6`，样例 `entry_id=297 / S-2-062-1 / 铸三车间 / 2#机 / 小夜`，`output_weight=null`。

管理端可见层：

- `LiveDashboard.vue` 已新增“待补产出重量”提示带，读取 `data_quality.missing_output_weight`，展示缺口卷数、受影响投入/废料和样例机列。
- 前端映射函数 `buildMissingOutputWeightSummary()` 已覆盖 snake_case / camelCase，避免接口字段形态差异导致管理端丢提示。
- 前端验证：`npm --prefix frontend test -- managementCommandCenter.test.js` 为 125 passed，`npm --prefix frontend run build` 通过；Playwright 视觉探针确认 1366px 与 390px 宽度横向溢出均为 0。
- 生产最终复验：`main@e9254c2`，dist 已包含 `待补产出重量` 与 `live-missing-output`。

## 受控人工补正入口

针对上述 6 条历史空产出记录，本轮新增专用补正入口，不复用通用工单编辑接口，不自动猜测真实产出：

- 后端新增 `PATCH /api/v1/aggregation/live/missing-output/{entry_id}`，请求以吨为单位接收 `output_weight` 和 `reason`。
- 服务层只允许补正式 `mobile_coil` 且当前 `output_weight` 为空的记录；若记录不存在、已存在产出、产出小于等于 0、投入缺失、产出大于投入或原因为空，分别返回明确错误。
- 实际写库复用 `work_order_service.update_entry()`，将吨转换为 kg 后进入既有审计、权限、成材率重算和事件链路。
- 管理端“待补产出重量”样例行新增“补重量”动作，弹窗只收产出重量和补正原因；提交成功后刷新实时聚合。
- 移动端提交门禁仍是源头防线；该补正入口只处理历史空产出，不放宽后续填报规则。

本地验证：

```powershell
python -m pytest backend/tests/test_realtime_routes.py::test_realtime_routes_are_registered backend/tests/test_realtime_routes.py::test_live_missing_output_resolve_endpoint_calls_service -q
python -m pytest backend/tests/test_realtime_service.py::test_resolve_missing_output_weight_updates_submitted_mobile_entry_and_clears_quality backend/tests/test_realtime_service.py::test_resolve_missing_output_weight_rejects_output_above_input backend/tests/test_realtime_routes.py -q
python -m pytest backend/tests/test_realtime_service.py backend/tests/test_realtime_routes.py backend/tests/test_mobile_submit_with_locked_fields.py -q
npm --prefix frontend test -- managementCommandCenter.test.js reviewTaskCenter.test.js
npm --prefix frontend run build
```

结果：

- 后端路由红绿验证：2 passed。
- 后端服务 + 路由关联验证：12 passed，1 个既有 `HTTP_422_UNPROCESSABLE_ENTITY` deprecation warning。
- 实时聚合 / 实时路由 / 移动填报重量门禁：46 passed，1 个同上 deprecation warning。
- 前端静态/工具测试：126 passed。
- 前端构建：通过；保留既有 Vite 大 chunk warning。
- 本地 Playwright 视觉探针：mock 实时数据下 `待补产出重量=6`、样例行出现 `补重量`；补正弹窗在 1366px 和 390px 宽度横向溢出均为 0；填写 `2.1t` 和“现场复核产出重量”后按钮可提交，并出现“产出重量已补正”。

生产复验：

- 部署：`main@7a3a9f0` 已通过 `./scripts/deploy_systemd_host.sh --pull http://8.140.218.13` 上线。
- 服务：`aluminum-bypass.service` 与 `nginx.service` 均为 active/running；公网 `/readyz` 返回 `status=ready`，`mes_sync.last_run_status=success`、`fetched_count=50`、`upserted_count=50`。
- OpenAPI：内网 `http://127.0.0.1:8000/openapi.json` 已包含 `PATCH /api/v1/aggregation/live/missing-output/{entry_id}`，operationId 为 `live_missing_output_resolve_api_v1_aggregation_live_missing_output__entry_id__patch`。
- 前端产物：生产 dist 已包含 `aggregation/live/missing-output`、`补产出重量`、`补重量` 和 `live-missing-output-dialog`。
- 只读聚合：`2026-05-12` 仍为 `data_source=mixed`、`factory_output=281.12t`、`data_quality.missing_output_weight.entry_count=6`；样例仍为 `entry_id=297 / S-2-062-1 / 铸三车间 / 2#机 / 小夜 / output_weight=null`，确认本轮没有自动改写真实历史重量。

补录工作台接入：

- 管理端 `异常与补录` 新增“待补重量”页签和 KPI，读取实时聚合 `data_quality.missing_output_weight`。
- 任务行显示车间、班次、随行卡、录入来源、归属线索、缺失字段和风险等级，操作为 `补重量`。
- 补正弹窗复用 `PATCH /api/v1/aggregation/live/missing-output/{entry_id}`，同样只收产出重量和补正原因，提交成功后刷新工作台。
- 本地验证：`npm --prefix frontend test -- reviewTaskCenter.test.js` 返回 126 passed；`npm --prefix frontend run build` 通过；Playwright mock 探针确认 390px 下 `待补重量`、`S-2-062-1`、`补重量` 可见，补正弹窗宽度 366px，横向溢出为 0。

待归属热力图：

- 管理端 `异常与补录/待归属` 复用现有 `PendingAssignmentHeatmap`，直接读取 `pendingAssignment.items`，按车间/班次展示草稿待归属卷数。
- 风险卡同步展示 `待归属填报 n 卷`，让管理者先看到压力，再在列表中逐条选择机列并 `绑定入账`。
- 本轮只增加可视化，不新增后端接口、不改变 `promote_draft_entry` 门禁、不让草稿卷进入正式产量。
- 本地验证：先写断言后确认红灯，随后 `npm --prefix frontend test -- reviewTaskCenter.test.js` 返回 126 passed；`npm --prefix frontend run build` 通过；Playwright mock 探针确认 390px 下热力图 canvas 正常渲染，`overflowX=0`，热力图区域 `334x300`，canvas `308x249`。

待归属绑定线索条：

- 管理端 `异常与补录/待归属` 新增只读绑定线索条，同样只消费 `pendingAssignment.items`，不新增后端字段。
- 分类为 `外部 MES 命中`、`唯一候选可入账`、`多候选待选择`、`缺班次阻断`，帮助管理者先判断待归属卷到底是可直接绑定、需要选机列，还是缺班次阻断。
- 本地验证：先写断言后确认红灯，随后 `npm --prefix frontend test -- reviewTaskCenter.test.js` 返回 126 passed；`npm --prefix frontend run build` 通过；Playwright mock 探针确认 390px 下四类数字为 `1/1/2/1`，`overflowX=0`，线索条区域 `334x106`，热力图继续正常渲染。

真实差异清单接入：

- 管理端 `异常与补录/差异` 不再只依赖 `exception_lane.reconciliation_open_count` 合成一条占位任务；页面同步请求 `/api/v1/reconciliation/items?business_date=<date>&status=open`，将真实 open 差异逐条映射进异常任务表。
- 差异行展示核对类型、车间/班次维度、来源对、差异字段、差异值和风险等级；`production_vs_mes` 明确标为填报端产量与外部 MES 核对，避免把外部 MES 当成本系统身份。
- 差异行新增 `详情` 与 `核对中心` 两个入口，前者直达 `/manage/reconciliation/detail/:id`，后者带当前日期与 `status=open` 进入 `/manage/reconciliation`；核对中心已读取 query 初始化筛选条件，且在 `desktop=1` 强制桌面入口下保留该参数，复用既有确认/忽略/修正处置闭环。
- 若差异清单接口暂不可用但 dashboard 仍返回 open count，页面保留原来的汇总占位行，不隐藏风险数量。
- 本地验证：先补断言并确认 `npm --prefix frontend test -- reviewTaskCenter.test.js` 红灯失败，随后实现后 `npm --prefix frontend test -- reconciliationDispositionValidation.test.js reviewTaskCenter.test.js` 返回 `126 passed`；`npm --prefix frontend run build` 通过，仅保留既有 Vite 大 chunk warning；Playwright mock 探针确认 390px 强制桌面入口下 `#77` 差异行可见、包含 `MES`、操作区按钮数为 `2`、页面 `overflowX=0`，点击 `核对中心` 后 URL 为 `/manage/reconciliation?business_date=2026-04-23&status=open&desktop=1`，核对中心日期输入为 `2026-04-23`。

## 核对中心业务口径列表

- 管理端 `差异核对中心` 不再直出 `来源 A / 来源 B / 差异值` 的技术字段，列表改为 `填报侧 / 对照侧 / 差异`，并在单元格内显示业务来源标签和值。
- `production` / `shift_production_data` 显示为 `填报端产量`，`mes` / `mes_export` 显示为 `外部 MES`，用于清楚表达填报端实时产量与外部 MES 机列数据的核对关系。
- 产出重量、投入重量、人数、能耗按字段补单位；例如 `1175 吨 / 1160 吨 / +15 吨`，避免管理端只看到裸数字。
- `dimension_key` 保留普通机列编码如 `XT-ZD-1`，并能把 `workshop:...|shift:...|machine:...` 这类组合维度格式化成车间、班次、机列口径。
- 从核对中心进入 `差异详情` 时保留 `desktop=1`，窄屏强制桌面入口不会在处置链路中丢失。
- 本地验证：先补断言并确认 `npm --prefix frontend test -- reconciliationDispositionValidation.test.js` 红灯失败，随后实现后 `npm --prefix frontend test -- reconciliationDispositionValidation.test.js reviewTaskCenter.test.js` 返回 `126 passed`；`npm --prefix frontend run build` 通过，仅保留既有 Vite 大 chunk warning；390px Playwright mock 探针确认核对中心显示 `填报端产量`、`外部 MES`、`1175 吨`、`1160 吨`、`+15 吨`，页面 `overflowX=0`，点击详情后 URL 为 `/manage/reconciliation/detail/11?desktop=1`。
