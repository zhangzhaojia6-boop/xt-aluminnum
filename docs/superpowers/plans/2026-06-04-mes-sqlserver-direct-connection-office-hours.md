# MES SQL Server 直连方案 Office Hours

## 结论

MES 方不再开发 API、改为提供数据库只读账号后，数据中枢不应立刻删除现有 MVC 抓取链路。

推荐做法是新增 `sqlserver` 类型的 MES 适配器，把 SQL Server 直连数据接入现有 `MesAdapter -> mes_sync_service -> mes_* 本地投影表 -> 管理端/填报端/AI` 这条链路。SQL Server 直连未通过硬性对账前，MVC 只作为对照源；SQL Server 连续对账通过后，MVC 进入短期可回滚窗口，随后从代码、配置、测试、文档和云端环境中彻底删除。

## 为什么不直接废掉 MVC

- MVC 现在已经能产生 `mes_coil_snapshots`、在制料、工艺、库存等本地投影数据，很多管理端页面依赖的是本地投影表，不是直接依赖 MVC 页面。
- SQL Server 的真实表名、字段名、更新时间字段、单位、删除/作废状态还没确认，直接切换容易出现“能连上但数据口径错”的风险。
- MVC 可作为短期对照源，帮助验证 SQL Server 抓到的数据是否少抓、重抓或字段映射错；验证通过后不再长期保留，避免系统形成双链路堆积。

## 成功标准

- 不把 MES 数据库账号密码写进代码、文档、提交记录或日志。
- SQL Server 账号权限为只读，最好限定只读视图或只读存储过程。
- 代码层只允许 SQL Server 适配器执行固定白名单内的 `SELECT` 查询，拒绝写入、删除、建表、堆叠 SQL 和存储过程执行。
- 新适配器能填充现有本地 MES 投影表，不破坏管理端、填报端和 AI 的现有读取方式。
- 关键数据连续对账通过：随行卡号、客户名、合金、规格、当前车间、当前工艺、工艺路线、在制卷/在制料、入库、投料、产量。
- SQL Server 切换前，MVC 或本地旧投影可兜底；SQL Server 正式验收并删除 MVC 后，仅保留本地旧投影缓存和回滚标签兜底。

## 执行状态：2026-06-04 至 2026-06-05

已完成：
- 后端新增 `SqlServerMesAdapter`，接入现有 `MesAdapter` 抽象，不改变管理端读取本地 `mes_*` 投影表的方式。
- 新增 SQL Server 只读预检脚本，可输出连接状态、数据库名、表/视图结构样本和字段地图。
- 预检输出会过滤密码、手机号、地址、邮箱、token 等敏感字段。
- SQL Server 查询执行前有只读护栏，只允许 `SELECT`，拒绝 `INSERT/UPDATE/DELETE/MERGE/DROP/ALTER/CREATE/TRUNCATE/EXEC` 等风险语句。
- 后端全量测试已通过。

