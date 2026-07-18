# Phase 3 MES/WMS 只读可靠性生产闭环报告

## 结论

2026-07-18（北京时间），Phase 3 已完成代码、测试、独立评审、精确 SHA 部署、三个已完成业务日真实审计、真实回滚、重新部署和最终复验。

本阶段已经证明：数据中枢只能通过登记的只读 SQL 读取外部 MES/WMS；生产 SQL Server 账号未发现数据库、对象、schema 或危险固定角色写权限；2026-07-15、2026-07-16、2026-07-17 三个业务日的五条日报关键来源查询均成功返回记录；同步日、同步新鲜度、断线/超时/schema 变化分类和恢复事件均可审计；生产可回滚后恢复到同一受信版本。

本阶段没有证明日报字段匹配率达到 90%，也没有证明五个关键事实已经全部准确。该业务准确性目标属于 Phase 4，不能用本报告替代。

## 版本与证据

- Phase 3 合并：[PR #52](https://github.com/zhangzhaojia6-boop/xt-aluminnum/pull/52)
- Data Hub 合并与最终生产版本：`81b3d17fd76a4ef70c40da152c821c2f1354cd89`
- Hermes 最终生产版本：`d21e9c247738d9d8029761534aea24668dc12119`
- PR push CI：[GitHub Actions #29641888016](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29641888016)
- PR CI：[GitHub Actions #29641896882](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29641896882)
- 部署前只读状态：[GitHub Actions #29642196719](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29642196719)
- 首次生产部署：[GitHub Actions #29642217287](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29642217287)
- 首次三日只读审计：[GitHub Actions #29642319803](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29642319803)
- 真实回滚：[GitHub Actions #29642371937](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29642371937)
- 重新部署：[GitHub Actions #29642477100](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29642477100)
- 最终三日只读审计：[GitHub Actions #29642572645](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29642572645)

首次和最终审计 artifact 分别为 `mes-readonly-audit-production-29642319803`、`mes-readonly-audit-production-29642572645`。artifact 只含状态、数量、时间窗、hash、权限结果和事件 ID，不含凭据、原始行、业务正文、聊天内容或个人数据。

## 本地与 CI 门禁

- Phase 3 定向测试：127 passed。
- 最终后端全量：2854 passed、3 skipped、27 deselected，耗时 723.96 秒。
- 前端未被本轮评审修复改动；既有全量单元测试 727 passed，生产构建与 PWA 生成通过。
- Python `compileall` 和 `git diff --check` 通过。
- 两条 PR 流水线的 backend、frontend 和 Compose smoke 全部通过；Vercel 预览通过。
- 独立规格与质量评审先后发现真实 adapter 未初始化、时间窗证据不足、故障事件未落真实 event bus、晚到补跑重复计日、schema/角色权限遗漏等问题；全部修复并复审为 PASS。

## 查询与权限

登记查询合同共 20 条：

- 10 条 current 查询。
- 6 条 window 查询。
- 4 条 database/object/schema/fixed-role 权限查询。

20 条查询全部通过静态只读解析，合同 SHA-256 为 `deb26d87962273a329f5a450d57bf232997a82cb4a904a9991a38af5bddc7ad1`。SQL guard 拒绝非 `SELECT`、堆叠语句、`SELECT INTO` 和其他写入/DDL 关键词；SQL Server adapter 的 completion 写入入口也会直接拒绝。

生产权限审计结果：

| 范围 | 审计数量 | 危险权限 |
|---|---:|---:|
| database | 1 | 0 |
| object | 9 个真实来源表 | 0 |
| schema | 1 | 0 |
| dangerous fixed role | 4 类候选角色 | 0 |

对象权限清单只由 `current/window` 查询规格生成，不会把 `DATABASE`、`REGISTERED_TABLES`、`REGISTERED_SCHEMAS` 或 `DATABASE_ROLES` 内部标记误当成 SQL Server 表名。

## 三日真实探针

三日真实探针覆盖日报投影依赖的五条关键时间窗来源：生产过程、入库明细、成品入库、发货、原料。每条证据均保留业务日、时间字段、窗口起止、来源表、来源路径、查询 hash、schema hash、行状态和本地投影数量，不保留原始行值。

| 业务日 | 探针 | 有记录 | 明确无数据 | 查询失败 | 同步日 |
|---|---:|---:|---:|---:|---|
| 2026-07-15 | 5 | 5 | 0 | 0 | success |
| 2026-07-16 | 5 | 5 | 0 | 0 | success |
| 2026-07-17 | 5 | 5 | 0 | 0 | success |

本次生产数据没有出现零行；如果后续真实零行，门禁会保留 `query_succeeded_no_rows` 和时间窗，不会把缺失改成业务数字 0。

首次审计同步状态为 `fresh/success`，门禁延迟约 18.82 秒；最终审计约 3.42 秒，生产阈值为 300 秒。每条同步日志只归属一个 `target_business_date`，晚到补跑不会同时算入两个业务日。

## 故障与恢复

三类受控演练均使用生产重试 helper，但只在进程内产生假异常，不调用真实 MES 查询或写入：

| 演练 | 分类 | 尝试 | 恢复 | 首次事件 | 最终事件 |
|---|---|---:|---|---|---|
| disconnect | `connection_failed` | 2 | pass | 225657-225658 | 225695-225696 |
| timeout | `query_timeout` | 2 | pass | 225659-225660 | 225697-225698 |
| schema_change | `schema_changed` | 2 | pass | 225661-225662 | 225699-225700 |

每组都真实持久化 `mes_sync_failed` 和 `mes_sync_recovered` 到数据中枢 event bus。受控 payload 不含 `workflow_event`，因此不会触发钉钉或其他外部发送。

## 生产健康

首次部署、回滚和重新部署后均确认：

- Data Hub 与 Hermes 仓库 tracked/untracked 状态干净，`/versionz` 与目标 SHA 一致。
- `aluminum-bypass`、`hermes-gateway`、`nginx` 三个服务均为 `active`。
- `/readyz=ready`；数据库、设备绑定、MES 同步、pipeline、排程和上传均为 `ok`。
- MES adapter 为 `sqlserver`，最近同步为 `fresh/success`，未开放 MES 写入。
- Hermes Gateway 为 running，钉钉 Stream 为 `connected/fresh`。
- 部署入站烟测均在 chat inbox 与 multimodal evidence 中形成同一 trace，没有执行外部群发送。
- 活跃生产车间口径为 13；更宽数据库管理口径为 15，本文不混用。

`iot_energy_sync=unconfigured` 是未来能耗数据库接入状态，不属于本阶段 MES/WMS 只读链路故障，也不把它写成已完成能力。

## 回滚与恢复

真实回滚将 Data Hub 从 `81b3d17fd76a4ef70c40da152c821c2f1354cd89` 切回上一已验收版本 `cb120f5e7977eef52ef1664f0dbf95708f644cc5`，Hermes 保持不变。回滚后 `/versionz`、三个服务、`readyz`、MES `fresh/success` 和 Stream `connected/fresh` 全部通过。

随后重新部署 `81b3d17fd76a4ef70c40da152c821c2f1354cd89`，再次通过相同健康门禁，并重新运行三日只读审计。第二次结果保持 15/15 探针有记录、20 条静态合同通过、危险权限 0、同步日 3/3、故障演练 3/3、blocker 0。

## 边界与下一阶段

- Phase 3 证明读取链路连续、只读、可审计、可恢复，不证明日报字段值已经与答案钥匙对齐。
- `D:\输出skill` 未参与本阶段事实生成、探针、权限或故障演练。
- 故障演练验证真实重试与事件持久化，但不会故意断开生产 MES 或修改供应商 schema。
- 三日门禁不替代 Phase 11 的连续七个业务日影子运行。
- GitHub artifact 上传动作有 Node.js 20 弃用警告，但动作被 runner 强制使用 Node.js 24 且上传成功；后续维护时升级 action 版本。

Phase 3 可以封档。下一步进入 #38 / Phase 4：先关闭总产量、成品入库、在制、总用电、成品率五个关键事实，再使用 compare-only 把三个业务日的答案钥匙已出现字段匹配率和 127 字段规范覆盖率提升到 90% 以上，所有数值容差保持不超过 20，答案钥匙继续不得填数。
