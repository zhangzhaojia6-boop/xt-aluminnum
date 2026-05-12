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
