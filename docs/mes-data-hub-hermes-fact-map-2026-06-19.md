# MES / WMS / 数据中枢 / Hermes 事实地图

日期：2026-06-19

本文只做事实地图，不写任何真实凭据、账号或连接配置。

小白版一句话：Hermes 是工厂超级大脑，负责主动看数据、找证据、判断冲突、推动动作和复盘成长；但正式数字不能靠它“猜”。日报最终数先看业务日窗口内 Hermes/钉钉收到的车间和内勤消息；再看 MES/WMS 系统里的最终页面或最终单据；最后才看数据中枢投影。MES/WMS SQL 原始行默认只是证据和兜底。

## 状态说明

| 状态 | 含义 |
|---|---|
| `已证实` | 已被本仓库文档、后端代码、前端代码或模型字段直接证明。 |
| `最终口径已对齐` | 已用真实业务日和人工统计核对过，可以作为该字段最终日报来源。 |
| `证据源` | 链路、字段、单位基本明确，但不能直接当最终日报数，只能用于核对、追溯、解释差异。 |
| `候选` | 表名、字段名或页面方向已经有证据，但还没有完成同级别字段对账或页面实测。 |
| `待浏览器/SQL复核` | 需要登录 MES 页面、跑只读 SQL 或拿真实业务日继续核对，不能当最终口径。 |

## 阅读边界

- 已读取：`README.md`、`docs/mes-page-table-mapping.md`、`docs/mes-xintaily-full-page-table-audit.md`、`docs/mes-xtmijd-alignment-matrix.md`、`docs/superpowers/plans/2026-06-04-mes-sqlserver-direct-connection-office-hours.md`、`docs/system-understanding-consolidated-2026-06-14.md`、`docs/audits/output-skill-data-mapping-baseline.md`、`docs/audits/template-daily-report-outputskill-baseline.md`。
- 已读取 skill 参考：`xintaily-mes-daily-report/SKILL.md`、`references/business-time-and-metrics.md`、`references/direct-mes-source-map.md`、`references/manual-alignment-source-priority.md`、`references/workshop-report-templates.md`。
- 已读取代码：`backend/app/core/business_time.py`、`backend/app/adapters/sqlserver_mes_adapter.py`、`backend/app/services/mes_sync_service.py`、`backend/app/services/report/mes_factory_production_fact.py`、`backend/app/services/report/mes_factory_packaging_fact.py`、`backend/app/services/report/mes_workshop_machine_reconciliation.py`、`backend/app/services/report/template_daily_fact_sources.py`、`backend/app/services/report/template_daily_report.py`、`backend/app/services/report/output_skill_report_parser.py`、`backend/app/routers/dashboard.py`、`backend/app/routers/mes.py`、`frontend/src/router/index.js`、`frontend/src/api/*.js`、`frontend/src/views/manage/workshop-dashboard/WorkshopDashboardPage.vue`。
- 指定的 `docs/longterm-ai-skill-system-spec.md` 在当前 worktree 未找到；本文件没有引用不存在文件里的结论。

## 业务时间

| 口径 | 时间窗口 | 状态 | 证据 |
|---|---|---|---|
| 普通生产车间 | `07:50-07:50` | `已证实` | `backend/app/core/business_time.py` 中 `PRODUCTION_BUSINESS_DAY_START = 07:50`；MES 对齐文档也写明默认 `07:50` 到次日 `07:50`。 |
| 铸二、铸三、热轧 | `10:00-10:00` | `已证实` | `BILLET_PRODUCTION_BUSINESS_DAY_START = 10:00`，`BILLET_BUSINESS_TIME_WORKSHOPS = {'铸二','铸三','热轧'}`。 |
| 内勤/一日汇总 | `09:30` 起算 | `已证实` | `OWNER_DAILY_BUSINESS_DAY_START = 09:30`，移动端也展示每日一录按 `09:30` 归属。 |
| 内勤迟报参考 | `10:00` | `已证实` | `OWNER_DAILY_LATE_CUTOFF = 10:00`。 |
| 旧文档里的 `07:30` | 历史口径或日报调度口径 | `待浏览器/SQL复核` | 旧总理解文档、部分 RAG 静态文本、日报任务仍出现 `07:30`；MES 字段对齐以当前 `business_time.py` 和 2026-06-18 MES 对齐文档为准。 |

### 交接 / 加班边界

普通生产车间的主窗口仍按 `07:50-次日07:50`，但 `07:30-08:00` 要当成“交接/加班复核区”，不能只按原始录入时间硬分业务日。

处理规则：