真实只读预检结果：
- 网络端口可达，SQL Server 登录成功。
- 可访问数据库包含业务库 `XTAL`。
- `XTAL` 中可见表/视图数量为 53。
- 账号权限探测结果：可 `SELECT`，不可 `INSERT`、`UPDATE`、`DELETE`、`CREATE TABLE`，不是 `sysadmin`，不是 `dbcreator`。
- 真实表结构中未发现原计划占位用的 `v_CoilStatus`、`v_WipTotals`、`v_StockIn` 等视图；适配器默认查询已改为真实发现的 `MES_Product`、`MES_ProductProcessRecord`、`MES_Feeding`、`WMS_Stock`、`WMS_InStockDetail`、`MES_Device`。
- `MES_Product.MaterialCode` 的形态与随行卡号最接近，已作为 `tracking_card_no` 的主映射；`MES_Product` 还包含客户、合金、规格、当前车间、当前工序、下一车间、下一工序、工艺路线、投料重量、入库时间等字段。
- 在制聚合已排除空车间和空工序，避免历史脏数据把管理端在制数量冲大。
- 新增只读对账脚本 `backend/scripts/check_mes_sqlserver_reconciliation.py`，可抽样比较 SQL Server 与本地 `mes_coil_snapshots`，输出匹配率、字段一致率和脱敏样本；脚本不触发同步、不写本地库、不写 SQL Server。
- 本地只读对账冒烟结果：SQL Server 抽样 20 条，本地 `mes_coil_snapshots` 表存在但当前行数为 0，因此本地匹配率为 0；这证明当前不能直接切 SQL Server 主用，必须先完成影子同步/本地投影写入策略和连续对账。
- 新增只读投影预演脚本 `backend/scripts/check_mes_sqlserver_projection_preview.py`，复用数据中枢现有 MES 投影算法，只计算将来会写入本地投影表的字段完整度，不写任何数据库。
- SQL Server 抽样 20 条投影预演结果：随行卡、批号、合同号、客户、合金、规格、投料重量、工艺路线完整率为 100%；当前车间/当前工序/下道车间/下道工序完整率为 75%；`MES_Product.InStockDate` 在该样本中完整率为 0，说明成品入库/全厂总产量口径不能只靠 `MES_Product`，必须继续以 `WMS_InStockDetail` 或包装入库相关表对账确认。
- 新增只读入库预览脚本 `backend/scripts/check_mes_sqlserver_stock_preview.py`，专门验证 `WMS_InStockDetail` 是否能支撑“包装入库/全厂总产量”口径；脚本只读 SQL Server，只输出字段完整率、部门汇总、重量自检和脱敏样本。
- 真实字段检查确认：`WMS_InStockDetail` 没有 `InStockDate` 字段；`OperateDate` 当前 0 条有值，`CreateDate` 与 `AllocationDate` 305095 条都有值。代码已把入库时间候选从 `InStockDate` 扩展为 `InStockDate/OperateDate/CreateDate/AllocationDate`，其中当前真实数据主要依赖 `CreateDate`。
- SQL Server 抽样 50 条入库预览结果：批号、净重、毛重、入库业务日、状态完整率 100%；合同号、客户完整率 98%；样本业务日均为 2026-06-04。
- 入库部门链路抽样结果：样本主要为 `精整 -> 成品库` 和 `园区精整 -> 成品库`。最近 7 天只读聚合按数据中枢 7:30 业务日归属，候选过滤下共有 736 条、约 1980.211 吨，覆盖 `精整/园区精整/拉矫车间/园区剪切/拉矫 -> 成品库`，和“包装入库产量”业务口径基本对齐。
- 重量口径风险：`WMS_InStockDetail.NetWeight` 更像总产量候选重量；`GrossWeight` 在普卷、彩卷、花纹卷等类型中大量小于净重，不能作为全厂总产量主口径。后续若接入总产量，候选过滤应先用 `ToDepartment=成品库`、`Status=1`、`FromDepartment` 包含 `精整/拉矫/剪切`，时间用 `CreateDate`，重量优先用 `NetWeight`，但仍需和人工日报做 7 个业务日单位/状态对账。
- 新增只读入库对账脚本 `backend/scripts/check_mes_sqlserver_stock_reconciliation.py`，用于比较 SQL Server 包装入库候选口径和本地 `mes_stock_records` 投影；脚本不触发同步、不写本地库、不写 SQL Server。
- 本地只读入库对账结果：SQL Server 最近 7 天候选口径共有 736 条、约 1980.211 吨，按 7:30 业务日拆为 2026-05-28 到 2026-06-04 共 8 个业务日；当前本地环境 `mes_stock_records` 表不存在，因此本地匹配为 0，结论为 `ready_for_cutover=false`，原因是 `local_projection_empty` 和 `needs_at_least_7_business_dates`。
- 本地缺表归因：代码模型 `MesStockRecord` 已声明 `mes_stock_records`，迁移 `0034_mes_mvc_extended_sources` 也包含建表逻辑；当前本地库为 `sqlite ./local-dev.db`，没有 `alembic_version`，表数 40，缺 `mes_stock_records`，因此这是本地数据库未迁移/未初始化到 MES 扩展投影阶段，不是模型或 SQL Server 口径缺失。
- 已按只读原则连接 MES SQL Server，并只写本地影子库；干净影子库 `backend/.codex-shadow/mes-sqlserver-shadow-clean.db` 迁移到当前 head，包含 78 张表和完整 `mes_*` 投影表。
- 影子同步真实 SQL Server 投影数据成功：参考项 50 条、机列 50 条、随行卡/卷材 1000 条、在制汇总 56 条、工序记录 1000 条、包装入库 1000 条、成品率候选 1000 条；`MES_Feeding` 真实表当前行数为 0，因此投料记录暂不能从该表取得，需 MES 方确认投料真实来源表。
- 同步过程发现并修复三类真实问题：`source_payload` 中 UUID、日期、Decimal 等类型不能安全写入 JSON 字段；SQL Server 在制汇总返回车间+工序但适配器未传给同步层，导致重复 `车间:total` 撞唯一约束；SQL Server 顶层 `Id` 未映射成 `mes_product_id`，导致卷材被写成 fallback id。
- 入库对账脚本已改为默认比较最近已完成的 7 个生产业务日，避免把正在进行中的今天算入历史验收，造成“当天未完结所以少一天”的假失败。
- 影子库 7 个已完成业务日对账通过：SQL Server 候选 769 条、2094.232 吨；本地投影 769 条、2094.232 吨；覆盖 2026-05-29 至 2026-06-04，逐日行数和吨数差值均为 0，`ready_for_cutover=true`。
- 干净影子库随行卡/卷材抽样对账通过：SQL Server 抽样 200 条，本地投影匹配 200 条，匹配率 100%；批号、合同号、当前车间、当前工序、合金、规格、工艺路线字段一致率均为 100%，无未匹配样本、无字段差异样本。

