# Hermes Day-1 Super Brain MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 张兆嘉在钉钉私聊 Hermes 一句话，Hermes 能主动查 MES、数据中枢、WMS、钉钉文本/文件、RAG、历史日报和输出 skill 样本，生成 root_owner 完整版三段式日报，并把证据、冲突和成长反馈发回钉钉。

**Architecture:** Day-1 直接落到生产服务层：钉钉入口识别 root_owner 和日报指令，Hermes 超级大脑服务用“感知、取数、推理、交付/学习”四层 engine 串起现有数据读取、日报模板、审计、RAG、记忆、Harness 和 outbox 能力，最后把三段式结果、证据、对齐分数和学习事件写回现有表。LangGraph/LangChain/ReAct 不先作为外部框架硬依赖，但必须在代码里落出等价的状态图、工具注册表和思考循环，后续能平滑替换成框架。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic not required for Day-1, pytest, existing DingTalk inbound route, existing `AgentRun` / `ChatInboxMessage` / `MultimodalEvidence` / `DailyReport` / `HermesLearningEvent`, existing `HermesMesReadService`, existing `HermesDataAuditService`, existing `template_daily_report`, existing `agent_cli.py`.

## Global Constraints

- 产品名称统一写 `鑫泰铝业 数据中枢` 或 `数据中枢`。不要把本系统叫 MES。
- MES 是外部生产系统，任何 Day-1 代码都只能只读 MES。
- WMS Day-1 先复用现有 SQL Server/WMS 表投影，例如 `WMS_InStock`、`WMS_InStockDetail`、`WMS_OutStockDetail`、`WMS_Stock`；`wms.xintaily.com` 直连等拿到稳定 API 或页面协议后再做 adapter。
- 不把数据库密码、token、cookie、连接串写入代码、日志、计划、测试快照或 RAG。
- RAG 只用于稳定知识、口径、模板、历史经验，不把 RAG 历史数字当今天最终事实。
- Day-1 只处理 root_owner 私聊和 root_owner 授权群/通道，不扫描全部钉钉群。
- Day-1 必须有独立开关，建议配置名为 `HERMES_DAY1_ENABLED`，默认关闭。
- Harness 不再只是测试 helper，必须进入生产服务层，用来记录每次日报的成熟度、真实值对齐分数和失败原因。
- `D:\输出skill` 里的 txt 每日日报是真实值参考源，只读读取，不修改，不提交原始内容到 Git。
- 三段式输出标题固定为：`工厂大脑判断单`、`正式日报正文`、`各车间明细`。
- 如果数据不足，Hermes 必须说清楚缺什么，不能编数字。
- 所有写动作必须留痕：`chat_inbox`、`agent_runs`、`daily_reports.report_data`、`multimodal_evidence`、`hermes_learning_events`、`audit_logs` 至少覆盖一处。
- 前端成长面板、完整多角色分发、7:30/9:35 定时发布、批量回滚界面不属于 Day-1。

---

## 0. 小白版执行图

这次不是给 Hermes 加一个“会聊天”的外壳，而是让它完成一条工厂大脑工作链：

```text
钉钉收到张兆嘉指令
  -> 确认这是最高权限者
  -> 看懂要生成哪一天日报
  -> 主动查已有数据和证据
  -> 找出缺失、冲突和风险
  -> 生成三段式日报
  -> 把本次证据、判断和成长反馈写入数据库
  -> 钉钉回复张兆嘉
```

实现上尽量少造新东西。现有系统已经有收消息、出消息、日报模板、MES 只读、RAG、记忆和审计能力；本计划把这些能力串起来。

---

## 0A. CEO Review 优化结论

本轮按 `plan-ceo-review` 视角复核后，采用 **SELECTIVE EXPANSION + HOLD SCOPE**：

```text
Day-1 目标不扩大
但把上线必需的门禁、可观测、回滚、错误登记补齐
```

通俗理解：不要第一版就做完整超级大脑平台，但也不能只做一个“能跑的 demo”。张兆嘉私聊触发三段式日报这条链路，必须能解释、能追踪、能失败可见、能回滚。

### 系统审计结论

| 审计项 | 结论 | 对本 plan 的影响 |
|---|---|---|
| 最近提交 | 近期集中在 Hermes 审计、MES/WMS、输出 skill 对齐 | Day-1 应复用这些能力，不另起数据链路 |
| 当前工作区 | 存在多处既有未提交改动和删除 | 实施时必须只暂存 Day-1 相关文件，不能 `git add -A` |
| TODO | 当前 `TODOS.md` 主要是低优先级前端/死代码清理 | Day-1 不依赖现有 TODO，不应顺手清理 |
| 高频文件 | `template_daily_report`、`agent_command_service`、`mapping_reconciliation_service`、`daily_overview_builder` 高频变动 | 这些是热区，实施必须小步提交和精确测试 |
| 计划复杂度 | 原计划新增 7 个生产/测试模块 | CEO Review 曾建议 5 个生产服务 + 1 个测试 helper；Eng Review 后改为生产 Harness 服务 |

### 实施方案对比

| 方案 | 内容 | 完整度 | 风险 | 结论 |
|---|---|---:|---|---|
| A. 最小补丁 | 只在 `agent_cli.py` 和 `dingtalk.py` 里拼接现有日报 | 5/10 | 快，但证据、审计、成长和失败路径散乱 | 不选 |
| B. 聚焦服务束 | 5 个 Day-1 服务串起现有底座，Harness 原建议不进生产 | 8.5/10 | 文件数可控，能形成上线闭环 | 已被 Eng Review 扩展 |
| C. 完整平台 | 直接落 LangGraph、LangChain 工具注册、前端面板、多角色分发 | 10/10 | 太大，会拖慢 root_owner 私聊闭环 | 后续阶段 |

CEO Review 当时推荐 B。原因是它最符合“先上线 root_owner 私聊闭环”的目标。

Eng Review 后，本计划按用户新要求升级：**Harness 进入生产服务层，Day-1 要能直接支撑超级大脑 agent 构建**。也就是说，仍不做前端成长面板和全厂自动分发，但后端服务层必须把状态图、工具注册、ReAct 思考循环、真实值对齐、学习反馈一次性设计完整。

### CEO Review 后的范围修正

接受进入本 plan：

- 合并 root_owner 权限判断和命令解析为 `backend/app/services/hermes_day1_intent_service.py`。
- Harness 升级为 `backend/app/services/hermes_day1_harness_service.py` 生产服务，用测试覆盖它。
- 增加 `HERMES_DAY1_ENABLED` 或等价配置门禁，默认关闭，生产验证通过后开启。
- 增加错误与失败模式登记表，禁止静默失败。
- 增加部署、回滚、首小时观测步骤。

仍然不进入 Day-1：

- 外部 LangGraph/LangChain 框架强依赖。
- 前端成长面板。
- 多角色自动分发。
- 直连 `wms.xintaily.com` 页面或未知接口。
- 数据中枢批量自动修正。

### 12 个月理想态

```text
当前状态
  数据中枢已有日报模板、MES/WMS 投影、RAG、审计和钉钉入口，但 Hermes 还没有形成 root_owner 私聊闭环
      ↓
Day-1 本计划
  Hermes 能从钉钉私聊触发，主动查证多源数据，生成三段式日报，并把证据、冲突、成长和审计留住
      ↓
12 个月理想态
  Hermes 成为工厂超级大脑：自动感知现场、解释异常、推动补录/修正、按角色分发、长期学习，且每一步可追责
```

---

## 0B. Eng Review 最终架构结论

本轮按 `plan-eng-review` 复核后，结论是：**完整建设生产服务层，先用确定性 Python 服务实现超级大脑骨架，再把 LangGraph/LangChain 作为可替换执行后端。**

通俗理解：先把“大脑的骨架、手脚、记忆、验收标准”做进系统，而不是只写一个能回复日报的脚本。这样 Hermes 后续要换成 LangGraph、接更多工具、做主动学习，都不用推翻 Day-1。

### 0B.1 Scope Challenge

| 检查项 | 工程判断 | 处理 |
|---|---|---|
| 现有能力能否复用 | 已有钉钉入口、Agent 收发、日报模板、MES 只读、输出 skill 解析、Hermes 审计、RAG、记忆 | 必须复用，禁止重建平行链路 |
| 文件数量是否过大 | 会超过 8 个文件、超过 2 个生产服务 | 用户明确要求完整方案和生产服务层，接受复杂度 |
| 最小可交付 | root_owner 私聊生成三段式日报并落库 | 仍保留为最小 smoke |
| 完整可交付 | 生产 service 层具备 state graph、tool registry、ReAct loop、Harness、真实值对齐 | 进入本 plan |
| 分发架构 | 没有新制品，不新增独立二进制/容器 | 沿用后端部署和现有云端发布流程 |
| TODO 交叉检查 | `TODOS.md` 当前是 P4 前端/死代码问题 | 不阻塞本 plan，不捆绑处理 |

### 0B.2 四层 Engine

```text
Hermes Super Brain
  1. Perception Engine 感知层
     - 钉钉私聊/授权群
     - 钉钉文本和文件元数据
     - CLI smoke
     - 历史日报和输出 skill 文件

  2. Data Engine 取数层
     - 数据中枢日报模板
     - MES SQL Server 只读
     - WMS 投影/只读数据
     - HermesDataAuditService
     - RAG 稳定知识
     - DailyReport 历史记录

  3. Reasoning Engine 推理层
     - 状态图
     - 工具注册表
     - ReAct 思考循环
     - 冲突、缺字段、风险、置信度判断

  4. Delivery & Learning Engine 交付/学习层
     - 三段式日报
     - Harness 成熟度评分
     - 输出 skill 真实值对齐分数
     - DailyReport / AgentRun / HermesLearningEvent / AuditLog
     - 钉钉回复 root_owner
```

### 0B.3 生产状态图

```text
received
  -> identified_actor
  -> parsed_intent
  -> planned_tools
  -> collected_sources
  -> reasoned_findings
  -> rendered_report
  -> aligned_with_output_skill
  -> scored_by_harness
  -> persisted
  -> replied

blocked:
  disabled
  unauthorized
  command_unrecognized
  source_failed_visible
  missing_required_facts
  output_skill_alignment_failed
  persistence_failed
```

### 0B.4 ReAct 循环

```text
Thought: 这份日报要用哪些数据证明？
Action: 调用 tool registry 中的一个只读工具
Observation: 得到数据、缺失、冲突或错误
Thought: 这份观察是否足够生成正式正文？
Action: 不足则继续查证，足够则生成判断单和日报
Final: 三段式日报 + 证据 + 对齐分数 + 学习事件
```

Day-1 不让大模型自由选择任意工具。工具必须来自白名单，且每次调用写入 `tool_trace`：