1. 如果 Hermes/钉钉消息、班次文字、加班说明、MES/WMS 最终页面明确说这条数据属于前一个业务日，就归前一个业务日。
2. 如果只有 MES/WMS 原始 SQL 时间落在 `07:30-08:00`，没有最终消息或页面佐证，只能作为证据，不能直接当最终日报数。
3. 不能把所有查询窗口简单改成 `07:30-08:00`；那会有把第二天早班重复算进前一天的风险。
4. 差异原因统一标记为 `业务日边界/加班归属需复核`。

## 架构决定

| 决定 | 状态 | 说明 |
|---|---|---|
| 页面不直查 MES SQL Server | `已证实` | 前端只调用 `/api/v1/...`；后端页面接口读本地业务库和 `mes_*` 投影。 |
| Hermes 可以作为高权限超级大脑调度数据源 | `设计目标` | Hermes 可以主动查 MES、数据中枢、WMS、钉钉、RAG 和历史报表，目标是感知、理解、判断、行动、复盘和成长。 |
| Hermes/钉钉接收消息是日报最高优先级事实输入 | `已证实` 业务规则 | 这是取数优先级，不是 SQL 查询链路。消息必须在业务日窗口内接收，并保留发送人、频道、接收时间和原文。 |
| Hermes 高自主执行必须可追责、可回滚 | `设计目标` | 数据中枢可允许 Hermes 高自主补齐、修正、归档、入库；每次写入必须记录证据、原因、操作者、前后值和回滚路径。 |
| SQL Server 只用于 adapter/sync/audit/read-through | `已证实` | `SqlServerMesAdapter` 只允许固定 `SELECT`；`mes_sync_service` 把结果写入本地投影；审计脚本只读；read-through 只能作为受控后端读取，不给页面直接绕过本地投影。 |
| 外部凭据不入代码、文档、日志 | `已证实` | SQL Server 方案文档明确禁止写真实凭据；代码有敏感字段过滤和错误脱敏。 |

## 日报最终事实优先级

按本次业务规则，日报最终值优先级如下。这里的“优先级”指最终字段取数，不是 Hermes 思考顺序；Hermes 可以灵活查证，但落正式数字时必须按字段证据等级走。

1. Hermes/钉钉接收消息：在对应业务日时间区间内收到的车间日报、内勤填报、能耗填报消息。必须保留发送人、频道、接收时间和原文片段。
2. MES 系统 = WMS 系统：MES final pages/APIs 和 WMS 最终单据并列。生产、在制、合同、投料、坯料、前世今生优先看 MES；成品库入库、成品库发货、仓库调拨优先看 WMS。
3. 数据中枢系统：本地 `mes_*` 投影、owner daily、日报事实包和能耗/成本汇总。用于兜底、审计、历史归档、接口展示和差异复盘。
5. Direct MES/WMS SQL rows：核对证据、审计追溯、已证明对齐字段的兜底。
6. `缺失`：远端最终源和已证明证据都没有时。

Hermes/钉钉消息只有在“接收时间落入目标业务日窗口，且消息内容能明确对应目标日期/业务日”时，才是最高优先级最终源；否则降级为证据源。MES 和 WMS 并列时，按字段归属选择：生产字段用 MES，仓储字段用 WMS；两者冲突时保留差异，不互相覆盖。数据中枢系统低于 Hermes/MES/WMS，因为它可能是同步投影或汇总结果，存在延迟和二次口径加工。

`MES_ProductProcessRecord.EndWeight`、`MES_Material.Weight` 这类原始过程重量，默认是证据源，不是最终日报产量。

别名硬规则：`园区精整 = 园区剪切 = 园区精整车间 = 园区剪切车间 = 剪切车间`。输出标准名用 `园区剪切`，但保留原始名称方便追溯。`精整` 仍是独立车间，不能合并到园区剪切。

标准链路：

```text
MES 页面/MVC 证据 + SQL Server 只读表
  -> SqlServerMesAdapter
  -> mes_sync_service
  -> 本地 mes_* 投影表
  -> FastAPI /api/v1 接口
  -> Vue 管理端/移动端
  -> Hermes 日报事实包 / RAG 历史 / 输出 skill 对齐
```

取数优先链路：

```text
Hermes/钉钉业务日消息
  -> MES 系统最终页面/API 或 WMS 系统最终单据
  -> 数据中枢系统投影/汇总
  -> Direct MES/WMS SQL 证据
  -> 缺失
```

## 不能直接对齐项的解决规则

