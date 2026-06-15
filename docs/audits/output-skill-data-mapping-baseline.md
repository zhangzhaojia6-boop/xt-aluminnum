# 输出skill 数据映射基线审计

生成日期：2026-06-15

## 1. 本轮目标

本轮只做第一阶段的只读对齐基线：把 `D:\输出skill` 作为参考源，把云端数据库里的平台生产、填报、能耗、异常、主数据作为系统源，先确认字段、单位、别名、班次和差异原因，不改生产原始数据。

## 2. 已读取的参考源

本地只读扫描 `D:\输出skill`，只记录文件结构和文件名，不提交原始文件。

| 类型 | 数量 |
|---|---:|
| `.xls` | 208 |
| `.xlsx` | 86 |
| `.png` | 235 |
| `.txt` | 77 |
| `.json` | 114 |
| `.jpg/.jpeg` | 14 |
| `.md` | 2 |
| 其他 | 42 |

样例文件名包括：

| 文件 |
|---|
| `2026-04-22_2026用电统计表.png` |
| `2026-04-22_各工序产量表.png` |
| `2026-04-22_各车间能耗明细表.png` |
| `2026-4-22_日均报表.xls` |
| `2026-4-22_日报正文.txt` |

注意：参考目录里也存在 `.exe/.cmd/.ps1` 等可执行或脚本类文件。后续 RAG 或对齐读取时必须拒绝这类文件，只允许把报表、文本、图片等当作只读参考源。

## 3. 已读取的云端系统源

云端只读查询已确认以下表存在。只读取表名、行数、字段结构，不读取客户、员工、密钥或连接配置。

| 表 | 行数 | 关键字段 |
|---|---:|---|
| `mes_stock_records` | 1547 | `contract_no`, `customer_alias`, `net_weight_kg`, `net_weight_tons`, `in_stock_date`, `business_date`, `status_name` |
| `mes_workshop_process_records` | 2180 | `batch_no`, `customer_alias`, `workshop_name`, `process_name`, `worker_name`, `device_name`, `input_weight_kg`, `output_weight_kg`, `yield_rate`, `end_time`, `business_date` |
| `shift_production_data` | 91 | `business_date`, `shift_config_id`, `workshop_id`, `equipment_id`, `actual_qty`, `scrap_qty`, `unit`, `raw_data` |
| `work_order_entries` | 2876 | `business_date`, `workshop_id`, `machine_id`, `shift_id`, `input_weight`, `output_weight`, `scrap_weight`, `extra_payload` |
| `daily_consumable_logs` | 1 | `workshop_id`, `workshop_type`, `business_date`, `payload` |
| `machine_energy_records` | 27 | `shift_report_id`, `machine_code`, `machine_name`, `energy_kwh`, `gas_m3` |
| `data_quality_issues` | 6 | `business_date`, `issue_type`, `source_type`, `dimension_key`, `field_name`, `issue_level`, `status` |
| `data_reconciliation_items` | 0 | `business_date`, `reconciliation_type`, `source_a`, `source_b`, `dimension_key`, `field_name`, `diff_value`, `status` |
| `daily_reports` | 1 | `report_date`, `report_type`, `report_data`, `status`, `text_summary`, `generated_scope`, `output_mode` |
| `workshops` | 25 | `code`, `name`, `workshop_type`, `is_active` |
| `equipment` | 185 | `code`, `name`, `workshop_id`, `equipment_type`, `is_active`, `qr_code`, `bound_user_id` |
| `shift_configs` | 6 | `code`, `name`, `start_time`, `end_time`, `is_cross_day`, `business_day_offset`, `is_active` |

## 4. 当前活跃口径

云端当前活跃管理口径包含 15 项，其中 13 个活跃生产车间加上 `回收车间`、`成品库`。

| 编码 | 名称 | 类型 |
|---|---|---|
| `ZD` | 铸锭分厂 | casting |
| `ZR2` | 铸轧二 | casting |
| `ZR3` | 铸轧三 | casting |
| `RZ` | 热轧 | hot_roll |
| `LZ2050` | 2050冷轧 | cold_roll |
| `LZ1850` | 1850冷轧 | cold_roll |
| `LZ1650` | 1650冷轧 | cold_roll |
| `JZ` | 精整车间 | finishing |
| `JQ` | 剪切车间 | shearing |
| `LJ` | 拉矫车间 | straightening |
| `ZXTF-N` | 新厂在线退火 | annealing |
| `ZXTF-P` | 园区在线退火 | annealing |
| `CH` | 淬火车间 | finishing |
| `HS` | 回收车间 | recycling |
| `CPK` | 成品库 | inventory |

班次当前活跃口径：

| 编码 | 名称 | 时间 | 跨日 |
|---|---|---|---|
| `A` | 长白班 | 07:30-15:30 | 否 |
| `B` | 小夜班 | 15:30-23:30 | 否 |
| `C` | 大夜班 | 23:30-07:30 | 是 |

## 5. 初始字段映射