| 工具名 | 来源 | 写权限 | 作用 |
|---|---|---|---|
| `template_daily_report` | `backend/app/services/report/template_daily_report.py` | 无 | 生成数据中枢标准日报 facts |
| `mes_wms_read` | `HermesMesReadService` / WMS 投影 | MES 只读 | 读取生产、入库、库存、在制等原始事实 |
| `data_audit` | `HermesDataAuditService` | 写审计表 | 对比 MES、数据中枢、输出 skill |
| `dingtalk_evidence` | `agent_multimodal_evidence_service.py` | 写证据表 | 收集文本、文件、说明和指令 |
| `rag_context` | `query_knowledge()` / `HermesRagService` | 写查询日志 | 查稳定口径和模板说明 |
| `history_report` | `DailyReport` | 无 | 查前一天、月累计、历史最终版 |
| `output_skill_alignment` | `output_skill_report_parser.py` / `output_skill_reconciliation.py` | 无 | 和 `D:\输出skill` txt 真实日报对齐 |
| `harness_score` | `hermes_day1_harness_service.py` | 写运行结果 | 判断 Hermes 是否像工厂大脑 |

### 0B.5 What Already Exists

| 子问题 | 已有代码 | 是否复用 |
|---|---|---|
| 钉钉入站 | `backend/app/routers/dingtalk.py::dingtalk_agent_inbound` | 复用，在旧逻辑前插入 Day-1 分流 |
| Agent 收发记录 | `backend/app/services/agent_command_service.py`、`AgentRun`、`ChatInboxMessage` | 复用 |
| RAG | `backend/app/services/rag_service.py::query_knowledge` | 复用，只做稳定知识 |
| MES 只读 | `backend/app/services/hermes_mes_read_service.py` | 复用 |
| 审计和修正建议 | `backend/app/services/hermes_data_audit_service.py` | 复用，Day-1 默认 dry-run |
| 输出 skill 解析 | `backend/app/services/report/output_skill_report_parser.py` | 复用 |
| 输出 skill 对齐 | `backend/app/services/report/output_skill_reconciliation.py` | 复用并扩展到真实 txt |
| 数据映射审计 | `backend/app/services/mapping_reconciliation_service.py` | 复用字段/单位/别名思想 |
| 钉钉外发记录 | `backend/app/services/dingtalk_daily_report.py`、`external_message_logs` | 复用 |

### 0B.6 NOT In Scope

| 不做 | 原因 |
|---|---|
| 不写 MES | MES 是外部生产系统，Day-1 只读 |
| 不修改 `D:\输出skill` | 这是真实值基准，只读使用 |
| 不新增前端成长面板 | 本轮目标是后端超级大脑生产服务层 |
| 不做未知协议的 `wms.xintaily.com` 页面抓取 | 没有稳定 API/页面协议，先用现有 WMS 投影 |
| 不自动批量修正数据中枢原始数据 | Day-1 只给 dry-run 建议和审计证据 |
| 不全厂自动群发 | 先只回复最高权限者，后续再按钉钉权限分发 |

---

## 1. 当前代码结构映射

这些文件已经存在，实施时优先复用：

| 能力 | 文件 |
|---|---|
| 钉钉入站入口 | `backend/app/routers/dingtalk.py` |
| Hermes 兼容入口 | `backend/app/routers/hermes.py` |
| CLI 指令入口 | `backend/scripts/agent_cli.py` |
| Agent 收发记录模型 | `backend/app/models/agent_communication.py` |
| RAG/记忆模型 | `backend/app/models/rag.py` |
| 日报模型 | `backend/app/models/reports.py` |
| 审计日志模型 | `backend/app/models/system.py` |
| Agent 指令服务 | `backend/app/services/agent_command_service.py` |
| Agent outbox 服务 | `backend/app/services/agent_communication_service.py` |
| 钉钉文本/文件证据表服务 | `backend/app/services/agent_multimodal_evidence_service.py` |
| Hermes MES 只读服务 | `backend/app/services/hermes_mes_read_service.py` |
| Hermes 数据审计服务 | `backend/app/services/hermes_data_audit_service.py` |
| Hermes RAG 服务 | `backend/app/services/hermes_rag_service.py` |
| Hermes 短期记忆服务 | `backend/app/services/hermes_memory_service.py` |
| Hermes 工厂总控配置 | `backend/app/services/hermes_governance_service.py` |
| 正式日报模板 | `backend/app/services/report/template_daily_report.py` |
| 输出 skill 解析器 | `backend/app/services/report/output_skill_report_parser.py` |
| 输出 skill 对齐解析底座 | `backend/app/services/mapping_reconciliation_service.py` |

Day-1 新增文件：

| 新文件 | 用途 |
|---|---|
| `backend/app/services/hermes_day1_intent_service.py` | 判断 root_owner、授权通道和自然语言日报指令 |
| `backend/app/services/hermes_day1_evidence_service.py` | 分类和入库钉钉文本/文件证据 |
| `backend/app/services/hermes_day1_source_service.py` | 主动收集 MES、WMS、数据中枢、钉钉、RAG、历史日报、输出 skill 证据 |
| `backend/app/services/hermes_day1_report_service.py` | 生成三段式日报文本 |
| `backend/app/services/hermes_day1_orchestrator.py` | 串起 Day-1 全流程 |
| `backend/app/services/hermes_day1_harness_service.py` | 生产成熟度评分、真实日报对齐评分、工具调用覆盖检查 |

Day-1 不新增数据库表。理由很简单：现有表已经能承载第一版闭环，新增表会拖慢上线并增加迁移风险。

---

## 2. 数据落库规则

Day-1 的结果按下面方式落库：

| 内容 | 落库位置 |
|---|---|
| 钉钉原始指令 | `chat_inbox` |
| Hermes 单次运行 | `agent_runs` |
| 三段式完整文本 | `agent_runs.answer` |
| 证据摘要、冲突摘要、查证路径 | `agent_runs.result_payload["hermes_day1"]` |
| 正式日报正文 | `daily_reports.final_text_summary`，仅在模板状态 ready 时写 |
| 完整三段式产物 | `daily_reports.report_data["hermes_day1_super_brain"]` |
| 钉钉文本/文件证据 | `multimodal_evidence`，细节放 `payload` |
| 成长候选 | `hermes_learning_events` |
| root_owner 回复 | 钉钉回调响应；如果私聊 channel 已绑定，则同时写 `agent_outbox_messages` |
| 审计 | `audit_logs` |

小白版理解：不是每件事都新建一张表。能放在已有“收件箱、运行记录、日报、证据、学习、审计”里的，就放进去。

---

## 3. 实施任务

### Task 1: 写失败测试，锁住 Day-1 行为

先写测试，再写实现。这样不会做偏。

- [ ] 新增 `backend/tests/test_hermes_day1_intent_service.py`
- [ ] 新增 `backend/tests/test_hermes_day1_evidence_service.py`
- [ ] 新增 `backend/tests/test_hermes_day1_report_service.py`
- [ ] 新增 `backend/tests/test_hermes_day1_orchestrator.py`
- [ ] 新增 `backend/tests/test_hermes_day1_harness_service.py`
- [ ] 新增 `backend/tests/test_hermes_day1_output_skill_alignment.py`
- [ ] 扩展 `backend/tests/test_dingtalk_agent_inbound_route.py`
- [ ] 扩展 `backend/tests/test_agent_cli.py`

命令解析测试至少覆盖：

```python
from datetime import date

from app.services.hermes_day1_intent_service import parse_day1_command


def test_parse_day1_three_part_daily_report_command() -> None:
    command = parse_day1_command(
        "生成 6月19日 root_owner 完整版三段式日报",
        default_year=2026,
    )

    assert command is not None
    assert command.intent == "day1_daily_report"
    assert command.business_date == date(2026, 6, 19)
    assert command.audience == "root_owner"
    assert command.output_style == "three_part"


def test_parse_day1_ignores_general_chat() -> None:
    assert parse_day1_command("今天辛苦了", default_year=2026) is None
```

权限测试至少覆盖：

```python
from types import SimpleNamespace

from app.services.hermes_day1_intent_service import classify_day1_actor


def test_root_owner_uses_configured_dingtalk_identity(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.hermes_day1_intent_service.settings.hermes_owner_dingtalk_user_ids",
        {"dt-owner-001", "union-owner-001"},
    )
    user = SimpleNamespace(
        id=7,
        name="张兆嘉",
        dingtalk_user_id="dt-owner-001",
        dingtalk_union_id="union-owner-001",
        is_active=True,
    )

    result = classify_day1_actor(
        user,
        sender_user_id="dt-owner-001",
        sender_union_id="union-owner-001",
        channel="dingtalk_private",
        group_id=None,
    )

    assert result.is_root_owner is True
    assert result.allowed is True
    assert result.reason == "root_owner"
```

三段式测试至少覆盖：

```python
from app.services.hermes_day1_report_service import render_three_part_daily_report


def test_three_part_report_has_fixed_titles() -> None:
    text = render_three_part_daily_report(
        business_date_label="6月19日",
        formal_text="6月19日，车间总产量日合计366吨。",
        workshop_details=[{"title": "2050车间", "lines": ["日产量：80吨。"]}],
        judgment={
            "summary": "总产量上升，2050 吨电耗需要复核。",
            "risks": ["2050 吨电耗高于月均"],
            "missing_fields": [],
            "conflicts": [],
            "sources": ["数据中枢", "MES/WMS", "钉钉证据"],
            "actions": ["已生成日报"],
            "learning": "下次优先核对 2050 能耗异常说明。",
        },
    )

    assert "工厂大脑判断单" in text
    assert "正式日报正文" in text
    assert "各车间明细" in text
    assert text.index("工厂大脑判断单") < text.index("正式日报正文") < text.index("各车间明细")
```

验证：

```bash
python -m pytest backend/tests/test_hermes_day1_intent_service.py backend/tests/test_hermes_day1_report_service.py -q
```

预期：这些测试先失败，因为实现文件还不存在。

### Task 2: 实现 root_owner 和钉钉通道权限

新增 `backend/app/services/hermes_day1_intent_service.py`。

核心规则：

- root_owner 优先用钉钉 `user_id` 或 `union_id`。
- `HERMES_OWNER_DINGTALK_USER_IDS` 继续复用，里面可以填 staffId 或 unionId。
- `HERMES_ALLOWED_DINGTALK_USER_IDS` 只允许普通 Day-1 查询，不允许 root_owner 完整版日报。
- `HERMES_ALLOWED_GROUP_IDS` 只允许授权群做证据来源或普通查询。
- 非生产环境可以保留姓名 `张兆嘉` 的兜底，生产环境不能只靠姓名。

实现骨架：