| 字段 | 远端直取问题 | 解决办法 |
|---|---|---|
| 1650 冷轧 | `MES_ProductProcessRecord.EndWeight` 是过程下机重量，可能包含中退、开坯、非最终成品，不等于人工日报成品产量。 | 先取业务日窗口内 Hermes/钉钉 1650 日报消息里的 `成品/中退/开坯/日轧道次`；没有消息时，再找 MES 车间报表最终页是否已拆分这些字段。原始过程重量只做证据。 |
| 2050 冷轧 | 同 1650，且 `WorkShop` 可能不如 `DeviceName` 准确。 | 同 1650；核对证据要优先看 `DeviceName`，不能只按 `WorkShop` 汇总。 |
| 拉矫下机 | 当前 MES 工序路径没有覆盖人工口径里的全部班次/下机字段。 | 先取 Hermes/钉钉拉矫消息；没有消息时，必须定位 MES 最终页或证明具体 `Process/DeviceName` 组合能覆盖白班、小夜、大夜。否则标 `MES未取到对应工序`。 |
| 园区剪切包装 | 园区精整就是园区剪切，但 `包装录入`、`成品调拨`、`成品库入库` 是三种单据，数值可以不同。 | 包装字段先取 Hermes/钉钉园区剪切消息；成品调拨只做入库产量证据；WMS 入库只做仓储入库事实。不要把三种数混成一个数。 |
| 热轧坯料 | 坯料明细简单按 `已使用+未使用` 求和不等于热轧最终产量。 | 先取 Hermes/钉钉热轧日报消息；没有消息时找 MES 热轧最终报表页。坯料明细只保留为审计证据，业务时间仍按 `10:00-10:00`。 |
| 铸二 | 坯料明细简单求和与人工日报不一致。 | 先取 Hermes/钉钉铸二日报消息；没有消息时找 MES 最终页。坯料明细只做证据。 |
| 铸三 | 坯料明细简单求和与人工日报不一致。 | 先取 Hermes/钉钉铸三日报消息；没有消息时找 MES 最终页。坯料明细只做证据。 |

## Hermes 超级大脑层

Hermes 不是统计员，也不是只会回答问题的报表助手。目标形态是制造业工厂超级大脑：

```text
感知 -> 理解 -> 判断 -> 行动 -> 复盘 -> 成长
```

| 层 | 作用 | 数据对象 |
|---|---|---|
| Perception Engine 感知引擎 | 负责看见现场和系统数据 | MES、数据中枢、WMS、钉钉文本、钉钉文件、RAG、历史报表、人工填报 |
| Reasoning Engine 推理引擎 | 负责判断可信度、异常、冲突和下一步查证路径 | 数据差异、缺失字段、历史均值、业务规则、来源优先级 |
| Action Engine 行动引擎 | 负责推动动作 | 生成日报草稿、归档文件、创建补录任务、写入数据中枢、发起审批或通知 |
| Learning Engine 学习引擎 | 负责沉淀经验 | 事实记忆、规则记忆、偏好记忆、案例记忆、能力复盘 |

技术骨架：

| 技术层 | 分工 |
|---|---|
| LangGraph | 编排 Hermes 状态流转：收任务、查证、推理、暂停确认、执行、输出、复盘。 |
| LangChain | 接入工具和 RAG：MES 查询、数据中枢查询、WMS 查询、钉钉消息/文件、输出 skill、知识库检索。 |
| ReAct Loop | 单次任务按 `Observe -> Think -> Act -> Reflect -> Answer` 运转，避免直接拍脑袋回答。 |
| Harness Loop | 持续测试 Hermes 是否查对来源、漏掉异常、误用钉钉、能否对齐输出 skill 成品。 |
| Policy/Audit Gate | 不做低自主刹车，而做可追责门禁：所有写入和修正必须有证据、记录和回滚路径。 |

主动触发器：

1. 到点未收到数据。
2. MES、数据中枢、WMS、钉钉之间数值冲突。
3. 产量、成材率、库存、发货、能耗、废料、停机等指标异常。
4. 钉钉出现“日报、产量表、库存表、发货清单、异常说明、补录、重发”等关键文本或文件。
5. 车间缺报、审批卡住、文件无人确认。
6. 老板或厂长近期关注项变化。
7. Hermes 自己发现证据不足、规则不适用或历史记忆冲突。

## 钉钉文本与文件入库规则

钉钉资料可以进入最终输出，但必须带来源身份。Hermes 可以自主监测并入库，但要保留 `群/频道、发送人、消息时间、接收时间、文件名、文件哈希、解析状态、证据等级`。

| 类型 | 例子 | 入库方式 | 最终输出作用 |
|---|---|---|---|
| 事实型文件 | 产量表、库存表、发货表、日报表 | 自动入库，解析字段，进入 RAG 和审计证据 | 可参与比对；上升为最终事实需看字段优先级和审计记录 |
| 解释型文本 | “2050 停机 2 小时，所以产量低” | 自动入库，保留上下文和发送人 | 可作为原因说明进入最终输出 |
| 指令型文本 | “把昨天数据改成这个数” | 自动入库，生成待执行或已执行审计项 | 可触发数据中枢修正，但必须记录证据、前后值和回滚路径 |
| 噪声型文本 | 闲聊、表情、重复无效文件 | 可低权重记录或丢弃 | 不进入最终输出 |

