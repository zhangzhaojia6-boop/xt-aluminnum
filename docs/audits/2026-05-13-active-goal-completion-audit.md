# 2026-05-13 活跃目标完成审计

## 结论

当前 `/goal` 不能标记为完成。

本轮已经把填报端真实写入、实时聚合、外部 MES 流转线索、机列保守绑定、差异核对业务口径、管理端实时可见性、外部 MES 机列绑定透明度、10w 级异常产量复验和生产部署推进到可验证状态；但总目标要求的是一个可展示、可试用、可继续接真实数据上线迭代的完整 `鑫泰铝业 数据中枢`，仍有设计稿反推落地、全模块真实业务闭环、外部应用连接/钉钉正式配置和最终交付审计未闭环。

下一轮最小实现切片应聚焦：正式外部配置与可试用演示门禁，尤其是 `APP_CONNECTION`、钉钉通讯录权限和 LLM/AI 分析能力的真实联通状态，不能把 `readyz` 的 MES 成功误判成全系统已经可交付。

## 当前证据

- 当前代码锚点：`3f69931 test: 补充管理端产量异常复验`，已推送到 `origin/main`；运行时代码仍是此前已部署的 `688073b feat: 展示实时填报与MES绑定状态`。
- 生产健康：`/readyz` 返回 ready，外部 MES 同步 `last_run_status=success`，最近拉取与写入均为 `50`。
- 后端全量验证：`python -m pytest backend/tests -q` 为 `796 passed, 124 deselected, 39 warnings`。
- 实时填报事实：生产活跃业务日为 `2026-05-12`，正式填报 `36` 条，非空机列格子 `9` 个，`factory_output=281.12t`，`data_source=mixed`。
- 当天现状：`2026-05-13` 暂无正式或草稿填报记录；管理端如果直接看今天，会呈现为空。
- 外部 MES 绑定事实：本轮外部 MES 行加载 `21` 条，其中 `7` 条已通过路线字段保守绑定到机列；样例可绑定到 `machine_id=123`、`2050轧机`。
- 上游限制：当前外部 MES 批次的 `machine_code` 为空，后端只能用 `current_workshop/current_process/next_workshop/next_process` 做唯一性推断；多机列歧义保持待归属。
- UI 蓝图资产：`docs/ui-reference/IMAGE2_PROMPTS.md`、`docs/ui-reference/UI_TARGET_SPEC.md`、`docs/ui-reference/DESIGN_REVERSE_PLAN.md` 和 `docs/ui-reference/highres/01-15` 已存在。
- 10w 级异常产量复验：4.30 真实日报补入后，生产 `ShiftProductionData` 活跃 `254` 行中，折吨后 `>=10000t` 的记录数为 `0`，最大折吨单行仍为 `1163.0t`；`2026-05-12` 厂级、车间、实时聚合分别返回 `281.12t`，`2026-05-13` 当天返回 `0.0t`，历史七日最大值为 `355.97t`。

## Prompt-to-artifact 核对

