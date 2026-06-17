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
| `machine_daily_cost_snapshots` | 已接入 | `business_date`, `workshop_id`, `machine_line_id`, `electricity_kwh`, `electricity_cost`, `natural_gas_m3`, `natural_gas_cost`, `total_cost` |
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
| 全厂叙述行 | 没有班次的日报正文水电气/成本行归到 `workshop=全厂`、`shift=''` |
| 金额单位 | `31.41万元 = 314100元` |
| 合同叙述 | `当天接合同192吨（含热轧158吨）` 会拆成当日合同和当日热轧合同 |
| 成本拆分 | `电费10.12万元`、`气费21.29万元` 会分别换算为元 |
| 差异原因 | `value_diff`、`missing_system_row`、`extra_system_row`、`missing_field_value` |
| 修正建议 | 只生成 `dry_run` 规则建议，不自动写生产配置 |

## 7. 已新增代码与测试

| 类型 | 文件 |
|---|---|
| 服务 | `backend/app/services/mapping_reconciliation_service.py` |
| API | `backend/app/routers/mapping_reconciliation.py` |
| 挂载 | `backend/app/main.py` |
| 持久化模型 | `backend/app/models/reconciliation.py` |
| 数据库迁移 | `backend/alembic/versions/0045_mapping_reconciliation_runs.py` |
| 测试 | `backend/tests/test_mapping_reconciliation_service.py` |
| 路由测试 | `backend/tests/test_mapping_reconciliation_route.py` |
| 脱敏 fixture | `backend/tests/fixtures/output_skill_mapping_sample.json` |

接口当前已具备：

| 接口 | 状态 | 说明 |
|---|---|---|
| `GET /api/v1/mapping-reconciliation/sources` | 已实现 | 列出参考源文件结构和系统源表名 |
| `POST /api/v1/mapping-reconciliation/run` | 已实现 | 支持传入脱敏/内存行，也支持传参考文件名 + 业务日自动 dry-run 对齐，并写入 `mapping_reconciliation_runs` |
| `GET /api/v1/mapping-reconciliation/runs/{id}` | 已实现 | 读取一次 dry-run 对齐运行记录和完整结果 |
| `GET /api/v1/mapping-reconciliation/runs/{id}/differences` | 已实现 | 读取一次运行记录里的差异明细和差异汇总 |
| `POST /api/v1/mapping-reconciliation/rules/propose` | 已实现 | 传入差异明细，单独生成规则建议，不写配置 |
| `POST /api/v1/mapping-reconciliation/rules/apply-dry-run` | 已实现 | 临时套用别名候选重新试算匹配率，返回 `applied=false`、`persisted=false` |

## 8. 当前测试证据

已执行：

```text
python -m pytest backend/tests/test_imports_daily_production_mapping_preview_route.py backend/tests/test_mapping_reconciliation_service.py backend/tests/test_mapping_reconciliation_route.py -q
23 passed
```

## 9. 当前匹配率说明

本轮已经把 `D:\输出skill` 常见文本和 Excel 参考文件接入到只读解析器，但还没有跑云端真实日期的全量批量匹配，所以不能宣称真实全量匹配率已达到 95%。

当前已经完成的是“匹配算法 + 文件解析 + 系统多表拉平”的第一版底座：