## MES 提取规则

MES 提取规则参考 `xintaily-mes-daily-report`：

1. 必须先确定业务日窗口：铸二、铸三、热轧是 `10:00-10:00`；其他车间是 `07:50-07:50`。
2. 汇总前必须归一化车间别名：`园区精整`、`园区精整车间`、`园区剪切`、`园区剪切车间`、`剪切车间` 都输出为 `园区剪切`；`精整` 仍是独立车间。
3. 远端最终事实优先，原始 SQL 行默认只是证据。不能用 MES 过程产量直接覆盖车间最终日报字段。
4. 原始重量字段按来源规则换算吨；多数 MES/WMS 重量字段需要 `/1000`。
5. 查到记录且求和为零，输出 `0`；字段、页面、表或工序没定位，输出 `缺失`；不能凭记忆补数。
6. 冲突说明使用固定标签：`别名已归并后仍差异`、`MES未取到对应工序`、`口径不同：包装录入 / 成品调拨 / 成品库入库`。

已证明可直接拉取或强证据拉取的规则：

| 字段 | 规则 | 事实等级 |
|---|---|---|
| 成品库入库 | `WMS_InStock.InStockDate` 落在 `07:50` 业务窗口，状态有效，`Type = InStockAllocation / 调拨入库`，汇总 `TotalNetWeight / 1000` | 仓储字段最终源 |
| 成品库发货 | `WMS_OutStock.OutStockDate` 落在 `07:50` 业务窗口，状态有效，`Type = OutStockDelivery / 通知出库`，排除 `OutStockRevoke / 返厂出库` | 仓储字段最终源 |
| 成品调拨车间量 | `MES_AllocationDetail.CreateDate` 落在 `07:50` 业务窗口，状态有效，目标部门是成品库，按 `FromDepartment` 归一化车间，汇总 `NetWeight / 1000` | 强证据；未精确对齐前不当最终日报数 |
| 铸二/铸三/热轧坯料证据 | `MES_Material.ProductionDate` 落在 `10:00` 业务窗口，状态含 `已使用`、`未使用` | 审计证据；未证明前不当最终产量 |

## 总事实地图

