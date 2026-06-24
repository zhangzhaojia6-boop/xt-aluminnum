# Hermes + 日报事实包 Phase-2 设计

日期：2026-06-22

## 1. 一句话目标

Phase-2 的目标是把 `鑫泰铝业 数据中枢` 从“报表加工层很多、事实入口很多”的状态，收口成：

```text
统一事实底座 -> Hermes 自然语言理解 -> 工厂大脑判断 -> 钉钉/日报输出 -> 复盘学习
```

小白版理解：

> 数据中枢以后主要负责把真实数据整理好、说清楚来源、留好痕迹。Hermes 负责像工厂超级大脑一样听懂人话、判断问题、组织日报和推动动作。

本规格的核心 module 是 `日报事实包`。

它不是日报正文，也不是一个新的报表页面。它是某个业务日的“可信事实集合”。

## 2. 已确认决策

### 2.1 日报事实包只负责事实

`日报事实包` 只输出：

- 字段值。
- 单位。
- 业务日。
- 来源。
- 缺失字段。
- 冲突字段。
- 数据新鲜度。
- 可信度。
- 采用原因。

它不负责：

- 生成日报文案。
- 发钉钉。
- 决定发给谁。
- 自动修改 MES/WMS 原始数据。
- 直接做角色版表达。

通俗说：`日报事实包` 是食材和质检单，Hermes 才是厨师。

### 2.2 业务日是主键，视角只是裁剪

事实包按业务日生成：

```text
build_daily_fact_bundle(business_date=2026-06-19)
```

同一天只生成一套事实底座。

不同输出只是同一套事实的不同视角：

- `root_owner` 完整日报。
- 老板摘要。
- 车间主任视角。
- 能耗负责人视角。
- 异常解释。

通俗说：同一天只煮一锅事实底汤，不同人喝不同碗。

### 2.3 Hermes 必须理解自然语言

Hermes 不能只识别固定命令。

它要能理解这类自然语言：

```text
今天产量怎么回事？
昨天日报发我看看。
6月19日按最终口径重新来一版。
这个文件以后当日报数据用。
为什么2050吨耗这么高？
把这个数按车间主任能看的版本发。
6月19日车间总产量改成366吨，直接按这个发。
```

但内部必须转成结构化任务：

```text
intent: daily_report
business_date: 2026-06-19
audience: root_owner
mode: final
evidence_policy: include_dingtalk_supplement
correction_policy: root_owner_direct
```

原则：

```text
自然语言自由输入，内部结构化执行。
```

## 3. 当前问题

### 3.1 数据中枢的报表加工层偏重

当前数据中枢里有多条日报相关链路：

- `template_daily_report`
- `template_daily_fact_sources`
- `daily_overview_builder`
- `dashboard_builder`
- `mes_fact_bundle`
- `HermesDataAuditService`
- `HermesDay1SourceService`
- 输出 skill 对齐逻辑

这些能力都有价值，但现在事实入口过多。

结果是：

- 同一个业务日可能被不同 module 重新拼 facts。
- Hermes 要理解太多报表加工 implementation。
- 页面、日报、审计、输出 skill 对齐之间容易出现口径差异。
- 数据中枢体积越来越大，减法越来越难。

### 3.2 Hermes 的灵活性不能只靠命令解析

Day-1 已经有可运行闭环，但自然语言意图仍需要升级。

下一步不能只增加更多固定命令。

否则 Hermes 会变成：

```text
命令机器人 + 报表脚本
```

而不是：

```text
能理解工厂业务的超级大脑
```

## 4. 领域语言

本规格使用 `CONTEXT.md` 中的语言。

核心术语：

| 术语 | 含义 |
|---|---|
| 数据中枢 | 汇集、校验、审计和分发生产经营数据的系统，不是 MES |
| 日报事实包 | 某个业务日用于生成日报的一组可信事实集合 |
| 业务日 | 生产经营数据归属日期，是事实包主键 |
| 视角 | 同一事实包面向不同接收人的裁剪方式 |
| Hermes 工厂大脑 | 基于事实证据理解业务、判断风险、组织输出和沉淀学习的智能体 |
| 自然语言意图 | 用户用不固定句式表达的业务目标 |
| 钉钉补充数据 | 授权人员通过钉钉发送的高优先级补充来源 |
| 冲突字段 | 多来源之间不一致的事实字段 |
| root_owner 修正事实 | 张兆嘉直接确认或修改的最高优先级事实 |
| 输出 skill | 历史真实日报成品和核对材料，只读验收参考 |