| 样例 | 匹配率 |
|---|---:|
| 脱敏 fixture：产量 kg/吨 + 车间别名 + 班次别名 | 100% |
| 临时 `.txt` 输出skill 样例：日期、车间、班次、产量、能耗、废料 | 解析成功 |
| 真实 `D:\输出skill\2026-6-14_日报正文.txt`：全厂叙述行水电气、合同和成本 | 只读解析成功，生成 3 行全厂参考数据 |
| 临时 `.xlsx/.xls` 输出skill 样例：日期、车间、班次、产量、能耗、废料 | 解析成功 |
| 内存数据库 `mes_workshop_process_records`：同业务日工序产量拉平 | 读取成功 |
| 内存数据库 `mes_stock_records`：同业务日成品库入库重量拉平 | 读取成功 |
| 内存数据库 `machine_energy_records`：同业务日车间/班次/机台能耗拉平 | 读取成功 |
| 内存数据库 `machine_daily_cost_snapshots`：同业务日电费、气费、总成本拉平 | 读取成功 |
| 内存数据库 `daily_consumable_logs`：同业务日内勤辅材和包装入库填报拉平 | 读取成功 |
| `/api/v1/mapping-reconciliation/run`：传文件名 + 业务日自动 dry-run | 100% |
| 人工构造：能耗值差异 + 缺系统行 | 0%，可解释差异 |
| 人工构造：车间/班次别名候选 | 生成 dry-run 建议 |
| 接口返回：差异原因汇总 | 返回 `difference_summary`，前端 `/manage/mapping-reconciliation` 已展示 |
| 接口返回：字段匹配摘要 | 返回 `match_summary`，包含可比字段、已匹配字段、未匹配字段和字段级匹配率 |
| 规则建议单独接口 | `/rules/propose` 可只根据差异生成 dry-run 规则建议 |
| 规则试算接口 | `/rules/apply-dry-run` 可临时套用别名候选重新计算匹配率，不写生产配置 |
| 前端默认 dry-run 字段 | 已覆盖 `yield_rate`、`rolling_oil_per_ton`、`cost_per_ton`、`daily_hot_roll_contract_weight`、`electricity_cost`、`natural_gas_cost` |
| dry-run 运行记录 | `POST /run` 返回 `run_id`，`GET /runs/{id}` 和 `/runs/{id}/differences` 可追溯 |

## 10. 下一步

1. 用真实 `D:\输出skill` 文件跑一个业务日只读匹配率，不提交原始数据。
2. 用真实业务日复核成材率、轧制油吨耗、吨成本的字段来源是否和经营日报口径一致。
3. 基于 `mapping_reconciliation_runs` 做运行记录列表页和差异明细分页。
4. 做真实日期的只读匹配率统计，不能为提高匹配率改生产原始数据。

## 11. 2026-06-15 字段匹配摘要补充

本轮新增 `/api/v1/mapping-reconciliation/run` 的 `match_summary` 返回结构：

| 字段 | 含义 |
|---|---|
| `total_fields` | 本次可比字段总数 |
| `matched_fields` | 已匹配字段数 |
| `unmatched_fields` | 未匹配字段数 |
| `overall_match_rate` | 沿用现有加权总匹配率 |
| `field_breakdown` | 每个指标的字段级匹配率 |

前端 `/manage/mapping-reconciliation` 已新增“字段匹配”“未匹配字段”和“字段匹配率”展示。小白版理解：以前页面主要告诉你“总匹配率”和“差异几条”，现在还能看到“到底有多少字段可比、哪些指标字段匹配、哪些字段没匹配”。

本轮验证：

```text
python -m pytest backend/tests/test_mapping_reconciliation_service.py backend/tests/test_mapping_reconciliation_route.py -q
24 passed

cd frontend && node --test tests/mappingReconciliationPage.test.js
12 passed

python -m compileall backend/app/services/mapping_reconciliation_service.py backend/app/routers/mapping_reconciliation.py
通过

cd frontend && npm run build
通过
```

## 13. 2026-06-17 真实验收补充

本轮按 `gstack=Goal/Scan/Test/Apply/Check/Keep` 复核第一阶段完成度。结论：旧版本不能直接评 9.5 分，原因不是生产原始数据错误，而是映射链路还有真实文件结构缺口。

### 13.1 扫描发现

| 项目 | 结果 | 影响 |
|---|---|---|
| 本地 `D:\输出skill` | 共 4381 个文件，其中可解析 560 个，图片待 OCR 273 个 | 不能只按标准表头解析，必须识别真实日报结构 |
| `2026-6-16_日报正文.txt` | 可解析 3 行，全厂水电气、合同、成本已读到 | 已补充 `wip_total` 和在制料拆分字段 |
| `2026-6-16_日均报表.xls` | 旧版本解析 0 行 | 原因是表头在第 5 行，且汇总表没有班次 |
| `delivery_override_2026-06-16.json` | 旧版本解析 0 行 | 原因是有效数据在 `summaries` 文本里，不是标准 `rows[]` |
| 云端 `reference/output-skill` | 生产机当前不存在该目录 | 云端页面会显示参考源未挂载，不能直接选择本地 `D:\输出skill` |
| 云端 `mes_daily_wip_snapshots` | 2026-06-16 有 2 行，但重量合计为 0 | 这会导致在制料显示 0 |
| 云端 `mes_wip_total_snapshots` | 有 57 行，总量快照可作为兜底来源 | 需要进入映射服务 dry-run，不直接改原始数据 |