| MES 页面/业务 | 状态 | SQL Server 表字段 | 本地投影 | API | 前端页面 | Hermes / 输出 skill 字段 |
|---|---|---|---|---|---|---|
| 在制料：调度管理 / 生产车间实时查询 `/Dispatch/Index`、在制料统计 | `已证实` 字段链路；重量单位仍 `待浏览器/SQL复核` | `MES_Product.CurrentWorkShop`、`CurrentProcess`、`FeedingWeight`，在制过滤排除 `InStockDate`、`DeliveryDate`、空车间、空工序 | `mes_wip_total_snapshots.workshop_name/process_name/doing_count/doing_weight_tons/snapshot_at/source_payload`；日快照 `mes_daily_wip_snapshots.business_date/workshop_name/process_name/coil_count/material_weight_tons/feeding_weight_tons` | `GET /api/v1/mes/extended/wip-total-snapshots`；`GET /api/v1/dashboard/daily-production`；`GET /api/v1/dashboard/workshop-director` | `/manage/workshop-dashboard` 的在制料明细；`/manage/today` 和 `/manage/live` 的在制分布 | `wip_total`、`wip_1650_2050_cold`、`wip_1850_cold`、`wip_milling`、`wip_anneal_total`、`wip_new_north`、`wip_new_south`、`wip_park_anneal`、`wip_finishing_total`、`wip_straightening`、`wip_finishing`、`wip_park_finishing`、`wip_hot_plate_shearing`、`wip_coating` |
| 投料管理：计划管理 / 投料管理 `/Feeding/Index` | `已证实` | `MES_Product.FeedingWeight`、`CreateDate`、`CurrentWorkShop` | `mes_coil_snapshots.feeding_weight/business_date/event_time/current_workshop/source_payload.metadata.CreateDate` | `GET /api/v1/dashboard/mes-factory-production-reconciliation` 返回 `factory_feeding_daily_input`、`factory_feeding_month_to_date_input`；`GET /api/v1/dashboard/daily-production` | `/manage/workshop-dashboard` KPI `全厂投料`；`/manage/today` 日报卡片；`/manage/live` 实时头部 | 投料本身不是模板正文直接字段；用于 `daily_yield_rate/monthly_yield_rate` 的事实来源候选和对账字段 |
| 随行卡管理：计划管理 / 随行卡管理 `/FollowCard/Index` | `已证实` 本地字段；MES 页面列仍 `待浏览器/SQL复核` | 主表 `MES_Product`；随行卡优先 `MaterialCode`，兼容 `TrackingCardNo/FollowCardNo/CardNo/BatchNumber`；还包含 `Customer/CustomerSimple`、`Alloy`、`Specification`、`CurrentWorkShop`、`CurrentProcess`、`NextWorkShop`、`NextProcess`、`ProcessRoute` | `mes_coil_snapshots.tracking_card_no/material_code/batch_no/contract_no/customer_alias/alloy_grade/spec_display/current_workshop/current_process/next_workshop/next_process/process_route_text`；流转事件 `coil_flow_events` | `GET /api/v1/factory-command/coils`；`GET /api/v1/factory-command/coils/{coil_key}/flow`；`GET /api/v1/mobile/coil-flow-suggestion`；`GET /api/v1/work-orders/{tracking_card_no}` | `/manage/coils` 卷级线索；`/entry/coil` 按卷录入辅助 | 日报模板不直接打印随行卡；输出 skill 对齐可用卷号、合同、客户、机台、工序作对账维度 |
| 车间报表：车间生产管理 / 车间报表 `/Report/ProductionWorkshopReport` | `已证实` 字段链路；日报产量为 `证据源` | `MES_ProductProcessRecord.WorkShop`、`Process`、`DeviceName`、`BeginWeight`、`EndWeight`、`EndDatetime`、`Worker`、`BatchNumber` | `mes_workshop_process_records.workshop_name/process_name/device_name/input_weight_tons/output_weight_tons/end_time/business_date/worker_name/batch_no` | `GET /api/v1/dashboard/mes-workshop-machine-reconciliation`；`GET /api/v1/mes/extended/workshop-process-records`；`GET /api/v1/dashboard/daily-production` | `/manage/workshop-dashboard` 车间投料量、车间下机量、机台明细；`/manage/production`；`/manage/today` | 只能作为机台上机/下机、道次、工序追溯证据。6月19日冷轧、退火、拉矫等字段与人工统计不吻合，不能直接填 `cold_1650_daily`、`online_anneal_daily` 等最终日报字段。 |
| 包装录入：包装管理 / 包装录入 `/Pack/Index` | `已证实` 字段链路；总产量为 `证据源` | `MES_ProductProcessRecord.Process = 包装`、`EndWeight`、`EndDatetime`、`WorkShop` | `mes_workshop_process_records.output_weight_tons/end_time/business_date/process_name/workshop_name`，过滤工序名包含 `包装` | `GET /api/v1/dashboard/mes-factory-production-reconciliation`；`GET /api/v1/dashboard/mes-home-reconciliation`；`GET /api/v1/dashboard/daily-production` | `/manage/workshop-dashboard` KPI `全厂包装`；`/manage/today` 包装/总产量；`/manage/production` | 包装过程量可做核对证据。不能直接等同于 `total_output_daily/month` 或输出 skill 中“车间总产量日合计/月累计”，最终值优先取业务日窗口内 Hermes/钉钉日报消息；没有消息时再看 MES 最终页，最后用数据中枢兜底。 |
| 成品调拨单：包装管理 / 成品调拨单 `/Allocation/Index` | `已证实` 远端表；日报入库产量为接近 `证据源` | 主表/明细：`MES_Allocation.TotalNetWeight/CreateDate/FromDepartment/ToDepartment`、`MES_AllocationDetail.NetWeight/CreateDate/FromDepartment/ToDepartment`；园区精整和园区剪切必须归并 | 当前后端投影仍可能通过 `mes_stock_records.source_payload.FromDepartment/ToDepartment` 对照；建议后续同步为 `MES_Allocation/MES_AllocationDetail` 专用映射 | `GET /api/v1/dashboard/mes-factory-production-reconciliation` 的 `packaging_fact.finished_transfer_day`；`GET /api/v1/mes/extended/stock-records` | `/manage/today`、`/manage/production` 可作为包装流转对照；具体展示位置 `待浏览器/SQL复核` | 不直接替代 WMS 成品库入库，也不能和包装工序混成一个数。若 Hermes/钉钉消息给出园区剪切入库产量，以消息为最终值；MES 调拨单作为证据。6月19日园区剪切归并调拨为 164.916t，接近人工 164.994t，但不是零差异最终口径。 |
| 成品库出入库：成品库 / 库存查询 `/Stock/Index` | WMS 入库/通知出库 `最终口径已对齐`；总日报入库成品仍需单独口径 | 入库：`WMS_InStock.TotalNetWeight/InStockDate/Type`，`Type=InStockAllocation/调拨入库`；发货：`WMS_OutStock.TotalNetWeight/OutStockDate/Type`，只算 `OutStockDelivery/通知出库`，排除 `OutStockRevoke/返厂出库` | `mes_stock_records.source_path='sqlserver:stock_header_records'` 或 `sqlserver:stock_records`，字段 `net_weight_tons/in_stock_date/business_date/status_name`；出库兜底也落 `mes_stock_records` | `GET /api/v1/dashboard/mes-factory-production-reconciliation` 返回 `factory_finished_inbound_daily_output`、`factory_finished_inbound_month_to_date_output`；`GET /api/v1/mes/extended/stock-records` | `/manage/workshop-dashboard` KPI `成品入库`；`/manage/today` 入库成品；`/manage/production` | 仓储字段按 WMS 系统最终单据取数。若 Hermes/钉钉业务日消息明确给出成品库入库/发货且接收时间在业务日窗口内，消息优先；否则 WMS 为最终源。6月19日 WMS 入库 382.208t、通知出库 185.933t 与人工“成品库入库/发货”吻合；但不能替代总日报“入库成品日合计 366t”。 |
| 坯料明细：坯料管理 / 坯料明细 `/Material/Index` | `已证实` 字段链路；最终产量为 `证据源` | `MES_Material.Weight`、`ProductionDate`、`WorkShopRolling/PWorkShop/WorkShop`、`MaterialCode`、`Alloy`、`Specification`、`StatusName`；状态包含 `已使用`、`未使用` | `mes_material_records.material_code/workshop_name/line_name/alloy_grade/spec_display/weight_tons/production_date/business_date/status_name` | `GET /api/v1/mes/extended/material-records`；`GET /api/v1/dashboard/mes-workshop-machine-reconciliation` 的坯料车间 source_mapping；`GET /api/v1/dashboard/daily-production` | 坯料车间日报/生产分析；具体页面明细展示 `待浏览器/SQL复核` | 用作铸二、铸三、热轧审计证据，业务时间 `10:00-10:00`。最终产量优先取业务日窗口内 Hermes/钉钉车间消息；没有消息时看 MES 最终页；数据中枢只兜底。6月19日简单按 `已使用+未使用` 求和与人工最终产量不吻合，不能直接填 `hot_roll_daily/month`、`cast_2_daily/month`、`cast_3_daily/month`。 |
| 前世今生：前世今生 `/Archives/Index` | 本地追溯 `已证实`；MES 原页面字段 `候选` | 候选串联 `MES_Product`、`MES_ProductProcessRecord`、`WMS_InStockDetail`、`WMS_Stock` | `mes_coil_snapshots` + `mes_workshop_process_records` + `mes_stock_records` + `coil_flow_events` | `GET /api/v1/factory-command/coils`；`GET /api/v1/factory-command/coils/{coil_key}/flow` | `/manage/coils` 卷级线索，可看当前车间/工序、上一道/下一道、入库/调拨/交付状态 | 日报不直接打印；Hermes/RAG 可把它作为卷级追溯事实。缺某段时标缺口，不能补假数据 |
| Hermes/DingTalk 接收消息与日报事实包 | Hermes/钉钉接收消息为最高优先级；事实包链路 `已证实` | 不直接读 SQL Server；优先采用业务日窗口内收到的车间日报、内勤填报、能耗填报消息；消息缺失时才看 MES/WMS 和数据中枢 | `TemplateDailyFacts.target_date/wip_date/values/sources/missing_fields/conflicts`；最终进入 `daily_reports.report_data.template_daily_report` 和 `final_text_summary` | `GET /api/v1/reports/template-daily/preview`；后台 `generate_daily_reports()`；RAG 归档 `archive_latest_daily_report_to_rag()` | `/manage/today` 日报工作台；Hermes 钉钉/日报推送链路 | `REQUIRED_FIELDS` 全量字段，分组为 opening、workshop_output、manual_supplement、wip、energy、contract_input、yield、cost。每个字段需保留消息来源、接收时间、原始车间名和归并后车间名。 |
| 输出 skill 样本 | `已证实` 为验证源；全量真实匹配率仍 `待浏览器/SQL复核` | 不作为运行时 SQL 源；只读参考文件结构和脱敏样本 | 系统侧拉平本地 `mes_*`、`work_order_entries`、`machine_energy_records`、`daily_reports` 等 | `GET /api/v1/mapping-reconciliation/sources`；`POST /api/v1/mapping-reconciliation/run`；`GET /api/v1/mapping-reconciliation/runs/{id}`；`GET /api/v1/mapping-reconciliation/runs/{id}/differences` | `/manage/mapping-reconciliation` 输出 skill 对齐 | `output_skill_report_parser.py` 把日报正文解析成模板字段；`D:\输出skill` 只做校验目标，不反向改生产数据 |

