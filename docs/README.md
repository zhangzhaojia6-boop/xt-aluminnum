# 项目文档入口

日期：2026-06-27

适用项目：`鑫泰铝业 数据中枢`

状态：封档基线

封档意思：

```text
从现在开始，这组文档是新任务的第一阅读入口。
旧文档继续保留为历史证据，但不再抢方向。
```

## 先读这 5 份

新加入项目的人，或者下一轮智能体，先按这个顺序读。

| 顺序 | 文档 | 用途 |
|---:|---|---|
| 1 | [产品方向](./product-direction.md) | 先知道项目现在为什么要“软件做减法，智能体做加法”。 |
| 2 | [当前 PRD](./software-minus-agent-plus-prd.md) | 明确下一阶段只做什么，不做什么，怎样算完成。 |
| 3 | [智能体工作指南](./agent-operating-guide.md) | 规定 Hermes 和后续智能体怎样查证据、怎样回答、怎样留痕。 |
| 4 | [系统与界面设计方向](./system-design-direction.md) | 规定页面、路由、数据流怎样收口，避免继续长出新入口。 |
| 5 | [Hermes 事实来源地图](./hermes/fact-source-map.md) | 查每个指标到底应该从哪里来，什么来源优先。 |

小白版：

```text
上面 5 份就是新的项目地图。
旧文档不是没用，而是更像施工记录。
以后先看地图，再翻施工记录。
```

## 这些文档各管什么

| 文档类型 | 管什么 | 不管什么 |
|---|---|---|
| PRD | 做什么、为什么做、验收标准 | 不写实现细节 |
| DESIGN | 系统怎么组织、页面怎么收口、数据怎么流 | 不追加产品愿望 |
| AGENTS 指南 | 智能体怎么工作、怎么查证、怎么留下证据 | 不替代代码测试 |
| 来源地图 | 每个业务数字从哪里来、谁优先 | 不手写维护生成结果 |
| 审计报告 | 某次检查发现了什么 | 不当长期方向 |
| 历史计划 | 当时准备怎么做 | 不自动代表当前方向 |

## 当前最重要的一句话

```text
数据中枢本体要变小、变稳、变清楚。
Hermes 和智能体要在 NousResearch Hermes 基础上增强，负责理解、查证、追踪、解释和闭环。
```

## 当前执行规格

- [去统计流与 Hermes 自成长运行 SPEC](./superpowers/specs/2026-08-14-statistics-free-operations-spec.md)
- [去统计流与 Hermes 自成长实施计划](./superpowers/plans/2026-08-14-statistics-free-operations-implementation-plan.md)
- [Hermes 钉钉私聊与群聊权限设计](./superpowers/specs/2026-08-20-hermes-dingtalk-dm-group-access-design.md)
- [日报 127 字段合同深化 SPEC](./superpowers/specs/2026-08-20-daily-report-contract-deepening-spec.md)

当前只执行实施计划的阶段 1：真实基线与 `/entry/fill` 可靠性。阶段 1 未通过真实验收前，不并行进入字段合同、开停机推断或管理大仪表盘改造。

这句话拆开看：

- 软件做减法：少入口、少页面、少重复服务、少手工解释。
- 软件保留大仪表盘：管理端围绕 `/manage` 收口成一个能看全局、查来源、追异常的大仪表盘。
- 智能体做加法：多证据、多来源追踪、多异常判断、多自动复核。
- MES 读取链路必须通：MES 数据库是外部只读来源，智能体回答生产数据前要保证读取、投影、来源追踪能跑通。

## 当前状态

项目已经有：

- `/entry` 一线填报入口。
- `/manage` 管理端入口。
- 权限、角色、车间、报表、生产、能耗、钉钉、RAG、Hermes 基础能力。
- Hermes 事实来源地图。
- 数据中枢减法登记表。
- Factory Brain / Hermes 闭环骨架和一批测试。

项目还不能夸大成：

- 不能说 Hermes 已经真正理解全厂。
- 不能说真实生产 smoke 已经全部通过。
- 不能说所有旧页面和旧服务都能删除。
- 不能说 RAG 可以替代实时数字来源。

## 现在不应该先读什么

`docs/superpowers/` 里有大量历史计划、评审、阶段报告。它们很有价值，但不适合做第一入口。

正确用法：

- 要看当前方向，读本目录这 5 份。
- 要追溯某个决策，读 `docs/superpowers/plans/`、`docs/superpowers/specs/`、`docs/superpowers/reports/`。
- 要查系统全貌，读 [系统理解合并版](./system-understanding-consolidated-2026-06-14.md)。
- 要查哪些东西不能删，读 [数据中枢冻结与候选删除登记表](./datahub-deprecation-register.md)。

根目录旧 Markdown 已归档到 [root-md-2026-06-27](./archive/root-md-2026-06-27/)。

归档内容包括：

- `CONTEXT.md`
- `DEPLOY.md`
- `DEPLOY_CHECKLIST.md`
- `memory.md`
- `PRODUCT.md`
- `PROJECT_STATE_RECOVERY.md`
- `TODOS.md`

这些文件只作为历史记录读取，不再作为新任务的默认入口。

## 写新文档的规则

以后写新文档，先问 4 个问题：

1. 这份文档会不会替代已有文档？
2. 如果不替代，它是不是只是一份临时报告？
3. 它有没有链接回本入口？
4. 它有没有写清楚验收标准？

硬规则：

- 新方向文档必须更新这个入口。
- 声称“完成”的文档必须写验证命令、验证结果或真实证据链接。
- 涉及指标来源，必须对齐 [Hermes 事实来源地图](./hermes/fact-source-map.md)。
- 涉及删减、冻结、合并，必须对齐 [数据中枢冻结与候选删除登记表](./datahub-deprecation-register.md)。
- 产品名字统一叫 `鑫泰铝业 数据中枢` 或 `数据中枢`。
- `MES` 只能作为外部生产系统、外部数据源或边界说明出现，不能当本产品名字。
- 智能体方向默认基于 NousResearch Hermes 做增强，不能把模型底座、产品名字和外部 MES 系统混成一件事。

## 给下一轮智能体的读取顺序

1. 读 [产品方向](./product-direction.md)。
2. 读 [当前 PRD](./software-minus-agent-plus-prd.md)。
3. 读 [智能体工作指南](./agent-operating-guide.md)。
4. 读 [系统与界面设计方向](./system-design-direction.md)。
5. 读 [Hermes 事实来源地图](./hermes/fact-source-map.md)。
6. 需要更多背景时，再读 [如果从第一天重来](./superpowers/plans/2026-06-27-retro-initial-prd-agents-design-and-next-prd.md)。