### 13.2 本轮修复

| 修复点 | 文件 |
|---|---|
| 解析真实 Excel：支持表头不在第一行、汇总表无班次、按工作表名补业务日 | `backend/app/services/mapping_reconciliation_service.py` |
| 解析 override JSON：从 `summaries` 文本抽取合同、投料、坯料、水电气 | `backend/app/services/mapping_reconciliation_service.py` |
| 解析日报正文在制料：新增 `wip_total` 和拆分在制字段别名 | `backend/app/services/mapping_reconciliation_service.py` |
| 系统侧在制料拉平：接入 `mes_daily_wip_snapshots` 和 `mes_wip_total_snapshots`，每日快照为 0 时用总量快照兜底 | `backend/app/services/mapping_reconciliation_service.py` |
| 页面默认比较在制料 | `frontend/src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue` |
| 测试覆盖真实缺口 | `backend/tests/test_mapping_reconciliation_service.py`、`frontend/tests/mappingReconciliationPage.test.js` |

### 13.3 本轮验证

```text
python -m pytest backend/tests/test_mapping_reconciliation_service.py backend/tests/test_mapping_reconciliation_route.py -q
31 passed

cd frontend && node --test tests/mappingReconciliationPage.test.js
15 passed

python -m compileall backend/app/services/mapping_reconciliation_service.py backend/app/routers/mapping_reconciliation.py
通过

cd frontend && npm run build
通过
```

真实本地只读解析结果：

| 文件 | 修复前 | 修复后 |
|---|---:|---:|
| `2026-6-16_日报正文.txt` | 3 行，但无在制料字段 | 3 行，包含 `wip_total=879` |
| `2026-6-16_日均报表.xls` | 0 行 | 187 行 |
| `delivery_override_2026-06-16.json` | 0 行 | 3 行 |

### 13.4 当前完成度判断

本轮后，第一阶段的代码底座、接口、页面和测试已经可继续做真实业务日 dry-run。仍不能把“全量真实匹配率 95%+”当作已完成，因为生产机还没有挂载参考文件目录，且图片类报表还处于 `image_pending_ocr`。下一步必须在云端只读放入可验收参考文件或接入上传入口，再用 `/api/v1/mapping-reconciliation/run` 跑真实业务日匹配率。

## 12. 2026-06-15 规则建议和规则试算接口补充

本轮补齐两个第一阶段规划里明确列出的接口：

| 接口 | 行为 |
|---|---|
| `POST /api/v1/mapping-reconciliation/rules/propose` | 根据差异明细生成 `alias_candidate` 规则建议，只返回建议，不保存 |
| `POST /api/v1/mapping-reconciliation/rules/apply-dry-run` | 把 `alias_candidate` 临时并入 `dimension_aliases` 后重新对比，返回试算后的匹配率和差异 |

安全边界：

- 两个接口都需要管理员权限。
- `apply-dry-run` 返回 `applied=false` 和 `persisted=false`。
- 不写 `master_code_aliases`，不写生产口径配置，不写 `mapping_reconciliation_runs`。
- 规则候选仍需要人工确认后再进入正式主数据或别名配置。

前端 `/manage/mapping-reconciliation` 规则建议区域已新增“试算规则影响”按钮，用来查看临时规则是否能改善匹配率。小白版理解：这一步像“先把规则放在草稿纸上算一遍”，不是直接改系统。

本轮验证：

```text
python -m pytest backend/tests/test_mapping_reconciliation_route.py backend/tests/test_mapping_reconciliation_service.py -q
26 passed

cd frontend && node --test tests/mappingReconciliationPage.test.js
13 passed

python -m compileall backend/app/routers/mapping_reconciliation.py
通过

cd frontend && npm run build
通过
```