## 关键本地投影字段

### `mes_coil_snapshots`

状态：`已证实`

用途：卷级主事实、投料、随行卡、当前工序、前世今生主干。

关键字段：

| 本地字段 | 外部候选字段 | 用途 |
|---|---|---|
| `coil_id`、`mes_product_id` | `MES_Product.Id/ProductId` | 卷材唯一键和去重。 |
| `tracking_card_no`、`material_code` | `MaterialCode`，兼容随行卡别名字段 | 随行卡查询、扫码/手输辅助。 |
| `batch_no` | `PBatchNumber/BatchNumber/BatchNo` | 批号追溯、工序记录关联。 |
| `contract_no` | `ContractCode/ContractNo` | 合同和日报辅助。 |
| `customer_alias` | `CustomerSimple/Customer/CustomerName` | 客户说明和检索。 |
| `alloy_grade` | `Alloy` | 合金。 |
| `spec_display/spec_thickness/spec_width/spec_length` | `Specification/SpecThickness/SpecWidth/SpecLength` | 规格。 |
| `feeding_weight` | `FeedingWeight` | 投料量。 |
| `current_workshop/current_process` | `CurrentWorkShop/CurrentProcess` | 当前在制位置。 |
| `next_workshop/next_process` | `NextWorkShop/NextProcess` | 下一道工序。 |
| `process_route_text` | `ProcessRoute` | 工艺路线。 |
| `in_stock_date/delivery_date/allocation_date` | 同名日期字段 | 判断入库、出库、调拨状态。 |
| `business_date/event_time/updated_from_mes_at/last_seen_from_mes_at` | `OperateDate/CreateDate/InStockDate` 等 | 业务日归属和同步新鲜度。 |

