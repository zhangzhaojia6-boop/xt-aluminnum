# 鑫泰铝业 数据中枢：管理端核心页面 QA 与数据链路底图

更新时间：2026-06-14 08:49 +08:00

## 1. 本轮做了什么

本轮只读验证管理端核心页面，不提交、不删除、不修改生产数据。

验证目标：

- 确认管理端核心页面能不能打开。
- 确认页面实际调用哪些后端接口。
- 确认前端显示的是 MES 外部数据、人工填报，还是算法数据。
- 记录哪些现象是真问题，哪些只是页面切换时的请求取消噪声。

## 2. 路由和页面组件

前端核心路由来自 `frontend/src/router/index.js`。

| 页面 | 组件 | 作用 |
|---|---|---|
| `/manage/live` | `LiveDashboardPage.vue` | 全厂实时调度墙 |
| `/manage/today` | `TodayPage.vue` | 昨日日报 |
| `/manage/production` | `ProductionPage.vue` | 生产分析 |
| `/manage/workshop-dashboard` | `WorkshopDashboardPage.vue` | 车间主任看板 |
| `/manage/coils` | `CoilTracePage.vue` | MES 卷级线索 |
| `/manage/fill-details` | `FillDetailsPage.vue` | 人工填报明细和 MES 对照异常 |
| `/manage/energy` | `EnergyCenter.vue` | 能耗中心 |
| `/manage/alerts` | `AlertsPage.vue` | 异常与对账队列 |
| `/manage/admin/settings` | `SystemSettingsPage.vue` | 系统配置入口 |
| `/manage/admin/agents` | `AgentManagementPage.vue` | 通讯治理台 |

旧入口兼容：

- `/admin/setting` 会跳到 `/manage/admin/settings`。
- `/manage/daily-report` 会跳到 `/manage/today`。
- `/review/*`、`/admin/*`、`/mobile/*` 有大量兼容跳转，清理前必须先查依赖，不要直接删。

## 3. 页面和接口对应关系

| 页面 | 主要接口 | 数据理解 |
|---|---|---|
| `/manage/live` | `/aggregation/live/active-date`、`/aggregation/live`、`/aggregation/live/fill-details`、`/realtime/stream` | 实时大屏，混合 MES 外部数据、人工填报、算法汇总 |
| `/manage/today` | `/dashboard/daily-production`、`/dashboard/timeseries`、`/users/`、`/aggregation/live` | 昨日报表，核心指标来自日报汇总，辅助查用户和实时聚合 |
| `/manage/production` | `/dashboard/daily-production`、`/factory-command/overview` | 生产分析，和昨日报表共用一部分日报口径 |
| `/manage/workshop-dashboard` | `/master/workshops`、`/aggregation/live/*`、`/mes/extended/*` | 车间看板，同时看人工填报、MES 工序、MES 物料和异常 |
| `/manage/coils` | `/factory-command/coils`、`/factory-command/coils/{coil_key}/flow` | 卷级线索，以 MES 投影数据为主 |
| `/manage/fill-details` | `/aggregation/live/fill-details`、`/aggregation/live/mes-fill-gaps`、`/dashboard/daily-production`、`/master/workshops` | 人工填报明细为主，MES 只做对照和缺口，不混成填报记录 |
| `/manage/energy` | `/energy/summary` | 能耗汇总，电工填报为能耗来源，MES 包装产量可作为吨耗分母 |
| `/manage/alerts` | `/quality/issues`、`/reconciliation/items`、`/aggregation/live/mes-fill-gaps`、`/aggregation/live` | 异常页，把质量、对账、MES 缺口、实时缺报汇到一起 |
| `/manage/admin/settings` | `/mes/supplement-readiness` | 设置入口，同时显示 MES 补录就绪情况 |
| `/manage/admin/agents` | `/agent-management/overview` | 智能体/外部通讯治理状态 |