```python
from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.models.system import User


@dataclass(frozen=True, slots=True)
class Day1ActorDecision:
    allowed: bool
    is_root_owner: bool
    reason: str
    conversation_key: str


def _clean(value: str | None) -> str:
    return str(value or "").strip()


def _identity_values(user: User | None, *, sender_user_id: str | None, sender_union_id: str | None) -> set[str]:
    return {
        item
        for item in (
            _clean(sender_user_id),
            _clean(sender_union_id),
            _clean(getattr(user, "dingtalk_user_id", None)),
            _clean(getattr(user, "dingtalk_union_id", None)),
        )
        if item
    }


def classify_day1_actor(
    user: User | None,
    *,
    sender_user_id: str | None,
    sender_union_id: str | None,
    channel: str,
    group_id: str | None,
) -> Day1ActorDecision:
    identities = _identity_values(user, sender_user_id=sender_user_id, sender_union_id=sender_union_id)
    owner_ids = set(settings.hermes_owner_dingtalk_user_ids)
    allowed_ids = set(settings.hermes_allowed_dingtalk_user_ids)
    allowed_groups = set(settings.hermes_allowed_group_ids)
    clean_channel = _clean(channel) or "dingtalk_group"
    clean_group_id = _clean(group_id)

    is_owner = bool(owner_ids & identities)
    if not is_owner and not settings.is_production_like and _clean(getattr(user, "name", None)) == "张兆嘉":
        is_owner = True

    if is_owner:
        return Day1ActorDecision(
            allowed=True,
            is_root_owner=True,
            reason="root_owner",
            conversation_key=clean_group_id or f"user:{getattr(user, 'id', 'unknown')}",
        )

    if clean_group_id and clean_group_id in allowed_groups:
        return Day1ActorDecision(
            allowed=True,
            is_root_owner=False,
            reason="authorized_group",
            conversation_key=clean_group_id,
        )

    if allowed_ids & identities:
        return Day1ActorDecision(
            allowed=True,
            is_root_owner=False,
            reason="authorized_user",
            conversation_key=clean_group_id or f"user:{getattr(user, 'id', 'unknown')}",
        )

    return Day1ActorDecision(
        allowed=False,
        is_root_owner=False,
        reason="not_authorized",
        conversation_key=clean_group_id or "unknown",
    )


def require_root_owner_for_day1_report(decision: Day1ActorDecision) -> None:
    if not decision.allowed:
        raise PermissionError(decision.reason)
    if not decision.is_root_owner:
        raise PermissionError("root_owner_required")
```

更新 `backend/app/services/hermes_governance_service.py`：

- `ensure_factory_controller_profile()` 的 `config_payload` 中把 Day-1 能力写清楚。
- 不把 root_owner 的真实手机号、密码、截图信息写进去。

更新 `backend/app/config.py`：

- 新增 `HERMES_DAY1_ENABLED: bool = False`。
- 新增只读属性 `hermes_day1_enabled`，统一返回布尔值。
- `dingtalk.py` 和 `agent_cli.py` 调 Day-1 前必须先检查这个开关。

示例配置：

```python
"day1_super_brain": {
    "enabled": True,
    "root_owner_required": True,
    "private_dingtalk_entry": True,
    "three_part_daily_report": True,
    "mes_original_read_only": True,
    "rag_not_realtime_fact_source": True,
}
```

验证：

```bash
python -m pytest backend/tests/test_hermes_day1_intent_service.py backend/tests/test_hermes_governance_service.py -q
```

### Task 3: 实现自然语言日报指令解析

新增 `backend/app/services/hermes_day1_intent_service.py`。

Day-1 至少识别这些输入：

- `生成 6月19日 root_owner 完整版三段式日报`
- `生成 6月19日正式日报`
- `/日报 2026-06-19`
- `生成 2026-06-19 日报`

实现骨架：

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re


@dataclass(frozen=True, slots=True)
class HermesDay1Command:
    intent: str
    business_date: date
    audience: str
    output_style: str
    raw_text: str


_ISO_DATE_RE = re.compile(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})")
_CN_MONTH_DAY_RE = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日")


def parse_day1_command(text: str, *, default_year: int) -> HermesDay1Command | None:
    clean = str(text or "").strip()
    if clean.startswith("/"):
        clean = clean[1:].strip()
    if not clean:
        return None

    if "日报" not in clean:
        return None
    if not any(keyword in clean for keyword in ("生成", "日报", "正式日报", "三段式")):
        return None

    business_date = _parse_business_date(clean, default_year=default_year)
    if business_date is None:
        return None

    return HermesDay1Command(
        intent="day1_daily_report",
        business_date=business_date,
        audience="root_owner" if "root_owner" in clean or "完整版" in clean else "root_owner",
        output_style="three_part",
        raw_text=clean,
    )


def _parse_business_date(text: str, *, default_year: int) -> date | None:
    iso_match = _ISO_DATE_RE.search(text)
    if iso_match:
        return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))

    cn_match = _CN_MONTH_DAY_RE.search(text)
    if cn_match:
        return date(default_year, int(cn_match.group(1)), int(cn_match.group(2)))

    return None
```

验证：

```bash
python -m pytest backend/tests/test_hermes_day1_intent_service.py -q
```

### Task 4: 实现钉钉文本/文件证据分类和入库

新增 `backend/app/services/hermes_day1_evidence_service.py`。

Day-1 证据类型：

| 类型 | 代码值 | 说明 |
|---|---|---|
| 事实型文件/文本 | `fact` | 产量、库存、发货、入库、能耗、成品率、成本等 |
| 解释型文本 | `explanation` | 停机原因、异常说明、为什么某车间低产 |
| 指令型文本 | `instruction` | 以这个为准、补录、修改、重发 |
| 噪声 | `noise` | 闲聊、表情、无业务关键词 |

实现骨架：

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.redaction import filter_sensitive_mapping
from app.models.agent_communication import MultimodalEvidence
from app.models.system import User
from app.services.agent_multimodal_evidence_service import record_evidence


FACT_KEYWORDS = ("日报", "产量", "每日产量", "库存", "发货", "入库", "在制", "电耗", "气耗", "成品率", "成本")
EXPLANATION_KEYWORDS = ("异常", "停机", "原因", "影响", "维修", "换辊", "故障")
INSTRUCTION_KEYWORDS = ("补录", "重发", "以这个为准", "改成", "修正", "替换")


@dataclass(frozen=True, slots=True)
class Day1EvidenceClassification:
    evidence_kind: str
    evidence_grade: str
    include_in_daily_sample: bool
    matched_keywords: list[str]


def classify_dingtalk_evidence(text: str, *, file_name: str | None = None) -> Day1EvidenceClassification:
    clean = str(text or "")
    haystack = f"{file_name or ''} {clean}"
    matched = [keyword for keyword in (*FACT_KEYWORDS, *EXPLANATION_KEYWORDS, *INSTRUCTION_KEYWORDS) if keyword in haystack]
    if any(keyword in haystack for keyword in INSTRUCTION_KEYWORDS):
        return Day1EvidenceClassification("instruction", "high", True, matched)
    if any(keyword in haystack for keyword in EXPLANATION_KEYWORDS):
        return Day1EvidenceClassification("explanation", "medium", True, matched)
    if any(keyword in haystack for keyword in FACT_KEYWORDS):
        return Day1EvidenceClassification("fact", "high", True, matched)
    return Day1EvidenceClassification("noise", "low", False, matched)


def record_day1_dingtalk_evidence(
    db: Session,
    *,
    payload: dict[str, Any],
    actor: User | None,
    business_date: date | None,
    channel: str,
    group_id: str | None,
    trace_id: str,
    recognized_text: str,
) -> MultimodalEvidence | None:
    file_name = str(payload.get("fileName") or payload.get("file_name") or "").strip() or None
    classification = classify_dingtalk_evidence(recognized_text, file_name=file_name)
    if classification.evidence_kind == "noise":
        return None

    raw_file_id = str(payload.get("mediaId") or payload.get("fileId") or payload.get("file_id") or "").strip()
    file_hash = hashlib.sha1(raw_file_id.encode("utf-8")).hexdigest() if raw_file_id else None
    evidence_type = "attachment" if file_name or raw_file_id else "text"

    return record_evidence(
        db,
        evidence_type=evidence_type,
        file_uri=f"dingtalk://media/{raw_file_id}" if raw_file_id else None,
        source_user_id=getattr(actor, "id", None),
        recognized_text=recognized_text,
        confirmation_status="machine_only",
        payload=filter_sensitive_mapping(
            {
                "source": "dingtalk",
                "day1_super_brain": True,
                "channel": channel,
                "group_id": group_id,
                "trace_id": trace_id,
                "business_date": business_date.isoformat() if business_date else None,
                "file_name": file_name,
                "file_hash": file_hash,
                "parse_status": "text_captured",
                "evidence_kind": classification.evidence_kind,
                "evidence_grade": classification.evidence_grade,
                "include_in_daily_sample": classification.include_in_daily_sample,
                "matched_keywords": classification.matched_keywords,
            }
        ),
        commit=False,
    )
```

注意：`record_evidence()` 当前会 `commit()`。在 orchestrator 里调用时要接受这一点，或者先把服务改成支持 `commit=False`。更小改法是新增可选参数：

```python
def record_evidence(..., commit: bool = True) -> MultimodalEvidence:
    ...
    db.add(evidence)
    if commit:
        db.commit()
        db.refresh(evidence)
    else:
        db.flush()
    return evidence
```

同时更新已有调用，默认行为不变。

验证：

```bash
python -m pytest backend/tests/test_hermes_day1_evidence_service.py backend/tests/test_agent_multimodal_evidence_service.py -q
```

### Task 5: 实现 Day-1 多源收集服务

新增 `backend/app/services/hermes_day1_source_service.py`。

它负责把 Hermes 要查的东西一次收齐，返回统一结构。

数据源：

- 数据中枢：`template_daily_report.build_template_daily_report_payload()`
- MES/WMS：`HermesMesReadService(get_mes_adapter()).read_sources()`
- 数据审计：`HermesDataAuditService.create_run()`
- 钉钉证据：`MultimodalEvidence` 和 `ChatInboxMessage`
- RAG：`query_knowledge()`
- 历史日报：`DailyReport`
- 输出 skill：通过 `HermesDataAuditService` 的 `output_skill_snapshot`

实现骨架：