## 5. 总体架构

```text
钉钉 / CLI / 页面
  -> HermesIntent
      听懂自然语言，转成结构化任务
  -> HermesBrainRun
      规划工具、调用事实包、推理、评分、学习
  -> DailyFactBundle
      按业务日生成可信事实集合
  -> Hermes 输出
      判断单、正式日报、车间明细、异常解释、分发版本
```

核心减法：

```text
旧链路各自拼 facts
  -> 统一到 DailyFactBundle
  -> 旧 module 退化为格式化、兼容或展示
```

## 6. DailyFactBundle module

### 6.1 Interface

第一期只保留一个主 interface：

```python
build_daily_fact_bundle(business_date)
```

不要第一期就做：

```python
build_for_owner()
build_for_workshop()
build_for_energy()
build_for_report()
build_for_dingtalk()
```

原因：

- 角色是视角，不是事实。
- 多入口会重新制造重复 facts。
- 一个小 interface 更容易测试。

### 6.2 输入

第一期主输入：

```text
business_date
```

后续可以增加可选输入，但不能改变事实包主键：

```text
requested_by
trace_id
include_dingtalk_supplement
include_root_owner_corrections
```

### 6.3 输出

建议输出结构：

```json
{
  "business_date": "2026-06-19",
  "status": "ready | partial | blocked",
  "facts": {
    "total_output_daily": {
      "value": 366.0,
      "unit": "吨",
      "source": "root_owner_correction",
      "confidence": 1.0,
      "freshness": "confirmed",
      "adoption_reason": "root_owner 钉钉确认"
    }
  },
  "sources": {},
  "missing": [],
  "conflicts": [],
  "freshness": {},
  "confidence": {},
  "correction_refs": [],
  "dingtalk_refs": [],
  "output_skill_alignment": {}
}
```

小白版理解：

> 每个数字都要说清楚：这个数是多少、单位是什么、从哪里来、为什么采用它、有没有冲突。

## 7. 事实优先级

日报事实包按下面顺序采用事实：

| 优先级 | 来源 | 说明 |
|---:|---|---|
| 1 | root_owner 修正事实 | 张兆嘉直接确认或修改，最高优先级 |
| 2 | 钉钉补充数据 | 授权人员发送的文本、文件、图片或确认意见 |
| 3 | MES/WMS | 生产、入库、库存、在制等原始事实 |
| 4 | 数据中枢人工填报 | 能耗、说明、异常、人工确认 |
| 5 | 数据中枢计算值 | 成品率、吨耗、成本等衍生指标 |
| 6 | 历史日报 | 前日、月累计、历史参考 |
| 7 | RAG | 只解释口径、规则、模板，不当每日数字真相 |
| 8 | 输出 skill | 只做验收对齐，不反向写成生产事实 |

### 7.1 钉钉补充数据冲突规则

钉钉补充数据优先级高，但不能无痕覆盖。

当钉钉与 MES/WMS 冲突时：

- 可以采用钉钉补充数据。
- 必须记录发送人、时间、原文或文件。
- 必须记录被覆盖的来源和值。
- 必须记录采用原因。
- 必须把冲突字段写进事实包。

Hermes 可以这样表达：

```text
本次采用钉钉补充数据，MES/WMS 作为冲突来源保留。
```

### 7.2 root_owner 修正事实规则

张兆嘉可以直接修改事实。

默认交互：

```text
张兆嘉：6月19日车间总产量改成366吨，按这个发日报。

Hermes：收到 root_owner 修正事实：
业务日：2026-06-19
字段：车间总产量
改后值：366 吨
原来源：当前事实包/MES/WMS
采用原因：root_owner 钉钉确认
是否立即用于本次日报？
```

如果张兆嘉明确说：

```text
不用确认，直接执行。
```

Hermes 可以免确认执行。

但必须保留：

- 谁改的。
- 什么时候改的。
- 改哪个字段。
- 改前值。
- 改后值。
- 原始来源。
- 修正原因。
- trace_id。

禁止：

- 无痕改数。
- 改 MES/WMS 原库。
- 删除原始证据。
- 让审计链看不出改过。

## 8. 第一期字段范围

第一期只覆盖日报必需字段。

进入范围：