## 4. 后端路由对应

后端核心路由文件：

- `backend/app/routers/dashboard.py`：日报、统计、时间序列、外部就绪。
- `backend/app/routers/realtime.py`：实时流、实时聚合、填报明细、MES 对照缺口、缺报导出。
- `backend/app/routers/factory_command.py`：生产流转、卷级线索、车间/机列、成本收益。
- `backend/app/routers/energy.py`：能耗汇总。
- `backend/app/routers/mes.py`：MES 同步状态、MES 扩展数据、补录就绪。
- `backend/app/routers/agent_management.py`：通讯治理台。
- `backend/app/routers/master.py`：车间、机列、别名、PC 工艺映射、规则配置。

## 5. 核心数据表和字段口径

本轮只读核对的生产库计数：

| 表 | 当前行数 | 用途 |
|---|---:|---|
| `mes_stock_records` | 1501 | MES 包装/入库口径，日报包装产量主来源 |
| `mes_workshop_process_records` | 2068 | MES 工序过站、下机、设备/PC、工艺 |
| `mes_material_records` | 268 | MES 坯料/物料 |
| `mes_yield_records` | 329 | MES 成品率/良率相关 |
| `mes_machine_line_snapshots` | 100 | MES 机列快照 |
| `mes_daily_wip_snapshots` | 120 | MES 在制快照 |
| `mobile_shift_reports` | 189 | 手机端班次/日报填报主记录 |
| `machine_energy_records` | 27 | 电工按机列填报能耗 |
| `work_order_entries` | 2761 | 主操卷级/随行卡录入 |
| `daily_consumable_logs` | 1 | 内勤每日一录 |
| `users` | 112 | 用户账号 |
| `workshops` | 25 | 车间和部门台账 |
| `equipment` | 185 | 机台和二维码台账 |

最新时间：

- `mes_workshop_process_records.business_date` 最新到 `2026-06-14`。
- `mes_workshop_process_records.last_seen_from_mes_at` 最新到 `2026-06-14 08:47 +08:00`。
- `mes_stock_records.business_date` 最新到 `2026-06-13`。
- `mes_stock_records.last_seen_from_mes_at` 最新到 `2026-06-14 08:47 +08:00`。
- `mobile_shift_reports.business_date` 最新到 `2026-06-14`。
- `machine_energy_records` 关联填报业务日最新到 `2026-06-14`。

字段纠错：

- MES 工序结束时间字段是 `end_time`，不是 `ended_at`。
- MES 同步可见时间字段是 `last_seen_from_mes_at`，不是 `synced_at`。
- 智能体表名是 `agent_profiles`、`agent_channel_bindings`、`agent_outbox_messages`、`agent_events`、`agent_operation_approvals` 等，不是 `agent_registry` 或 `agent_message_channels`。

## 6. 线上接口摘要

本轮使用管理员登录态只读请求接口。

| 接口 | 结果 | 关键返回 |
|---|---|---|
| `/dashboard/daily-production?target_date=2026-06-13` | 200 | 包装产量 `233.0` 吨，全厂入库产量 `246.38` 吨，日成品率 `94.57%` |
| `/factory-command/overview?target_date=2026-06-14` | 200 | `business_date=2026-06-14`，`source=mixed` |
| `/aggregation/live?business_date=2026-06-14` | 200 | 实时大屏聚合，包含车间、全厂、数据质量、MES 同步 |
| `/aggregation/live/fill-details?business_date=2026-06-13&limit=10` | 200 | 填报明细样本 10 条 |
| `/aggregation/live/mes-fill-gaps?business_date=2026-06-13` | 200 | MES 对照缺口 195 条 |
| `/factory-command/coils?limit=5` | 200 | 卷级线索样本，含随行卡、合金、当前工艺、机列、自动废料 |
| `/energy/summary?business_date=2026-06-13` | 200 | 能耗明细 7 条 |
| `/agent-management/overview?limit=20` | 200 | `safe_mode=true`，当前智能体记录数为 0 |

