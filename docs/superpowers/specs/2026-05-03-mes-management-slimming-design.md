# MES 接入健康与管理端瘦身设计

日期：2026-05-03
状态：待用户审阅
适用系统：鑫泰铝业 数据中枢

## 背景

上一轮已经把系统方向从“填报 + 审阅 + 日报后台”推进到“MES 可读投影 + 工厂指挥中心”。当前代码也已经具备 `MES` 只读适配、同步游标、卷级投影、机列投影、工厂总览、生产流转、卷级追踪、库存去向和 AI 助手入口。

但本轮评估暴露出一个更重要的问题：产品主路径比真实运行状态走得快。代码契约已经准备好接 `MES`，当前本地运行配置和数据库迁移却还没有跟上；同时管理端导航又重新露出“填报审核、班次中心、导入历史、权限治理、系统设置”等后台型入口，容易把 `数据中枢` 做回一个复杂后台。

本设计目标是：先把 `MES` 接入是否健康、数据是否新鲜、投影是否可用变成一眼可判断的事实；再把管理端从“多后台入口”收敛成“工厂运行 + 异常处理 + 必要配置”。

## 当前证据

本轮只读检查得到的事实：

- 当前运行配置仍是 `MES_ADAPTER=null`、`MOBILE_DATA_ENTRY_MODE=manual_only`、`MOBILE_MES_DISPLAY_ENABLED=False`。
- 本地数据库 `alembic_version` 停在 `0021_machine_energy_records`，而当前 `MesCoilSnapshot` 模型依赖 `0022_factory_command_projection` 新增字段。
- 运行 `backend/scripts/check_mes_sync_lag.py --json` 会因 `mes_coil_snapshots.mes_product_id` 缺列失败，说明运行库尚未完成 MES 投影迁移。
- `backend/tests/test_mes_api_contract.py`、`test_rest_api_mes_adapter.py`、`test_mvc_mes_adapter.py`、`test_mes_sync_service.py`、`test_mes_sync_lag.py`、`test_factory_command_routes.py` 共 25 个 MES/指挥中心相关测试通过，说明代码契约本身可用。
- `frontend/src/config/manage-navigation.js` 当前暴露了多个重叠入口：`班次中心`、`填报审核/录入中心`、两个成本入口、导入历史、别名映射、系统设置、权限治理。
- `frontend/src/views/shift/ShiftCenter.vue` 仍带有“导入生产班次数据”的后台操作语义，不适合作为接入 MES 后的管理主入口。
- `frontend/src/views/review/ReviewTaskCenter.vue` 使用“待审/已审/批量通过/批量驳回”语义，和后端当前“自动校验、自动确认、异常退回”的主路径不一致。

## 推荐结论

采用“MES 健康优先 + 管理端瘦身”的方向。

不要在这一轮继续增加新的 `MES` 功能页面，也不要删除后端兼容逻辑。先完成四件事：

1. 把 `MES` 接入状态做成可见 contract：未配置、迁移缺失、同步成功、同步滞后、同步失败都能被后端稳定返回，前端能准确展示。
2. 把工厂指挥中心的数据查询从全量内存扫描逐步改成数据库聚合/分页，避免 `MES` 数据量上来后页面变慢。
3. 管理端主导航删除或降级不应存在于主路径的入口，普通管理者只看工厂运行、异常、AI 和必要配置。
4. 保留班次模型和审核状态字段，但把它们从主流程功能降级为“基础配置”和“异常兜底”。

## 不建设内容

- 不把 `数据中枢` 改名或包装成 `MES`。
- 不在本轮回写 `MES`。
- 不删除 `mes_sync_service`、`work_orders`、`review_report` 等后端兼容资产。
- 不新增第三方依赖。
- 不重写整套前端信息架构。
- 不引入新的人工审核主流程。
- 不新增“说明型/营销型”页面。

## 目标状态

管理层进入 `/manage/overview` 后，应能直接判断：

- 当前数据来自 `MES 投影`、`本地填报` 还是 `混合来源`。
- `MES` 是否已配置。
- 本地迁移是否满足当前模型。
- 最近同步是否成功。
- 当前滞后多久。
- 如果 `MES` 不可用，页面是否仍能基于本地填报继续运行。

管理员进入配置区后，应只看到必要配置：

- 主数据与模板。
- 用户与角色。
- 数据接入健康。
- 字段映射。

普通管理者不应在第一层导航看到：

- 班次观察台。
- 填报审核。
- 导入历史。
- 别名映射。
- 系统设置。
- 权限治理。
- 重复成本入口。

## 信息架构

### 主导航保留

普通管理/审阅角色：

1. `工厂总览`
   当前默认入口。展示全厂指标、同步新鲜度、异常数量和重点机列。

2. `生产流转`
   从卷级投影看当前工艺、下道工艺、停滞和流向。

3. `车间机列`
   展示车间、机列、卷数、在制吨数、停滞情况。

