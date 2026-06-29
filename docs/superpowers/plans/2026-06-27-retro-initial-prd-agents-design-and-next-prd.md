# 如果从第一天重来：初始 PRD / AGENTS / DESIGN 与下一步减量增强 PRD

日期：2026-06-27

状态：封档参考 / 复盘产物 + 下一步 PRD 草案

封档说明：

```text
这份文档作为“为什么要转向”的复盘依据。
当前正式入口以 docs/README.md、docs/product-direction.md、
docs/software-minus-agent-plus-prd.md、docs/agent-operating-guide.md、
docs/system-design-direction.md 为准。
```

适用项目：`鑫泰铝业 数据中枢`

## 0. 这份文档解决什么

这份文档回答三个问题：

1. 如果一开始就把提示词、PRD、AGENTS、DESIGN 写清楚，怎样能少绕弯。
2. 当前项目到底进展到哪，不把愿景当完成。
3. 下一步应该做什么，既减量，又增强。

小白版一句话：

```text
以前像是边盖工厂边改图纸。
现在要先把主生产线验收清楚，再决定哪些旧管道可以封存。
```

## 1. 本次阅读范围和假设

### 1.1 已读和已验证

本次阅读基于：

- `README.md`
- `AGENTS.md`
- `CONTEXT.md`
- `TODOS.md`
- `CHANGELOG.md`
- `docs/system-understanding-consolidated-2026-06-14.md`
- `docs/superpowers/` 下最新 specs、plans、reports、context
- `backend/app/main.py`
- Hermes / Factory Brain 核心服务和测试
- 前端 router、API 入口、导航配置、设计 token
- CodeGraph 全仓库结构索引

CodeGraph 当前索引：

| 项 | 数量 |
|---|---:|
| 索引文件 | 1190 |
| 符号节点 | 19134 |
| 关系边 | 38003 |
| Python 文件 | 740 |
| Vue 文件 | 179 |
| JavaScript 文件 | 262 |

仓库规模抽样：

| 区域 | 数量 |
|---|---:|
| 后端服务文件 | 163 |
| 后端测试文件 | 306 |
| 前端视图文件 | 57 |
| 前端组件文件 | 92 |
| docs 文件 | 177 |
| docs/superpowers 文件 | 81 |

### 1.2 重要发现

`AGENTS.md` 要求先读的 `docs/longterm-ai-skill-system-spec.md` 当前不存在。

README 也引用了 `docs/longterm-ai-product-system-spec.md`，当前也不存在。

这不是小问题。它说明项目早期文档索引有漂移，后续 agent 容易先找错文件，再凭旧记忆继续写。

### 1.3 测试验证

本次只跑和判断相关的小范围测试：

```powershell
cd backend
python -m pytest tests/test_hermes_factory_super_brain_graph.py tests/test_hermes_factory_brain_orchestrator.py tests/test_hermes_factory_super_brain_acceptance.py tests/test_hermes_rag_router_service.py tests/test_hermes_fact_source_map_service.py tests/test_hermes_phase2_source_map_acceptance.py -q
```

结果：

```text
26 passed, 1 warning
```

结论：

```text
Hermes 闭环骨架和来源地图测试是绿的。
但真实生产 smoke 还不能说通过。
```

## 2. 当前项目进度判断

### 2.1 现在最准确的一句话

`鑫泰铝业 数据中枢` 已经有比较完整的生产数据底座、前端主入口、权限、MES 投影、日报、钉钉、RAG、Hermes 工厂大脑骨架。

但当前最关键的缺口不是继续加功能，而是：

```text
让 Hermes 用真实来源回答 20 个自然语言问题，并留下可查证证据。
```

### 2.2 已经比较稳的部分