注意：直接请求 `/aggregation/live` 不带 `business_date` 会返回 422。这不是页面错误，页面实际会带业务日期参数。

## 7. 浏览器 QA 结果

截图目录：

`.gstack/qa-reports/manage-core-2026-06-14T00-43-55-270Z/`

| 页面 | 是否打开 | 控制台错误 | 失败请求 | 结论 |
|---|---|---:|---:|---|
| `/manage/live` | 是 | 0 | 0 | 正常 |
| `/manage/today` | 是 | 0 | 1 | 页面正常，失败请求为离开实时页时 SSE 被取消 |
| `/manage/production` | 是 | 0 | 3 | 页面正常，失败请求为切页取消旧请求 |
| `/manage/workshop-dashboard` | 是 | 0 | 1 | 页面正常，失败请求为切页取消旧请求 |
| `/manage/coils` | 是 | 0 | 1 | 页面正常，失败请求为切页取消旧请求 |
| `/manage/fill-details` | 是 | 0 | 0 | 正常 |
| `/manage/energy` | 是 | 0 | 0 | 正常 |
| `/manage/alerts` | 是 | 0 | 0 | 正常 |
| `/manage/admin/settings` | 是 | 0 | 1 | 页面正常，失败请求为切页取消旧请求 |
| `/manage/admin/agents` | 是 | 0 | 0 | 正常 |

`net::ERR_ABORTED` 判断：

- 本轮失败请求都是切页时旧请求被浏览器取消，主接口已经返回 200。
- 暂不按业务阻塞处理。
- 后续若出现 4xx/5xx 或页面明确报错，才应升级为问题。

## 8. 页面观察

已确认：

- 实时页显示 `MES 外部数据 / 人工填报 / 算法数据` 三类来源。
- 填报明细页同屏区分 `MES包装产量`、`内勤入库填报`、`过站下机参考`、`算法总用电`、`电工填报`。
- 能耗页显示电耗、气耗、水耗、总能耗、产量、单吨峰值，明细来源能显示为 `电工填报`、`MES包装产量` 等。
- 通讯治理台当前为空状态，接口返回安全模式。

需要继续跟踪：

- `/manage/today` 当前截图里很多卡片显示“暂无可信数据”，但接口直接返回了 `2026-06-13` 的包装产量、入库产量和成品率。需要下一轮继续查是前端可信度规则、日期同步时机、还是字段映射让部分卡片未展示。
- `/manage/production` 截图里核心卡片显示 `—`，但接口返回了日报和生产概览数据。需要下一轮查 `buildProductionStitchSurface` 的字段映射和空值判断。
- `/manage/workshop-dashboard` 管理员默认看到 `铸锭分厂`，但车间选择里仍有回收、成品库等更宽口径。这里不是错误，但必须区分生产口径和部门口径。
- `/manage/admin/agents` 当前表为空，表示外部通讯/agent 治理功能框架已在，数据尚未配置或尚未产生。

## 9. 本轮没有验证的内容

不能把下面内容说成已经通过：

- 没有点击写入类按钮。
- 没有导出缺报 Excel。
- 没有测试新增、编辑、删除用户或配置。
- 没有测试 AI 对话真实生成。
- 没有测试钉钉真实消息发送。
- 没有跑完整自动化回归测试。
- 没有对每个角色逐个页面做全覆盖。

## 10. 下一步建议

下一轮建议优先查两个“页面显示与接口返回不一致”的点：

1. `/manage/today` 为什么直接接口有数据，但部分 KPI 卡片显示“暂无可信数据”。
2. `/manage/production` 为什么接口有数据，但生产分析页大卡显示 `—`。

这两项更接近真实用户痛点：用户看到的是页面，不是接口；如果页面空态规则过严，就会误以为系统没数据。