- 产量。
- 月累计。
- 各车间明细。
- 在制料。
- 用电。
- 用气。
- 吨耗。
- 入库。
- 合同。
- 投料。
- 成品率。
- 成本核算。
- 钉钉补充数据。
- root_owner 修正事实。
- 来源、缺失、冲突、可信度。

不进入第一期：

- 全部卷级明细。
- 全部设备状态。
- 全部考勤明细。
- 全部库存流水。
- 全部质量缺陷记录。

这些以后作为下钻数据，不作为事实包本体。

## 9. Hermes 自然语言意图

### 9.1 规则 + LLM 混合

第一版采用：

```text
规则 + LLM 混合意图理解
```

规则负责稳定场景：

- 日期。
- 日报。
- 查来源。
- 修正事实。
- 发送。
- 角色视角。

LLM 负责模糊表达：

- 用户说得不标准。
- 句子夹带上下文。
- 问“怎么回事”。
- 要求解释异常。
- 多句话里混合了事实和指令。

### 9.2 执行前必须结构化

LLM 不能直接写库。

它只能输出结构化任务：

```json
{
  "intent": "daily_report",
  "business_date": "2026-06-19",
  "audience": "root_owner",
  "mode": "final",
  "requested_corrections": [],
  "evidence_policy": "include_dingtalk_supplement"
}
```

结构化任务必须通过校验后，才能进入 `HermesBrainRun`。

如果不确定，要追问：

```text
你是要重生成日报，还是要把这个数作为 root_owner 修正事实？
```

## 10. 入库和体积优化

### 10.1 两层入库

不要每次页面刷新都保存完整 JSON。

第一层：事实包运行记录。

保存：

- business_date。
- requested_by。
- requested_at。
- source_status。
- missing_count。
- conflict_count。
- confidence。
- trace_id。

第二层：事实包完整快照。

只有这些场景保存完整快照：

- 正式日报。
- root_owner 修正。
- 钉钉发送。
- 输出 skill 对齐。
- Harness 评测。

完整快照保存：

- facts。
- sources。
- conflicts。
- adopted_values。
- correction_refs。
- dingtalk_refs。
- output_skill_alignment。

小白版理解：

> 普通查看只记“查过一次”；正式出报告才保存“当时用的那一版证据”。

### 10.2 数据中枢减法

先减报表加工层，不先动采集层。

第一期退到事实包后面的能力：

| 能力 | 减法方式 |
|---|---|
| 日报生成 | 从事实包取 facts，只负责渲染 |
| 今日/昨日管理页 | 读取事实包视角，不各自拼 facts |
| Hermes Day-1 | 先拿事实包，再判断输出 |
| 输出 skill 对齐 | 成为事实包验收项 |

暂时不动：

- 手机填报。
- MES 同步。
- WMS 同步。
- 权限系统。
- 主数据维护。

通俗说：

```text
先统一水源，再拆旧水管。
```

## 11. 和现有代码的关系

### 11.1 复用现有能力

不从零重写。

复用：

- `template_daily_report`：现有日报模板和字段渲染经验。
- `template_daily_fact_sources`：现有日报事实来源。
- `mes_fact_bundle`：MES/WMS 事实映射。
- `HermesMesReadService`：MES 只读能力。
- `HermesDataAuditService`：数据审计和冲突检测。
- `hermes_day1_source_service`：Day-1 多源收集经验。
- `output_skill_reconciliation`：输出 skill 对齐能力。
- `hermes_day1_harness_service`：Harness 评测。
- `dingtalk` 入站和 Agent 通讯表。

### 11.2 新增建议 module

建议新增：

```text
backend/app/services/report/daily_fact_bundle.py
```

建议职责：

- 统一事实包 interface。
- 调用现有事实来源。
- 处理优先级。
- 处理 root_owner 修正事实。
- 处理钉钉补充数据。
- 生成 missing/conflicts/confidence。
- 输出可序列化 facts。

不要让它负责：

- 钉钉外发。
- 日报文案。
- 页面排版。
- LLM 提示词。

### 11.3 后续建议 module

后续再新增：

```text
backend/app/services/hermes_intent_service.py
backend/app/services/hermes_brain_run_service.py
backend/app/services/agent_delivery_service.py
```

但第一步先做 `DailyFactBundle`。

原因：

> Hermes 的聪明程度受事实层限制。事实层不稳，LLM 越灵活越容易乱。

## 12. 验收标准

### 12.1 事实包验收