| 目标片段 | 当前状态 | 证据 | 缺口 |
| --- | --- | --- | --- |
| image-2 理想设计稿与功能蓝图 | 部分完成 | `docs/ui-reference/*` 与 15 张 highres 参考图已存在 | 继续改 UI 前需要按设计门禁锁定方向并做浏览器验收 |
| 全仓上下文、计划、文档审计 | 部分完成 | `docs/deploy/current-state.md`、`docs/audits/*`、`docs/superpowers/plans/*` 持续更新 | 大 goal 级完成审计此前不集中；本文补齐 |
| 管理端接收填报端测试数据 | 可验收 | `2026-05-12` 有 `36` 条正式填报与 `281.12t` 实时聚合；管理端实时页已显示最近有效业务日 | `2026-05-13` 仍无填报，这是现场数据状态，不是链路故障 |
| 填报端到 API/BFF、数据库、管理端、报表图表链路 | 可验收 | 实时聚合、待补产出、差异核对、人工补正、管理端入口均已有测试和部署证据 | 后续继续扩展到更多经营模块，不再把实时填报链路作为当前阻断 |
| 外部 MES 链接稳定通畅 | 部分完成 | `/readyz` 外部 MES 同步成功，最近拉取/写入 `50` | 上游 `machine_code` 为空，绑定依赖保守推断；需要把歧义待归属数量暴露给管理端 |
| 与外部 MES 绑定的机列数据搭配绑定 | 可验收 | `/api/v1/aggregation/live` 返回 `mes_machine_binding`，管理端实时页展示外部 MES 行数、匹配填报、已绑机列、路线推断和上游机列码缺失 | 上游 `machine_code` 仍为空；多机列歧义保持待归属，不静默强绑 |
| 产量约 10w 异常来源治理 | 已验证 | 真实日报与能耗事实已多批次入库，当前实时产量为 `281.12t`；生产审计确认折吨后 `>=10000t` 记录数为 `0`，管理端厂级/车间/实时路由不吐 10w 级产量 | 后续如新增数据源，必须继续走 `10000t` 门禁和 kg/t 折算测试 |
| `D:\鑫泰报表` 真实文件参考与入库 | 部分完成 | 4 月、5 月多天真实产量与能耗已通过门禁入正式事实；`2026-04-30` 已用 `输出skill/2026-4-30_主表完整字段填充.xls` 替代表补入正式事实 | `2026-04-22` 原始源表仍为空，`输出skill/2026-4-22_日均报表.xls` 不是当前综合报表格式，必须继续阻断 |
| 设计系统、组件体系、路由和页面品质 | 部分完成 | 管理端差异核对、实时页、移动端等已有多轮前端验证 | 后续新增可见 UI 仍需遵循设计规则，跑 mock/e2e/响应式溢出检查 |
| 后端可维护结构 | 部分完成 | 实时、扫码、移动提交、差异核对等服务已拆到 services/routes/tests | 仍需持续避免把业务算法塞进页面；新增聚合状态优先复用后端服务输出 |
| 云服务器环境、部署与运行 | 部分完成 | 生产 systemd 部署、`/readyz`、当前状态文档已有证据 | 外部应用连接、钉钉、密钥等配置仍应按运行清单持续复验 |
| 每轮自测、代码审查、文档收口 | 部分完成 | 后端全测、前端构建、Playwright 探针、部署记录已多次执行 | 下一轮 UI 切片完成后仍需重新跑相关测试和浏览器验收 |

## 本轮 10w 异常复验切片

### 目标

确认管理端当前可访问生产口径不再显示 10w 级异常产量，并把 kg/t 折算门禁补进回归测试。

### 生产复验证据

- 生产事实表：4.30 真实日报补入后，`ShiftProductionData` 非 `voided` 活跃行 `254`。
- 折吨后 `>=10000t` 的活跃行：`0`。
- 非 `mobile_coil_agg` 来源、原始 `output_weight >= 10000` 的活跃行：`0`。
- 最大单行折吨产量：`1163.0t`，来源为 `daily_production_report/confirmed`，不是 kg 误读。
- `2026-05-12` `/dashboard/factory-director`：`today_total_output=281.12`、`leader_today_output=281.12`、`month_to_date_output=12230.53`、七日最大 `355.97`。
- `2026-05-12` `/dashboard/workshop-director`：`total_output=281.12`、最大班次项 `141.03`。
- `2026-05-12` `/aggregation/live`：`factory_output=281.12`、`data_source=mixed`、`formal_entry_count=36`。
- `2026-05-13` 厂级、车间和实时聚合当日产量均为 `0.0`，对应当天暂无填报，不是异常大数。

### 新增回归门禁

`backend/tests/test_report_service_contract_lane.py` 新增 `test_build_history_digest_converts_mobile_coil_aggregate_kg_to_tons`：

- 种入 `mobile_coil_agg` 原始 `126460kg` 与 `281120kg`。
- 断言历史走势显示 `126.46t`、`281.12t`。
- 断言月累计为 `407.58t`、日均为 `203.79t`。
- 断言七日走势最大值 `<10000`，防止 `/manage/factory` 把 kg 当吨展示。

## 本轮外部配置门禁复验切片

### 目标

确认生产 `/readyz` 通过不被误判为完整外部联通通过，并把正式试用前缺失的真实配置沉淀为可执行清单。

### 生产复验证据

- `scripts/check_statistics_module_ready.py --json` 返回 `hard_gate_passed=false`、`module_usable=false`、`external_connection_enabled=false`。
- 基础运行项正常：`local_runnable=true`、`runtime_valid=true`、`database_ok=true`。
- 业务底座正常：`workflow_enabled=true`、`auto_publish_enabled=true`、`auto_push_enabled=true`。
- 外部 MES 可用：`mes_adapter=mvc`、`mes_ready=true`。
- 当前 hard issues：`LLM_DISABLED`、`APP_CONNECTION_DISABLED`。
- 当前 warning issue：`DINGTALK_NO_BOUND_USERS`，且 `active_dingtalk_user_count=0`、`active_dingtalk_employee_count=0`。