| 部分 | 当前状态 |
|---|---|
| `/entry` 手机填报 | 主入口已收口，旧 `/mobile` 保留跳转 |
| `/manage` 管理端 | 主入口已收口，旧 `/review`、`/admin` 多数跳转 |
| 权限边界 | 管理、车间主任、手机角色已有基础隔离 |
| MES 边界 | MES 是外部只读来源，不是本系统名字 |
| 事实来源地图 | 已生成 `docs/hermes/fact-source-map.md` |
| Hermes 闭环骨架 | LangGraph 节点、意图、归一化、工具计划、进度卡、持久化已落地 |
| 数据中枢减法 | 已有审计报告和冻结登记表 |
| 设计系统 | 有工业风 token、HUD、动效、Element Plus 组件体系 |

### 2.3 还不能诚实宣称完成的部分

| 缺口 | 为什么重要 |
|---|---|
| 20 条真实自然语言 smoke | 没有它，Hermes 只是会跑骨架，不代表能现场回答 |
| 生产或 staging 备份确认 | 没有它，不能导入知识种子或灰度 |
| 真实 DingTalk / API smoke | 没有真实通道，就不能说钉钉闭环通过 |
| Factory Brain 真实取数 | 现在 `FactoryBrainDataReference.value` 多数还是 `None` |
| LangGraph checkpoint | 当前 `build_factory_brain_graph(checkpointer=None)`，不是生产可恢复状态 |
| 减法候选复核 | 很多文件仍是 `manual_review`，不能直接删 |

### 2.4 当前 Hermes 的真实状态

现在已经有：

```text
输入文本
  -> 意图识别
  -> 归一化
  -> 工具计划
  -> 证据占位
  -> 进度卡
  -> 回复
  -> chat_inbox / agent_runs 持久化
```

但还没有完全做到：

```text
输入文本
  -> 真实查 DailyFactBundle / MES / WMS / 钉钉证据 / 历史日报
  -> 返回真实 value
  -> 展示冲突和采用理由
  -> 通过 20 条生产 smoke
```

这就是下一步的主战场。

## 3. 为什么前面会绕弯

### 3.1 第一类绕弯：目标太大，验收太晚

很多文档把 Hermes 定义成“全厂业务工厂大脑”，范围包括：

- 生产
- 库存
- 发货
- 合同
- 质量
- 能耗
- 成本
- 设备
- 人员
- 异常
- 工艺
- 经营分析
- 成果物生成
- browse
- computer use
- Meta Skill
- Codex 施工

这个愿景没错，但早期 PRD 没把“第一条能验收的主链路”压到足够小。

正确做法应该是：

```text
先让 Hermes 对 3 个问题给出真实可追溯答案。
再扩成 20 个问题。
再扩成全厂业务。
```

### 3.2 第二类绕弯：事实来源地图来得太晚

事实来源地图现在已经有了，但如果一开始就先做，它会挡住很多绕路。

比如：

- 产量到底是包装量、入库量、过站下机量，不能混说。
- 电耗分母到底是产量、包装量、入库量，必须写清。
- RAG 不能当实时数字来源。
- DingTalk 文件四条件不全时，不能直接覆盖正式事实。

没有这张图，agent 容易看到一个字段就拿来答。

### 3.3 第三类绕弯：前端主入口收口晚

前端现在已经把很多旧入口 redirect 到 `/entry` 和 `/manage`。

但路由里还能看到大量历史路径：

- `/review/*`
- `/admin/*`
- `/mobile/*`
- `/dashboard/*`
- `/master/*`
- `/quality/*`
- `/reconciliation/*`

这些兼容必须保留，但如果一开始 PRD 没写清：

```text
旧入口只保留跳转，不再承载新功能。
```

后续就会出现“旧入口要不要继续改”的重复判断。

### 3.4 第四类绕弯：AI 愿景和确定性工程混在一起

Hermes 应该聪明，但工程第一版必须笨一点、稳一点。

正确顺序应该是：

```text
确定性来源
  -> 确定性规则
  -> 确定性测试
  -> 再让模型润色、追问、总结
```

不是：

```text
先把超级大脑愿景写满
  -> 再回头补证据和权限
```

### 3.5 第五类绕弯：DESIGN 太容易被理解成“做漂亮页面”

这个项目的 DESIGN 不只是视觉。

更关键的是：