```python
from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.adapters import get_mes_adapter
from app.core.redaction import redact_secret_text
from app.models.agent_communication import ChatInboxMessage, MultimodalEvidence
from app.models.reports import DailyReport
from app.models.system import User
from app.services.hermes_data_audit_service import DEFAULT_AUDIT_FIELDS, HermesDataAuditService
from app.services.hermes_mes_read_service import HermesMesReadService
from app.services.rag_service import query_knowledge
from app.services.report import template_daily_report


DAY1_MES_QUERY_KEYS = (
    "workshop_process_records",
    "stock_records",
    "finished_inbound_records",
    "delivery_records",
    "material_records",
    "yield_records",
    "wip_totals",
)


def collect_day1_sources(
    db: Session,
    *,
    business_date: date,
    actor: User | None,
    trace_id: str,
) -> dict[str, Any]:
    template_payload = template_daily_report.build_template_daily_report_payload(db, target_date=business_date)
    mes_reader = HermesMesReadService(get_mes_adapter())
    mes_payload = mes_reader.read_sources(
        business_date=business_date,
        query_keys=DAY1_MES_QUERY_KEYS,
    )
    audit_payload = _create_audit_payload(
        db,
        business_date=business_date,
        actor=actor,
        mes_reader=mes_reader,
        template_payload=template_payload,
    )
    rag_payload = query_knowledge(
        db,
        query=f"{business_date.isoformat()} 日报 模板 WMS_InStock MES 路线 数据来源",
        limit=5,
        user=actor,
    )

    return {
        "trace_id": trace_id,
        "business_date": business_date.isoformat(),
        "template_daily_report": template_payload,
        "mes_wms": mes_payload,
        "audit_run": audit_payload,
        "dingtalk_evidence": _list_dingtalk_evidence(db, business_date=business_date),
        "historical_reports": _list_historical_reports(db, business_date=business_date),
        "rag": {
            "answer": rag_payload.get("answer"),
            "citations": rag_payload.get("citations") or [],
        },
    }


def _build_hub_snapshot_reader(template_payload: dict[str, Any]):
    values = dict((template_payload.get("facts") or {}).get("values") or {})

    def _reader(_business_date: date, fields: Sequence[str]) -> dict[str, Any]:
        return {field: values.get(field) for field in fields if field in values}

    return _reader


def _audit_run_payload(run) -> dict[str, Any]:
    return {
        "id": run.id,
        "status": run.status,
        "match_rate": float(run.match_rate) if run.match_rate is not None else None,
        "source_status": run.source_status,
        "source_errors": run.source_errors,
        "diffs": run.diffs,
        "suggested_actions": run.suggested_actions,
    }


def _create_audit_payload(
    db: Session,
    *,
    business_date: date,
    actor: User | None,
    mes_reader: HermesMesReadService,
    template_payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        run = HermesDataAuditService(
            db,
            mes_read_service=mes_reader,
            hub_snapshot_reader=_build_hub_snapshot_reader(template_payload),
        ).create_run(
            business_date=business_date,
            fields=DEFAULT_AUDIT_FIELDS,
            mes_query_keys=DAY1_MES_QUERY_KEYS,
            created_by_id=getattr(actor, "id", None),
        )
        return _audit_run_payload(run)
    except Exception as exc:
        return {
            "id": None,
            "status": "failed",
            "match_rate": None,
            "source_status": {"audit": "failed"},
            "source_errors": {"audit": redact_secret_text(str(exc))},
            "diffs": [],
            "suggested_actions": [],
        }


def _list_dingtalk_evidence(db: Session, *, business_date: date) -> list[dict[str, Any]]:
    business_date_text = business_date.isoformat()
    rows = (
        db.query(MultimodalEvidence)
        .filter(MultimodalEvidence.payload.is_not(None))
        .order_by(MultimodalEvidence.id.desc())
        .limit(200)
        .all()
    )
    result = []
    for row in rows:
        payload = dict(row.payload or {})
        if payload.get("business_date") != business_date_text:
            continue
        if not payload.get("include_in_daily_sample"):
            continue
        result.append(
            {
                "id": row.id,
                "evidence_type": row.evidence_type,
                "recognized_text": row.recognized_text,
                "payload": payload,
            }
        )
    return result


def _list_historical_reports(db: Session, *, business_date: date) -> list[dict[str, Any]]:
    rows = (
        db.query(DailyReport)
        .filter(DailyReport.report_type == "production")
        .filter(DailyReport.report_date <= business_date)
        .order_by(DailyReport.report_date.desc(), DailyReport.id.desc())
        .limit(7)
        .all()
    )
    return [
        {
            "id": row.id,
            "report_date": row.report_date.isoformat(),
            "status": row.status,
            "quality_gate_status": row.quality_gate_status,
            "has_final_text": bool(row.final_text_summary),
        }
        for row in rows
    ]
```

实现注意：

- `HermesDataAuditService.create_run()` 会提交事务；测试里要用独立 SQLite session。
- `OUTPUT_SKILL_ROOT` 环境变量如果没配，输出 skill 状态应是 `missing`，不能 500。
- MES adapter 如果是 null，MES/WMS 状态应是 `failed` 或 `empty`，不能编造成 ok。

验证：

```bash
python -m pytest backend/tests/test_hermes_day1_orchestrator.py backend/tests/test_hermes_data_audit_service.py backend/tests/test_hermes_mes_read_service.py -q
```

### Task 6: 实现三段式日报生成器

新增 `backend/app/services/hermes_day1_report_service.py`。

输入：Task 5 的 `sources`。

输出：

```python
{
    "status": "ready" | "blocked",
    "text": "...三段式完整文本...",
    "formal_text": "...正式日报正文...",
    "brain_judgment": {...},
    "workshop_details": [...],
    "missing_fields": [...],
    "conflicts": [...],
}
```

实现骨架：

```python
from __future__ import annotations

from datetime import date
from typing import Any


WORKSHOP_DETAIL_SPECS = (
    ("铸轧分厂", "cast_roll"),
    ("铸锭车间", "foundry"),
    ("热轧车间", "hot_roll"),
    ("1650车间", "cold_1650"),
    ("1850车间", "cold_1850"),
    ("2050车间", "cold_2050"),
    ("在线退火", "online_anneal"),
    ("拉矫", "straightening"),
    ("精整车间", "finishing"),
    ("剪切车间", "shearing"),
    ("彩涂车间", "coating"),
    ("回收车间", "recovery"),
)


def build_day1_three_part_report(*, business_date: date, sources: dict[str, Any]) -> dict[str, Any]:
    template_payload = dict(sources.get("template_daily_report") or {})
    facts = dict(template_payload.get("facts") or {})
    values = dict(facts.get("values") or {})
    missing_fields = list(template_payload.get("missing_fields") or [])
    conflicts = _collect_conflicts(sources)
    formal_text = str(template_payload.get("text") or "").strip()
    status = "ready" if template_payload.get("status") == "ready" and formal_text else "blocked"

    brain_judgment = _build_brain_judgment(
        business_date=business_date,
        sources=sources,
        missing_fields=missing_fields,
        conflicts=conflicts,
        status=status,
    )
    workshop_details = _build_workshop_details(values=values, sources=dict(facts.get("sources") or {}))
    text = render_three_part_daily_report(
        business_date_label=f"{business_date.month}月{business_date.day}日",
        formal_text=formal_text if formal_text else "当前关键字段缺失，Hermes 未生成正式日报正文；请先补齐缺失字段后重跑。",
        workshop_details=workshop_details,
        judgment=brain_judgment,
    )

    return {
        "status": status,
        "text": text,
        "formal_text": formal_text,
        "brain_judgment": brain_judgment,
        "workshop_details": workshop_details,
        "missing_fields": missing_fields,
        "conflicts": conflicts,
    }


def render_three_part_daily_report(
    *,
    business_date_label: str,
    formal_text: str,
    workshop_details: list[dict[str, Any]],
    judgment: dict[str, Any],
) -> str:
    return "\n\n".join(
        [
            "工厂大脑判断单\n" + _render_brain_judgment(judgment),
            "正式日报正文\n" + formal_text.strip(),
            "各车间明细\n" + _render_workshop_details(workshop_details),
        ]
    )


def _build_brain_judgment(
    *,
    business_date: date,
    sources: dict[str, Any],
    missing_fields: list[str],
    conflicts: list[dict[str, Any]],
    status: str,
) -> dict[str, Any]:
    audit = dict(sources.get("audit_run") or {})
    source_status = dict(audit.get("source_status") or {})
    risks = []
    if missing_fields:
        risks.append(f"缺失字段 {len(missing_fields)} 个")
    if conflicts:
        risks.append(f"发现冲突 {len(conflicts)} 条")
    if source_status.get("mes") in {"failed", "partial_failed"}:
        risks.append("MES/WMS 读取不完整")
    return {
        "summary": f"{business_date.month}月{business_date.day}日日报状态：{status}",
        "risks": risks,
        "missing_fields": missing_fields,
        "conflicts": conflicts,
        "sources": ["数据中枢", "MES/WMS", "钉钉证据", "RAG", "历史日报", "输出 skill"],
        "actions": ["已生成三段式日报" if status == "ready" else "已阻断正式正文并列出缺失字段"],
        "learning": "本次查证路径已记录为学习候选。",
    }
```

`_build_workshop_details()` 要从 `template_daily_report` 的 `values` 里取字段，不直接从 RAG 取数字。

示例字段拼接：

```python
def _build_workshop_details(*, values: dict[str, Any], sources: dict[str, Any]) -> list[dict[str, Any]]:
    details = []
    for title, prefix in WORKSHOP_DETAIL_SPECS:
        lines = [
            f"日产量：{_display(values.get(f'{prefix}_daily'), '吨')}，月累计：{_display(values.get(f'{prefix}_month'), '吨')}。",
            f"日吨电耗：{_display(values.get(f'{prefix}_electricity_per_ton_daily'), '度')}，月吨电耗：{_display(values.get(f'{prefix}_electricity_per_ton_month'), '度')}。",
        ]
        gas_daily = values.get(f"{prefix}_gas_per_ton_daily")
        gas_month = values.get(f"{prefix}_gas_per_ton_month")
        if gas_daily is not None or gas_month is not None:
            lines.append(f"日吨气耗：{_display(gas_daily, 'm³')}，月吨气耗：{_display(gas_month, 'm³')}。")
        source_keys = [key for key in values.keys() if key.startswith(prefix)]
        source_types = sorted({str((sources.get(key) or {}).get("source_type")) for key in source_keys if sources.get(key)})
        lines.append(f"数据来源：{('、'.join(source_types) if source_types else '暂无明确来源')}。")
        lines.append("Hermes判断：已纳入全厂日报核验。")
        details.append({"title": title, "lines": lines})
    return details
```

验证：

```bash
python -m pytest backend/tests/test_hermes_day1_report_service.py backend/tests/test_template_daily_report.py -q
```

### Task 7: 实现 Day-1 Orchestrator

新增 `backend/app/services/hermes_day1_orchestrator.py`。

它是 Day-1 的主入口，负责：

- 接收结构化命令。
- 调用多源收集服务。
- 调用三段式生成器。
- 写 `AgentRun`。
- 写 `DailyReport`。
- 写成长候选。
- 写审计日志。
- 返回钉钉可回复文本。

