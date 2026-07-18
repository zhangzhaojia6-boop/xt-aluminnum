# Phase 2 事实合同生产闭环报告

## 结论

2026-07-18（北京时间），Phase 2 已完成代码、测试、独立评审、生产静态门禁、三日 compare-only 诊断、真实回滚、重新部署和最终只读复核。

本阶段已经证明：127 个投产判分字段有统一合同；130 个模板展示字段不会混入规范分母；答案钥匙只参与比较；未声明 N/A 的缺字段会以 `reference_absent` 阻塞；生产能够在旧版和新版之间受控切换并恢复。

本阶段没有证明日报业务对齐达到 90%。2026-07-15 至 2026-07-17 的答案钥匙已出现字段匹配率仍为 7.26%、8.87%、9.68%，五个关键事实也未全部 confirmed。该缺口属于后续 Phase 3/4，不能用 Phase 2 合同门禁通过来替代。

## 版本与证据

- Phase 2 合并：[PR #50](https://github.com/zhangzhaojia6-boop/xt-aluminnum/pull/50)
- Data Hub 合并与生产版本：`cb120f5e7977eef52ef1664f0dbf95708f644cc5`
- Hermes 生产版本：`d21e9c247738d9d8029761534aea24668dc12119`
- PR push CI：[GitHub Actions #29636037945](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29636037945)
- PR CI：[GitHub Actions #29636039315](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29636039315)
- main 合并提交 CI：[GitHub Actions #29636400551](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29636400551)
- 首次生产部署：[GitHub Actions #29636674363](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29636674363)
- 首次三日 compare-only：[GitHub Actions #29636970116](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29636970116)
- 真实回滚：[GitHub Actions #29637081280](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29637081280)
- 重新部署：[GitHub Actions #29637188407](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29637188407)
- 最终只读状态：[GitHub Actions #29637297416](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29637297416)
- 最终三日 compare-only：[GitHub Actions #29637319936](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29637319936)

所有普通日志和本文只记录状态、数量、版本与不可逆摘要，不记录密钥、聊天原文、文件正文或答案钥匙正文。

## 自动门禁

- 最终后端全量：2818 passed、5 skipped、27 deselected。
- 前端依赖安装、依赖审计、生产构建与 PWA 生成通过。
- 两条 PR 流水线和 main 流水线的 backend、frontend、Compose、`healthz`、`readyz`、Nginx 登录与 Playwright 烟测均通过。
- 独立规格评审通过；独立代码复审提出的 4 项问题全部修复后通过。
- 合同文档连续生成两次，SHA-256 保持 `12D0C230941EA4BC015A24ACF4109740F263A939B85842346910F045B1652A84`。
- 旧对齐键、新双分母、结构化 N/A 和兼容入口验证通过。

## 生产静态合同

首次部署、重新部署和最终只读状态均得到 `status=pass`：

| 合同项 | 结果 |
|---|---|
| 规范判分字段 | 127 |
| 模板展示字段 | 130 |
| 最大绝对容差 | 20 |
| 标准生产起点 | 07:50 |
| 铸二/铸三/热轧起点 | 10:00 |
| 责任人每日一录提交时间 | 09:30 |
| 迟报截止 | 10:00 |
| 生成文档 | current |
| 合同问题 | 0 |

统一来源顺序为：钉钉证据、授权纠错、MES/WMS 只读、扫码补录、数据中枢投影、历史记录、RAG 仅解释。`output_skill` 不在真实来源通道内，RAG 不能生成实时数字。

## 生产健康

重新部署和最终只读状态证明：

- Data Hub 与 Hermes 仓库均为受控 SHA，tracked 与 untracked 状态干净。
- `aluminum-bypass`、`hermes-gateway`、`nginx` 三个服务均为 `active`。
- `/readyz` 为 `ready`；数据库、设备绑定、MES 同步、pipeline、排程与上传均为 `ok`。
- 外部 MES SQL Server 只读适配器为 `fresh/success`，最近一次读取 50 条并投影 50 条，未开放 MES 写入。
- Hermes 部署合同为 `ready`，钉钉 Stream 为 `connected`。
- 正式钉钉验收底账保持 `chat_inbox=17`、`multimodal_evidence=17`。
- 部署使用的无外发入站烟测同时持久化到 chat inbox 与 multimodal evidence，没有向验收群重复发送 Phase 1 标记。
- 能耗数据库仍为 `unconfigured`，这是未来来源接入项，不伪装为当前已完成能力。
- 活跃生产车间口径为 13；包含更宽数据库管理范围时为 15，本文不混用两个口径。

## 三日 compare-only

两个生产对齐工作流都成功生成并上传 JSON、Markdown 产物，随后只在“业务门禁未通过”步骤按设计返回 1。红色结论被保留，没有改写成通过。

| 业务日 | 答案已出现字段 | 已出现匹配率 | 规范字段 | 规范覆盖率 | `reference_absent` | 事实缺字段 | 状态 |
|---|---:|---:|---:|---:|---:|---:|---|
| 2026-07-15 | 9 / 124 | 7.26% | 9 / 127 | 7.09% | 3 | 79 | blocked |
| 2026-07-16 | 11 / 124 | 8.87% | 11 / 127 | 8.66% | 3 | 65 | blocked |
| 2026-07-17 | 12 / 124 | 9.68% | 12 / 127 | 9.45% | 3 | 65 | blocked |

三天均满足以下诊断合同：

- `reference_mode=compare`。
- `reference_only=false`，答案钥匙没有进入事实生成。
- 规范分母固定为 127，答案钥匙已出现字段分母为 124。
- 未声明 N/A 和非法 N/A 均为 0。
- 三个 `reference_absent` 每天都精确列出：`cast_roll_active_lines`、`cast_roll_daily`、`finished_inbound_month`。
- 字段容差最大值为 20，没有超过 owner 允许的误差上限。
- 关键事实来源中不存在 `output_skill` 或 `official_daily_report`。

五个关键事实仍未闭环：

| 业务日 | confirmed | mismatch | missing | needs_evidence |
|---|---:|---:|---:|---:|
| 2026-07-15 | 1 | 2 | 1 | 1 |
| 2026-07-16 | 1 | 4 | 0 | 0 |
| 2026-07-17 | 0 | 3 | 0 | 2 |

总产量和成品入库已走 MES/WMS 只读投影；在制、用电和成品率仍有日期、单位、证据锚或分子分母口径需要后续关闭。本文不复述答案钥匙值，也不把投影存在写成事实已准确。

## 回滚与恢复

真实回滚将生产 Data Hub 从 `cb120f5e7977eef52ef1664f0dbf95708f644cc5` 切换到 Phase 2 前 SHA `d4eb882594c5e0d9708e3d3980fc9b6906995b84`，Hermes 保持 `d21e9c247738d9d8029761534aea24668dc12119`。

回滚后：

- 生产仓库 HEAD 与 `/versionz` 都返回 `d4eb882594c5e0d9708e3d3980fc9b6906995b84`。
- 三个服务均为 `active`，`/readyz=ready`，MES 只读同步为 `fresh/success`。
- 旧 SHA 没有合同脚本，工作流明确输出 `DAILY_REPORT_FIELD_CONTRACT_GATE=not_available_for_sha`，没有误判成服务失败。

随后重新部署 `cb120f5e7977eef52ef1664f0dbf95708f644cc5`：

- 生产仓库 HEAD 与 `/versionz` 都恢复到 accepted SHA。
- 三个服务、`/readyz`、MES 只读同步、Hermes Gateway 与 Stream 全部恢复。
- 静态合同门禁重新得到 pass，127/130、最大容差 20、文档 current、问题 0。

每次 deploy/rollback 都在切换前执行 PostgreSQL custom-format `pg_dump`，并用 `pg_restore -l` 验证备份可读；备份保留在生产 `backups/pre-task10-deploy-*.dump`。迁移前后均为 `0055_chat_inbox_inbound_dedupe`，本阶段没有数据库版本漂移。对应工作流链接已在“版本与证据”中封档。

## 最终复跑稳定性

回滚并重新部署后的第二次三日产物保持相同的业务日、compare-only 模式、分母、缺字段、匹配率、规范覆盖率和 blocked 状态。

两次产物的动态差异只有：

- 回滚与重新部署各产生一条无外发入站烟测，钉钉诊断总行数从 46 增加到 48。
- 最新在制快照的业务窗口从 15:58 刷新到 16:11；已采用值和 7 月 15 日 missing 状态没有变化。

这两类变化没有进入答案钥匙来源，也没有改变任何判分结果。历史日在制快照应采用哪个采样时点仍需在 Phase 3 核验，本文不先下结论。

## 下一阶段

Phase 2 可以封档并关闭 #36。下一步进入 #37 / Phase 3：验证 MES/WMS 全部日报查询键、只读 SQL、游标、同步延迟、历史业务日采样语义、来源 trace、断线与恢复告警。只有 Phase 3 完成后，才进入 Phase 4 把五个关键事实和全字段匹配率提升到 90% 以上。
