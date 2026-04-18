# MES Phase 1 字段映射表

## 1. 这张表解决什么

这张表只解决一件事：

- 把 `MES -> aluminum-bypass` Phase 1 的字段落点讲清楚

它重点回答：

- 哪些字段来自 `MES`
- 这些字段在本系统里应该落到哪里
- 哪些字段应该锁定，不能让现场手改
- 哪些字段根本不该由 `MES` 提供，而应由现场补充

## 2. 先把边界说死

这个仓库里现在同时有两套录入面：

1. **卷级扫码 / 工序填报面**
   - 核心对象是 `work_orders` + `work_order_entries`
   - 适合承接“扫随行卡 -> 拉 MES 头字段 -> 填本工序事实”

2. **班组日报面**
   - 核心对象是 `mobile_shift_reports`
   - 适合承接“班次级汇总数据”

本表默认优先服务 **第 1 类：卷级扫码 / 工序填报面**。

不要把 `mobile_shift_reports` 的班组汇总字段，误当成卷级扫码页头字段。

## 3. 如何阅读这张表

状态说明：

- `已落地`：当前代码里已经有明确字段和落点
- `半落地`：契约和 adapter 已有，但本地还没变成正式一等字段
- `待确认`：业务方向已定，但还需要 `MES` 方给正式字段或样例

页面行为说明：

- `锁定`：扫码带出后默认不允许现场修改
- `可编辑`：由现场补充
- `只读`：只用于展示或查询，不作为编辑输入

## 4. A 表：Tracking Card Info -> 卷级扫码页头字段

接口来源：`GET /tracking-cards/{card_no}`

| 业务含义 | MES 字段 | Adapter 字段 | 本地落点 | 页面行为 | 状态 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| 随行卡号 | `card_no` | `CardInfo.card_no` | `work_orders.tracking_card_no` | 锁定 | 已落地 | 本地创建工单时的业务主键，MES 返回值主要用于校验 |
| 工艺路线 | `process_route_code` | `CardInfo.process_route_code` | `work_orders.process_route_code` | 锁定 | 已落地 | 当前已通过 `_apply_mes_card_info()` 回填 |
| 合金 | `alloy_grade` | `CardInfo.alloy_grade` | `work_orders.alloy_grade` | 锁定 | 已落地 | 当前已通过 `_apply_mes_card_info()` 回填 |
| 批号 | `batch_no` | `CardInfo.batch_no` | 当前无一等列；建议先落到扫码页头字段 / `extra_payload.mes_header.batch_no` | 锁定 | 半落地 | adapter 契约已有，当前 `work_orders` 没有 `batch_no` 列 |
| 卡面二维码 | `qr_code` | `CardInfo.qr_code` | 当前无一等列；建议先落到扫码页头字段 / `extra_payload.mes_header.qr_code` | 锁定 | 半落地 | 契约已有，但本地工单头尚无正式列 |
| 产品类型 | `product_type` 或 `metadata.product_type` | `CardInfo.metadata.product_type` | 建议先落到 `extra_payload.mes_header.product_type` | 锁定 | 待确认 | 当前仅在契约文档中定义为推荐字段 |
| 状态 | `status` 或 `metadata.status` | `CardInfo.metadata.status` | 建议先落到 `extra_payload.mes_header.status` | 锁定 | 待确认 | 这里指扫码时的头信息状态，不等同于卷级流转快照状态 |
| 成品规格 | `finished_spec` 或 `metadata.finished_spec` | `CardInfo.metadata.finished_spec` | 建议先落到 `extra_payload.mes_header.finished_spec` | 锁定 | 待确认 | 当前 `work_order_entries` 只有 `input_spec/output_spec`，没有统一“成品规格头字段” |
| 生产安排 | `production_schedule` 或 `metadata.production_schedule` | `CardInfo.metadata.production_schedule` | 建议先落到 `extra_payload.mes_header.production_schedule` | 锁定 | 待确认 | 用于头信息展示，不应让现场手工改主计划 |

## 5. B 表：Coil Snapshot -> 卷级投影 / 驾驶舱

