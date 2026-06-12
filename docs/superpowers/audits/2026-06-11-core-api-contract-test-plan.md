# 鑫泰铝业 数据中枢：核心接口字段契约测试计划

日期：2026-06-11

状态：只读审计版，供下一阶段 TDD 修复使用。

## 1. 这份计划解决什么问题

现在系统最大的问题不是“没有接口”，而是“页面、算法、外部 MES、填报数据都在用同一批字段”。一旦字段名、单位、时间口径或数据来源变了，前端就可能出现：

1. 后端有数据，页面却显示 0。
2. MES 包装产量和内勤入库填报混在一起。
3. 能耗有电量，但吨耗因为产量分母不清楚显示异常。
4. PC、WAN、一体机设备名没有正确匹配到机列。
5. 调度大屏数字跳动，但跳的是不可信数据。

所以先写“契约测试”。白话说，就是给核心接口定规矩：这些字段必须有，单位必须对，时间窗口必须对，数据来源必须说清楚。以后前端重构、卷级线索页、实时大屏、物联网能耗接入，都不能破坏这些规矩。

## 2. 审计证据来源

- 代码图谱：当前索引 972 个文件、14742 个符号、30663 条关系。
- 实时聚合结构：`backend/app/schemas/realtime.py`。
- MES 同步和补录结构：`backend/app/schemas/mes_sync.py`、`backend/app/schemas/mobile.py`。
- 工厂调度结构：`backend/app/schemas/factory_command.py`。
- 能耗结构：`backend/app/schemas/energy.py`。
- 已有测试：`backend/tests/test_realtime_routes.py`、`backend/tests/test_realtime_service.py`、`backend/tests/test_mes_supplement_readiness_service.py`、`backend/tests/test_mobile_mes_pending_supplements.py`、`backend/tests/test_energy_summary.py`、`backend/tests/test_factory_command_service.py`。
- 页面覆盖底表：`docs/superpowers/audits/2026-06-11-page-api-coverage-matrix.md`。
- 后端风险底图：`docs/superpowers/audits/2026-06-11-backend-architecture-risk-map.md`。

## 3. 核心接口契约清单

| 接口 | 主要页面 | 必须稳定的字段 | 必须测试的业务规矩 |
| --- | --- | --- | --- |
| `/api/v1/aggregation/live` | `/manage/live`、`/manage/today`、`/manage/fill-details`、车间看板 | `business_date`、`business_date_context`、`overall_progress`、`workshops`、`factory_total`、`data_quality`、`mes_machine_binding`、`owner_daily_status`、`mes_sync_status`、`data_source` | 后端有包装产量时前端不能显示 0；异常废料和异常成品率不能直接进主指标；业务日必须跟 07:30 主口径一致 |
| `/api/v1/mes/supplement-readiness` | 系统设置、补录健康、终端匹配 | `business_date`、`status`、`coverage`、`machine_binding`、`material_categories`、`window_comparison`、`unmatched_devices`、`warnings` | PC/WAN 通用终端不能强行归机；低匹配率必须给出待处理清单；补录窗口必须说明 09:30 |
| `/api/v1/factory-command/coils` | 卷级线索页、实时调度大屏 | `coil_key`、`tracking_card_no`、`batch_no`、`material_code`、`line_code`、`machine_code`、`current_workshop`、`current_process`、`next_workshop`、`next_process`、`destination` | 未匹配机列必须明确显示为未匹配，不能伪装成真实机列；随行卡、客户、合金、规格要作为填报辅助线索 |
| `/api/v1/factory-command/destinations` | 库存去向、未来调度大屏 | `kind`、`label`、`coil_count`、`tons`、`freshness` | `tons` 必须确认真的是吨，不是 kg；无数据显示 0，但要带同步状态 |
| `/api/v1/energy/summary` | `/manage/energy`、实时大屏能耗区 | `business_date`、`workshop_id`、`workshop_code`、`shift_config_id`、`shift_code`、`electricity_value`、`gas_value`、`water_value`、`total_energy`、`output_weight`、`energy_per_ton` | 有能耗但产量分母为 0 时，吨耗应显示“无产量分母”，不能显示成 0 吨耗；未来物联网库只能同步到本地影子表后再给前端 |
| `/api/v1/mobile/current-shift` | 手机填报首页 | `business_date`、`shift_code`、`shift_name`、`workshop_id`、`machine_id`、`machine_code`、`machine_name`、`entry_channel`、`active_reminders` | 主操、电工等生产角色按 07:30 循环；内勤补录另按 09:30；真实二维码和机台账号必须复测 |
| `/api/v1/mobile/mes-pending-supplements` | 手机 MES 辅助补录 | `business_date`、`business_day_start`、`is_machine_bound`、`machine`、`summary`、`items` | 只显示当前机台相关待补录卷；字段可编辑不锁死；MES 缺失时不阻断手填 |
| `/api/v1/assistant/live-probe` | AI 助手健康检查 | `ready`、`text_probe_ok`、`image_probe_ok`、`overall_ok`、`text_model`、`image_model`、`checked_at`、`errors` | AI 只能读，不能写生产数据；回答必须能带来源和更新时间 |