4. `卷级追踪`
   搜索批号、卷号、随行卡，展示完整流转。

5. `库存去向`
   展示在制、成品库、分配、交付、未知去向。

6. `异常地图`
   汇总停滞、路线缺失、同步滞后、重量异常、缺报和退回。

7. `AI 助手`
   常驻入口，不作为大块后台模块。

管理员额外看到：

8. `主数据与模板`
9. `用户管理`
10. `数据接入`

### 降级入口

以下入口保留路由，不进入普通主导航：

- `班次中心`
  降级到主数据与模板内部，作为班次配置，不作为观察台。

- `录入中心 / 审阅中心`
  改名或改语义为 `异常与补录`，仅处理缺报、退回、数据异常，不再呈现“待审/已审”人工审核台。

- `日报与交付中心`
  不再作为主路径；保留在总览或报表导出入口里，服务历史查询和导出。

- `成本核算与效益中心`
  只保留一个入口。现阶段如果仍是估算，应留在 `经营效益` 或 `AI` 辅助里，不重复暴露。

- `导入历史 / 别名映射 / 字段映射`
  收进 `数据接入`。

- `系统设置 / 权限治理`
  收进管理员配置区。

## MES 接入健康设计

新增或强化一个后端健康 contract，不要求新建复杂服务，可以先复用现有 `mes_sync_service.latest_sync_status` 和 `health.build_readiness_payload`。

返回语义建议：

```text
configured: boolean
migration_ready: boolean
status: unconfigured | idle | fresh | stale | failed | migration_missing
source: mes_projection | local_entry | mixed
lag_seconds: number | null
last_synced_at: string | null
last_event_at: string | null
last_error: string | null
action_required: none | configure_mes | run_migration | check_vendor | check_credentials
```

关键规则：

- `MES_ADAPTER=null` 时返回 `unconfigured`，不是错误。
- 表结构缺字段时返回 `migration_missing`，不能让页面请求 500。
- 最近同步失败时返回 `failed`，保留最近成功投影数据。
- `lag_seconds > 300` 显示 `stale`，`lag_seconds > 900` 显示高风险。
- 管理者只看到状态和建议，管理员才能看到具体错误。

前端展示规则：

- 工厂总览顶部固定显示一个紧凑状态条。
- 指标卡片里不写长说明，只显示 `实时 / 滞后 / 未配置 / 迁移缺失 / 失败`。
- 如果 `MES` 未配置但本地填报可用，页面继续显示本地数据，不把系统整体打成不可用。
- 如果迁移缺失，管理员看到“运行迁移”类操作指引；普通管理者只看到“数据投影未就绪”。

## 数据速度设计

当前 `factory_command_service` 的风险点是多个路径使用 `_all(db, Model)` 把投影表全量拉进内存后再聚合。这在少量测试数据下没问题，但 `MES` 上线后卷级数据会增长。

本轮只做必要瘦身：

- `build_overview`
  从全量 rows 改为数据库聚合：在制吨数、库存吨数、今日产出、异常数量按 SQL 计算。

- `list_workshops`
  按车间 group by 聚合，不全量返回卷。

- `list_machine_lines`
  先查询机列快照和机列聚合指标，卷级明细留给卷追踪页面。

- `list_coils`
  增加分页和筛选参数，默认只取最近或异常优先的有限结果。

- `get_coil_flow`
  保持单卷查询，按 `coil_id / tracking_card_no / batch_no` 命中。

速度目标：

- 工厂总览和车间机列接口在 10 万卷级投影数据下仍应保持秒级返回。
- 前端默认首屏不拉全量卷列表。
- AI 助手从具体对象发问时只传上下文 key，不传整表数据。

## 班次功能判断

`ShiftConfig` 必须保留。

原因：

- 移动端当前班次计算依赖它。
- 权限范围 `assigned_shift_ids` 依赖它。
- 催报、缺报、日报、考勤确认、移动填报历史均依赖 `shift_id`。
- `MES` 只读投影中也有 `shift_code`，仍需要本地班次口径做匹配。

但管理端 `班次中心` 不应作为主功能存在。

推荐处理：

- 保留后端 `/master/shift-configs`。
- 保留班次配置表单。
- 将 `/manage/shift` 从主导航移除。
- 如果保留兼容路由，页面改成只读或重定向到主数据与模板。
- 删除或隐藏 `ShiftCenter.vue` 中的生产班次导入操作入口，生产导入统一进入数据接入。

## 审核功能判断

人工审核不应存在于主流程。

现有后端已经有更合适的主路径：

- 工人提交后由 `ValidatorAgent` 自动校验。
- 通过后进入 `approved / auto_confirmed` 等兼容状态。
- 不通过进入 `returned`，给可执行退回原因。
- `AggregatorAgent` 可以自动汇总和发布。

因此本轮判断：