真实字段映射初表：

| SQL Server 来源 | 数据中枢入口 | 本地投影字段 | 管理端/填报端用途 | 当前判定 |
| --- | --- | --- | --- | --- |
| `MES_Product.Id` | `CoilSnapshot.coil_id` / `metadata.Id` | `mes_coil_snapshots.coil_id`、`mes_product_id` | 卷材唯一识别、去重、流转事件 | 可用 |
| `MES_Product.MaterialCode` | `CoilSnapshot.tracking_card_no`、`metadata.MaterialCode` | `tracking_card_no`、`material_code` | 填报端扫码/手输随行卡自动带出；工单和历史填报匹配 | 主映射 |
| `MES_Product.PBatchNumber` / `BatchNumber` | `CoilSnapshot.batch_no` | `batch_no` | 大屏、车间看板、追溯列表展示 | 可用 |
| `MES_Product.ContractCode` | `CoilSnapshot.contract_no` | `contract_no` | 合同进度、填报辅助、管理端筛选 | 可用 |
| `MES_Product.Customer` / `CustomerSimple` | `metadata.Customer*` | `customer_alias` | 合同/日报/AI 说明性字段 | 待确认优先用哪个名称 |
| `MES_Product.Alloy` | `metadata.Alloy` | `alloy_grade` | 填报端自动带出合金，减少人工录入 | 可用 |
| `MES_Product.Specification`、`SpecThickness`、`SpecWidth`、`SpecLength` | `metadata.Specification/Spec*` | `spec_display`、`spec_thickness`、`spec_width`、`spec_length` | 填报端自动带出规格，管理端检索 | 可用 |
| `MES_Product.FeedingWeight` | `metadata.FeedingWeight` | `feeding_weight` | 投料量、在制口径参考 | 单位疑似吨，需与人工日报对账确认 |
| `MES_Product.NetWeight/GrossWeight/Weight` | `metadata.NetWeight/GrossWeight/Weight` | `net_weight`、`gross_weight`、`material_weight` | 重量对照、库存/入库参考 | 单位需继续对账 |
| `MES_Product.CurrentWorkShop`、`CurrentProcess` | `CoilSnapshot.workshop_code/process_code`、`metadata.Current*` | `current_workshop`、`current_process` | 实时大屏、车间看板、填报端当前工序提示 | 可用 |
| `MES_Product.NextWorkShop`、`NextProcess` | `metadata.Next*` | `next_workshop`、`next_process` | 工艺路线、下道工序提醒 | 可用 |
| `MES_Product.ProcessRoute` | `metadata.ProcessRoute` | `process_route_text` | 工艺路线展示、机列承担工艺分析、AI 问答 | 可用 |
| `MES_Product.OperateDate/CreateDate` | `CoilSnapshot.updated_at/event_time` | `event_time`、`updated_from_mes_at` | 同步增量、数据新鲜度、业务日归属参考 | 先用 `OperateDate`，缺失时兜底 `CreateDate` |
| `MES_Product.InStockDate` | `metadata.InStockDate` | `in_stock_date` | 判断已入库、全厂总产量口径参考 | 需和包装入库字段继续对账 |
| `MES_Product.DeliveryDate/AllocationDate` | `metadata.DeliveryDate/AllocationDate` | `delivery_date`、`allocation_date` | 排除已出库/已调拨数据，避免在制虚高 | 可用但需状态对照 |
| `MES_Product.CurrentWorkShop + CurrentProcess + SUM(FeedingWeight)` | `MesWipTotal` | `mes_wip_total_snapshots` | 今日/昨日报表、实时大屏、车间看板在制分布 | 已排除空车间/空工序，状态口径还需对账 |
| `MES_ProductProcessRecord` | `MesSourceRecord` | `mes_workshop_process_records` | 工序产量、下机量、成品率算法对照 | 需确认 Begin/End 权重单位 |
| `MES_Feeding` | `MesSourceRecord` | `mes_material_records` | 投料量、投料时间、投料工艺路线 | 可作为投料主候选 |
| `WMS_InStockDetail.CreateDate + NetWeight + FromDepartment/ToDepartment + Status` | `MesSourceRecord` | `mes_stock_records` | 包装入库、全厂总产量参考 | 真实样本支持；候选口径为 `ToDepartment=成品库`、`Status=1`、来源含精整/拉矫/剪切、重量用 `NetWeight`；仍需 7 个业务日对账 |
| `WMS_Stock` | `MesStockItem` | `mes_stock` 相关同步入口 | 库存、在库/已入库状态参考 | 需继续对账 |
| `MES_Device` | `MesMachineLineSource` | `mes_machine_line_snapshots` | 机列/车间映射、车间主任看板 | 可用 |