给定 `2026-06-19`：

- 能生成一套日报事实包。
- 能包含日报必需字段。
- 能指出缺失字段。
- 能指出冲突字段。
- 能显示每个字段来源。
- 能采用 root_owner 修正事实。
- 能采用钉钉补充数据。
- 能保留 MES/WMS 冲突来源。
- 能输出可供 Hermes 使用的结构化结果。

### 12.2 Hermes 验收

Hermes 应能理解：

```text
6月19日按最终口径重新来一版。
6月19日车间总产量改成366吨，直接按这个发。
这个钉钉文件以后作为日报补充数据。
为什么2050吨耗这么高？
```

并转成结构化任务。

### 12.3 输出 skill 对齐

使用 `D:\输出skill` 或生产 `/srv/aluminum-bypass/reference/output-skill` 中的日报正文：

- 字段匹配率达到设定阈值。
- 差异字段必须列出。
- 低于阈值时不能写“已对齐”。
- 缺样本时不能 500，要明确提示缺少输出 skill。

### 12.4 体积优化验收

- 普通查询只写轻量运行记录。
- 正式日报才写完整快照。
- 快照中不保存密钥、连接串、token。
- 大型原始文件只保存引用、哈希和解析结果，不把文件内容重复塞进数据库。

## 13. 不进入本期

本期不做：

- 全厂数据湖。
- 任意 SQL 自由执行。
- 自动修改 MES/WMS 原库。
- 前端大型新页面。
- 全角色自动分发。
- 全部 LangGraph/LangChain 框架替换。
- 删除旧报表代码。
- 删除手机填报链路。

本期可以预留：

- LangGraph 状态图接口。
- LangChain 工具注册接口。
- ReAct 观察记录。
- 事实包版本和快照表。

## 14. 推荐落地顺序

### Phase 2.1：事实包骨架

- 新增 `daily_fact_bundle.py`。
- 输出固定 schema。
- 接入现有 `template_daily_report` 和 `mes_fact_bundle`。
- 暂不改旧页面。

### Phase 2.2：优先级和冲突

- 接入 root_owner 修正事实。
- 接入钉钉补充数据。
- 实现 source priority。
- 输出 conflicts/adoption_reason。

### Phase 2.3：Hermes 接入

- `Hermes Day-1` 改为先拿事实包。
- `Hermes` 输出继续三段式日报。
- Harness 使用事实包结果评分。

### Phase 2.4：数据中枢减法

- 旧日报生成改为读事实包。
- 今日/昨日管理页改为读事实包视角。
- 输出 skill 对齐纳入事实包验收。
- 观察 7-14 天后删除重复取数逻辑。

### Phase 2.5：自然语言升级

- 新增混合意图理解。
- 规则先判定高置信意图。
- LLM 处理模糊表达。
- 结构化任务校验后再进入 HermesBrainRun。

## 15. 风险和处理

| 风险 | 处理 |
|---|---|
| 钉钉补充数据质量不稳定 | 必须记录发送人、来源、文件、哈希、采用原因 |
| root_owner 修正事实误操作 | 默认回显确认，明确直接执行才免确认 |
| 事实包过大 | 普通运行轻记录，正式输出才完整快照 |
| 旧页面口径被改坏 | 先新增事实包，不立即替换旧页面 |
| LLM 输出不稳定 | LLM 只做意图理解，最终必须结构化校验 |
| 输出 skill 缺样本 | 明确提示缺少样本，不阻断系统健康 |

## 16. 最终判断

`日报事实包` 是数据中枢做减法的第一刀。

它把报表、页面、Hermes、审计和输出 skill 对齐所需的事实统一起来。

Hermes 要成为工厂超级大脑，不能直接站在一堆散乱数据源上思考。它应该站在一个可信、可追责、可复查的事实包上思考。

一句话：

```text
数据中枢负责事实，Hermes 负责判断。
```

## 17. Implementation Status

Phase 2.1 implementation added the `DailyFactBundle` module, persistence models, source priority handling, root_owner corrections, DingTalk supplements, output skill alignment, Hermes Day-1 source integration, flexible intent parsing, traceable historical daily report archive, monthly and annual cumulative operation snapshots, monthly and annual operating situation analysis, and the professional Hermes knowledge layer.

Production rollout remains behind the existing Hermes Day-1 gate until focused tests, historical trace checks, period rollup checks, knowledge retrieval checks, and production doctor checks pass.