- 哪个角色看哪个入口。
- 哪些数字必须带来源。
- 哪些旧页面冻结。
- 哪些操作只做 dry-run。
- 哪些状态不能用大段 AI 文案解释。

如果 DESIGN 一开始只写颜色和卡片风格，后续就容易前端好看但业务不稳。

## 4. 如果从第一天开始，最初提示词应该这样写

下面是一份更高效的初始提示词。

```text
你正在开发“鑫泰铝业 数据中枢”。

它不是 MES。MES 是外部只读生产数据源。

第一目标不是做一个大而全系统，而是跑通一条可信主链路：

现场或钉钉输入一个生产经营问题
  -> 系统识别业务日、车间、指标
  -> 查 DailyFactBundle / MES 投影 / WMS 投影 / 人工填报 / 授权钉钉证据
  -> 返回结论、关键数字、来源、冲突、缺口、trace_id
  -> 管理端能看到同一条证据链
  -> 测试、浏览器、钉钉或 API smoke 留证据

开发顺序必须是：

1. 先画事实来源地图，不清楚来源就不写页面。
2. 先做 3 个验收问题，不做全厂所有业务。
3. 先让数字可信，再让回答好看。
4. 先保留旧入口 redirect，不在旧入口加新功能。
5. 先写测试和 smoke，再宣称完成。

硬边界：

- 不把系统叫 MES。
- 不让前端直连 MES SQL Server。
- 不让 RAG 回答实时数字。
- 不让模型凭空编生产数字。
- 不允许非 root_owner 触发 Codex 施工。
- 不直接删除生产表、证据、审计日志、DailyFactBundle、Hermes、DingTalk、MES/WMS 投影。
- 手机端优先少字、大按钮、单手操作。
- 管理端优先看结果、来源、冲突、缺口，不堆说明文案。

第一阶段只交付：

1. `/entry` 手机填报主链路。
2. `/manage/today`、`/manage/live`、`/manage/production` 三个管理核心页。
3. 事实来源地图。
4. Hermes 对 3 个问题的可追溯回答：
   - 今天产量出来了吗？
   - 2050 今天吨电耗为什么高？
   - 今天生产和发货会不会影响合同交付？
5. 20 条自然语言 smoke 的测试框架。

每次完成必须输出：

- 改了哪些文件。
- 跑了哪些测试。
- 哪些真实链路没有验证。
- 哪些能力只是骨架，不是生产闭环。
```

## 5. 如果最初 PRD 应该这样写

### PRD：鑫泰铝业 数据中枢 Phase 1 可信主链路

## 5.1 产品定位

`鑫泰铝业 数据中枢` 是生产经营数据的汇集、校验、审计和分发系统。

它不是 MES。

MES 是外部只读数据源之一。

## 5.2 用户和场景

| 用户 | 要做什么 | 系统给什么 |
|---|---|---|
| 主操 / 电工 / 内勤 | 手机填报、补录、看历史 | `/entry` 少字快速填报 |
| 车间主任 | 看本车间生产和缺口 | 只看本车间管理视图 |
| 管理层 / root_owner | 看日报、异常、产量、来源 | `/manage` 聚合和证据链 |
| Hermes | 回答生产经营问题 | 只基于可追溯来源回答 |

## 5.3 第一阶段只做什么

第一阶段只做三条线：

1. 手机填报线  
   `/entry` 负责提交人工事实和补录。

2. 管理审阅线  
   `/manage/today`、`/manage/live`、`/manage/production` 负责看核心结果和来源。

3. Hermes 问答线  
   Hermes 只回答 3 类验收问题，不扩成全业务。

## 5.4 不做什么

第一阶段不做：

- 不重建 MES。
- 不把所有旧入口都继续做新功能。
- 不做全厂所有业务域。
- 不做真实生产写库自动修正。
- 不让 RAG 保存每日动态数字。
- 不把 AI 回答做成大段解释文。
- 不做大规模删除。

## 5.5 数据来源规则

所有关键数字必须有：

- 指标名
- 数值
- 单位
- 业务日
- 来源
- 口径
- 置信度
- trace_id

