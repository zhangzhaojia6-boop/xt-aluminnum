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