### `mes_workshop_process_records`

状态：`已证实`

用途：车间报表、机台上机/下机、包装工序、道次和过程产量证据。最终日报产量仍按 Hermes/钉钉消息、MES/WMS 最终页、数据中枢的优先级判断。

| 本地字段 | SQL Server 字段 | 用途 |
|---|---|---|
| `workshop_name` | `WorkShop/Workshop/WorkShopName` | 车间。 |
| `process_name` | `Process/ProcessName/WorkShopProcess` | 工序。 |
| `device_name` | `DeviceName/Device/MachineName` | 机台。 |
| `input_weight_kg/input_weight_tons` | `BeginWeight/InputWeight/UpWeight` | 上机量/车间投料量。 |
| `output_weight_kg/output_weight_tons` | `EndWeight/OutputWeight/CalcWeight` | 下机量/包装量/过程产量。 |
| `end_time` | `EndDatetime/CalcDatetime/StrOperateDate` | 工序完成时间。 |
| `business_date` | 由 `end_time` 加业务日规则计算 | 日报、看板和对账。 |

### `mes_stock_records`

状态：入库 `已证实`，出库/调拨细分 `候选`

用途：成品入库、成品调拨、发货兜底。

| 本地字段 | SQL Server 字段 | 用途 |
|---|---|---|
| `source_path` | `sqlserver:stock_header_records/stock_records/delivery_stock_records` | 区分入库表头、入库明细、出库兜底。 |
| `net_weight_kg/net_weight_tons` | `TotalNetWeight/NetWeight/InStockNetWeight` | 入库或出库净重。 |
| `gross_weight_kg/gross_weight_tons` | `TotalGrossWeight/GrossWeight` | 毛重参考。 |
| `in_stock_date` | `InStockDate/CreateDate/AllocationDate/OperateDate` | 入库或流转时间。 |
| `business_date` | 由时间字段加业务日规则计算 | 日报归属。 |
| `source_payload.FromDepartment/ToDepartment` | 同名部门字段 | 成品调拨单过滤和对照。 |

### `mes_material_records`

状态：`已证实`

用途：铸二、铸三、热轧等坯料产量证据。6月19日已验证简单求和不能直接等同最终日报产量。

| 本地字段 | SQL Server 字段 | 用途 |
|---|---|---|
| `material_code` | `MaterialCode/MaterialAutoCode` | 坯料编号。 |
| `workshop_name` | `WorkShopRolling/PWorkShop/WorkShop` | 坯料来源车间。 |
| `weight_kg/weight_tons` | `Weight/MaterialWeight` | 坯料重量。 |
| `production_date` | `ProductionDate/StrProductionDate` | 坯料生产时间。 |
| `business_date` | 按车间业务时间计算 | 日报归属，铸二/铸三/热轧走 `10:00-10:00`。 |
| `status_name` | `StatusName/Status` | 当前包含 `已使用`、`未使用`。 |

## Hermes 日报字段分组

状态：`已证实`

Hermes 日报事实包不是一个单表查询结果，而是：