已确认页面/服务读取链路：
- 填报端扫码/手输随行卡：`scan_lookup_service` 读取 `mes_coil_snapshots.tracking_card_no`，自动带出合金、规格、当前车间、当前工序、下道工序。
- 实时大屏和车间看板：`factory_command_service` 读取 `mes_coil_snapshots`、`mes_wip_total_snapshots`、`mes_daily_wip_snapshots`。
- 昨日报表/今日页在制分布：日报 builder 读取 `mes_daily_wip_snapshots`，缺失时回看 `mes_coil_snapshots`。
- AI 总览和 AI 问答：读取本地 MES 投影和同步健康状态，不直接读 SQL Server。

未完成，不能标记整个计划完成：
- 字段映射表已形成第一版，随行卡/卷材和包装入库候选链路已通过影子库对账；在制、下机、工艺产量、状态枚举仍需继续补齐同级别业务对账。
- 投料链路不能按 `MES_Feeding` 继续假设，因为真实表当前为 0 行；需向 MES 方确认投料量是否来自 `MES_Product.FeedingWeight`、工序记录、库存流转表或其他隐藏表/视图。
- 干净影子库已证明管理端依赖的本地 `mes_coil_snapshots`、`mes_wip_total_snapshots`、`mes_stock_records` 等投影表可写入；下一步还需启动测试/云端影子环境，验证管理端页面是否读取同一投影口径。
- SQL Server 投影预演已证明填报自动带出的核心字段基本可用；成品入库/全厂总产量 SQL 候选口径已通过影子库技术对账，但仍需和人工日报做业务验收。
- `WMS_InStockDetail` 已证明可提供包装入库时间、部门和净重候选，但 `GrossWeight` 字段存在明显口径风险，不能直接作为总产量；`NetWeight` 已通过影子库对账，正式切主用前还需和人工日报做业务验收。
- 本地影子库已具备 `mes_stock_records` 投影数据；下一步要验证管理端总产量页面是否读取同一投影口径，并补齐云端影子同步/页面验收。
- 尚未进入主用切换和删除 MVC 阶段。