实现骨架：

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.reports import DailyReport
from app.models.system import User
from app.services.audit_service import log_action
from app.services.hermes_day1_intent_service import HermesDay1Command
from app.services.hermes_day1_report_service import build_day1_three_part_report
from app.services.hermes_day1_source_service import collect_day1_sources
from app.services.hermes_governance_service import FACTORY_PROFILE_CODE
from app.services import hermes_memory_service, hermes_rag_service


@dataclass(frozen=True, slots=True)
class HermesDay1Result:
    trace_id: str
    status: str
    answer: str
    agent_run_id: int
    report_id: int
    payload: dict[str, Any]


def run_day1_super_brain(
    db: Session,
    *,
    command: HermesDay1Command,
    actor: User,
    trace_id: str,
    chat_inbox: ChatInboxMessage | None = None,
) -> HermesDay1Result:
    sources = collect_day1_sources(
        db,
        business_date=command.business_date,
        actor=actor,
        trace_id=trace_id,
    )
    product = build_day1_three_part_report(
        business_date=command.business_date,
        sources=sources,
    )
    report = _upsert_daily_report(
        db,
        command=command,
        actor=actor,
        product=product,
        sources=sources,
    )
    run = AgentRun(
        trace_id=trace_id,
        agent_code=FACTORY_PROFILE_CODE,
        chat_inbox_id=getattr(chat_inbox, "id", None),
        status="answered" if product["status"] == "ready" else "blocked",
        status_color="green" if product["status"] == "ready" else "yellow",
        answer=product["text"],
        rag_citation_count=len((sources.get("rag") or {}).get("citations") or []),
        result_payload={
            "hermes_day1": {
                "command": {
                    "intent": command.intent,
                    "business_date": command.business_date.isoformat(),
                    "audience": command.audience,
                    "output_style": command.output_style,
                },
                "status": product["status"],
                "report_id": report.id,
                "sources": sources,
                "missing_fields": product["missing_fields"],
                "conflicts": product["conflicts"],
                "brain_judgment": product["brain_judgment"],
            }
        },
    )
    db.add(run)
    db.flush()

    hermes_memory_service.remember_short_term(
        db,
        conversation_key=f"user:{actor.id}",
        memory_key="last_day1_super_brain_report",
        memory_value={
            "business_date": command.business_date.isoformat(),
            "status": product["status"],
            "report_id": report.id,
            "agent_run_id": run.id,
        },
        actor=actor,
        trace_id=trace_id,
    )
    hermes_rag_service.record_learning_event(
        db,
        question=command.raw_text,
        answer=_growth_feedback_text(command=command, product=product),
        trace_id=trace_id,
        tools_called=["collect_day1_sources", "build_day1_three_part_report"],
        sources=_learning_sources(sources),
        actor=actor,
    )
    log_action(
        db,
        user_id=actor.id,
        user_name=actor.name,
        action="hermes_day1_super_brain_report",
        module="hermes",
        table_name="daily_reports",
        record_id=report.id,
        old_value=None,
        new_value={
            "trace_id": trace_id,
            "status": product["status"],
            "business_date": command.business_date.isoformat(),
        },
        reason="root_owner 触发 Hermes Day-1 Super Brain MVP",
    )
    db.flush()
    return HermesDay1Result(
        trace_id=trace_id,
        status=product["status"],
        answer=product["text"] + "\n\n" + _growth_feedback_text(command=command, product=product),
        agent_run_id=run.id,
        report_id=report.id,
        payload=run.result_payload,
    )
```

`_upsert_daily_report()` 规则：

```python
def _upsert_daily_report(
    db: Session,
    *,
    command: HermesDay1Command,
    actor: User,
    product: dict[str, Any],
    sources: dict[str, Any],
) -> DailyReport:
    report = (
        db.query(DailyReport)
        .filter(
            DailyReport.report_date == command.business_date,
            DailyReport.report_type == "production",
        )
        .one_or_none()
    )
    if report is None:
        report = DailyReport(
            report_date=command.business_date,
            report_type="production",
            generated_scope="hermes_day1",
            output_mode="text",
            status="draft",
        )
        db.add(report)
        db.flush()

    report_data = dict(report.report_data or {})
    report_data["hermes_day1_super_brain"] = {
        "status": product["status"],
        "three_part_text": product["text"],
        "brain_judgment": product["brain_judgment"],
        "workshop_details": product["workshop_details"],
        "missing_fields": product["missing_fields"],
        "conflicts": product["conflicts"],
        "source_status": (sources.get("audit_run") or {}).get("source_status"),
    }
    report.report_data = report_data
    report.text_summary = product["text"]
    report.generated_at = datetime.now(timezone.utc)
    report.status = "generated" if product["status"] == "ready" else "draft"
    report.quality_gate_status = "passed" if product["status"] == "ready" else "blocked"
    report.quality_gate_summary = "Hermes Day-1 三段式日报已生成" if product["status"] == "ready" else "缺字段，未生成正式日报正文"
    if product["status"] == "ready" and product.get("formal_text"):
        report.final_text_summary = product["formal_text"]
        report.final_confirmed_by = actor.id
        report.final_confirmed_at = datetime.now(timezone.utc)
        report.is_final_version = True
        report.delivery_ready = True
    db.flush()
    return report
```

验证：

```bash
python -m pytest backend/tests/test_hermes_day1_orchestrator.py backend/tests/test_hermes_learning_loop.py -q
```

### Task 8: 接入钉钉入站和 CLI

更新 `backend/app/routers/dingtalk.py`。

改动点：

- 增加 `_resolve_inbound_channel_type()`，识别私聊和群聊。
- 现有 `/agent-inbound` 不再固定写 `dingtalk_group`。
- `settings.HERMES_DAY1_ENABLED` 为 `False` 时，已识别的 Day-1 指令返回 `hermes_day1_disabled`，其他普通消息继续走旧逻辑。
- 在进入旧 `handle_agent_command()` 前，先尝试 `parse_day1_command()`。
- 如果是 Day-1 日报指令，必须 `require_root_owner_for_day1_report()`。
- 所有授权消息都可以先走证据分类；噪声不入库。

关键接入片段：

```python
from datetime import datetime
from uuid import uuid4

from app.services.hermes_day1_intent_service import parse_day1_command
from app.services.hermes_day1_evidence_service import record_day1_dingtalk_evidence
from app.services.hermes_governance_service import FACTORY_PROFILE_CODE
from app.services.hermes_day1_orchestrator import run_day1_super_brain
from app.services.hermes_day1_intent_service import classify_day1_actor, require_root_owner_for_day1_report
```

在 `dingtalk_agent_inbound()` 中替换固定 channel：

```python
channel = _resolve_inbound_channel_type(payload, group_id=group_id)
decision = classify_day1_actor(
    user,
    sender_user_id=sender_external_id,
    sender_union_id=_clean_text(_first_payload_value(payload, "senderUnionId", "unionId")),
    channel=channel,
    group_id=group_id or None,
)
if not decision.allowed:
    raise HTTPException(status_code=403, detail=decision.reason)

command = parse_day1_command(text, default_year=datetime.now().year)
if command is not None and not settings.HERMES_DAY1_ENABLED:
    return {
        "errcode": 0,
        "errmsg": "ok",
        "trace_id": trace_id,
        "status": "disabled",
        "answer": "Hermes Day-1 三段式日报能力当前未开启。",
    }
if command is not None:
    require_root_owner_for_day1_report(decision)
    inbox = ChatInboxMessage(
        channel=channel,
        group_id=group_id or None,
        sender_external_id=sender_external_id or None,
        text=text,
        agent_code=FACTORY_PROFILE_CODE,
        trace_id=trace_id or uuid4().hex,
        source_payload=_sanitize_inbound_payload(payload),
    )
    db.add(inbox)
    db.flush()
    record_day1_dingtalk_evidence(
        db,
        payload=_sanitize_inbound_payload(payload),
        actor=user,
        business_date=command.business_date,
        channel=channel,
        group_id=group_id or None,
        trace_id=inbox.trace_id,
        recognized_text=text,
    )
    result = run_day1_super_brain(
        db,
        command=command,
        actor=user,
        trace_id=inbox.trace_id,
        chat_inbox=inbox,
    )
    db.commit()
    return {
        "errcode": 0,
        "errmsg": "ok",
        "trace_id": result.trace_id,
        "status": result.status,
        "answer": result.answer,
        "chat_inbox_id": inbox.id,
        "agent_run_id": result.agent_run_id,
        "report_id": result.report_id,
    }
```

`_resolve_inbound_channel_type()`：

```python
def _resolve_inbound_channel_type(payload: dict[str, Any], *, group_id: str) -> str:
    raw_type = _clean_text(_first_payload_value(payload, "conversationType", "conversation_type", "chatType", "chat_type")).lower()
    if raw_type in {"private", "single", "1", "one_to_one"}:
        return "dingtalk_private"
    if not group_id:
        return "dingtalk_private"
    return "dingtalk_group"
```

更新 `backend/scripts/agent_cli.py`：

- `COMMAND_LEVELS` 新增 `day1-report: L3`。
- `_parse_args()` 不需要新增参数，复用 `--text`、`--target-date`、`--dingtalk-user-id`、`--dingtalk-union-id`。
- `_run_with_db()` handlers 增加 `_cmd_day1_report`。
- `_cmd_dingtalk_command()` 中遇到自然语言 Day-1 指令时调用 `_cmd_day1_report`。

CLI 接入片段：

```python
from app.services.hermes_day1_intent_service import HermesDay1Command, parse_day1_command
from app.services.hermes_day1_orchestrator import run_day1_super_brain
from app.services.hermes_day1_intent_service import classify_day1_actor, require_root_owner_for_day1_report
```

```python
def _cmd_day1_report(db: Session, args: argparse.Namespace, auth: HermesAuth) -> dict[str, Any]:
    if not settings.HERMES_DAY1_ENABLED:
        raise AgentCliError("hermes_day1_disabled")
    text = args.text or args.query or "/日报"
    business_date = _target_date(args)
    command = parse_day1_command(text, default_year=business_date.year) or HermesDay1Command(
        intent="day1_daily_report",
        business_date=business_date,
        audience="root_owner",
        output_style="three_part",
        raw_text=text,
    )
    decision = classify_day1_actor(
        auth.user,
        sender_user_id=args.dingtalk_user_id,
        sender_union_id=args.dingtalk_union_id,
        channel=args.channel,
        group_id=args.group_id or None,
    )
    require_root_owner_for_day1_report(decision)
    inbox = _record_dingtalk_command_inbox(db, args, auth, text=text, handling="day1_super_brain")
    result = run_day1_super_brain(
        db,
        command=command,
        actor=auth.user,
        trace_id=_trace_id(args),
        chat_inbox=inbox,
    )
    return {
        "action": "day1-report",
        "reply": result.answer,
        "trace_id": result.trace_id,
        "data": {
            "status": result.status,
            "agent_run_id": result.agent_run_id,
            "report_id": result.report_id,
        },
    }
