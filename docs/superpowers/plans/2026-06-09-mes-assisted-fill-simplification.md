# MES 辅助填报简化执行计划

> 面向后续 agent 执行：按 TDD 执行，每个阶段先写失败测试，再改代码，再跑验证。不要一次性大改。不要直连外部 SQL Server。不要把 MES 原始数据混进“填报明细”当作人工填报记录。

## 目标

让主操扫码后，系统从数据中枢本机已经同步好的 MES 投影表中自动带出能确定的字段：随行卡号、合金、规格、上下机重量、上下机时间、工序、机列提示。人工只补系统无法可靠判断的字段，如废料、套筒、异常说明。

业务上要做到三件事：

- 手机填报更省事：扫码后能自动填的字段自动填，并锁定，避免人手改乱。
- 管理端更可信：MES 只做“辅助和对照”，不能伪装成人工填报。
- 缺报更清楚：能看出是“MES 有工序但本地没填”、“本地填了但重量不一致”、“MES 批号没映射到随行卡”、“机列没匹配”。

## 当前系统事实

- 系统名是 `鑫泰铝业 数据中枢`，MES 是外部数据源，不是本系统名称。
- 后端已有本机投影表：`MesCoilSnapshot` 和 `MesWorkshopProcessRecord`，位置在 `backend/app/models/mes.py`。
- 扫码入口已有：`backend/app/services/scan_lookup_service.py::lookup_qr`。
- 当前扫码只锁定 `tracking_card_no`、`alloy_grade`、`input_spec`，常量是 `SUBMISSION_LOCK_KEYS`。
- 手机端已有两套扫码赋值入口：`UnifiedEntryForm.vue` 和 `CoilEntryWorkbench.vue`。
- 缺报导出服务已经存在：`backend/app/services/missing_report_export_service.py`，执行时不要重复新建同名文件。
- 实时接口已有：`/aggregation/live/fill-details`、`/aggregation/live/pending-assignment`、`/aggregation/live/missing-report-export`。
- 业务日期口径已有：`backend/app/core/business_time.py`，生产填报按早上 `07:30` 起算，内勤每日填报按 `10:00` 起算。本计划只处理主操卷级填报，默认使用生产业务日。
- 当前工作区可能已有未提交改动。执行前必须先 `git status --short`，不得覆盖非本阶段文件。

## 不做的事

- 不修改 MES 同步任务本身。
- 不直接从手机端或页面连接 SQL Server。
- 不把数据库账号、密码、IP 写入代码、测试、文档或前端。
- 不把 MES 记录写入 `work_order_entries` 伪造成填报。
- 不改变能耗、耗材、质检、回收、大修、内勤每日填报口径。
- 不重构前端视觉，不新建大页面。只在现有手机填报和管理端对照位置做最小展示。

## 数据流

```text
外部 MES
  ↓ 已有同步任务
mes_coil_snapshots / mes_workshop_process_records
  ↓ 只读整理
mes_assisted_fill_service
  ↓ 合并到扫码返回
/api/v1/mobile/scan-lookup
  ↓
手机填报页自动填入并锁字段
  ↓ 人工提交
work_order_entries / mobile_shift_reports
  ↓ 对照
mes_fill_gap_service
  ↓
车间看板 / 填报明细对照区 / 缺报 Excel
```

## 字段口径

| 前端/填报字段 | 主来源 | 降级来源 | 单位 | 锁定 |
| --- | --- | --- | --- | --- |
| `tracking_card_no` | `MesCoilSnapshot.tracking_card_no` | 扫码值 | 原值 | 是 |
| `alloy_grade` | `MesCoilSnapshot.alloy_grade` | 无 | 原值 | 是 |
| `input_spec` | `MesWorkshopProcessRecord.source_payload.BeginSpecification` | `MesCoilSnapshot.spec_display` | 原值 | 是 |
| `output_spec` | `MesWorkshopProcessRecord.source_payload.EndSpecification` | 无 | 原值 | 是 |
| `input_weight` | `MesWorkshopProcessRecord.input_weight_kg` | 无 | kg | 是 |
| `output_weight` | `MesWorkshopProcessRecord.output_weight_kg` | 无 | kg | 是 |
| `on_machine_time` | `source_payload.BeginDatetime` | 无 | 本地时间 `HH:mm` | 是 |
| `off_machine_time` | `MesWorkshopProcessRecord.end_time` | `source_payload.EndDatetime` | 本地时间 `HH:mm` | 是 |
| `material_state` | `MesCoilSnapshot.material_state` | 无 | 原值 | 是 |
| `current_workshop/current_process` | 最新工序记录 | 卷快照字段 | 原值 | 否，只作提示 |
| `scrap_weight/spool_weight` | 人工填报 | 无 | kg | 否 |

原则：