## 阶段 0：安全前置

1. 要求 MES 方确认账号只读，禁止写入、删除、建表、改表。
2. 要求 MES 方尽量按我方服务器公网 IP 做白名单，而不是全网开放 1433。
3. 要求 MES 方最好提供只读视图，例如 `v_CoilStatus`、`v_ProcessRoute`、`v_StockIn`、`v_WorkshopProcess`。
4. 生产环境只通过 `.env` 或服务器密钥保存连接信息，不进入 Git。
5. 本次聊天里已经出现了明文密码，上线稳定后建议让 MES 方轮换一次密码。

## 阶段 1：只读探测

目标：只确认能连、能读、有哪些表字段，不写任何业务数据。

计划动作：
- 新增本地预检脚本，例如 `backend/scripts/check_mes_sqlserver_preflight.py`。
- 输出只包含：连通状态、数据库名、可访问表/视图数量、候选表名、字段名样本、行数估计。
- 输出不得包含密码、完整连接串、敏感客户电话、地址等字段。

验收：
- 能在本地或云端只读连通 SQL Server。
- 能列出候选表/视图。
- 能识别每张候选表的主键、更新时间字段、时间字段、业务状态字段。

## 阶段 2：字段地图与口径确认

目标：把 SQL Server 原始字段映射到数据中枢现有 MES 模型。

优先字段：
- 随行卡号：用于填报端自动带出信息。
- 客户名：用于合同、排产、经营日报和大屏说明。
- 合金、规格：用于减少填报端人工输入。
- 当前车间、当前工艺、下一车间、下一工艺、工艺路线：用于在制卷、机列责任、工序产量分析。
- 投料量、下机量、入库量、废料、成品量：用于和人工填报做对照。
- 入库时间、操作时间、更新时间、生产日期：用于业务日归属。
- 状态字段：用于排除已作废、已出库、已完成但不应算在制的数据。

验收：
- 形成 `SQL Server 字段 -> MesAdapter 数据类 -> 本地 mes_* 表 -> 管理端页面` 的映射表。
- 对每个吨/公斤字段明确单位换算。
- 对每个时间字段明确使用业务日规则，而不是自然日随便截取。

## 阶段 3：新增 SQL Server 适配器

目标：不改管理端页面读取方式，只新增数据入口。

工程改动：
- 增加依赖：优先评估 `pyodbc` 或 `pymssql`，选择云端 Linux 更稳定、部署成本更低的方案。
- 增加配置项：
  - `MES_ADAPTER=sqlserver`
  - `MES_SQLSERVER_HOST`
  - `MES_SQLSERVER_PORT`
  - `MES_SQLSERVER_DATABASE`
  - `MES_SQLSERVER_USERNAME`
  - `MES_SQLSERVER_PASSWORD`
  - `MES_SQLSERVER_TIMEOUT_SECONDS`
  - `MES_SQLSERVER_ENCRYPT`
- 新增 `SqlServerMesAdapter`，实现现有 `MesAdapter` 接口：
  - `list_coil_snapshots`
  - `get_tracking_card_info`
  - `list_follow_cards`
  - `list_dispatch`
  - `list_wip_totals`
  - `list_workshop_process_records`
  - `list_stock_records`
  - `list_material_records`
  - `list_yield_records`
  - `list_reference_items`
  - `list_machine_line_sources`
- 保持 `mes_sync_service` 不大改，让它继续写入本地投影表。

验收：
- 单元测试覆盖字段映射、空值、单位换算、时间解析、状态过滤。
- 集成测试使用假 SQL Server 查询结果，不依赖真实数据库。
- 配置校验能发现缺少 SQL Server 必需环境变量。

## 阶段 4：双源对账

