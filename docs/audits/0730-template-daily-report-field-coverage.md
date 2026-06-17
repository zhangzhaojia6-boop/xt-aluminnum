# 7:30 模板文字日报字段覆盖审计

日期：2026-06-17

## 目标

每天 7:30 生成前一个已完成生产业务日的文字日报。正文严格按 `docs/模板.md` 输出，只替换已验证数字，不让大模型编数字或改写句式。

## 生产日规则

- 生产业务日从 7:30 开始。
- 7:30 定时任务使用 `last_completed_production_business_date()`。
- 例：6月17日 7:30 生成 6月16日业务日的日报。

## 字段来源优先级

- 全厂总产量、入库成品：优先 MES 成品入库/包装口径。
- 在制料：优先 MES 在制快照。
- 热轧、铸二、铸三、铸锭：按人工填报口径。
- 1650、1850、2050、在线退火、拉矫、精整、剪切、彩涂：优先 MES 工序记录。
- 回收、大修：优先专表，缺专表时可回退到人工每日填报。
- 成品率、能耗：按人工每日填报口径。
- 合同、投料、余合同：复用合同投料汇总，人工补录优先于导入汇总。

## 已接入字段

- `total_output_daily`、`total_output_month`、`total_output_delta`：来自 MES 包装/入库产量。
- `finished_inbound_daily`、`finished_inbound_month`：当前按 MES 包装/入库产量渲染。
- `hot_roll_daily`、`foundry_daily`、`cast_2_daily`、`cast_3_daily`：来自人工卷级/车间填报。
- `cold_1650_daily`、`cold_1850_daily`、`cold_2050_daily`、`online_anneal_daily`、`straightening_daily`、`finishing_daily`、`shearing_daily`、`coating_daily`：来自 MES 工序产量。
- `wip_total`：来自 MES 在制料汇总。
- `daily_contract_weight`、`remaining_contract_weight`、`remaining_contract_delta`：来自合同投料汇总。
- `daily_yield_rate`：优先人工填报全厂成品率。
- `total_electricity_kwh`、`total_gas_m3`：来自能耗汇总或人工每日填报。
- `recovery_daily`、`recovery_month`：来自回收专表。
- `roller_grind_daily`、`roller_grind_month`：来自大修专表。

## 仍需补齐或现场确认

- `outsourced_daily`、`outsourced_month`：外加工日报/月累计口径需要固定填报字段。
- `cast_roll_active_lines`：铸轧开机条数需要固定人工填报字段。
- `consignment_weight`：系统已有成品库寄存字段，但需确认是否仍按人工填报，还是必须从 MES 识别。
- `subitem_electricity_kwh`：模板里的分项用电合计需要固定来源。
- 细分气耗：铸二、铸三、东炉、西炉、新厂北线、新厂南线、餐厅等需要固定填报字段。
- 各车间吨电耗、吨气耗：需要确认由人工直接填，还是按产量和能耗自动计算。
- 分项成品率：热轧日成品率、热轧月成品率、铸轧成品率、普板/卷成品率需要固定填报字段。
- 投料细分：2050投、1850投、外加工投、中厚板需要固定字段。
- 在制料分桶：1650/2050冷轧、1850冷轧、铣床、退火分厂、精整分厂等需要继续完善 MES 别名映射。

## 缺字段处理

- 缺 P0 字段时，不生成正式日报正文。
- 系统把缺字段写入 `report_data.template_daily_report.missing_fields`。
- 补录后可重新生成日报，不允许沿用旧数字或编数字。

## 本轮代码行为

- 新增模板日报服务：构建事实包、校验缺字段、严格渲染正文。
- 定时日报任务在汇总后、推送前应用模板正文。
- `daily_report` 调度从 8:00 改为 7:30。
- `ReporterAgent` 有模板正文时直接发送模板正文；模板缺字段阻断时不发送旧短摘要。
- 手动生成生产日报时也会写入 `report_data.template_daily_report`，ready 时同步写 `final_text_summary`。
