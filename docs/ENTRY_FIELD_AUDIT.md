# 录入端字段完整性审计

审计日期：2026-04-26

本轮只审计并轻量补齐前端录入端字段呈现，不修改后端模型、数据库表、migration 或 MES 对接逻辑。

## 审计来源

- 当前前端录入页：`CommandEntryHome.vue`、`ShiftReportForm.vue`、`DynamicEntryForm.vue`
- 当前模板接口字段：`/templates/{templateKey}` 对应 `backend/app/core/workshop_templates.py`
- 当前 work-order / mobile schema：`backend/app/schemas/work_orders.py`、`backend/app/schemas/mobile.py`
- 当前 e2e：`mobile-entry-smoke.spec.js`、`zd1-machine-smoke.spec.js`
- 业务文档：`docs/SYSTEM_CENTER.md`、`docs/current-route-map.md`、`docs/known-gaps-and-todos.md`
- MES 边界文档：`docs/mes-handover-brief-front-back-process-2026-04-13.md`、`docs/mes-field-mapping-table-phase1.md`

## 字段差异表

| 字段名 | 中文名 | 当前是否已有 | 所属角色 | 所属阶段 | Phase 1 必填 | 依赖 MES | 当前处理建议 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `alloy_grade` | 合金牌号 / 合金成分 | 是，高级表单模板字段 | 主操 | 基础信息 | 是 | 否 | 保持高级表单 |
| `batch_no` | 批次号 / 批号 | 是，冷轧/精整/剪切模板字段 | 主操 | 基础信息 | 是，适用模板必填 | 否 | 保持高级表单 |
| `input_spec` / `ingot_spec` | 要求规格 / 上机规格 / 铸锭规格 | 是，按车间模板字段 | 主操 | 基础信息 | 是，适用模板必填 | 否 | 保持高级表单 |
| `on_machine_time` | 上机时间 | 是，高级表单模板字段 | 主操 | 重量时间 | 否 | 否 | 保持高级表单 |
| `off_machine_time` | 下机时间 | 是，高级表单模板字段 | 主操 | 重量时间 | 否 | 否 | 保持高级表单 |
| `input_weight` | 上机重量 / 投入重量 | 是，高级表单和快速填报均有 | 主操 | 重量时间 | 是 | 否 | 保持主表单必填 |
| `output_weight` | 下机重量 / 产出重量 | 是，高级表单和快速填报均有 | 主操 | 重量时间 | 是，慢工序接续时可延后 | 否 | 保持主表单必填规则 |
| `scrap_weight` | 废料 | 是，部分模板可填；部分模板只读计算 | 主操 / 系统 | 废料成品率 | 否 | 否 | 保持模板口径 |
| `yield_rate` | 成品率 | 是，只读计算 | 系统 | 废料成品率 | 否 | 否 | 保持只读计算 |
| `workshop_id` / `workshop_name` | 车间 | 是，当前班次和表单摘要字段 | 系统 | 基础信息 | 是 | 否 | 保持系统带入 |
| `machine_id` / `machine_name` | 产线 / 机台 | 是，机台账号绑定或手选 | 主操 / 系统 | 基础信息 | 适用时必填 | 否 | 保持表单选择/绑定 |
| `shift_id` / `shift_name` | 班次 | 是，当前班次和路由参数 | 系统 | 基础信息 | 是 | 否 | 保持系统带入 |
| `business_date` | 业务日期 | 是，当前班次和路由参数 | 系统 | 基础信息 | 是 | 否 | 保持系统带入 |
| `operator_notes` | 异常说明 / 班末补充确认 | 已补到高级表单可选区 | 主操 | 异常 / 班末确认 | 否 | 否 | 加入高级表单 |
| `completionMode` / `entry_type` | 班末补充确认状态 | 是，慢工序本班交接 | 主操 | 班末确认 | 否 | 否 | 保持慢工序表单 |
| `attendance_count` | 出勤人数 | 是，快速填报字段 | 主操 | 生产数据 | 是，快速填报提交时 | 否 | 保持快速填报 |
| `storage_*` / `shipment_*` | 入库、发货、结存 | 是，owner-only 成品库字段 | owner | 生产数据 | owner 场景按模板 | 否 | 不下发给普通主操 |
| `energy_*` / `gas_*` / `water_*` | 水电气 | 是，owner-only 水电气字段 | owner | 生产数据 | owner 场景按模板 | 否 | 不下发给普通主操 |
| `contract_no` | 合同号 | 后端和 owner 字段已有，普通主操不可写 | owner / MES | MES 线索 | 否 | 部分依赖 MES | owner 保留；线索区标注待 MES |
| `billet_inventory_weight` | 坯料库存重量 | owner 字段已有 | owner | MES 线索 | 否 | 否 | 计划科补录，普通主操暂缓 |
| `billet_no` | 坯料号 | 当前无正式表单字段 | MES / 主操线索 | MES 线索 | 否 | 是 | 标注待 MES / 需要人工确认 |
| `tracking_card_no` | 随行卡号 | 是，高级表单入口字段 | 主操 | MES 线索 | 是，普通主操高级表单 | 否 | 保持可选线索记录入口 |
| `mes_code` | MES 后续码 | 当前无正式表单字段 | MES | MES 线索 | 否 | 是 | 标注待 MES，不设必填 |
| `next_object_no` | 后续对象号 | 当前无正式表单字段 | MES | MES 线索 | 否 | 是 | 标注待 MES |
| `source_billet_no` | 来源坯料线索 | 当前无正式表单字段 | MES | MES 线索 | 否 | 是 | 标注待 MES |
| `current_process` | 当前所在工艺 | MES 文档字段，当前前端只读中心有说明 | MES | MES 线索 | 否 | 是 | 标注待 MES |
| `spec` | 后工序规格 | MES 文档字段；主操已有前工序规格字段 | MES | MES 线索 | 否 | 是 | 标注待 MES，避免混同前工序规格 |
| `status` | MES 状态 | MES 文档字段 | MES | MES 线索 | 否 | 是 | 标注待 MES |
| `updated_at` | MES 更新时间 | MES 文档字段 | MES | MES 线索 | 否 | 是 | 标注待 MES |

## 本轮已补字段

- `operator_notes`：在 `/entry/advanced/:businessDate/:shiftId` 普通主操高级表单中补为可选“异常说明 / 班末补充确认”。

## 暂缓字段

- 坯料号、MES 后续码、后续对象号、来源坯料线索、当前所在工艺、后工序状态、MES 更新时间。
- 暂缓原因：这些字段的正式真源和映射关系依赖 MES 方确认，当前不能伪装成已可自动追踪。

## 需要人工确认字段

- “坯料号”是否由前工序主操现场可稳定获得。
- “随行卡号”与“坯料号”是否一一对应，还是只作为现场临时线索。
- “合同号”是否允许普通主操看见，当前建议继续由计划科 owner 或 MES 提供。
- 后工序“规格”与前工序“要求规格 / 上机规格”是否同口径。

## MES 依赖边界

- 前工序采集由本系统承担。
- 后工序真实追踪依赖 MES。
- 当前“坯料 -> MES 后续对象”映射待 MES 对接确认。
- MES 后续码、来源坯料线索、后续对象号当前不作为主操必填。
- 本轮只在录入端展示“线索追踪（待 MES 对接确认）”，不表示 MES 已正式联通。