目标：SQL Server 与 MVC 并跑一段时间，确认新链路可信。

对账内容：
- 同一天随行卡数量。
- 同一随行卡的合金、规格、客户、当前工艺是否一致。
- 各车间在制卷数量、在制吨数是否一致。
- 入库记录和包装入库产量是否能对齐。
- 工艺产量和人工填报下机量是否差异合理。

硬性通过标准：
- 连续 7 个业务日核心字段对账通过，至少覆盖 1 个周末或低产日。
- 三班口径均覆盖：长白班、小夜班、大夜班。
- 随行卡匹配率不低于 99%，未匹配记录必须能解释。
- 合金、规格、客户名、当前车间、当前工艺、工艺路线核心字段一致率不低于 99%。
- 各车间在制卷数量差异不超过 1%，在制吨数差异不超过 1%，且大额差异都有解释。
- 入库、投料、下机关键记录能按数据中枢业务日规则归属，不允许自然日和业务日混算。
- SQL Server 同步失败时，管理端必须显示“使用本地缓存”，不能把 0 当成真实数据。
- 管理端增加“MES 数据来源：SQLServer/MVC/本地缓存”的可见状态。

## 阶段 5：灰度切换

目标：线上逐步把主数据源切到 SQL Server。

切换方式：
- 第一阶段：`MES_ADAPTER=mvc` 保持主用，SQL Server 仅预检和手动对账。
- 第二阶段：`MES_ADAPTER=sqlserver_shadow` 影子同步，只写对账日志，不影响页面。
- 第三阶段：`MES_ADAPTER=sqlserver` 主用，MVC 不再写入业务投影，只保留 48 小时紧急回滚能力。
- 第四阶段：SQL Server 主用稳定 7 个业务日且无 P0/P1 数据事故后，生成回滚标签并删除 MVC 链路。

回滚：
- 把 `MES_ADAPTER` 改回 `mvc`。
- 重启服务。
- 本地 `mes_*` 投影表不清空，避免页面突然无数据。

## 阶段 6：删除 MVC 链路

目标：避免系统同时存在 SQL Server 和 MVC 两套 MES 入口，降低维护成本和错误口径。

删除前硬闸门：
- SQL Server 已连续 7 个业务日主用稳定。
- 管理端、填报端、日报、AI、实时大屏均读取本地 `mes_*` 投影表正常。
- 线上健康检查 `mes_sync` 为 `ok`，同步失败能明确提示，不返回假 0。
- 已打 Git 回滚标签，例如 `pre-remove-mvc-mes-adapter-YYYYMMDD`。
- 服务器 `.env` 已备份，但不进入 Git。

删除范围：
- 删除 `backend/app/adapters/mvc_mes_adapter.py`。
- 删除 `MES_ADAPTER=mvc` 分支和 `MES_MVC_*` 配置项。
- 删除 MVC 预检脚本和 MVC 专用测试。
- 删除 MVC 专用文档、计划和部署说明中的运行配置。
- 删除云端 `.env` 中的 MVC 地址、账号、密码。
- 保留 `MesAdapter` 抽象层和 `mes_sync_service`，因为 SQL Server 仍然走这条标准入口。

删除后验证：
- 后端全量测试通过。
- 前端生产构建通过。
- SQL Server 预检通过。
- 手动触发一次 MES 同步成功。
- 公开 `/readyz` 返回 `mes_sync=ok`。
- 抽查管理端大屏、昨日报表、填报辅助、AI 数据体检均能显示 SQL Server 投影数据。

删除后回滚：
- 仅在 SQL Server 发生 P0/P1 且 30 分钟内无法恢复时，回滚到删除前 Git 标签。
- 回滚不清空本地 `mes_*` 表。
- 回滚完成后仍需保留 SQL Server 错误现场日志，避免问题被覆盖。

## 五视角 Plan Review