事实优先级：

```text
root_owner 确认
  -> 满足四条件的 DingTalk 专项责任人证据
  -> DailyFactBundle
  -> MES/WMS 只读投影
  -> 数据中枢人工填报
  -> 历史日报
  -> RAG 口径知识
  -> 模型普通知识
```

注意：

```text
RAG 可以解释，不可以当今天事实。
模型可以组织语言，不可以编数字。
```

## 5.6 第一阶段验收问题

只验 3 个问题：

```text
今天产量出来了吗？
2050 今天吨电耗为什么高？
今天生产和发货会不会影响合同交付？
```

每个问题必须返回：

```text
结论
关键数字
来源
冲突
缺口
建议动作
trace_id
```

## 5.7 验收标准

第一阶段完成必须同时满足：

1. `/entry` 能用真实角色提交或查看关键流程。
2. `/manage/today` 能解释日报核心数字来源。
3. `/manage/live` 能显示实时状态和缺报。
4. `/manage/production` 能区分包装量、入库量、过站参考。
5. Hermes 3 个问题能返回真实来源。
6. 20 条 smoke 框架存在，但可以先只跑 3 条。
7. 所有未验证真实生产的地方必须写成 `blocked` 或 `not_verified`。

## 6. 如果最初 AGENTS 应该这样写

### AGENTS：鑫泰铝业 数据中枢开发规则

## 6.1 先读

每次开始前先读：

1. `README.md`
2. `CONTEXT.md`
3. `docs/hermes/fact-source-map.md`
4. `docs/datahub-deprecation-register.md`
5. 当前任务相关的 spec / plan / test

如果文档不存在，必须报告，不要凭记忆继续。

## 6.2 先查结构

结构问题优先用 CodeGraph。

文字内容查找用 `rg`。

不要先大面积打开文件。

## 6.3 每次只做一个主链路

一次任务只能属于一种：

- 手机填报
- 管理审阅
- Hermes 问答
- DingTalk 通讯
- RAG / 知识
- 来源地图
- 减法审计
- 部署 / smoke

不要一个 PR 同时做视觉、权限、RAG、钉钉、数据库和部署。

## 6.4 事实优先

涉及数字时，先回答：

```text
这个数从哪来？
哪个表？
哪个服务？
哪个接口？
哪个页面？
有没有冲突？
有没有 trace_id？
```

答不上来就先补来源地图，不要先写 UI。

## 6.5 测试规则

每个改动至少要有一种验证：

- 单元测试
- API smoke
- CLI smoke
- 浏览器 smoke
- 钉钉真实或 dry-run smoke

不能用“看起来应该可以”代替验证。

## 6.6 完成定义

完成只能有三种：

| 状态 | 含义 |
|---|---|
| `done` | 测试或真实 smoke 通过 |
| `blocked` | 外部条件缺失，无法诚实验证 |
| `not_verified` | 代码做了，但还没验 |

不要把 `not_verified` 写成完成。

## 6.7 减法规则

任何删除前必须满足：

1. 没有生产路由引用。
2. 没有导航引用。
3. 没有 API 调用引用。
4. 没有测试依赖。
5. 没有 Hermes 工具依赖。
6. 没有 DailyFactBundle 依赖。
7. 没有历史二维码或收藏入口风险。
8. 有回滚方式。
9. 观察 7 到 14 天。

第一步永远是 freeze，不是 delete。

## 7. 如果最初 DESIGN 应该这样写

### DESIGN：数据中枢产品设计规则

## 7.1 设计目标

不是“炫酷 AI 系统”。

是“现场和管理层都能信的数据操作台”。

视觉关键词：

```text
安静
清楚
工业
可信
少字
强来源
强状态
```

## 7.2 信息架构

只保留两个主入口：

| 主入口 | 作用 |
|---|---|
| `/entry` | 现场填报 |
| `/manage` | 管理审阅 |

旧入口：

```text
/mobile/*
/review/*
/admin/*
```

只做兼容跳转，不承载新功能。

## 7.3 手机端原则

手机端是给现场用的。

规则：