接口来源：`GET /coil-snapshots`

| 业务含义 | MES 字段 | Adapter 字段 | 本地落点 | 页面/服务用途 | 状态 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| 卷唯一标识 | `coil_id` / `id` | `CoilSnapshot.coil_id` | `mes_coil_snapshots.coil_id` | 幂等 upsert 主键 | 已落地 | 当前同步主键 |
| 随行卡号 | `tracking_card_no` | `CoilSnapshot.tracking_card_no` | `mes_coil_snapshots.tracking_card_no` | 合同投影 / 实时看板关联 | 已落地 | 当前正式列 |
| 二维码 | `qr_code` | `CoilSnapshot.qr_code` | `mes_coil_snapshots.qr_code` | 扫码线索 / 对账 | 已落地 | 当前正式列 |
| 批号 | `batch_no` | `CoilSnapshot.batch_no` | `mes_coil_snapshots.batch_no` | 批次线索 / 检索 | 已落地 | 当前正式列 |
| 合同号 | `contract_no` | `CoilSnapshot.contract_no` | `mes_coil_snapshots.contract_no` | 合同推进投影 | 已落地 | 当前正式列 |
| 车间 | `workshop_code` | `CoilSnapshot.workshop_code` | `mes_coil_snapshots.workshop_code` | 车间聚合 / 看板过滤 | 已落地 | 当前正式列 |
| 当前工序 | `process_code` | `CoilSnapshot.process_code` | `mes_coil_snapshots.process_code` | 卷级流转可见性 | 已落地 | 当前正式列 |
| 机列 | `machine_code` | `CoilSnapshot.machine_code` | `mes_coil_snapshots.machine_code` | 机列视角看板 | 已落地 | 当前正式列 |
| 班次 | `shift_code` | `CoilSnapshot.shift_code` | `mes_coil_snapshots.shift_code` | 班次聚合 | 已落地 | 当前正式列 |
| 卷状态 | `status` | `CoilSnapshot.status` | `mes_coil_snapshots.status` | 活跃 / 完成 / 停滞判断 | 已落地 | 状态枚举仍需 MES 方正式确认 |
| 事件时间 | `event_time` | `CoilSnapshot.event_time` | `mes_coil_snapshots.event_time` | 流转发生时间 | 已落地 | 当前正式列 |
| MES 更新时间 | `updated_at` | `CoilSnapshot.updated_at` | `mes_coil_snapshots.updated_from_mes_at` | 判新旧 / lag 计算 | 已落地 | 当前正式列 |
| 产品类型 | `product_type` 或 `metadata.product_type` | `CoilSnapshot.metadata.product_type` | 先落 `mes_coil_snapshots.source_payload` | 驾驶舱补充维度 | 半落地 | 当前无一等列 |
| 成品规格 | `finished_spec` 或 `metadata.finished_spec` | `CoilSnapshot.metadata.finished_spec` | 先落 `mes_coil_snapshots.source_payload` | 驾驶舱补充维度 | 半落地 | 当前无一等列 |
| 生产安排 | `production_schedule` 或 `metadata.production_schedule` | `CoilSnapshot.metadata.production_schedule` | 先落 `mes_coil_snapshots.source_payload` | 计划对照 | 半落地 | 当前无一等列 |
| 投入重量 | `input_weight` | `CoilSnapshot.metadata.input_weight` | 先落 `mes_coil_snapshots.source_payload` | 辅助比对 | 半落地 | 当前 adapter 会把这类数值塞进 `metadata` |
| 产出重量 | `output_weight` | `CoilSnapshot.metadata.output_weight` | 先落 `mes_coil_snapshots.source_payload` | 辅助比对 | 半落地 | 当前 adapter 会把这类数值塞进 `metadata` |
| 废料重量 | `scrap_weight` | `CoilSnapshot.metadata.scrap_weight` | 先落 `mes_coil_snapshots.source_payload` | 辅助比对 | 半落地 | 当前 adapter 会把这类数值塞进 `metadata` |

## 6. C 表：扫码后仍由现场补充的字段