- 存储层继续用 kg，不在后端自动转吨。
- 管理端展示可按现有格式转吨，但不能改原始填报单位。
- 自动带出的字段必须进入 `locked_fields_snapshot` 和签名 token。
- 用户提交时如果改了锁定字段，后端必须拒绝。
- MES 有值但本地已有人工填报时，不自动覆盖历史填报，只在对照区显示差异。

## 阶段 0：执行前门禁

目的：保护已有改动，避免执行计划时误覆盖正在施工的文件。

步骤：

- [ ] 运行 `git status --short`。
- [ ] 如果存在和本计划同文件的未提交改动，先读 diff，确认是继续接着做还是另起分支。
- [ ] 运行当前基线测试：

```powershell
python -m pytest backend/tests/test_scan_lookup_service.py backend/tests/test_mobile_scan_lookup_route.py backend/tests/test_mobile_submit_with_locked_fields.py -q
npm --prefix frontend test -- coilEntryWorkbench.scan.test.js manageFillDetailsAudit.test.js
```

通过标准：

- 测试能跑起来。
- 如果失败，先判断是否是已有未提交改动导致。不是本计划引起的问题，不要顺手修，先记录。

回滚：

- 阶段 0 不改代码，无需回滚。

## 阶段 1：后端 MES 辅助字段服务

目的：把本机 MES 投影数据整理成扫码可用字段。

文件：

- 新建 `backend/app/services/mes_assisted_fill_service.py`
- 新建 `backend/tests/test_mes_assisted_fill_service.py`

测试先行：

- [ ] 写测试：命中卷快照和最新工序记录时，返回全部可带字段和锁字段。
- [ ] 写测试：只有卷快照没有工序记录时，只返回卷号、合金、上机规格、料态。
- [ ] 写测试：找不到随行卡时，返回空字段，不抛 500。
- [ ] 写测试：时间字段带时区时转成本地 `HH:mm`。
- [ ] 写测试：同一批号多条工序时，按 `end_time` 最新优先，`end_time` 为空时按 `id` 兜底。

实现要求：

- 输入只接受 `tracking_card_no` 或扫码识别出的等价标识。
- 查询顺序：`tracking_card_no`、`qr_code`、`material_code`、`batch_no`。
- 工序关联优先用 `snapshot.batch_no` 匹配 `MesWorkshopProcessRecord.batch_no`。
- 不在服务内写数据库。
- 不调用外部 SQL Server。
- 返回结构固定为：

```python
{
    "source": "mes_process_record | mes_coil_snapshot | none",
    "fields": {...},
    "lock_keys": [...]
}
```

验证命令：

```powershell
python -m pytest backend/tests/test_mes_assisted_fill_service.py -q
```

通过标准：

- 新测试全部通过。
- 未修改扫码接口行为。

回滚：

- 删除新服务和新测试即可。

## 阶段 2：合并到扫码接口和锁字段

目的：扫码返回里带上 MES 辅助字段，并让后端锁字段校验继续生效。

文件：

- 修改 `backend/app/services/scan_lookup_service.py`
- 修改 `backend/tests/test_scan_lookup_service.py`
- 修改 `backend/tests/test_mobile_scan_lookup_route.py`
- 修改 `backend/tests/test_mobile_submit_with_locked_fields.py`

测试先行：

- [ ] 扫 `qr_code` 命中卷和工序时，`header_fields` 包含 `output_spec/input_weight/output_weight/on_machine_time/off_machine_time`。
- [ ] `lock_keys` 包含所有自动填入的可锁字段。
- [ ] `lock_token` 解开后包含同样字段和值。
- [ ] 提交时篡改 `output_weight` 或 `off_machine_time` 会被拒绝。
- [ ] 扫机台二维码时仍返回 `machine_identity`，不受 MES 辅助逻辑影响。

实现要求：

- 扩展 `SUBMISSION_LOCK_KEYS`，不要绕过现有 `locked_fields_service`。
- `_coil_payload` 保留原有字段，并用辅助字段补充，不删除现有 `flow` 相关字段。
- 如果 MES 辅助服务返回空，扫码接口行为必须和现在一致。
- 如果辅助字段和卷快照字段冲突，工序记录优先，卷快照只做降级。

验证命令：

```powershell
python -m pytest backend/tests/test_mes_assisted_fill_service.py backend/tests/test_scan_lookup_service.py backend/tests/test_mobile_scan_lookup_route.py backend/tests/test_mobile_submit_with_locked_fields.py -q
```

通过标准：

- 主操扫码路径通过。
- 机台二维码登录/识别路径不退化。
- 锁字段 token 测试通过。

回滚：

- 回退 `scan_lookup_service.py` 和相关测试。
- 阶段 1 服务可保留但不被调用，风险低。

## 阶段 3：手机填报页自动赋值