### 需要现场补齐的真实值

| 用途 | 所在位置 | 缺失字段 | 影响 |
| --- | --- | --- | --- |
| LLM/AI 摘要增强 | 服务器 `backend/.env` | `LLM_ENABLED`、`LLM_API_BASE`、`LLM_API_KEY`、`LLM_MODEL` 或 `LLM_ENDPOINT_ID` | AI 摘要与分析增强不可用，不能宣称 AI 能力正式联通 |
| 应用连接外发 | 服务器 `backend/.env` | `APP_CONNECTION_ENABLED`、`APP_CONNECTION_PUSH_MODE`、`APP_CONNECTION_API_BASE`、`APP_CONNECTION_API_KEY` | 统计模块不能对外推送，正式外部连接面未启用 |
| 钉钉真实人员触达 | 生产数据库与钉钉通讯录权限 | `users.dingtalk_user_id` 或 `employees.dingtalk_user_id`，以及通讯录同步权限 | token 可用但通知不能送达真实人员，真实客户端 UAT 不能闭环 |

### 管理端暴露状态

管理端实时页已经展示 `外部联通闸门` 和 `外部联通明细`，并把 `LLM_DISABLED`、`APP_CONNECTION_DISABLED`、`DINGTALK_NO_BOUND_USERS` 转成 `LLM 摘要`、`应用连接`、`钉钉人员` 三类业务标签；因此当前最小收口是文档和门禁清单，不需要伪造配置或改写生产数据。

## 本轮真实日报 4.30 补齐切片

### 目标

复核 `2026-04-30` 是否存在可替代的非空真实日报源，并在门禁通过后补入正式生产事实。

### 生产复验证据

- 原缺口：生产库 `2026-04-30` 的 `daily_production_report` 正式事实行为 `0`。
- 可用替代表：`D:\鑫泰报表\输出skill\2026-4-30_主表完整字段填充.xls`。
- 本机 dry-run：只读转换为 `xintai-daily-production-2026-04-30-filled.xlsx` 后，锁定报告日 `2026-04-30` 返回 `hard_gate_passed=true`、`total_rows=16`、`ready_rows=16`、`unresolved_rows=0`、`daily_output_tons=2345.849`。
- 写库前备份：`/srv/aluminum-bypass/backups/pre-daily-production-promote-20260430-20260513-084441.dump`，已通过 `pg_restore -l` 校验。
- 转换源留档：`/srv/aluminum-bypass/backups/import_sources/daily-production-20260430-20260513-0844/xintai-daily-production-2026-04-30-filled.xlsx`，服务器 Git 工作区保持干净。
- 生产 staging：`ImportBatch id=32`、`batch_no=IMP-DAILY-LOCKED-20260513084453608065`、`quality_status=warning`，warning 仅为原表头日期 `2026-04-22` 与锁定报告日 `2026-04-30` 不一致。
- 正式提升：写入 `ShiftProductionData` `14` 行，`input=2388.531t`、`output=2345.849t`、`scrap=111.682t`。
- 服务层复验：`build_factory_dashboard(2026-04-30)` 返回 `today_total_output=2345.85`、`total_energy=194186.6`、`energy_per_ton=82.77881483420288`。
- 生产健康：`/readyz` 仍为 `status=ready`，`aluminum-bypass` 与 `nginx` 均为 `active`。

### 仍然阻断

`2026-04-22` 原始 `鑫泰每日产量4月22日.xls` 解析为 0 行；`输出skill/2026-4-22_日均报表.xls` 返回 `no_daily_production_summary_sheet`。人工复核该日输出资产后，`日报正文.txt` 写明热轧日产 `262t`，但 `日均报表.xls` 的“各工序产量报表”中 `热轧` 行日产量为 `0t`，且表内混有包装/在制类行，不能按当前综合报表门禁提升。该日仍需要同日非空综合日报源表或现场确认替代表。

## 完成判断

完成该切片后，仍不能直接宣称总 goal 完成；只能把“管理端实时数据可见性 + 外部 MES 机列绑定透明度 + 10w 级异常产量复验 + 外部配置门禁复验 + 4.30 真实日报补齐”推进到可验收/已验证。总 goal 完成前还需要继续执行设计还原、真实业务模块补齐、外部配置正式联通、完整视觉验收和最终代码审查。