这些字段**不应**从 `MES` 头字段覆盖。

它们属于“本工序新增事实”，应该由现场在卷级工序填报页填写。

| 业务含义 | 推荐本地字段 | 当前落点 | 页面行为 | 状态 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 上机重量 | `input_weight` | `work_order_entries.input_weight` | 可编辑 | 已落地 | 复核后可进入 `verified_input_weight` |
| 下机重量 / 产出 | `output_weight` | `work_order_entries.output_weight` | 可编辑 | 已落地 | 完工后可参与成材率计算 |
| 废料 | `scrap_weight` | `work_order_entries.scrap_weight` | 可编辑 | 已落地 | 当前正式列 |
| 来料规格 | `input_spec` | `work_order_entries.input_spec` | 可编辑 | 已落地 | 现场补充 |
| 出料规格 | `output_spec` | `work_order_entries.output_spec` | 可编辑 | 已落地 | 现场补充 |
| 材料状态 | `material_state` | `work_order_entries.material_state` | 可编辑 | 已落地 | 当前正式列 |
| 电耗 | `energy_kwh` | `work_order_entries.energy_kwh` | 可编辑 | 已落地 | 卷级补充值，不等于班组日报总电耗 |
| 气耗 | `gas_m3` | `work_order_entries.gas_m3` | 可编辑 | 已落地 | 卷级补充值 |
| 道次 | `passes` | 建议先落 `work_order_entries.extra_payload.passes` | 可编辑 | 待确认 | 当前没有一等列，建议先走自定义字段 |
| 机列主操备注 | `operator_notes` | `work_order_entries.operator_notes` | 可编辑 | 已落地 | 当前正式列 |
| 后台自定义字段 | 自定义 key | `work_order_entries.extra_payload.*` | 可编辑 | 已落地 | 适合作为模板化扩展位 |
| 质检补充字段 | 自定义 key | `work_order_entries.qc_payload.*` | 可编辑 | 已落地 | 质检专用扩展位 |

## 7. D 表：哪些字段不要混进班组日报页

下表不是不能出现在日报，而是**不要把它们当成日报主输入头字段**：

| 字段 | 原因 |
| --- | --- |
| `tracking_card_no` | 它是卷级主键，不是班组汇总主键 |
| `coil_id` | 它是卷级投影主键，不是班次汇总字段 |
| `qr_code` | 它是扫码线索，不是日报汇总指标 |
| `batch_no` | 它可以作为线索字段，但不应变成日报主键 |
| `product_type / finished_spec / production_schedule` | 它们更适合卷级头字段或投影视图，不适合作为班组日报核心汇总项 |

## 8. 当前最该锁定的字段分组

### 扫码后自动带出并锁定

- `tracking_card_no`
- `process_route_code`
- `alloy_grade`
- `batch_no`
- `qr_code`
- `product_type`
- `status`
- `finished_spec`
- `production_schedule`

### 扫码后现场继续填写

- `input_weight`
- `output_weight`
- `scrap_weight`
- `input_spec`
- `output_spec`
- `material_state`
- `energy_kwh`
- `gas_m3`
- `passes`
- `operator_notes`
- `extra_payload.*`
- `qc_payload.*`

## 9. 联调前必须再确认的 6 个点

1. `batch_no` 是否是稳定业务字段，还是仅历史兼容字段
2. `qr_code` 返回原始扫码值，还是 MES 内部编码
3. `status` 的完整枚举表
4. `event_time` 与 `updated_at` 的语义差异
5. `product_type / finished_spec / production_schedule` 是否能提供正式字段，而不只放 `metadata`
6. `passes` 是否未来要升成正式列，还是继续保留为自定义字段

## 10. 结论

Phase 1 的正确落法不是“把所有字段都做成正式列”。

更稳的方式是：

- 先把卷级主链字段落到正式投影列
- 把扫码头字段和现场补充字段边界分清
- 对暂未稳定的业务字段，先放在 `metadata / source_payload / extra_payload`
- 等 `MES` 样例和状态枚举确认后，再决定哪些字段升成一等列