目的：用户扫码后在现有表单里看到自动带出的字段。

文件：

- 修改 `frontend/src/views/mobile/UnifiedEntryForm.vue`
- 修改 `frontend/src/views/mobile/CoilEntryWorkbench.vue`
- 修改 `frontend/tests/coilEntryWorkbench.scan.test.js`

测试先行：

- [ ] 源码测试确认两个页面都映射同一批字段：`tracking_card_no/alloy_grade/input_spec/output_spec/input_weight/output_weight/on_machine_time/off_machine_time/material_state`。
- [ ] 源码测试确认扫码后会更新 `lockedFieldsSnapshot` 和 `lockedFieldsToken`。
- [ ] 源码测试确认 `spec` 字段自动填入后会同步规格拆分输入。

实现要求：

- 不重写页面布局。
- 不新增解释性文案。
- 只给现有字段赋值，字段不存在时跳过。
- `CoilEntryWorkbench` 和 `UnifiedEntryForm` 使用同一套字段映射思路，避免两个页面行为不一致。
- 锁定字段继续用现有禁用态，不额外造一套状态。

验证命令：

```powershell
npm --prefix frontend test -- coilEntryWorkbench.scan.test.js manageFillDetailsAudit.test.js
npm --prefix frontend run build
```

通过标准：

- 扫码后字段自动填入。
- 自动字段不可编辑。
- 前端构建通过。

回滚：

- 回退两个 Vue 文件和测试。后端仍可返回扩展字段，前端忽略时不影响旧流程。

## 阶段 4：MES 填报差异服务

目的：把 MES 工序和本地填报做对照，但不把 MES 记录塞进填报明细。

文件：

- 新建 `backend/app/services/mes_fill_gap_service.py`
- 新建 `backend/tests/test_mes_fill_gap_service.py`

测试先行：

- [ ] MES 有工序，本地同业务日没有填报，标记 `missing_local_entry`。
- [ ] MES 批号找不到卷快照，标记 `mes_batch_unmapped`。
- [ ] 本地填报有记录但没机列，标记 `local_entry_unassigned`。
- [ ] MES 下机重量和本地 `output_weight` 差异超过 1 kg，标记 `weight_mismatch`。
- [ ] 已匹配且重量在容差内，标记 `matched`。
- [ ] 传 `workshop_id` 时只能看本车间。

实现要求：

- 使用 `MesWorkshopProcessRecord.business_date` 和 `WorkOrderEntry.business_date` 对齐。
- 若需要从时间推业务日，使用 `production_business_window`，不要写第二套 07:30 逻辑。
- 输出包括 `summary` 和 `items`。
- `items` 必须包含：状态、车间、工序、批号、随行卡、本地填报 ID、MES 重量、本地重量、MES 机列、本地机列。
- 不写入业务表。

验证命令：

```powershell
python -m pytest backend/tests/test_mes_fill_gap_service.py -q
```

通过标准：

- 以上状态都被测试覆盖。
- 无数据库写入。

回滚：

- 删除新服务和新测试。

## 阶段 5：实时接口、导出和管理端对照区

目的：让管理端能看到 MES 对照结果，但不污染现有填报明细。

文件：

- 修改 `backend/app/schemas/realtime.py`
- 修改 `backend/app/routers/realtime.py`
- 修改 `backend/app/services/missing_report_export_service.py`
- 修改 `backend/tests/test_missing_report_export_service.py`
- 修改 `backend/tests/test_realtime_routes.py`
- 修改 `frontend/src/api/realtime.js`
- 修改 `frontend/src/views/manage/fill-details/FillDetailsPage.vue`
- 修改 `frontend/src/views/manage/workshop-dashboard/WorkshopDashboardPage.vue`
- 修改 `frontend/tests/manageFillDetailsAudit.test.js`

测试先行：

- [ ] 后端接口 `/aggregation/live/mes-fill-gaps` 返回模型测试。
- [ ] 车间主任访问时只能返回自己车间。
- [ ] 普通主操不能访问管理端对照接口。
- [ ] 缺报 Excel 新增 `MES异常明细` 工作表。
- [ ] 前端 API 存在 `fetchMesFillGaps`。
- [ ] 填报明细页新增的是“MES 对照/异常区”，不是把 MES 行混进人工填报表格。
- [ ] 车间看板只显示本车间 MES 对照摘要和异常条数。

实现要求：

- 新接口走 `get_realtime_user` 和 `_resolve_stream_scope`。
- 加限流，参考现有 realtime 路由。
- Excel 保留原有 `缺报明细`、`车间汇总`，只追加第三张表。
- 管理端显示只做紧凑对照区，不新增大页面。
- 空状态明确显示“暂无 MES 对照异常”，不能显示成缺报。
- 接口失败时页面不能白屏，保持旧数据区可用。

验证命令：