```

验证：

```bash
python -m pytest backend/tests/test_dingtalk_agent_inbound_route.py backend/tests/test_agent_cli.py -q
```

### Task 9: 实现生产 Harness 成熟度与真实值对齐服务

新增 `backend/app/services/hermes_day1_harness_service.py`。

它是生产服务层，不是测试 helper。作用是让 Hermes 每次生成日报后，都能自己回答三个问题：

1. 我有没有主动查证足够多的数据源？
2. 我有没有把冲突、缺字段、风险讲清楚？
3. 我的正式日报正文和 `D:\输出skill` txt 真实日报对齐到什么程度？

测试类型：

| 测试 | Day-1 判断 |
|---|---|
| 主动查证 | `tools_called` 必须包含 MES/WMS、数据中枢、钉钉证据、RAG、历史日报、输出 skill |
| 数据冲突 | `conflicts` 非空时必须进入 `工厂大脑判断单` |
| 缺数据追问 | `missing_fields` 非空时正式正文不能编造 |
| 钉钉证据分类 | fact/explanation/instruction/noise 分类正确 |
| 记忆成长 | 生成 `HermesLearningEvent` |
| 真实值对齐 | `field_match_rate` 必须达到阈值；低于阈值时阻断正式发布 |
| 高自主可追责 | L5 修正不在 Day-1 默认执行，但 correction action 必须有审计设计 |

实现骨架：

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.services.report.output_skill_reconciliation import reconcile_rendered_daily_report


@dataclass(frozen=True, slots=True)
class HarnessCaseResult:
    name: str
    passed: bool
    detail: str


def evaluate_day1_run_payload(
    payload: dict[str, Any],
    *,
    answer: str,
    output_skill_expected_text: str | None = None,
    min_field_match_rate: float = 95.0,
) -> list[HarnessCaseResult]:
    day1 = dict(payload.get("hermes_day1") or {})
    sources = dict(day1.get("sources") or {})
    alignment = (
        reconcile_rendered_daily_report(answer, output_skill_expected_text)
        if output_skill_expected_text
        else {"field_match_rate": 0.0, "expected_fields": 0, "differences": []}
    )
    results = [
        HarnessCaseResult(
            "active_verification",
            all(key in sources for key in ("template_daily_report", "mes_wms", "audit_run", "dingtalk_evidence", "historical_reports", "rag", "output_skill_alignment")),
            "需要查数据中枢、MES/WMS、审计、钉钉、历史日报、RAG 和输出 skill",
        ),
        HarnessCaseResult(
            "three_part_output",
            all(title in answer for title in ("工厂大脑判断单", "正式日报正文", "各车间明细")),
            "输出必须是固定三段式",
        ),
        HarnessCaseResult(
            "conflict_visibility",
            (not day1.get("conflicts")) or "冲突" in answer,
            "有冲突时必须明说",
        ),
        HarnessCaseResult(
            "missing_field_visibility",
            (not day1.get("missing_fields")) or "缺失" in answer or "缺字段" in answer,
            "缺字段时必须明说",
        ),
        HarnessCaseResult(
            "output_skill_alignment",
            alignment["expected_fields"] == 0 or alignment["field_match_rate"] >= min_field_match_rate,
            f"真实日报字段匹配率 {alignment['field_match_rate']}%，低于 {min_field_match_rate}% 时不能说已对齐",
        ),
    ]
    return results


def load_output_skill_daily_text(root: str | Path, business_date: date) -> str | None:
    root_path = Path(root)
    # Day-1 只读读取，匹配 2026-6-19_日报正文.txt / 2026-06-19_日报正文.txt 等常见命名。
    patterns = [
        f"{business_date.year}-{business_date.month}-{business_date.day}_日报正文.txt",
        f"{business_date.year}-{business_date.month:02d}-{business_date.day:02d}_日报正文.txt",
        f"{business_date.year}-{business_date.month}-{business_date.day}*日报*.txt",
        f"{business_date.year}-{business_date.month:02d}-{business_date.day:02d}*日报*.txt",
    ]
    for pattern in patterns:
        matches = sorted(root_path.glob(pattern))
        if matches:
            return matches[0].read_text(encoding="utf-8")
    return None
```

测试：

```python
from app.services.hermes_day1_harness_service import evaluate_day1_run_payload


def test_day1_harness_requires_three_part_output() -> None:
    results = evaluate_day1_run_payload(
        {
            "hermes_day1": {
                "sources": {
                    "template_daily_report": {},
                    "mes_wms": {},
                    "audit_run": {},
                    "dingtalk_evidence": [],
                    "historical_reports": [],
                    "rag": {},
                    "output_skill_alignment": {},
                },
                "conflicts": [],
                "missing_fields": [],
            }
        },
        answer="工厂大脑判断单\n...\n正式日报正文\n...\n各车间明细\n...",
    )

    assert all(item.passed for item in results)
```

验证：

```bash
python -m pytest backend/tests/test_hermes_day1_harness_service.py backend/tests/test_hermes_day1_output_skill_alignment.py -q
```

### Task 10: 端到端验收

先跑小范围测试：

```bash
python -m pytest \
  backend/tests/test_hermes_day1_intent_service.py \
  backend/tests/test_hermes_day1_evidence_service.py \
  backend/tests/test_hermes_day1_report_service.py \
  backend/tests/test_hermes_day1_orchestrator.py \
  backend/tests/test_hermes_day1_harness_service.py \
  backend/tests/test_hermes_day1_output_skill_alignment.py \
  backend/tests/test_dingtalk_agent_inbound_route.py \
  backend/tests/test_agent_cli.py \
  -q
```

再跑相关旧测试，确认没有破坏已有链路：

```bash
python -m pytest \
  backend/tests/test_template_daily_report.py \
  backend/tests/test_daily_report_task.py \
  backend/tests/test_hermes_data_audit_service.py \
  backend/tests/test_hermes_mes_read_service.py \
  backend/tests/test_hermes_learning_loop.py \
  backend/tests/test_agent_multimodal_evidence_service.py \
  backend/tests/test_output_skill_report_parser.py \
  backend/tests/test_output_skill_reconciliation.py \
  backend/tests/test_mapping_reconciliation_service.py \
  -q
```

真实值对齐 smoke：

```bash
set OUTPUT_SKILL_ROOT=D:\输出skill
python backend/scripts/agent_cli.py day1-report \
  --dingtalk-user-id dt-owner \
  --text "生成 6月19日 root_owner 完整版三段式日报" \
  --target-date 2026-06-19 \
  --channel dingtalk_private \
  --trace-id day1-output-skill-align-20260619
```

验收规则：

- 只读读取 `D:\输出skill` 对应日期的 `*_日报正文.txt`。
- 用 `parse_output_skill_daily_report()` 提取真实日报字段。
- 用 `reconcile_rendered_daily_report()` 对比 Hermes 生成的正式日报正文。
- `field_match_rate >= 95.0` 才算对齐通过。
- 低于 95.0 时，`工厂大脑判断单` 必须列出差异字段，正式正文不能标记为已对齐。
- 测试和日志里不能保存 `D:\输出skill` 原文全文，只保存文件名、字段数、匹配率、差异字段和脱敏摘要。

最后做 CLI smoke：

```bash
python backend/scripts/agent_cli.py day1-report \
  --dingtalk-user-id dt-owner \
  --text "生成 6月19日 root_owner 完整版三段式日报" \
  --target-date 2026-06-19 \
  --channel dingtalk_private \
  --trace-id day1-smoke-20260619
```

验收点：

- 返回文本包含 `工厂大脑判断单`、`正式日报正文`、`各车间明细`。
- `agent_runs.result_payload["hermes_day1"]["harness"]` 有成熟度评分。
- `agent_runs.result_payload["hermes_day1"]["output_skill_alignment"]["field_match_rate"] >= 95.0`，或明确说明未对齐字段。
- `agent_runs` 有一条 `agent_code='xt-factory-controller'` 的记录。
- `daily_reports.report_data["hermes_day1_super_brain"]` 有完整三段式产物。
- 如果模板字段 ready，`daily_reports.final_text_summary` 写入正式日报正文。
- `hermes_learning_events` 有成长候选。
- `audit_logs` 有 `hermes_day1_super_brain_report`。
- 如果 `OUTPUT_SKILL_ROOT` 不存在，系统只标记输出 skill 缺失，不报 500。

---

## 4. 生产配置说明

生产环境需要配置这些环境变量。这里只写变量名，不写真实值：

```bash
HERMES_OWNER_DINGTALK_USER_IDS=<张兆嘉的钉钉 staffId 或 unionId>
HERMES_ALLOWED_DINGTALK_USER_IDS=<允许普通查询的钉钉身份，逗号分隔>
HERMES_ALLOWED_GROUP_IDS=<root_owner 授权的钉钉群 conversationId，逗号分隔>
HERMES_DINGTALK_INBOUND_TOKEN=<钉钉入站 token>
HERMES_DAY1_ENABLED=false
HERMES_DAY1_MIN_OUTPUT_SKILL_FIELD_MATCH_RATE=95.0
MES_ADAPTER=sqlserver
OUTPUT_SKILL_ROOT=D:\输出skill
```

上线前把 `HERMES_DAY1_ENABLED` 保持为 `false`。完成 CLI smoke、钉钉回调 dry-run、2026-06-19 样本对齐后，再改为 `true`。

如果暂时拿不到张兆嘉的 staffId 或 unionId：

- 开发环境可以用姓名兜底。
- 生产环境不要只用姓名兜底。
- 生产环境上线前必须通过钉钉回调拿到真实 `senderStaffId` 或 `senderUnionId`。

---

## 5. 不做的事

这份 plan 不做：

- 不写 MES。
- 不直连 `wms.xintaily.com` 做未确认协议的爬取。
- 不做前端成长面板。
- 不做完整多角色钉钉分发。
- 不做 7:30/9:35 定时发布。
- 不让 RAG 决定当天动态数字。
- 不把钉钉闲聊当事实。
- 不修改 `D:\输出skill` 原始历史成品。

---

## 6. 风险和处理

| 风险 | 处理 |
|---|---|
| root_owner 身份拿不到 staffId/unionId | 先用开发兜底验证；生产上线前必须补真实身份 |
| MES/WMS adapter 未配置 | 输出 `source_status`，日报可阻断，不能编数 |
| 输出 skill 目录不存在 | 记录 `output_skill_source_missing`，不能 500 |
| 输出 skill 有真实 txt，但字段匹配率低于 95% | 判断单列出差异字段，`final_text_summary` 不标记为已对齐 |
| 输出 skill 文件名日期格式不统一 | Harness 用多 pattern 只读匹配，并在结果里记录命中文件名 |
| 钉钉文件只能拿到 mediaId，不能下载正文 | 先记录文件证据元数据；正文解析状态写 `text_unavailable` |
| 模板日报字段缺失 | 三段式仍输出判断单和缺字段清单，正式正文写阻断说明 |
| `record_evidence()` 当前会 commit | 增加 `commit=False` 可选参数，旧调用默认不变 |
| 旧 `/agent-inbound` 群聊行为被影响 | Day-1 parser 没命中时继续走旧 `handle_agent_command()` |

