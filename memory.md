# memory.md

## 1. 系统当前定位

`aluminum-bypass` 不是新的 `MES`。

它当前的正式定位是：

- 保持 `MES` 为卷级流转唯一真源
- `aluminum-bypass` 作为下游统计、投影、经营估算和驾驶舱系统
- Docker Compose 是当前主运行形态
- 手机端 `/mobile` 仍是现场填报主入口
- 管理层优先看聚合结果和驾驶舱，不重建人工统计中间层

## 2. 当前稳定约束

以下约束默认长期有效，除非业务方明确改口：

- 不改现场 `MES` 扫码流程
- 不在本系统内再造一条卷级真源
- Phase 1 只做经营估算，不做财务级真实利润
- 管理层看到卷级变化的目标时效是 `5 分钟内`
- 手机扫码后的页面应是：
  - `MES` 头字段自动带出并锁定
  - 现场只补充本工序新增事实

## 3. 已完成的关键沉淀

截至 `2026-04-11`，这条线已经完成的高价值沉淀不是零散聊天，而是 3 份正式文档：

1. [docs/mes-api-sync-contract-phase1.md](./docs/mes-api-sync-contract-phase1.md)
   - 锁死 `MES -> aluminum-bypass` Phase 1 同步契约
   - 明确扫码预填与锁定字段规则
2. [docs/mes-field-mapping-table-phase1.md](./docs/mes-field-mapping-table-phase1.md)
   - 锁死“MES 头字段 / 卷级投影字段 / 现场补充字段”的落点边界
3. [docs/mes-api-integration-checklist.md](./docs/mes-api-integration-checklist.md)
   - 联调前必须问清的字段、认证、时间口径、状态枚举、错误样例
4. [docs/mes-api-two-week-prep-plan.md](./docs/mes-api-two-week-prep-plan.md)
   - `MES API` 未就绪期间的两周施工计划

此外，根目录工作记录中的正式共识计划是：

- `/mnt/d/zzj/.omx/plans/aluminum-bypass-mes-clue-stats-system-consensus-20260411T061435Z.md`

## 4. 上次工作的真实断点

上次在 `2026-04-11` 的实际结论是：

- 本系统侧的架构方向已经明确
- `REST API MES adapter + 卷级投影 + sync + 驾驶舱落点` 这条主线已被作为正式方向确认
- 但真实外部阻塞不是代码，而是 `MES API` 还没有对接就绪
- 当时的预计是：`MES API` 还需要约两周，目标时间大约到 `2026-04-25`

所以那次工作的正确延续方式不是继续空写联调代码，而是先把记忆、契约、清单和准备动作固化。

## 5. 当前外部阻塞

在 `MES API` 真正可联调之前，下面这些仍然是阻塞项：

- `MES_API_BASE` 未最终确认
- 认证方式未最终锁死
- 测试环境 / 正式环境地址未全部到位
- `tracking card info` 与 `coil snapshots` 的正式样例未收齐
- 状态枚举、时间口径、游标规则仍需由 `MES` 方确认

## 6. 下次进来应直接继续什么

下次如果继续这条线，默认不要重新讨论“大方向”，直接做下面几件事：

1. 跟 `MES` 方确认接口地址、认证方式、测试环境和预计就绪日
2. 收齐 3 类样例：
   - 正常样例
   - 空数据样例
   - 错误 / 限流样例
3. 固化字段映射表，尤其是：
   - `batch_no`
   - `qr_code`
   - `contract_no`
   - `status`
   - `event_time`
   - `updated_at`
4. 明确扫码页锁定字段与人工补充字段边界
5. 用 mock 数据先演练一次同步链路和驾驶舱链路

## 7. 继续施工时不要做什么

- 不要因为接口未就绪就重做现场扫码流程
- 不要在没有正式契约前猜字段硬接
- 不要把范围提前扩成财务系统
- 不要让 `work_orders` 和 `MES` 投影争抢卷级真相地位