- 大按钮。
- 大输入。
- 少文字。
- 默认当前业务日。
- 出错直接告诉人怎么补。
- 不放复杂图表。
- 不放大段 AI 文案。

## 7.4 管理端原则

管理端先看：

1. 结论。
2. 数字。
3. 来源。
4. 冲突。
5. 缺口。
6. 下一步动作。

每个关键数字旁边必须能看到来源状态：

```text
已证实
候选
待复核
缺失
冲突
```

## 7.5 Hermes / AI 设计原则

Hermes 不要像聊天玩具。

它在页面上应该像一个“运行中的业务同事”：

- 显示处理阶段。
- 显示查了哪些来源。
- 显示缺什么证据。
- 显示 trace_id。
- 支持采纳、不准、重新查询、查看来源。

不要展示模型完整思维链。

展示可审计步骤。

## 7.6 视觉系统

继续使用现有设计 token：

- `frontend/src/design/xt-tokens.css`
- `frontend/src/design/theme.css`
- `frontend/src/design/industrial.css`
- `frontend/src/design/xt-hud.css`

不要另起一套视觉系统。

页面变好看的优先级：

```text
减少无用内容
  -> 统一信息层级
  -> 强化来源和状态
  -> 最后再做视觉细节
```

## 8. 下一步 PRD：Hermes 真实证据闭环与数据中枢减量增强

## 8.1 一句话目标

下一步不继续扩“超级大脑”范围。

只做一件事：

```text
让 Hermes 对 20 条自然语言问题输出真实可追溯答案，并把不能答的原因说清楚。
```

小白版：

```text
先让它别装懂。
能查到就说来源。
查不到就说缺哪条证据。
```

## 8.2 目标用户

| 用户 | 目标 |
|---|---|
| root_owner 张兆嘉 | 随口问业务问题，看到可信结论和来源 |
| 管理层 | 看到日报、产量、异常、合同风险的可信摘要 |
| 车间主任 | 只看本车间相关来源和缺口 |
| 工程维护者 | 能用 trace_id 找到运行记录、工具计划和证据链 |

## 8.3 范围

本 PRD 只覆盖四个垂直切片。

### 切片 1：真实证据适配

目标：

```text
FactoryBrainDataReference.value 不再总是 None。
```

第一批接入指标：

| 指标 | 来源优先级 |
|---|---|
| `daily_output` | fact source map -> DailyFactBundle / dashboard daily production / historical report |
| `monthly_output` | operation period / daily report history / DailyFactBundle |
| `electricity_per_ton` | energy summary / DailyFactBundle / RAG 口径 |
| `remaining_contract_weight` | factory command / contract projection |

要求：

- 查不到真实值时，必须保留 `needs_live_query=true`。
- 查到真实值时，必须有 source、unit、business_definition、confidence。
- 不能为了通过测试写假数。

### 切片 2：20 条自然语言 smoke

建立固定 smoke 清单：

```text
今天产量出来了吗？
今天这个数从哪来的？
生成昨天日报草稿。
6月19日正式日报和历史成品能对齐吗？
2050 今天吨电耗为什么高？
今天生产和发货会不会影响合同交付？
本月经营情况怎么样？
今年累计产量和成本趋势怎么样？
哪个车间今天异常最大？
这个钉钉文件能作为正式数据吗？
这个数能信吗？
如果 MES 和钉钉冲突，采用谁？
日报里的成品率怎么算？
入库和包装为什么不是一个数？
数据中枢哪些旧页面可以冻结？
哪些表绝对不能删？
哪些文档已经过期？
把今天日报按老板看的版本发我。
把这条规则记住，以后日报先看责任人文件。
现在你缺什么证据？
```

每条 smoke 必须给出：

- 是否进入 factory brain。
- 识别出的 intent。
- 归一化结果。
- 查询计划。
- 证据列表。
- 缺口。
- 最终回答。
- trace_id。

### 切片 3：灰度门禁

灰度前必须满足：