```text
collect_template_daily_facts()
  -> TemplateDailyFacts.values
  -> validate_template_daily_report_facts()
  -> render_template_daily_report()
  -> daily_reports.report_data.template_daily_report
  -> daily_reports.final_text_summary
```

字段分组：

| 分组 | 代表字段 |
|---|---|
| `opening` | `report_date`、`total_output_daily`、`total_output_delta`、`total_output_month` |
| `workshop_output` | `cast_roll_daily/month`、`hot_roll_daily/month`、`cold_1650_daily/month`、`rolling_daily/month`、`finishing_daily/month` 等 |
| `manual_supplement` | `recovery_daily/month`、`roller_grind_daily/month` |
| `wip` | `wip_total` 及各在制料拆分字段 |
| `energy` | 全厂用电、用气、各车间吨耗字段 |
| `contract_input` | `finished_inbound_daily/month`、`daily_contract_weight`、`cold_roll_input_daily`、`remaining_contract_weight` |
| `yield` | `daily_yield_rate`、`monthly_yield_rate`、`hot_roll_yield_rate`、`cast_roll_yield_rate` |
| `cost` | `electricity_cost_10k`、`gas_cost_10k`、`total_cost_10k`、`cost_per_ton` |

特别说明：

- `D:\输出skill` 是验证目标，不是运行时事实源。
- 输出 skill 正文解析器会把中文日报正文反解析成同一批字段，用来对账。
- `missing_fields` 不为空时，系统应显示缺字段或阻断自动文本，不能让模型猜数。

## 待复核清单

| 项 | 状态 | 需要复核什么 |
|---|---|---|
| 在制料 `doing_weight_tons` 单位 | `待浏览器/SQL复核` | 代码字段名是吨，但 SQL 来源是 `MES_Product.FeedingWeight`；需要用真实 SQL 和 MES 页面确认是 kg 还是吨，避免输出 skill 对账误差。 |
| 成品调拨单精确表 | `待浏览器/SQL复核` | 当前后端用 `WMS_InStockDetail` 和 `WMS_OutStockDetail` 做对照，MES 页面是否还依赖 `WMS_Stock` 需要页面和 SQL 同步确认。 |
| 成品库出库扩展明细主次 | `候选` | WMS `WMS_OutStock` 的 `通知出库` 已能作为发货最终单据；但 `MES_DeliveryDetail`、`WMS_OutStockDetail`、`WMS_Stock` 与发货明细、返厂、调拨的主次关系仍需确认。 |
| 前世今生页面字段 | `候选` | 本地 `/manage/coils` 已能追溯，但 MES `/Archives/Index` 原页面具体接口和字段还需浏览器抓取。 |
| Hermes RAG 静态路线里的 `07:30` | `待浏览器/SQL复核` | `business_time.py` 和新 MES 文档是 `07:50`，但 `hermes_rag_service.build_mes_route_catalog_text()` 仍写 `07:30`，需要后续统一。 |
| 输出 skill 真实全量匹配率 | `待浏览器/SQL复核` | 已有解析和 dry-run 底座，但不能宣称真实全量 95%+ 已完成。 |

## 可直接使用的结论

1. 日报最终值的提取优先级是：业务日窗口内 Hermes/钉钉接收消息 > MES 系统 = WMS 系统 > 数据中枢系统 > Direct MES/WMS SQL 证据 > `缺失`。
2. Hermes/钉钉消息优先的前提是：接收时间落入对应业务日窗口，消息内容能明确对应目标日期/业务日，并能追溯发送人、频道、接收时间和原文。
3. 页面、API、Hermes 的技术读取层通常是本地 `mes_*` 投影，不是 MES SQL Server；但这只是技术链路，不代表数据中枢在最终取数优先级最高。
4. SQL Server 的主职责是只读同步、审计、对账和受控 read-through。
5. 投料、包装、入库是三件事：
   - 投料：`MES_Product.FeedingWeight`。
   - 包装：Hermes/钉钉消息优先；MES 包装录入 `MES_ProductProcessRecord.EndWeight` 且 `Process=包装` 只做证据，除非已对齐。
   - 入库：仓储字段优先 WMS 最终单据；总日报入库成品另看 Hermes/钉钉或最终日报口径。
6. 车间/机台报表用 `MES_ProductProcessRecord.BeginWeight/EndWeight/DeviceName/EndDatetime` 做过程证据，不能直接当冷轧、退火、拉矫等最终日报产量。
7. 坯料明细用 `MES_Material.Weight/ProductionDate` 做铸二、铸三、热轧证据，业务时间 `10:00-10:00`；6月19日简单求和不能直接当最终产量。
8. Hermes 日报只渲染事实包字段；缺字段必须显式暴露，不能让模型补数字。