## 4. 已有测试覆盖

已经有比较好的覆盖：

1. 实时聚合路由和服务已有测试，覆盖了实时大屏、填报明细、缺报导出、MES 投影不混进人工填报明细、机列匹配摘要、业务日上下文。
2. MES 补录就绪度已有服务测试，覆盖了 PC 包装通用终端不阻断、匹配率、输出重量覆盖率、低覆盖预警。
3. 手机 MES 待补录已有测试，覆盖了当前机台过滤、已完成补录排除、未绑定机台、09:30 窗口、缺少 MES 下机重量跳过、冷轧道次标记。
4. 能耗摘要已有路由测试，覆盖了字段返回、权限、车间范围过滤、导入接口停用。
5. 工厂调度服务已有较多测试，覆盖了 MES 工序、填报数据、机列、卷流向、移动卷数据等混合场景。
6. AI 助手健康检查已有测试，覆盖了 LLM 未配置和配置可用两种情况。

## 5. 还缺的测试

这些缺口建议下一阶段优先补：

| 缺口 | 为什么重要 | 推荐测试文件 |
| --- | --- | --- |
| 实时大屏字段映射契约 | 线上曾出现接口有数但页面显示 0 | `backend/tests/test_realtime_contracts.py` 或现有 realtime 测试内新增 |
| `factory_total` 主指标来源契约 | MES 包装产量、内勤入库、车间下机量不能混 | `backend/tests/test_core_metric_contracts.py` |
| 异常废料/成品率隔离契约 | 防止异常值上主屏误导管理决策 | `backend/tests/test_realtime_service.py` |
| 库存去向单位契约 | `tons` 如果实际是 kg 会严重误导 | `backend/tests/test_factory_command_service.py` |
| 合同中心指标矛盾契约 | 履约率、延期、交付吨数不能互相打架 | `backend/tests/test_contracts_routes.py` |
| 能耗分母状态契约 | 有电量但无产量分母时不能显示成 0 吨耗 | `backend/tests/test_energy_summary.py` |
| 前端字段使用契约 | 防止 Vue 页面接错后端字段 | `frontend` 对应页面测试或轻量字段映射测试 |
| 手机真实二维码回归 | 管理员账号测试不能代表机台扫码体验 | 浏览器 QA 脚本 |

## 6. 第一批 TDD 建议

下一阶段不要一上来重构大屏。先做 6 个小测试，让系统数字先稳住：

1. `/aggregation/live` 返回 MES 包装产量时，断言 `factory_total.packaging_output`、`daily_output`、`finished_inbound_output` 同时存在，且来源标签清楚。
2. 构造异常数据：投料很大、废料很大、成品率异常，断言主屏主指标不直接采用，并进入 `data_quality`。
3. `/energy/summary` 返回电量但 `output_weight=0` 时，断言 `energy_per_ton=None`，并要求前端展示“无产量分母”。
4. `/factory-command/destinations` 返回库存去向时，断言 `tons` 单位为吨，并加一个 kg/吨换算防错用例。
5. `/mes/supplement-readiness` 遇到 `PC`、`WAN`、未知一体机时，断言进入未匹配或终端绑定待处理，不自动归到任意机列。
6. `/mobile/mes-pending-supplements` 断言 `business_day_start='09:30'`，字段保持可编辑，且无 MES 匹配不阻断手工填报。

## 7. 前端验收规则

前端只做视觉重构还不够，必须保证页面显示的字段和后端契约一致：

1. 所有 `0` 必须分清：真实为 0、未同步、无权限、接口失败、异常隔离。
2. MES 包装产量和内勤入库填报必须并列展示，不能互相覆盖。
3. 卷级线索页展示 MES 记录，填报明细页只展示人工填报记录。
4. 实时大屏只对真实变化做数字滚动，不对未知值做“假跳动”。
5. PC/WAN 未匹配时，页面要显示“待绑定”，不能显示成某台机。
6. 能耗接物联网库后，前端仍只读本地接口，不直接连接外部库。

## 8. 五视角评分

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.7 | 能先保护管理决策最关心的数字可信度 |
| 工程师 | 9.7 | 测试切口小，能防止后续大屏和卷级页改坏旧链路 |
| 设计师 | 9.6 | 明确了 0、未同步、异常、待绑定等状态语言 |
| 安全审查 | 9.7 | 明确外部 MES 和物联网库只读同步，前端不直连外部库 |
| 真实用户 | 9.6 | 能减少重复填报和看错数，但还需要真实二维码回归 |

综合：9.66/10。

结论：可以进入下一阶段 TDD 修复准备，但建议先补契约测试，再做实时大屏和卷级线索页的前端重构。