---

## 6A. Error & Rescue Registry

Day-1 不允许“失败了但看起来成功”。下面每一类错误都要有名字、日志、用户可见结果和测试。

| 方法/路径 | 可能失败 | 错误名 | 是否兜底 | 用户看到 |
|---|---|---|---|---|
| `parse_day1_command()` | 文本为空、没有日期、日期非法 | `Day1CommandParseError` 或返回 `None` | 是 | 走旧 agent 问答或提示“没有识别到日报日期” |
| `classify_day1_actor()` | 钉钉身份缺失、未绑定、非 root_owner | `Day1PermissionError` | 是 | `root_owner_required` 或 `user_not_allowed` |
| `record_day1_dingtalk_evidence()` | 文件无 mediaId、文本为空、证据类型不支持 | `Day1EvidenceError` | 是 | 不阻断日报，但判断单显示“钉钉证据不完整” |
| `collect_day1_sources()` | MES/WMS adapter 失败 | `Day1SourceError` | 是 | 判断单显示 MES/WMS 失败，不编数字 |
| `collect_day1_sources()` | 输出 skill 目录不存在 | `OutputSkillSourceMissingError` | 是 | 判断单显示输出 skill 缺失 |
| `collect_day1_sources()` | 审计 run 无可比数据 | `NoComparableDataError` | 是 | 审计状态为 failed，日报继续按模板字段决定 |
| `build_day1_three_part_report()` | 模板字段缺失 | `Day1ReportBlockedError` | 是 | 三段式输出保留，正式正文写阻断说明 |
| `run_day1_super_brain()` | 写 `DailyReport` 或 `AgentRun` 失败 | `SQLAlchemyError` | 否，必须回滚 | 钉钉返回失败，审计日志不伪造成功 |
| 钉钉回调 | 重复 messageId/traceId | `Day1DuplicateMessage` | 是 | 返回 duplicate，不重复生成日报 |

实现规则：

- 禁止只写 `except Exception: pass`。
- 如果必须兜底 `Exception`，只能在最外层兜底，并且要写 `trace_id`、`business_date`、`actor_user_id`、`source`。
- 所有错误文本经过 `redact_secret_text()`。
- 每个错误至少有一个测试。

## 6B. Failure Modes Registry

| 路径 | 失败模式 | 兜底 | 测试 | 用户可见 | 日志 |
|---|---|---|---|---|---|
| root_owner 私聊 | senderStaffId 缺失 | 是 | 是 | 提示身份缺失 | 是 |
| root_owner 私聊 | 非 root_owner 触发完整版日报 | 是 | 是 | 提示权限不足 | 是 |
| 命令解析 | `6月32日` | 是 | 是 | 提示日期非法 | 是 |
| 钉钉证据 | 群消息未授权 | 是 | 是 | 不进入高权限链路 | 是 |
| MES/WMS 查询 | adapter null | 是 | 是 | 判断单显示数据源缺失 | 是 |
| MES/WMS 查询 | 超时或 SQL Server 异常 | 是 | 是 | 判断单显示读取失败 | 是 |
| 输出 skill | `OUTPUT_SKILL_ROOT` 不存在 | 是 | 是 | 判断单显示缺少输出 skill | 是 |
| 输出 skill | 真实 txt 可读但匹配率低 | 是 | 是 | 判断单列差异字段 | 是 |
| Harness | 工具调用覆盖不足 | 是 | 是 | 判断单显示“查证不足” | 是 |
| 模板日报 | required fields 缺失 | 是 | 是 | 不生成假正文 | 是 |
| 日报落库 | `daily_reports` 唯一键冲突 | 是 | 是 | 读取已有日报后更新 | 是 |
| AgentRun 落库 | 数据库异常 | 否，回滚 | 是 | 返回失败 | 是 |
| 钉钉回调 | 同一 traceId 重放 | 是 | 是 | duplicate | 是 |

任何一行如果实现时变成“兜底=否、测试=否、用户不可见”，就是 P1 阻断。

## 6C. 必备图

系统架构：

```text
钉钉私聊/授权群
  -> dingtalk.py / hermes.py
  -> hermes_day1_intent_service.py
  -> hermes_day1_orchestrator.py
      -> hermes_day1_evidence_service.py
      -> hermes_day1_source_service.py
          -> template_daily_report.py
          -> HermesMesReadService -> MES/WMS 只读
          -> HermesDataAuditService -> 数据中枢/输出 skill 对账
          -> query_knowledge -> RAG 稳定知识
          -> DailyReport 历史记录
      -> hermes_day1_report_service.py
      -> hermes_day1_harness_service.py
          -> output_skill_reconciliation.py
          -> D:\输出skill 只读 txt 真实值
      -> DailyReport / AgentRun / HermesLearningEvent / AuditLog
  -> 钉钉回复 root_owner
```

数据流和阴影路径：

```text
输入文本
  -> 身份校验
      -> 缺身份：拒绝并记录
      -> 非 root_owner：拒绝完整版日报
  -> 指令解析
      -> 无日期：不进入 Day-1
      -> 非日报：走旧 agent
  -> 多源收集
      -> MES/WMS 失败：source_status 标红
      -> 输出 skill 缺失：issues 记录
      -> 钉钉证据为空：继续，但判断单说明
  -> 三段式生成
      -> 模板 ready：写正式正文
      -> 模板 blocked：不编数，只列缺字段
  -> Harness 和真实值对齐
      -> 对齐通过：允许标记已对齐
      -> 对齐失败：判断单列差异，不伪装成功
  -> 落库和回复
      -> 落库成功：回复 root_owner
      -> 落库失败：回滚并返回失败
```

状态机：

```text
received
  -> authorized
  -> collecting_sources
  -> composing
  -> aligning_output_skill
  -> scoring_harness
  -> persisted
  -> replied

blocked states:
  unauthorized
  command_unrecognized
  source_failed_but_visible
  report_blocked_missing_fields
  output_skill_alignment_failed
  persistence_failed
```

部署顺序：

```text
1. 部署代码，`HERMES_DAY1_ENABLED=false`
2. 跑 pytest 相关集合
3. 用 CLI 跑 2026-06-19 smoke
4. 用钉钉回调 dry-run 验证 traceId、身份、三段式
5. 设置 root_owner staffId/unionId
6. 打开 `HERMES_DAY1_ENABLED=true`
7. 首小时观察 AgentRun、DailyReport、AuditLog、错误日志
```

回滚：

```text
发现问题
  -> 先把 `HERMES_DAY1_ENABLED=false`
  -> 确认旧 `/agent-inbound` 仍走 `handle_agent_command()`
  -> 如已写错日报：按 `report_data["hermes_day1_super_brain"]` 和 audit log 定位
  -> 需要代码回滚时 revert Day-1 commit
  -> 不需要回滚数据库表，因为 Day-1 不新增表
```

---

## 6D. Eng Review Test Coverage Diagram

```text
CODE PATHS                                                   USER FLOWS
[+] dingtalk.py / hermes.py                                  [+] root_owner 私聊生成日报
  ├── [GAP] Day-1 disabled -> disabled response                 ├── [GAP] [->E2E] 私聊 /日报 2026-06-19
  ├── [GAP] root_owner -> Day-1 orchestrator                    ├── [GAP] 非 root_owner 被拒绝
  ├── [GAP] authorized group -> evidence only                   └── [GAP] 普通消息走旧 agent
  └── [GAP] parser miss -> handle_agent_command()

[+] hermes_day1_intent_service.py                            [+] 指令理解
  ├── [GAP] ISO 日期 2026-06-19                                ├── [GAP] 生成 6月19日正式日报
  ├── [GAP] 中文日期 6月19日                                   ├── [GAP] /日报 2026-06-19
  ├── [GAP] 非日报文本 -> None                                  └── [GAP] 6月32日 -> clear error
  └── [GAP] root_owner / authorized_user / denied

[+] hermes_day1_source_service.py                            [+] 主动查证
  ├── [GAP] template_daily_report ready                         ├── [GAP] 查数据中枢
  ├── [GAP] MES/WMS ok / missing / timeout                      ├── [GAP] 查 MES/WMS 只读
  ├── [GAP] data_audit ok / no comparable data                  ├── [GAP] 查钉钉证据
  ├── [GAP] RAG no hit / citations                              └── [GAP] 查历史日报和输出 skill
  └── [GAP] output skill root missing / parsed

[+] hermes_day1_report_service.py                            [+] 三段式输出
  ├── [GAP] ready -> formal report text                         ├── [GAP] 工厂大脑判断单在最前
  ├── [GAP] missing fields -> no fake numbers                   ├── [GAP] 正式日报正文沿用模板口径
  ├── [GAP] conflicts -> visible in judgment                    └── [GAP] 各车间明细包含车间级指标
  └── [GAP] workshop detail empty -> explain

[+] hermes_day1_harness_service.py                            [+] 真实值对齐
  ├── [GAP] tools_called complete                               ├── [GAP] 读取 D:\输出skill txt
  ├── [GAP] output_skill field_match_rate >= 95                 ├── [GAP] 字段匹配率 >= 95 通过
  ├── [GAP] output_skill field_match_rate < 95                  └── [GAP] 低于 95 列差异并阻断已对齐状态
  └── [GAP] no expected txt -> visible missing source

[+] hermes_day1_orchestrator.py                               [+] 落库和回复
  ├── [GAP] persist ChatInboxMessage / AgentRun / DailyReport   ├── [GAP] 钉钉返回三段式文本
  ├── [GAP] duplicate trace/message -> duplicate                ├── [GAP] 数据库异常时返回失败
  ├── [GAP] SQLAlchemyError -> rollback                         └── [GAP] 审计日志能追查本次运行
  └── [GAP] HermesLearningEvent created

COVERAGE TARGET: 0/45 Day-1 planned paths currently covered because implementation does not exist yet.
QUALITY TARGET: every GAP above must become at least ★★, and persistence/security/alignment paths must become ★★★.
E2E/EVAL: root_owner 私聊、CLI smoke、真实输出 skill 对齐属于 integration/eval 级验收。
```

测试要求：

- 新增测试必须先红后绿。
- 每个 `Error & Rescue Registry` 行至少一个失败路径测试。
- 每个 `Failure Modes Registry` 行至少一个用户可见结果断言。
- 真实 `D:\输出skill` 对齐测试只能读文件名和字段，不把原文写入 fixture 或 Git。
- 允许用 `backend/tests/fixtures/output_skill_daily_reports` 做单元测试基线，但最终 smoke 必须能读取本机 `D:\输出skill`。