1. `HERMES_FACTORY_BRAIN_ENABLED=false` 保守默认不变。
2. staging 或 production 备份确认存在。
3. 知识种子导入只在确认环境执行。
4. 20 条 smoke 至少本地 fixture 模式通过。
5. 3 条 production API 或 DingTalk smoke 有真实证据。
6. 不更新 `docs/deploy/current-state.md`，除非 production smoke 真的通过。

### 切片 4：减法增强

目标不是删除，而是把减法审计变准。

本阶段只做：

- 把 `manual_review` 里和 Hermes 主链路相关的文件分成 protect / freeze / merge_candidate。
- 更新 `docs/datahub-deprecation-register.md`。
- 明确每个 freeze 对象的观察期和回滚方式。

本阶段不做：

- 不直接删除文件。
- 不删表。
- 不删历史入口 redirect。
- 不删证据、审计、RAG、DingTalk、DailyFactBundle、MES/WMS 投影。

## 8.4 非目标

本 PRD 不做：

- 不做全业务域扩张。
- 不做 computer use 自动操作。
- 不做图像生成。
- 不做新的大前端重构。
- 不做生产数据自动修正。
- 不做大规模文件删除。
- 不把旧入口改成新功能入口。
- 不把模型 provider 迁移当主任务。

## 8.5 成功标准

### 必须达成

1. 20 条自然语言 smoke 都能跑。
2. 至少 12 条返回 `replied`。
3. 至少 8 条带真实非空 `value`。
4. 所有回答都带来源或缺口。
5. 所有回答都不出现 `Codex token refresh failed`。
6. 所有 root_owner 施工类请求都被权限检查保护。
7. `python -m pytest` 的 Hermes 相关测试通过。
8. `docs/superpowers/reports/hermes-phase2-grey-verification-*.md` 不能把未验证写成通过。

### 推荐达成

1. 3 条 production smoke 通过。
2. 1 条 DingTalk dry-run 或真实通道 smoke 通过。
3. 1 条 source map 问答能从 UI 或 API 追到 `agent_runs.result_payload`。

## 8.6 建议任务拆分

### Task A：证据值接入

改动范围：

- `backend/app/services/hermes_factory_evidence_service.py`
- `backend/app/services/hermes_fact_source_map_service.py`
- 相关测试

验收：

```powershell
cd backend
python -m pytest tests/test_hermes_factory_evidence_service.py tests/test_hermes_fact_source_map_service.py -q
```

### Task B：Smoke harness

改动范围：

- `backend/scripts/hermes_factory_brain_cli.py`
- 新增 smoke fixture 或 JSON 输出文件
- 新增测试

验收：

```powershell
cd backend
python scripts/hermes_factory_brain_cli.py ask "今天产量出来了吗？"
python -m pytest tests/test_hermes_factory_super_brain_acceptance.py -q
```

### Task C：灰度报告门禁

改动范围：

- `docs/superpowers/reports/*grey-verification*.md`
- 如需要，新增检查脚本

验收：

```text
没有真实 production smoke，就只能写 blocked 或 not_verified。
```

### Task D：减法登记表升级

改动范围：

- `docs/datahub-deprecation-register.md`
- `docs/superpowers/reports/datahub-diet-audit-*.md`

验收：

```text
每个 freeze 对象都有观察期和回滚方式。
没有删除动作。
```

## 8.7 交付物

本 PRD 完成后至少交付：

1. Hermes 20 条 smoke 结果报告。
2. 真实证据接入测试。
3. 更新后的灰度验证报告。
4. 更新后的冻结与候选删除登记表。
5. 一段小白能看懂的当前状态总结：

```text
哪些问题能答。
哪些问题不能答。
为什么不能答。
下一步要补哪条证据。
```

## 9. 总结

如果一开始只写“做一个工厂超级大脑”，agent 很容易把范围摊开。

更好的初始设计应该是：

```text
先做可信事实链。
再做自然语言。
再做知识库。
再做主动性。
最后做全厂超级大脑。
```

下一步最值得做的不是再加能力，而是把已经有的能力从：

```text
骨架可跑
```

推进到：

```text
真实可验收
```