| 输出skill/日报参考字段 | 系统优先字段 | 单位处理 | 当前说明 |
|---|---|---|---|
| 包装产量 / 入库参考 | `mes_stock_records.net_weight_tons` | 吨 | 用于 MES 包装/入库参考，不能和内勤入库填报混成一个数 |
| 工序产量 | `mes_workshop_process_records.output_weight_tons` | 吨 | 可按 `business_date + workshop_name + process_name + device_name` 汇总 |
| 上机量 / 投料量 | `mes_workshop_process_records.input_weight_tons`、`work_order_entries.input_weight` | kg/吨统一成吨 | 不同来源要显示来源标签 |
| 下机量 | `mes_workshop_process_records.output_weight_tons`、`work_order_entries.output_weight` | kg/吨统一成吨 | 后工序优先 MES，前工序缺口保留人工补录 |
| 废料 | `work_order_entries.scrap_weight` 或算法差值 | kg/吨统一成吨 | 需要按车间规则确定自动计算公式 |
| 能耗 | `machine_energy_records.energy_kwh` | kWh | 当前行数 27，后续需接能耗数采库后再扩展 |
| 辅材 | `daily_consumable_logs.payload` | 依字段 | 当前生产库只有 1 条，需要和内勤口径分开 |
| 吨成本 | 参考源 `cost_per_ton`；系统侧 `cost_daily_result.output_ton_cost` | 元/吨 | 当前接的是经营估算成本策略日结果，不等同财务正式成本 |
| 质量异常 | `data_quality_issues` | 条数/状态 | 可用于异常页和 Agent 判断 |
| 对账差异 | `data_reconciliation_items` | 差值 | 当前 0 条，本轮新增服务先 dry-run，不直接写入 |

## 6. 初始别名与单位规则

已用测试固化的规则：

| 类型 | 示例 |
|---|---|
| 单位换算 | `12500 kg = 12.5 吨` |
| 车间别名 | `精整车间 -> 精整` |
| 班次别名 | `白班 -> 长白班`、`小夜 -> 小夜班` |
| 差异原因 | `value_diff`、`missing_system_row`、`extra_system_row`、`missing_field_value` |
| 修正建议 | 只生成 `dry_run` 规则建议，不自动写生产配置 |

## 7. 已新增代码与测试

| 类型 | 文件 |
|---|---|
| 服务 | `backend/app/services/mapping_reconciliation_service.py` |
| API | `backend/app/routers/mapping_reconciliation.py` |
| 挂载 | `backend/app/main.py` |
| 测试 | `backend/tests/test_mapping_reconciliation_service.py` |
| 路由测试 | `backend/tests/test_mapping_reconciliation_route.py` |
| 脱敏 fixture | `backend/tests/fixtures/output_skill_mapping_sample.json` |

接口当前已具备：

| 接口 | 状态 | 说明 |
|---|---|---|
| `GET /api/v1/mapping-reconciliation/sources` | 已实现 | 列出参考源文件结构和系统源表名 |
| `POST /api/v1/mapping-reconciliation/run` | 已实现 | 支持传入脱敏/内存行，也支持传参考文件名 + 业务日自动 dry-run 对齐 |
| `GET /api/v1/mapping-reconciliation/runs/{id}` | 未实现 | 后续需要持久化运行记录后再做 |
| `GET /api/v1/mapping-reconciliation/runs/{id}/differences` | 未实现 | 后续需要持久化运行记录后再做 |
| `POST /api/v1/mapping-reconciliation/rules/propose` | 未单独实现 | 目前 `run` 返回 `rule_proposals` |
| `POST /api/v1/mapping-reconciliation/rules/apply-dry-run` | 未实现 | 后续做规则试算，不写正式配置 |

## 8. 当前测试证据

已执行：

```text
python -m pytest backend/tests/test_imports_daily_production_mapping_preview_route.py backend/tests/test_mapping_reconciliation_service.py backend/tests/test_mapping_reconciliation_route.py -q
13 passed
```

## 9. 当前匹配率说明

本轮已经把 `D:\输出skill` 常见文本和 Excel 参考文件接入到只读解析器，但还没有跑云端真实日期的全量批量匹配，所以不能宣称真实全量匹配率已达到 95%。

当前已经完成的是“匹配算法 + 文件解析 + 系统多表拉平”的第一版底座：

| 样例 | 匹配率 |
|---|---:|
| 脱敏 fixture：产量 kg/吨 + 车间别名 + 班次别名 | 100% |
| 临时 `.txt` 输出skill 样例：日期、车间、班次、产量、能耗、废料 | 解析成功 |
| 临时 `.xlsx/.xls` 输出skill 样例：日期、车间、班次、产量、能耗、废料 | 解析成功 |
| 内存数据库 `mes_workshop_process_records`：同业务日工序产量拉平 | 读取成功 |
| 内存数据库 `mes_stock_records`：同业务日成品库入库重量拉平 | 读取成功 |
| 内存数据库 `machine_energy_records`：同业务日车间/班次/机台能耗拉平 | 读取成功 |
| 内存数据库 `daily_consumable_logs`：同业务日内勤辅材和包装入库填报拉平 | 读取成功 |
| `/api/v1/mapping-reconciliation/run`：传文件名 + 业务日自动 dry-run | 100% |
| 人工构造：能耗值差异 + 缺系统行 | 0%，可解释差异 |
| 人工构造：车间/班次别名候选 | 生成 dry-run 建议 |
| 接口返回：差异原因汇总 | 返回 `difference_summary`，前端 `/manage/mapping-reconciliation` 已展示 |

## 10. 下一步

1. 用真实 `D:\输出skill` 文件跑一个业务日只读匹配率，不提交原始数据。
2. 让 `/manage/mapping-reconciliation` 从静态样例改为选择文件和业务日后调用真实 dry-run。
3. 增加运行记录持久化表后再做 `/runs/{id}` 和差异明细分页。
4. 做真实日期的只读匹配率统计，不能为提高匹配率改生产原始数据。