## 6E. Eng Review Failure Modes

| Codepath | 生产失败方式 | 测试 | 错误处理 | 用户是否看得懂 |
|---|---|---|---|---|
| `dingtalk_agent_inbound` | 钉钉 payload 缺 senderStaffId/senderUnionId | 必须有 | 返回身份缺失 | 是 |
| `parse_day1_command` | 日期非法，例如 `6月32日` | 必须有 | 返回日期非法，不走旧日报 | 是 |
| `classify_day1_actor` | 误把普通用户当 root_owner | 必须有 | root_owner 白名单硬校验 | 是 |
| `collect_day1_sources` | MES SQL Server 超时 | 必须有 | `source_status.mes=failed` | 是 |
| `collect_day1_sources` | WMS 投影缺表或无数据 | 必须有 | `source_status.wms=missing` | 是 |
| `collect_day1_sources` | RAG 查不到口径 | 必须有 | RAG 标 empty，不影响事实 | 是 |
| `load_output_skill_daily_text` | `D:\输出skill` 日期命名不统一 | 必须有 | 多 pattern 匹配并记录 missing | 是 |
| `evaluate_day1_run_payload` | 工具调用不完整 | 必须有 | Harness 标查证不足 | 是 |
| `reconcile_rendered_daily_report` | 字段匹配率低于 95% | 必须有 | 阻断“已对齐”状态 | 是 |
| `run_day1_super_brain` | `DailyReport` 唯一键冲突 | 必须有 | 读取已有日报后更新 | 是 |
| `run_day1_super_brain` | `AgentRun` 写库失败 | 必须有 | 回滚并返回失败 | 是 |

Critical gaps: 0 after this plan update。原因是：每个失败方式都已经要求有测试、有处理方式、用户能看懂。

## 6F. Worktree Parallelization Strategy

| Step | Modules touched | Depends on |
|---|---|---|
| Lane A: intent + config gate | `backend/app/config.py`, `backend/app/services/`, `backend/tests/` | — |
| Lane B: evidence + source collection | `backend/app/services/`, `backend/tests/` | Lane A types |
| Lane C: report + harness + output skill alignment | `backend/app/services/report/`, `backend/app/services/`, `backend/tests/` | Lane A types |
| Lane D: orchestrator + route + CLI | `backend/app/routers/`, `backend/scripts/`, `backend/app/services/` | Lane A+B+C |
| Lane E: integration smoke docs/tests | `backend/tests/`, `docs/` | Lane D |

并行建议：

- 先顺序完成 Lane A，因为后面都依赖 command、actor、配置门禁的数据结构。
- Lane B 和 Lane C 可以并行，但都要避免同时改 `hermes_day1_orchestrator.py`。
- Lane D 必须等 B+C 合并后再做。
- Lane E 最后跑真实 `D:\输出skill` 对齐和钉钉 dry-run。

冲突提醒：Lane B/C/D 都会碰 `backend/app/services/`，并行时只适合拆 worktree，不适合多人随手改同一个文件。

## 6G. Eng Review Implementation Tasks

Synthesized from `plan-eng-review`. These tasks are additions or corrections to the build plan above.

- [ ] **E1 (P1, human: ~2h / CC: ~20min)** — 生产大脑状态 — Implement Day-1 state graph and tool trace as production payload.
  - Surfaced by: Architecture Review — plan needs a real state graph, not only a linear script.
  - Files: `backend/app/services/hermes_day1_orchestrator.py`, `backend/tests/test_hermes_day1_orchestrator.py`
  - Verify: every state transition appears in `agent_runs.result_payload["hermes_day1"]["state_trace"]`.

- [ ] **E2 (P1, human: ~2h / CC: ~20min)** — Harness 生产化 — Move maturity evaluation into `hermes_day1_harness_service.py`.
  - Surfaced by: Code Quality Review — test helper would not give production accountability.
  - Files: `backend/app/services/hermes_day1_harness_service.py`, `backend/tests/test_hermes_day1_harness_service.py`
  - Verify: harness score is persisted in `agent_runs.result_payload`.

- [ ] **E3 (P1, human: ~2h / CC: ~20min)** — 真实值对齐 — Read `D:\输出skill` txt and compare field values.
  - Surfaced by: Test Review — user requires real txt daily report alignment.
  - Files: `backend/app/services/hermes_day1_harness_service.py`, `backend/tests/test_hermes_day1_output_skill_alignment.py`, `backend/app/services/report/output_skill_reconciliation.py`
  - Verify: `field_match_rate >= 95.0` passes; lower rate lists fields and blocks aligned status.

- [ ] **E4 (P1, human: ~1h / CC: ~15min)** — Tool whitelist — Add explicit tool registry inside source/orchestrator layer.
  - Surfaced by: Architecture Review — ReAct without a whitelist can call wrong sources or trust RAG as facts.
  - Files: `backend/app/services/hermes_day1_source_service.py`, `backend/app/services/hermes_day1_orchestrator.py`
  - Verify: `tools_called` exactly records allowed tools, and unregistered tool names are rejected.

- [ ] **E5 (P2, human: ~1h / CC: ~10min)** — Test artifact — Keep an eng-review test plan artifact for QA.
  - Surfaced by: Test Review — QA needs a direct list of paths and interactions.
  - Files: `~/.gstack/projects/aluminum-bypass/*-eng-review-test-plan-*.md`
  - Verify: artifact exists and names root_owner private report, CLI smoke, output skill alignment.

---

## 7. 自检清单

实施完成前，执行者必须确认：

- [ ] 三段式标题完全一致：`工厂大脑判断单`、`正式日报正文`、`各车间明细`。
- [ ] `MES` 在代码里只读，没有 insert/update/delete。
- [ ] 日报数字来自 `template_daily_report` 和数据审计结果，不来自 RAG 猜测。
- [ ] Harness 在生产服务层执行，并把成熟度评分写入 `agent_runs.result_payload`。
- [ ] Hermes 正式日报正文和 `D:\输出skill` txt 真实值对齐，字段匹配率达到配置阈值或清楚列出差异。
- [ ] root_owner 完整版日报只能由 root_owner 触发。
- [ ] `HERMES_DAY1_ENABLED=false` 时，钉钉入口不会触发 Day-1。
- [ ] 授权群消息可以入证据池，但不能直接触发高权限日报。
- [ ] 缺字段时不生成假正式正文。
- [ ] 冲突进入判断单。
- [ ] 成长反馈进入 `hermes_learning_events`。
- [ ] 审计日志能查到本次任务。
- [ ] 相关 pytest 通过。

---

## 8. 建议执行顺序

1. Task 1：先写失败测试。
2. Task 2：做 root_owner 权限。
3. Task 3：做命令解析。
4. Task 4：做钉钉证据分类。
5. Task 5：做多源收集。
6. Task 6：做三段式生成。
7. Task 7：做 orchestrator。
8. Task 8：接钉钉和 CLI。
9. Task 9：做 harness。
10. Task 10：跑验收。

---

## 9. 完成定义

当下面事情都成立，Day-1 MVP 才算完成：

- root_owner 私聊输入 `生成 6月19日 root_owner 完整版三段式日报` 能得到三段式输出。
- 输出能解释用了哪些数据源、哪些字段缺失、哪些来源冲突。
- Harness 生产服务能给出主动查证、三段式、冲突可见、缺字段可见、真实值对齐评分。
- `D:\输出skill` 对应日期 txt 能作为只读真实值基准，Hermes 输出字段匹配率达到 `HERMES_DAY1_MIN_OUTPUT_SKILL_FIELD_MATCH_RATE`。
- 钉钉文本/文件能按 fact/explanation/instruction/noise 分类，业务证据能入库。
- `DailyReport`、`AgentRun`、`HermesLearningEvent`、`AuditLog` 都有记录。
- `HERMES_DAY1_ENABLED` 支持一键关闭 Day-1。
- 相关测试通过。
- 没有把 `鑫泰铝业 数据中枢` 叫成 MES。
- 没有泄露任何真实账号密码或 token。

---

## 10. CEO Review Implementation Tasks

Synthesized from `plan-ceo-review`. These tasks are additions or corrections to the build plan above.

- [ ] **T1 (P1, human: ~30min / CC: ~5min)** — 配置门禁 — Add `HERMES_DAY1_ENABLED` and wire it into DingTalk + CLI.
  - Surfaced by: CEO Review — Day-1 needs an instant kill switch.
  - Files: `backend/app/config.py`, `backend/app/routers/dingtalk.py`, `backend/scripts/agent_cli.py`
  - Verify: disabled state returns `hermes_day1_disabled`; enabled state runs Day-1.

- [ ] **T2 (P1, human: ~1h / CC: ~10min)** — 模块收敛 — Keep intent parsing and root_owner authorization in one service.
  - Surfaced by: CEO Review — original plan introduced too many small production modules.
  - Files: `backend/app/services/hermes_day1_intent_service.py`, `backend/tests/test_hermes_day1_intent_service.py`
  - Verify: parser and permission tests pass from one module.

- [ ] **T3 (P1, human: ~2h / CC: ~15min)** — 错误可见 — Implement named errors and tests from Error & Rescue Registry.
  - Surfaced by: CEO Review — silent failure would make Hermes look correct while using incomplete data.
  - Files: all new Day-1 service files and route/CLI integration tests
  - Verify: each registry row has a failure-path test.

- [ ] **T4 (P2, human: ~1h / CC: ~10min)** — 上线观测 — Add structured logs with `trace_id`, `business_date`, `actor_user_id`, `source_status`.
  - Surfaced by: CEO Review — post-ship bugs must be reconstructable from logs.
  - Files: `backend/app/services/hermes_day1_orchestrator.py`, `backend/app/services/hermes_day1_source_service.py`
  - Verify: smoke run logs one start, one source summary, one final status.

- [ ] **T5 (P2, human: ~30min / CC: ~5min)** — 回滚流程 — Document and verify flag rollback.
  - Surfaced by: CEO Review — production deployment is not atomic.
  - Files: this plan, deploy notes if implementation adds them
  - Verify: setting `HERMES_DAY1_ENABLED=false` stops Day-1 without reverting code.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | CLEAR | SELECTIVE + HOLD reviewed; Eng Review supersedes harness placement per user direction |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | not run | Outside voice not run in this pass |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 5 issues converted to tasks; 0 critical gaps after adding production Harness, state graph, tool whitelist, output skill alignment |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | skipped | No frontend UI scope in Day-1 MVP |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run | Not required for this backend-first plan |

- **UNRESOLVED:** 0
- **VERDICT:** CEO + ENG CLEARED — ready for implementation of the production service layer.