- 保留后端状态字段、审计字段和兼容路由。
- 保留管理员对异常记录的覆盖能力，必须要求原因。
- 移除或重命名前端“待审/已审/批量通过/批量驳回”表达。
- 将 `ReviewTaskCenter.vue` 语义改成 `异常与补录`：
  - 缺报。
  - 退回。
  - 同步滞后。
  - 差异待处理。
  - 质量异常。
  - 需要管理员覆盖的记录。

禁用方向：

- 不再给普通管理者提供“批量审核通过”按钮。
- 不再把 `reviewed` 作为用户需要理解的主状态。
- 不再在导航中使用 `填报审核` 分组。

## 数据流

```text
MES MVC / REST
    |
    v
MES adapter
    |
    v
mes_sync_service
    |
    v
本地 MES 投影表
    |
    +--> 工厂指挥中心接口
    |       |
    |       v
    |    管理端工厂大屏
    |
    +--> AI 证据上下文

移动填报 / 本地专项 owner
    |
    v
自动校验 / 自动退回 / 自动确认
    |
    v
日报汇总 / 异常地图 / 管理端补录
```

`MES` 失败不应阻断移动填报。移动填报是兜底数据源，`MES` 是外部真源和自动补数来源。

## 错误处理

后端：

- 捕获投影表缺字段、缺表、连接失败、登录失败、供应商接口超时。
- 返回结构化状态，不在工厂总览接口中直接抛 500。
- 同步失败时保留旧投影，不清空数据。
- 管理员可见错误摘要，普通管理者只能看到状态。

前端：

- `unconfigured`：显示未配置，不使用危险色。
- `migration_missing`：管理员显示迁移缺失，普通管理者显示投影未就绪。
- `failed`：显示同步失败，仍展示最后一次可用数据。
- `stale`：显示滞后分钟数。
- `fresh`：显示实时。

## 影响范围

推荐实施时主要触达：

- `backend/app/services/mes_sync_service.py`
  增强同步状态对迁移缺失的兜底。

- `backend/app/core/health.py`
  将 MES 健康状态纳入 readiness，同时区分未配置和异常。

- `backend/app/services/factory_command_service.py`
  将关键聚合从全量内存扫描改成数据库聚合/分页。

- `backend/app/schemas/factory_command.py`
  如需补充 `migration_ready / action_required` 等字段。

- `frontend/src/config/manage-navigation.js`
  收敛主导航。

- `frontend/src/router/index.js`
  保留兼容路由，必要时调整重定向。

- `frontend/src/views/factory-command/FactoryOverview.vue`
  展示 MES 新鲜度与迁移状态。

- `frontend/src/views/shift/ShiftCenter.vue`
  降级或退出主导航。

- `frontend/src/views/review/ReviewTaskCenter.vue`
  改为异常与补录语义。

- `frontend/src/views/review/IngestionCenter.vue`
  承接导入历史、字段映射、别名映射、MES 导出导入。

## 测试路径

后端：

- `MES_ADAPTER=null` 返回 `unconfigured`，readiness 不因此失败。
- 数据库缺 `0022` 字段时返回 `migration_missing`，工厂总览不 500。
- 最近运行失败时返回 `failed`，错误只对管理员可见。
- `lag_seconds <= 300` 为 `fresh`，`300 < lag <= 900` 为 `stale`，`lag > 900` 为高风险滞后。
- `factory_command_service` 聚合结果与原全量算法在小样本下保持一致。
- `list_coils` 默认分页，不返回全量。

前端：

- 管理端普通角色主导航不出现 `填报审核`、`班次中心`、`导入历史`、`别名映射`、`系统设置`、`权限治理`。
- 管理员仍可进入主数据、用户、数据接入。
- 工厂总览在 `fresh / stale / unconfigured / migration_missing / failed` 状态下都有明确显示。
- 审核页不再出现 `待审 / 已审 / 批量通过 / 批量驳回`。
- 兼容 `/review/*`、`/admin/*`、`/manage/shift` 等旧路径不会断链。

## 回滚

本轮是导航、状态契约和查询优化，回滚成本低：

- 后端健康字段可以保留为向后兼容新增字段。
- 前端导航收敛可以通过恢复 `manage-navigation.js` 回退。
- 旧路由保持重定向，不涉及数据迁移删除。
- 查询优化只改变读接口实现，不改写业务数据。

## 关键假设

本设计假设：接下来 `MES` 仍以只读接入为主，数据中枢负责汇聚、投影、补缺、分析和展示。

如果未来要求数据中枢反向回写 `MES`，本设计仍可保留，但必须新增写回审计、幂等、失败补偿和权限审批，本轮不做。

## 设计结论

这轮改动应把系统从“功能很多的后台”推向“接得上外部真源、看得出数据新鲜度、普通管理者不被配置页面打扰”的数据中枢。

班次和审核都不应被粗暴删除。正确做法是：

- 班次保留为基础口径和权限边界。
- 审核保留为异常兜底和审计状态。
- 两者都退出普通管理主路径。