| 视角 | 分数 | 结论 | 9.7 分以上的关键原因 |
| --- | ---: | --- | --- |
| CEO | 9.8 | 值得做，且应尽快从 MVC 过渡到 SQL Server | 直接解决填报减负、日报可信、实时大屏和 AI 数据源问题；删除 MVC 避免长期双链路维护成本 |
| 工程师 | 9.8 | 架构稳，不推翻现有系统 | 新增 SQL Server 适配器接入现有投影表；先影子同步再主用；删除 MVC 前有硬闸门、测试和回滚标签 |
| 设计师 | 9.7 | 用户路径清晰 | 用户不需要理解 MVC 或 SQL Server，只看到数据来源状态、同步健康、填报自动带出字段和异常提示 |
| 安全审查员 | 9.7 | 可接受，但必须执行安全前置 | 只读账号、IP 白名单、不落库密码、不写日志、上线后密码轮换；删除 MVC 后减少一个攻击面 |
| 真实用户 | 9.8 | 能明显省事 | 扫码或输入随行卡后自动带出客户、合金、规格、工艺路线、当前工艺，减少重复填报和人工对账 |

综合评分：9.76。

## 最终完美方案

一句话：先用 SQL Server 只读直连替代 MVC 的数据来源，但不直接让页面读 SQL Server；仍然先同步到数据中枢自己的 `mes_*` 投影表。SQL Server 经过影子同步、双源对账、灰度主用、线上稳定后，删除 MVC 抓取链路，让系统最终只保留一条清晰、可测、可维护的 MES 数据入口。

最终阶段顺序：

1. 安全确认：只读账号、IP 白名单、密码不入库不入 Git。
2. 只读预检：确认能连、能看表结构、能识别候选表字段。
3. 字段地图：确认随行卡、客户、合金、规格、工艺路线、当前工艺、在制、投料、入库、下机字段。
4. SQL Server 适配器：接入现有 `MesAdapter`，不改管理端读取逻辑。
5. 影子同步：SQL Server 写对账表或对账日志，不影响当前页面。
6. 双源对账：连续 7 个业务日达到硬性通过标准。
7. 主用切换：`MES_ADAPTER=sqlserver`，页面继续读本地投影表。
8. 删除 MVC：满足删除硬闸门后，清理 MVC 代码、配置、测试、文档和云端环境变量。
9. 上线验收：全量测试、构建、同步、健康检查、核心页面抽查全部通过。
10. 后续增强：把 SQL Server 多出来的实时字段接入填报辅助、车间看板、在制预警、AI 数据体检。

## 对用户价值

- 填报端可自动带出随行卡、客户、合金、规格、工艺路线、当前工艺，减少人工输入。
- 管理端大屏能更实时看到各车间在制卷、在制吨数、投料、入库和异常。
- 日报能把 MES 算法数据与人工填报数据并列对照，减少“到底信谁”的争议。
- 未来可以做工艺路线偏离、超时滞留、车间积压、机列负荷等智能提醒。

## 最短可交付版本

第一版不要追求把 MES 全部表一次吃完，只做四组最有价值数据：

1. 随行卡基础信息：客户、合金、规格、合同、批号。
2. 当前在制状态：当前车间、当前工艺、当前重量、状态、更新时间。
3. 工艺路线：路线文本、当前工艺排序、下一工艺。
4. 入库/投料/下机关键记录：用于日报、成品率、全厂总产量对照。

## 风险清单

- SQL Server 直连如果没有 IP 白名单，数据库暴露风险较高。
- 只给账号密码但不给字段说明，会增加字段误判风险。
- SQL Server 表可能没有稳定更新时间字段，会影响增量同步，只能先做窗口扫描。
- 生产库直接读大表可能给 MES 方造成压力，需要限制频率、分页和只读视图。
- 不同系统时间口径可能不一致，必须统一为数据中枢业务日规则。

## 推荐给 MES 方补问

- 这个账号是否只读？是否限制了写权限和库范围？
- 能否给我方服务器 IP 加白名单？
- 哪些表或视图对应随行卡、在制、工艺路线、入库、投料、下机？
- 每张表的主键、更新时间字段、作废/删除状态字段分别是什么？
- 重量单位是 kg 还是吨？
- 时间字段是北京时间还是 UTC？
- 是否允许创建只读视图给我们使用？