```powershell
python -m pytest backend/tests/test_mes_fill_gap_service.py backend/tests/test_missing_report_export_service.py backend/tests/test_realtime_routes.py -q
npm --prefix frontend test -- manageFillDetailsAudit.test.js
npm --prefix frontend run build
```

通过标准：

- 管理端填报明细人工记录仍来自原 `fill-details`。
- MES 对照数据只在对照区和 Excel 附加页出现。
- 车间主任权限不越权。

回滚：

- 回退阶段 5 文件。
- 阶段 1 到 4 可保留，不会被页面使用。

## 阶段 6：端到端验收

本阶段只验证，不新增功能。

后端验证：

```powershell
python -m pytest backend/tests/test_mes_assisted_fill_service.py backend/tests/test_scan_lookup_service.py backend/tests/test_mobile_scan_lookup_route.py backend/tests/test_mobile_submit_with_locked_fields.py backend/tests/test_mes_fill_gap_service.py backend/tests/test_missing_report_export_service.py backend/tests/test_realtime_routes.py -q
```

前端验证：

```powershell
npm --prefix frontend test -- coilEntryWorkbench.scan.test.js manageFillDetailsAudit.test.js
npm --prefix frontend run build
```

浏览器验收：

- [ ] 手机端扫码命中有工序的卷，卷号、合金、规格、重量、时间自动填。
- [ ] 自动填的字段不可编辑。
- [ ] 手机端扫码只有卷快照时，至少带出卷号、合金、上机规格。
- [ ] 手机端扫机台码仍走机台识别，不误当卷。
- [ ] 填报明细页人工填报表格不出现 MES 原始行。
- [ ] MES 对照区能显示缺报、重量差异、批号未映射、机列未归属。
- [ ] 车间主任只能看到自己车间。
- [ ] 缺报 Excel 包含 `MES异常明细`。

上线前检查：

- [ ] `git diff --check`
- [ ] 确认没有密钥、IP、密码进入代码。
- [ ] 确认没有生产数据迁移。
- [ ] 确认 `/healthz`、`/readyz` 不因 MES 对照接口失败而失败。

## 风险和处理

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| MES 工序字段有空值 | 自动带不全 | 字段级降级，空值不锁 |
| 批号和随行卡映射不准 | 误判缺报 | `mes_batch_unmapped` 单独列出，不自动写入 |
| kg/吨混乱 | 产量统计错 | 后端存 kg，管理端展示按现有格式转换 |
| 页面把 MES 当填报 | 管理端误会 | 对照区单独命名，禁止混入填报明细表 |
| 车间主任越权 | 数据泄露 | 使用现有 scope 解析和权限测试 |
| 现有未提交改动被覆盖 | 施工事故 | 阶段 0 必须先处理 dirty worktree |

## 执行顺序

推荐按 6 个小提交执行：

1. `feat: map mes records into assisted fill fields`
2. `feat: enrich scan lookup with mes assisted fields`
3. `feat: apply assisted scan fields on mobile entry`
4. `feat: detect mes fill gaps`
5. `feat: expose mes fill gap detail`
6. `test: verify mes assisted fill flow`

不要跨阶段混提交。任一阶段失败，只回滚本阶段。

## 五视角评审

| 视角 | 评分 | 结论 |
| --- | ---: | --- |
| CEO | 9.7 | 直接减少一线填报时间，并把 MES 与人工填报冲突变成可见对照，业务价值清楚。 |
| 工程 | 9.6 | 不直连外部库，不改同步链路，复用扫码、锁字段、权限和导出机制，风险可控。 |
| DevEx | 9.6 | 阶段清楚，文件清楚，测试命令清楚，失败时知道从哪一层排查。 |
| 设计 | 9.5 | 不做大改版，只在现有表单和管理端增加明确反馈，避免页面臃肿。 |
| 安全/真实用户 | 9.6 | 不暴露 MES 连接信息，不越权，不自动覆盖人工填报，用户能看懂字段来源。 |

达标线：每个视角必须大于等于 9.5。当前计划可进入执行。

## GSTACK REVIEW REPORT

| Review | Result | Key changes made to plan |
| --- | --- | --- |
| plan-ceo-review | PASS 9.7 | 收敛到一线扫码减负和管理端对照可信，不扩成大改版。 |
| plan-eng-review | PASS 9.6 | 增加阶段门禁、真实文件入口、数据流、权限、回滚和测试矩阵。 |
| plan-devex-review | PASS 9.6 | 改成每阶段可执行步骤，明确失败信号和验证命令。 |
| plan-design-review | PASS 9.5 | 明确不重构视觉，只做现有表单自动填入和紧凑对照区。 |
| safety-user-review | PASS 9.6 | 增加不泄密、不直连外部库、不污染填报明细、不越权的硬门槛。 |
