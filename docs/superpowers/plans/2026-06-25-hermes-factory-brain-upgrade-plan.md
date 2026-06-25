# Hermes Factory Brain Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Hermes into the `鑫泰铝业 数据中枢` full-factory business brain: natural-language tasks, long-term rules, DingTalk four-condition sampling, routed RAG, LangChain/LangGraph orchestration, Codex construction, and three production-grade acceptance scenarios.

**Architecture:** Add a new Hermes factory brain lane beside the existing `agent_command_service` lane. DingTalk inbound first checks whether the new factory brain is enabled and applicable; if not, it falls back to the existing command/RAG path. LangChain owns model/tool/structured-output integration, LangGraph owns state graph/checkpoint/resume, and existing data services remain the source of production facts.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest, LangChain `1.3.11`, LangGraph `1.2.6`, `langgraph-checkpoint-postgres` `3.1.0`, `psycopg[binary,pool]` `3.3.4`, existing DingTalk inbound/outbox, existing RAG, existing Hermes audit and report services.

---

## Scope Check

This spec spans several subsystems: natural language, long-term rules, DingTalk evidence, RAG, graph orchestration, Codex construction, and business scenario evaluation.

Keep one master plan because the subsystems are not independent products. They meet at the Hermes graph state and must be tested through the same entrypoint. Execute this plan in vertical slices, with a passing test set and commit after each task.

## CEO / Eng / DevEx / Design Review Hardening

This section is the review pass applied before implementation. It is written in plain language so every executor knows what matters before touching code.

### Review Decision

- **CEO view:** use selective expansion. Keep the factory brain scope, but make it operationally mature instead of only "feature complete".
- **Engineering view:** use full review. This plan touches many services, so every data path needs tests, named errors, logs, rollback, and feature flags.
- **DevEx view:** use DX polish. The main "developer" is the operator or engineer implementing and debugging Hermes, not an external SDK user.
- **Design view:** no new visual UI is planned. Design work means DingTalk conversation quality, command flexibility, visible states, error copy, and report readability.

### Implementation Approach Compared

| Approach | Summary | Effort | Risk | Decision |
|---|---|---:|---:|---|
| Minimal patch | Add flexible natural-language routing around the existing command lane only. | S | Med | Rejected because it keeps Hermes as a smarter command bot, not a factory brain. |
| Vertical factory-brain lane | Add the new factory brain lane beside the current command lane, reuse existing report, RAG, audit, DingTalk, MES read, and agent tables. | L | Med | **Selected.** Best balance: real capability, reversible rollout, no big-bang rewrite. |
| Full platform rewrite | Replace existing agent, RAG, report, and command services with a unified graph-first platform. | XL | High | Deferred. Too much blast radius for production. |

### Dream State Delta

```
CURRENT STATE
  Hermes can answer narrow commands and some data questions.
  It fails awkwardly on slash commands, model auth errors, missing home channel, and vague user asks.

THIS PLAN
  Hermes becomes a reversible factory-brain lane:
  natural language -> intent -> graph state -> tools -> evidence -> DingTalk answer.
  Every answer carries source, confidence, conflict handling, and trace id.

12-MONTH IDEAL
  Hermes understands production, operations, quality, process, energy, contracts, inventory, and cost.
  It learns from approved DingTalk files and messages, proposes rules, verifies new knowledge with Codex,
  and can call construction tools to improve the data hub under root_owner authority.
```

### What Already Exists And Must Be Reused

| Need | Existing asset | Plan rule |
|---|---|---|
| DingTalk entrypoint | `backend/app/routers/dingtalk.py::dingtalk_agent_inbound` | Route through the factory-brain lane first, then fall back to existing command handling. |
| Old command/RAG fallback | `backend/app/services/agent_command_service.py::handle_agent_command` | Do not remove it. It is the rollback lane. |
| Daily report facts | `backend/app/services/report/template_daily_report.py` | Use this as the first hub fact source. Do not reimplement daily report math. |
| MES read-only data | `backend/app/services/hermes_mes_read_service.py::HermesMesReadService.read_sources` | Keep MES high-permission read-only. No writes to MES. |
| Output skill alignment | `backend/app/services/hermes_data_audit_service.py` and `D:/输出skill` parsing | Use for historical true-value alignment. |
| RAG | `backend/app/services/rag_service.py` and `backend/app/services/hermes_rag_service.py` | Add routing and knowledge units, do not bypass the existing document/chunk model. |
| Memory | `backend/app/services/hermes_memory_service.py` | Keep short-term memory separate from Soul and long-term rules. |
| Audit trail | `AgentRun`, `ChatInboxMessage`, `ExternalMessageLog`, `MultimodalEvidence` | Every factory-brain answer must leave a trace. |

### NOT In Scope

- Direct MES writes. MES is read-only for this work.
- A full frontend redesign. DingTalk answer quality and operator visibility are in scope; new dashboards are not required for MVP.
- Replacing the existing command lane. It remains the fallback and rollback path.
- Perfect autonomous learning without approval. Hermes can propose learning, but formal knowledge is promoted only after root_owner or Codex verification rules allow it.
- Enterprise-grade model provider migration. Codex-token mode is acceptable now; provider abstraction is included so it can be replaced later.

### System Architecture Diagram

```
DingTalk message / file
        |
        v
backend/app/routers/dingtalk.py
        |
        +-- factory brain enabled and applicable? -- no --> existing handle_agent_command()
        |
       yes
        v
HermesFactoryBrainOrchestrator
        |
        v
LangGraph StateGraph
        |
        +--> intent classifier
        +--> Soul.md + active long-term rules
        +--> DingTalk sampling evidence
        +--> fact priority merger
        +--> routed RAG
        +--> LangChain tool registry
        +--> Codex construction request recorder
        |
        v
AgentRun + tool calls + conflict decisions + final answer
        |
        v
DingTalk reply with trace id, confidence, and source summary
```

### Data Flow With Shadow Paths

```
INPUT TEXT / FILE
  |
  +-- missing or empty --> fallback reply: "我没拿到有效内容" + trace id
  |
  +-- slash command not registered --> strip slash and re-route as natural language
  |
  +-- recognized request --> validate actor, group, date, and data scope
  |
  +-- upstream source empty --> continue with lower-priority source and mark confidence lower
  |
  +-- upstream source error --> name source error, log it, keep partial answer if possible
  |
  +-- source conflict --> choose by priority rule and show conflict decision
  |
  +-- model unavailable --> degraded read-only answer from deterministic tools
  |
  v
FINAL ANSWER
  includes: conclusion, numbers, source priority, missing data, conflict notes, trace id
```

### Error And Rescue Registry

| Codepath | What can go wrong | Error name | Rescue action | User sees |
|---|---|---|---|---|
| DingTalk inbound | Message uses `/今日产量` and platform treats it as unknown command | `SlashCommandReroute` | Strip leading slash and re-run intent classifier | Normal answer, not "Unknown command". |
| Model call | Codex token refresh returns 401 | `FactoryBrainModelUnavailable` | Degrade to deterministic read-only tools and log `model_auth_401` | "模型暂不可用，已用只读数据模式回答。" |
| Home channel | No DingTalk home channel configured | `DingTalkHomeChannelMissing` | Reply in current chat and record setup hint | Current chat gets the result and a short setup note. |
| MES/WMS tool | Read service missing or timed out | `ReadonlySourceUnavailable` | Continue with hub/DingTalk/RAG, mark source unavailable | Answer includes missing source and lower confidence. |
| RAG route | No reliable chunks found | `RagNoReliableSource` | Do not invent. Return data-insufficient note | "知识库没有找到可靠来源。" |
| Fact merge | DingTalk specialist data conflicts with hub/MES | `FactConflictDetected` | Apply priority ladder and store conflict decision | Answer shows selected value and conflicting value. |
| Rule command | Non-root user tries to add permanent rule | `LongTermRulePermissionDenied` | Store as chat context only, no permanent rule | "该规则需要张兆嘉确认后才长期生效。" |
| Codex construction | Non-root user asks Hermes to change code or data hub | `CodexConstructionDenied` | Reject and audit | "只有 root_owner 可以提交施工请求。" |
| Checkpoint setup | LangGraph checkpoint tables are missing | `CheckpointUnavailable` | Run without durable resume if flag allows, otherwise block startup | Readiness report says checkpoint blocked. |

### Failure Modes Registry

| Flow | Failure mode | Rescued? | Test? | User sees? | Logged? |
|---|---|---:|---:|---:|---:|
| DingTalk natural language | Slash command prefix breaks routing | Y | Y | Y | Y |
| Daily report answer | Output skill true-value file missing | Y | Y | Y | Y |
| Daily report answer | Values conflict across DingTalk, hub, MES | Y | Y | Y | Y |
| RAG answer | RAG returns process knowledge as daily fact | Y | Y | Y | Y |
| Model layer | 401 auth failure | Y | Y | Y | Y |
| LangGraph | Checkpoint unavailable | Y | Y | Y | Y |
| Codex construction | Unauthorized construction request | Y | Y | Y | Y |
| Sampling | File from non-specialist is ingested as high-priority evidence | Y | Y | Y | Y |

Any new row with `Rescued=N`, `Test=N`, and `User sees?=N` blocks production.

### DingTalk Interaction State Map

| User state | Hermes behavior |
|---|---|
| Normal question, enough data | Answer directly with conclusion first, then key numbers, then source summary. |
| Vague question such as "产量出来了吗" | Infer likely intent, answer best-known production status, and ask one short follow-up only if needed. |
| Slash command not registered | Treat `/今日产量` as `今日产量`, then answer normally. |
| Partial data | Say what is known, what is missing, and which source is missing. |
| Source conflict | Show the selected value, rejected value, and priority rule. |
| Model unavailable | Use deterministic tools and say it is degraded mode. |
| Permission blocked | Explain who can approve and what was not changed. |
| Successful long-term rule proposal | Confirm whether it is active, pending confirmation, or temporary. |

### Operator / Developer Experience Gate

Target operator persona:

```
Who:      data hub engineer or factory operator debugging Hermes in production
Context:  DingTalk answer is wrong, slow, missing, or too rigid
Tolerance: 10 minutes to reproduce locally, 2 minutes to see trace evidence
Expects:  one command, clear logs, clear source ranking, no guessing
```

Time-to-hello-world target:

1. `python backend/scripts/hermes_factory_brain_cli.py --scenario daily_report --business-date 2026-06-19`
2. The CLI prints final answer, selected sources, conflict decisions, tool calls, and `trace_id`.
3. A failing source still returns a structured degraded answer, not a stack trace.

Magical moment:

- Ask Hermes "产量出来了吗" in DingTalk.
- It understands the intent without needing a command.
- It answers with today's production status, source priority, confidence, and trace id.
- If data conflicts, it says why it trusted one source over another.

### Test Coverage Diagram

```
CODE PATHS                                      TEST TYPE
  dingtalk_agent_inbound
    |-- factory brain off -------------------- regression
    |-- factory brain on/applicable ---------- integration
    |-- slash command reroute ---------------- regression
    |-- permission blocked ------------------- unit + integration

  HermesFactoryBrainOrchestrator
    |-- intent -> graph -> tools -> answer ---- integration
    |-- model unavailable -------------------- unit
    |-- partial source failure --------------- unit
    |-- conflict decision -------------------- unit

  LangGraph app
    |-- initial state ------------------------ unit
    |-- conditional route -------------------- unit
    |-- checkpoint setup --------------------- integration

  Tool registry
    |-- every tool registered ---------------- unit
    |-- real adapter output shape ------------ unit
    |-- no unregistered tool allowed --------- unit

USER FLOWS
  /今日产量 works as natural language -------- E2E-style route test
  产量出来了吗 returns flexible answer -------- acceptance harness
  日报对齐 6月19日真实值 ------------------- acceptance harness
  非root提交长期规则 ------------------------ permission test
  root_owner提交规则 ------------------------ integration

LLM/EVAL PATHS
  report answer keeps template shape -------- eval-like harness
  no hallucinated daily facts from RAG ------- eval-like harness
  witty Soul remains professional ----------- eval-like harness
```

### Observability And Rollout Gate

Before enabling `HERMES_FACTORY_BRAIN_ENABLED=true` in production:

- Every inbound message creates or links a `ChatInboxMessage`.
- Every factory-brain run creates an `AgentRun` with `trace_id`, status, intent, tool calls, degraded flag, and final source summary.
- Every external reply writes `ExternalMessageLog`.
- Every DingTalk file/message used as evidence writes `MultimodalEvidence`.
- Every conflict decision is queryable by `trace_id` and business date.
- Readiness report includes the exact smoke command and the DingTalk test message used.
- Rollback is tested by turning `HERMES_FACTORY_BRAIN_ENABLED=false` and confirming fallback to `handle_agent_command`.

### Parallelization Strategy

| Lane | Work | Depends on |
|---|---|---|
| A | Config, models, migrations, Soul/rules | none |
| B | Intent, DingTalk sampling, RAG routing, fact priority | A models |
| C | LangChain tools and model degradation | A models |
| D | LangGraph and orchestrator | B + C |
| E | DingTalk inbound, Codex construction, acceptance harness | D |
| F | Readiness report, deployment smoke, rollback verification | E |

Execution order: start A first. After A passes, B and C can run in parallel. D waits for B/C. E waits for D. F is last.

Conflict flag: B, C, and D all touch `backend/app/services/`; use separate worktrees or merge sequentially after tests.

## Current Code Facts

- Current DingTalk agent entrypoint is `backend/app/routers/dingtalk.py::dingtalk_agent_inbound`.
- Current fallback command lane is `backend/app/services/agent_command_service.py::handle_agent_command`.
- Existing agent audit tables include `chat_inbox`, `agent_runs`, `agent_outbox_messages`, `external_message_logs`, and `multimodal_evidence`.
- Existing Hermes/RAG tables include `rag_documents`, `rag_chunks`, `rag_embeddings`, `rag_query_logs`, `hermes_learning_events`, `hermes_short_term_memories`, and `hermes_approved_lessons`.
- Existing Day-1/report sources include `backend/app/services/report/template_daily_report.py`, `backend/app/services/hermes_data_audit_service.py`, `backend/app/services/hermes_mes_read_service.py`, and output skill reconciliation services.
- `backend/requirements.txt` does not yet include LangChain/LangGraph packages.

## File Structure

Create these files:

- `backend/app/models/hermes_factory_brain.py`
  Owns long-term rules, Soul profile versions, DingTalk sampling rules, knowledge units, and Codex construction run records.

- `backend/alembic/versions/0052_hermes_factory_brain.py`
  Adds Hermes factory brain persistence tables and indexes.

- `backend/app/hermes/Soul.md`
  Source-controlled default Hermes personality and behavior profile.

- `backend/app/services/hermes_factory_brain_types.py`
  Pydantic and dataclass types shared by intent, graph, tools, and response rendering.

- `backend/app/services/hermes_soul_service.py`
  Loads `Soul.md`, persists profile versions, and returns the active soul text.

- `backend/app/services/hermes_long_term_rule_service.py`
  Parses, stores, modifies, lowers priority, deletes, and retrieves root_owner long-term rules.

- `backend/app/services/hermes_factory_brain_intent_service.py`
  Classifies incoming text into task instruction, long-term rule management, context query, construction request, or fallback.

- `backend/app/services/hermes_dingtalk_sampling_service.py`
  Applies group + owner + content type + time range sampling rules and writes qualifying evidence.

- `backend/app/services/hermes_rag_router_service.py`
  Routes RAG by domain/object/metric/time/source/knowledge type before calling existing `rag_service.query_knowledge`.

- `backend/app/services/hermes_fact_priority_service.py`
  Merges root_owner, DingTalk, hub, MES/WMS, RAG/history/output-skill evidence and exposes visible conflict decisions.

- `backend/app/services/hermes_langchain_tools.py`
  Defines LangChain tool whitelist and adapters around existing data services.

- `backend/app/services/hermes_langchain_model.py`
  Wraps the temporary Codex-token model lane and exposes model-degraded fallback behavior.

- `backend/app/services/hermes_langgraph_app.py`
  Defines LangGraph `StateGraph`, nodes, conditional edges, interrupt points, and Postgres checkpointer creation.

- `backend/app/services/hermes_factory_brain_orchestrator.py`
  Public service entrypoint used by DingTalk route and CLI. Owns transaction boundary, `AgentRun` persistence, and fallback decisions.

- `backend/app/services/hermes_codex_construction_service.py`
  Records root_owner-authorized light/heavy construction requests and returns a structured construction plan or execution result.

- `backend/app/services/hermes_factory_brain_harness.py`
  Scores the three acceptance scenarios and checks tool coverage, conflict visibility, RAG routing, and degraded-model behavior.

- `backend/scripts/setup_langgraph_checkpoint.py`
  One-time operational script that calls `PostgresSaver.setup()` against the data hub PostgreSQL connection.

- `backend/scripts/hermes_factory_brain_cli.py`
  Local smoke CLI for the three acceptance scenarios.

- `backend/tests/test_hermes_factory_brain_models.py`
- `backend/tests/test_hermes_factory_brain_intent_service.py`
- `backend/tests/test_hermes_long_term_rule_service.py`
- `backend/tests/test_hermes_dingtalk_sampling_service.py`
- `backend/tests/test_hermes_rag_router_service.py`
- `backend/tests/test_hermes_fact_priority_service.py`
- `backend/tests/test_hermes_langchain_tools.py`
- `backend/tests/test_hermes_langgraph_app.py`
- `backend/tests/test_hermes_factory_brain_orchestrator.py`
- `backend/tests/test_hermes_codex_construction_service.py`
- `backend/tests/test_dingtalk_factory_brain_inbound.py`
- `backend/tests/test_hermes_factory_brain_acceptance.py`

Modify these files:

- `backend/requirements.txt`
  Add LangChain/LangGraph dependencies.

- `backend/.env.example`
  Add factory brain flags and checkpoint setup guidance.

- `backend/app/config.py`
  Add settings and validation.

- `backend/app/models/__init__.py`
  Export new models.

- `backend/app/routers/dingtalk.py`
  Add enabled/applicable factory brain lane before fallback command lane.

- `backend/app/routers/hermes.py`
  Add a factory-brain inbound alias and status endpoint.

- `backend/scripts/agent_cli.py`
  Add a small bridge or note to call `hermes_factory_brain_cli.py` for factory brain smoke checks.

- `docs/superpowers/specs/2026-06-25-hermes-factory-brain-upgrade-design.md`
  No spec rewrite expected during implementation. Only append implementation notes if a later review explicitly changes scope.

---

## Task 1: Dependencies, Flags, and Baseline Gate

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/.env.example`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_hermes_factory_brain_config.py`

- [ ] **Step 1: Write failing config tests**

Create `backend/tests/test_hermes_factory_brain_config.py`:

```python
from app.config import Settings


def test_factory_brain_defaults_are_safe() -> None:
    settings = Settings()

    assert settings.HERMES_FACTORY_BRAIN_ENABLED is False
    assert settings.HERMES_FACTORY_BRAIN_MODEL_PROVIDER == 'codex_token'
    assert settings.HERMES_CODEX_CONSTRUCTION_ENABLED is False
    assert settings.HERMES_LANGGRAPH_CHECKPOINT_SETUP_ON_START is False
    assert settings.HERMES_SOUL_PATH == 'app/hermes/Soul.md'


def test_factory_brain_validates_model_provider() -> None:
    settings = Settings(HERMES_FACTORY_BRAIN_MODEL_PROVIDER='unknown-provider')

    issues = settings.validate_runtime()

    assert 'HERMES_FACTORY_BRAIN_MODEL_PROVIDER must be one of codex_token, service_llm' in issues


def test_factory_brain_validate_checkpoint_mode() -> None:
    settings = Settings(HERMES_LANGGRAPH_CHECKPOINT_MODE='sqlite')

    issues = settings.validate_runtime()

    assert 'HERMES_LANGGRAPH_CHECKPOINT_MODE must be postgres' in issues
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest backend/tests/test_hermes_factory_brain_config.py -q
```

Expected: fail because the new settings do not exist.

- [ ] **Step 3: Add pinned dependencies**

Append to `backend/requirements.txt`:

```text
langchain==1.3.11
langgraph==1.2.6
langgraph-checkpoint-postgres==3.1.0
psycopg[binary,pool]==3.3.4
```

- [ ] **Step 4: Add example env keys**

Append to `backend/.env.example` near existing Hermes settings:

```dotenv
HERMES_FACTORY_BRAIN_ENABLED=false
HERMES_FACTORY_BRAIN_MODEL_PROVIDER=codex_token
HERMES_LANGGRAPH_CHECKPOINT_MODE=postgres
HERMES_LANGGRAPH_CHECKPOINT_SETUP_ON_START=false
HERMES_SOUL_PATH=app/hermes/Soul.md
HERMES_CODEX_CONSTRUCTION_ENABLED=false
HERMES_FACTORY_BRAIN_MAX_TOOL_STEPS=8
HERMES_FACTORY_BRAIN_MIN_CONFIDENCE=0.65
```

- [ ] **Step 5: Add settings**

Modify `backend/app/config.py` near existing Hermes settings:

```python
    HERMES_FACTORY_BRAIN_ENABLED: bool = False
    HERMES_FACTORY_BRAIN_MODEL_PROVIDER: str = 'codex_token'
    HERMES_LANGGRAPH_CHECKPOINT_MODE: str = 'postgres'
    HERMES_LANGGRAPH_CHECKPOINT_SETUP_ON_START: bool = False
    HERMES_SOUL_PATH: str = 'app/hermes/Soul.md'
    HERMES_CODEX_CONSTRUCTION_ENABLED: bool = False
    HERMES_FACTORY_BRAIN_MAX_TOOL_STEPS: int = 8
    HERMES_FACTORY_BRAIN_MIN_CONFIDENCE: float = 0.65
```

Add to `Settings.validate_runtime()`:

```python
        factory_brain_provider = str(self.HERMES_FACTORY_BRAIN_MODEL_PROVIDER or '').strip().lower()
        if factory_brain_provider not in {'codex_token', 'service_llm'}:
            issues.append('HERMES_FACTORY_BRAIN_MODEL_PROVIDER must be one of codex_token, service_llm')

        checkpoint_mode = str(self.HERMES_LANGGRAPH_CHECKPOINT_MODE or '').strip().lower()
        if checkpoint_mode != 'postgres':
            issues.append('HERMES_LANGGRAPH_CHECKPOINT_MODE must be postgres')

        if self.HERMES_FACTORY_BRAIN_MAX_TOOL_STEPS <= 0:
            issues.append('HERMES_FACTORY_BRAIN_MAX_TOOL_STEPS must be greater than 0')

        if not (0 < self.HERMES_FACTORY_BRAIN_MIN_CONFIDENCE <= 1):
            issues.append('HERMES_FACTORY_BRAIN_MIN_CONFIDENCE must be in (0, 1]')
```

- [ ] **Step 6: Run config test**

Run:

```powershell
python -m pytest backend/tests/test_hermes_factory_brain_config.py -q
```

Expected: pass.

- [ ] **Step 7: Run dependency import smoke**

After installing dependencies in the active environment, run:

```powershell
python - <<'PY'
import langchain
import langgraph
from langgraph.checkpoint.postgres import PostgresSaver
print('langchain/langgraph imports ok')
PY
```

Expected: `langchain/langgraph imports ok`.

- [ ] **Step 8: Commit**

```powershell
git add backend/requirements.txt backend/.env.example backend/app/config.py backend/tests/test_hermes_factory_brain_config.py
git commit -m "feat: add Hermes factory brain runtime flags"
```

---

## Task 2: Persistence Models for Rules, Knowledge, Sampling, and Construction

**Files:**
- Create: `backend/app/models/hermes_factory_brain.py`
- Create: `backend/alembic/versions/0052_hermes_factory_brain.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_hermes_factory_brain_models.py`

- [ ] **Step 1: Write failing model persistence tests**

Create `backend/tests/test_hermes_factory_brain_models.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.hermes_factory_brain import (
    HermesCodexConstructionRun,
    HermesDingTalkSamplingRule,
    HermesKnowledgeUnit,
    HermesLongTermRule,
    HermesSoulProfile,
)


def _db() -> Session:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_long_term_rule_stores_raw_and_structured_rule() -> None:
    db = _db()
    rule = HermesLongTermRule(
        rule_key='root-owner-rule-001',
        raw_text='以后日报先看专项责任人发的钉钉文件',
        structured_rule={'rule_type': 'source_priority', 'priority': ['dingtalk_specialist', 'hub', 'mes_wms']},
        scope_payload={'domain': 'daily_report'},
        status='active',
        risk_level='high',
        created_by_id=1,
    )

    db.add(rule)
    db.commit()

    saved = db.query(HermesLongTermRule).one()
    assert saved.raw_text == '以后日报先看专项责任人发的钉钉文件'
    assert saved.structured_rule['rule_type'] == 'source_priority'
    assert saved.status == 'active'


def test_sampling_rule_requires_four_condition_payload() -> None:
    db = _db()
    rule = HermesDingTalkSamplingRule(
        rule_key='sampling-production-daily',
        channel_key='cid-production-daily',
        specialist_user_id='dt-owner-001',
        content_types=['daily_report', 'production_table'],
        time_window_payload={'mode': 'recent_days', 'days': 30},
        priority='high',
        status='active',
        created_by_id=1,
    )

    db.add(rule)
    db.commit()

    saved = db.query(HermesDingTalkSamplingRule).one()
    assert saved.channel_key == 'cid-production-daily'
    assert saved.specialist_user_id == 'dt-owner-001'
    assert saved.content_types == ['daily_report', 'production_table']
    assert saved.time_window_payload['days'] == 30


def test_knowledge_unit_records_verification_state() -> None:
    db = _db()
    unit = HermesKnowledgeUnit(
        unit_key='metric-ton-electricity-001',
        layer='field',
        unit_type='metric',
        title='吨电耗定义',
        content='吨电耗 = 用电量 / 对应产量。',
        status='candidate',
        verification_payload={'method': 'not_verified'},
    )

    db.add(unit)
    db.commit()

    saved = db.query(HermesKnowledgeUnit).one()
    assert saved.status == 'candidate'
    assert saved.layer == 'field'
    assert saved.unit_type == 'metric'


def test_soul_and_codex_construction_records_are_persisted() -> None:
    db = _db()
    soul = HermesSoulProfile(
        profile_key='default',
        version=1,
        soul_text='Hermes 是有趣、轻松、诙谐但严谨的工厂大脑。',
        status='active',
    )
    run = HermesCodexConstructionRun(
        trace_id='trace-construction-001',
        request_text='直接修好并部署',
        construction_type='heavy',
        authorization_level='root_owner',
        status='requested',
        payload={'goal': 'fix production issue'},
        requested_by_id=1,
    )

    db.add_all([soul, run])
    db.commit()

    assert db.query(HermesSoulProfile).one().version == 1
    assert db.query(HermesCodexConstructionRun).one().construction_type == 'heavy'
```

- [ ] **Step 2: Run model test to verify it fails**

Run:

```powershell
python -m pytest backend/tests/test_hermes_factory_brain_models.py -q
```

Expected: fail because `app.models.hermes_factory_brain` does not exist.

- [ ] **Step 3: Add model file**

Create `backend/app/models/hermes_factory_brain.py`:

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, json_object_type


class HermesSoulProfile(Base):
    __tablename__ = 'hermes_soul_profiles'
    __table_args__ = (UniqueConstraint('profile_key', 'version', name='uq_hermes_soul_profile_key_version'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    soul_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active', index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class HermesLongTermRule(Base):
    __tablename__ = 'hermes_long_term_rules'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rule_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_rule: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    scope_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active', index=True)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default='low', index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100, index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    confirmed_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    source_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class HermesDingTalkSamplingRule(Base):
    __tablename__ = 'hermes_dingtalk_sampling_rules'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rule_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    channel_key: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    specialist_user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    content_types: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    time_window_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default='high', index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='active', index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class HermesKnowledgeUnit(Base):
    __tablename__ = 'hermes_knowledge_units'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    unit_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    layer: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    unit_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    verification_payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='candidate', index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey('rag_documents.id'), nullable=True, index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    verified_by: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class HermesCodexConstructionRun(Base):
    __tablename__ = 'hermes_codex_construction_runs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    construction_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    authorization_level: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='requested', index=True)
    payload: Mapped[dict] = mapped_column(json_object_type, nullable=False, default=dict)
    result_payload: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 4: Export models**

Modify `backend/app/models/__init__.py` to import and export:

```python
from app.models.hermes_factory_brain import (
    HermesCodexConstructionRun,
    HermesDingTalkSamplingRule,
    HermesKnowledgeUnit,
    HermesLongTermRule,
    HermesSoulProfile,
)
```

Add each name to the module `__all__` list.

- [ ] **Step 5: Add Alembic migration**

Create `backend/alembic/versions/0052_hermes_factory_brain.py` with SQLAlchemy operations for the five tables. Use JSON-compatible columns through the same type pattern already used by generated migrations in this repo.

The migration must include these table names exactly:

```python
TABLES = (
    'hermes_soul_profiles',
    'hermes_long_term_rules',
    'hermes_dingtalk_sampling_rules',
    'hermes_knowledge_units',
    'hermes_codex_construction_runs',
)
```

Set:

```python
revision = '0052_hermes_factory_brain'
down_revision = '0051_report_history_period_knowledge'
```

- [ ] **Step 6: Run model tests**

```powershell
python -m pytest backend/tests/test_hermes_factory_brain_models.py -q
```

Expected: pass.

- [ ] **Step 7: Run migration smoke**

```powershell
cd backend
python -m alembic upgrade head
python -m alembic current
```

Expected: `0052_hermes_factory_brain (head)`.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/models/hermes_factory_brain.py backend/app/models/__init__.py backend/alembic/versions/0052_hermes_factory_brain.py backend/tests/test_hermes_factory_brain_models.py
git commit -m "feat: add Hermes factory brain persistence"
```

---

## Task 3: Soul.md and Long-Term Rule Services

**Files:**
- Create: `backend/app/hermes/Soul.md`
- Create: `backend/app/services/hermes_soul_service.py`
- Create: `backend/app/services/hermes_long_term_rule_service.py`
- Test: `backend/tests/test_hermes_long_term_rule_service.py`

- [ ] **Step 1: Write failing service tests**

Create `backend/tests/test_hermes_long_term_rule_service.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.hermes_factory_brain import HermesLongTermRule
from app.services.hermes_long_term_rule_service import (
    LongTermRuleCommand,
    classify_rule_command,
    create_or_confirm_rule,
    lower_rule_priority,
    list_active_rules,
)
from app.services.hermes_soul_service import load_default_soul_text


def _db() -> Session:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_soul_text_defines_funny_but_serious_boundary() -> None:
    text = load_default_soul_text()

    assert '有趣' in text
    assert '轻松' in text
    assert '诙谐' in text
    assert '不能拿生产事实开玩笑' in text


def test_classify_natural_language_rule_add() -> None:
    command = classify_rule_command('以后日报先看专项责任人发的钉钉文件')

    assert command.action == 'add'
    assert command.risk_level == 'high'
    assert command.structured_rule['rule_type'] == 'source_priority'


def test_classify_temporary_override_does_not_persist() -> None:
    command = classify_rule_command('今天按临时口径，不要记住')

    assert command.action == 'temporary_override'
    assert command.persist is False


def test_root_owner_rule_persists_raw_and_structured_rule() -> None:
    db = _db()
    command = LongTermRuleCommand(
        action='add',
        raw_text='以后回答我先给结论，再给数据来源',
        structured_rule={'rule_type': 'response_style', 'order': ['conclusion', 'sources']},
        scope_payload={'domain': 'all'},
        risk_level='low',
        persist=True,
        requires_confirmation=False,
    )

    rule = create_or_confirm_rule(db, command=command, actor_user_id=1, trace_id='trace-rule-001')
    db.commit()

    assert rule.status == 'active'
    assert rule.raw_text == '以后回答我先给结论，再给数据来源'
    assert rule.structured_rule['rule_type'] == 'response_style'


def test_lower_rule_priority_changes_status_and_priority() -> None:
    db = _db()
    db.add(
        HermesLongTermRule(
            rule_key='rule-001',
            raw_text='以后日报先看钉钉文件',
            structured_rule={'rule_type': 'source_priority'},
            scope_payload={'domain': 'daily_report'},
            status='active',
            risk_level='high',
            priority=100,
        )
    )
    db.commit()

    lowered = lower_rule_priority(db, rule_key='rule-001', actor_user_id=1)
    db.commit()

    assert lowered.status == 'lowered'
    assert lowered.priority == 200
    assert list_active_rules(db) == []
```

- [ ] **Step 2: Run failing tests**

```powershell
python -m pytest backend/tests/test_hermes_long_term_rule_service.py -q
```

Expected: fail because services and `Soul.md` do not exist.

- [ ] **Step 3: Create Soul.md**

Create `backend/app/hermes/Soul.md`:

```markdown
# Hermes Soul

Hermes 是鑫泰铝业 数据中枢里的工厂大脑。

## 性格

Hermes 是一个有趣、轻松、诙谐的人。它说话自然，不死板，不把自己伪装成冷冰冰的命令菜单。

## 工作方式

Hermes 主动、好奇、会追问、会总结规律、会推动下一步。

## 工厂判断习惯

先看事实，再看来源，再看冲突，再给判断，再建议动作。

## 边界

Hermes 不能拿生产事实开玩笑，不能拿数据准确性开玩笑，不能拿权限开玩笑，不能用幽默掩盖不确定性。

## 与 root_owner 的互动

面对 root_owner，Hermes 可以更直接、更自然、更有陪伴感，但最终判断必须尊重 root_owner 权限和确认。
```

- [ ] **Step 4: Implement soul service**

Create `backend/app/services/hermes_soul_service.py`:

```python
from __future__ import annotations

from pathlib import Path

from app.config import settings


def load_default_soul_text() -> str:
    configured = Path(str(settings.HERMES_SOUL_PATH or 'app/hermes/Soul.md'))
    if configured.is_absolute():
        path = configured
    else:
        path = Path(__file__).resolve().parents[1] / configured.relative_to('app')
    return path.read_text(encoding='utf-8')
```

- [ ] **Step 5: Implement long-term rule service**

Create `backend/app/services/hermes_long_term_rule_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.redaction import redact_secret_text
from app.models.hermes_factory_brain import HermesLongTermRule


@dataclass(frozen=True, slots=True)
class LongTermRuleCommand:
    action: str
    raw_text: str
    structured_rule: dict
    scope_payload: dict
    risk_level: str
    persist: bool
    requires_confirmation: bool


def classify_rule_command(text: str) -> LongTermRuleCommand:
    clean = str(text or '').strip()
    if '不要记住' in clean or '临时口径' in clean or '只是临时' in clean:
        return LongTermRuleCommand(
            action='temporary_override',
            raw_text=clean,
            structured_rule={'rule_type': 'temporary_override'},
            scope_payload={'domain': 'current_task'},
            risk_level='low',
            persist=False,
            requires_confirmation=False,
        )
    if '删' in clean:
        return LongTermRuleCommand(
            action='delete',
            raw_text=clean,
            structured_rule={'rule_type': 'rule_deletion'},
            scope_payload={'domain': 'rule_management'},
            risk_level='high',
            persist=True,
            requires_confirmation=True,
        )
    if '降' in clean and '优先级' in clean:
        return LongTermRuleCommand(
            action='lower_priority',
            raw_text=clean,
            structured_rule={'rule_type': 'priority_lowering'},
            scope_payload={'domain': 'rule_management'},
            risk_level='high',
            persist=True,
            requires_confirmation=True,
        )
    if '钉钉' in clean and ('优先' in clean or '先看' in clean):
        return LongTermRuleCommand(
            action='add',
            raw_text=clean,
            structured_rule={'rule_type': 'source_priority', 'priority': ['dingtalk_specialist', 'hub', 'mes_wms']},
            scope_payload={'domain': 'daily_report'},
            risk_level='high',
            persist=True,
            requires_confirmation=True,
        )
    return LongTermRuleCommand(
        action='add',
        raw_text=clean,
        structured_rule={'rule_type': 'response_style', 'order': ['conclusion', 'sources']},
        scope_payload={'domain': 'all'},
        risk_level='low',
        persist=True,
        requires_confirmation=False,
    )


def create_or_confirm_rule(
    db: Session,
    *,
    command: LongTermRuleCommand,
    actor_user_id: int | None,
    trace_id: str | None,
) -> HermesLongTermRule:
    rule = HermesLongTermRule(
        rule_key=f'rule-{uuid4().hex}',
        raw_text=redact_secret_text(command.raw_text),
        structured_rule=command.structured_rule,
        scope_payload=command.scope_payload,
        status='pending_confirmation' if command.requires_confirmation else 'active',
        risk_level=command.risk_level,
        priority=100,
        created_by_id=actor_user_id,
        confirmed_by_id=None if command.requires_confirmation else actor_user_id,
        source_trace_id=trace_id,
    )
    db.add(rule)
    db.flush()
    return rule


def lower_rule_priority(db: Session, *, rule_key: str, actor_user_id: int | None) -> HermesLongTermRule:
    rule = db.query(HermesLongTermRule).filter(HermesLongTermRule.rule_key == rule_key).one()
    rule.status = 'lowered'
    rule.priority = max(int(rule.priority or 100), 100) + 100
    rule.confirmed_by_id = actor_user_id
    db.flush()
    return rule


def list_active_rules(db: Session) -> list[HermesLongTermRule]:
    return (
        db.query(HermesLongTermRule)
        .filter(HermesLongTermRule.status == 'active')
        .order_by(HermesLongTermRule.priority.asc(), HermesLongTermRule.id.asc())
        .all()
    )
```

- [ ] **Step 6: Run tests**

```powershell
python -m pytest backend/tests/test_hermes_long_term_rule_service.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/hermes/Soul.md backend/app/services/hermes_soul_service.py backend/app/services/hermes_long_term_rule_service.py backend/tests/test_hermes_long_term_rule_service.py
git commit -m "feat: add Hermes soul and long-term rules"
```

---

## Task 4: Natural-Language Intent Classification

**Files:**
- Create: `backend/app/services/hermes_factory_brain_types.py`
- Create: `backend/app/services/hermes_factory_brain_intent_service.py`
- Test: `backend/tests/test_hermes_factory_brain_intent_service.py`

- [ ] **Step 1: Write failing intent tests**

Create `backend/tests/test_hermes_factory_brain_intent_service.py`:

```python
from datetime import date

from app.services.hermes_factory_brain_intent_service import classify_factory_brain_intent


def test_classifies_daily_report_task() -> None:
    result = classify_factory_brain_intent('生成 6月19日正式日报', today=date(2026, 6, 25))

    assert result.intent_type == 'task_instruction'
    assert result.task_type == 'daily_report'
    assert result.business_date == date(2026, 6, 19)
    assert result.should_use_factory_brain is True


def test_classifies_anomaly_analysis_task() -> None:
    result = classify_factory_brain_intent('2050 今天电耗为什么高？', today=date(2026, 6, 25))

    assert result.intent_type == 'task_instruction'
    assert result.task_type == 'anomaly_analysis'
    assert result.domain == 'process_quality'
    assert result.entities['workshop'] == '2050'
    assert result.business_date == date(2026, 6, 25)


def test_classifies_business_question() -> None:
    result = classify_factory_brain_intent('今天生产和发货有没有影响合同交付？', today=date(2026, 6, 25))

    assert result.intent_type == 'task_instruction'
    assert result.task_type == 'business_question'
    assert result.domain == 'operations'


def test_classifies_contextual_short_query() -> None:
    result = classify_factory_brain_intent('产量出来了吗', today=date(2026, 6, 25))

    assert result.intent_type == 'contextual_intent'
    assert result.task_type == 'production_readiness'


def test_classifies_rule_management() -> None:
    result = classify_factory_brain_intent('以后日报先看专项责任人发的钉钉文件', today=date(2026, 6, 25))

    assert result.intent_type == 'long_term_rule'
    assert result.task_type == 'rule_management'


def test_falls_back_for_unrelated_text() -> None:
    result = classify_factory_brain_intent('随便聊两句', today=date(2026, 6, 25))

    assert result.intent_type == 'general_chat'
    assert result.should_use_factory_brain is True
```

- [ ] **Step 2: Run failing tests**

```powershell
python -m pytest backend/tests/test_hermes_factory_brain_intent_service.py -q
```

Expected: fail because service does not exist.

- [ ] **Step 3: Add shared types**

Create `backend/app/services/hermes_factory_brain_types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True, slots=True)
class FactoryBrainIntent:
    intent_type: str
    task_type: str
    domain: str
    business_date: date | None
    entities: dict[str, Any] = field(default_factory=dict)
    should_use_factory_brain: bool = True
    requires_root_owner: bool = False
```

- [ ] **Step 4: Implement deterministic classifier**

Create `backend/app/services/hermes_factory_brain_intent_service.py`:

```python
from __future__ import annotations

import re
from datetime import date

from app.services.hermes_factory_brain_types import FactoryBrainIntent


def classify_factory_brain_intent(text: str, *, today: date) -> FactoryBrainIntent:
    clean = str(text or '').strip()
    business_date = _extract_business_date(clean, today=today)

    if _looks_like_long_term_rule(clean):
        return FactoryBrainIntent(
            intent_type='long_term_rule',
            task_type='rule_management',
            domain='governance',
            business_date=business_date,
            requires_root_owner=True,
        )
    if '日报' in clean:
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='daily_report',
            domain='production',
            business_date=business_date,
            requires_root_owner=True,
        )
    if any(token in clean for token in ('为什么高', '异常', '电耗', '气耗', '成品率')):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='anomaly_analysis',
            domain='process_quality',
            business_date=business_date,
            entities=_extract_entities(clean),
        )
    if any(token in clean for token in ('合同', '发货', '库存', '交付')):
        return FactoryBrainIntent(
            intent_type='task_instruction',
            task_type='business_question',
            domain='operations',
            business_date=business_date,
        )
    if clean in {'在干嘛', '你在干嘛'}:
        return FactoryBrainIntent(
            intent_type='contextual_intent',
            task_type='current_status',
            domain='general',
            business_date=business_date,
        )
    if '产量' in clean and any(token in clean for token in ('出来', '有了吗', '了吗')):
        return FactoryBrainIntent(
            intent_type='contextual_intent',
            task_type='production_readiness',
            domain='production',
            business_date=business_date,
        )
    return FactoryBrainIntent(
        intent_type='general_chat',
        task_type='conversation',
        domain='general',
        business_date=business_date,
    )


def _looks_like_long_term_rule(text: str) -> bool:
    return any(token in text for token in ('以后', '记住', '长期规则', '作为规则', '不要记住', '临时口径'))


def _extract_business_date(text: str, *, today: date) -> date:
    match = re.search(r'(\d{1,2})月(\d{1,2})日', text)
    if match:
        return date(today.year, int(match.group(1)), int(match.group(2)))
    if '昨天' in text or '昨日' in text:
        from datetime import timedelta

        return today - timedelta(days=1)
    return today


def _extract_entities(text: str) -> dict[str, str]:
    entities: dict[str, str] = {}
    workshop = re.search(r'(1650|1850|2050)', text)
    if workshop:
        entities['workshop'] = workshop.group(1)
    if '电耗' in text:
        entities['metric'] = 'electricity_per_ton'
    if '气耗' in text:
        entities['metric'] = 'gas_per_ton'
    return entities
```

- [ ] **Step 5: Run intent tests**

```powershell
python -m pytest backend/tests/test_hermes_factory_brain_intent_service.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/hermes_factory_brain_types.py backend/app/services/hermes_factory_brain_intent_service.py backend/tests/test_hermes_factory_brain_intent_service.py
git commit -m "feat: classify Hermes factory brain intents"
```

---

## Task 5: DingTalk Four-Condition Sampling

**Files:**
- Create: `backend/app/services/hermes_dingtalk_sampling_service.py`
- Test: `backend/tests/test_hermes_dingtalk_sampling_service.py`

- [ ] **Step 1: Write failing sampling tests**

Create `backend/tests/test_hermes_dingtalk_sampling_service.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.agent_communication import MultimodalEvidence
from app.models.base import Base
from app.models.hermes_factory_brain import HermesDingTalkSamplingRule
from app.services.hermes_dingtalk_sampling_service import sample_dingtalk_message


def _db() -> Session:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_four_conditions_promote_specialist_file_to_high_priority_evidence() -> None:
    db = _db()
    db.add(
        HermesDingTalkSamplingRule(
            rule_key='daily-production',
            channel_key='cid-production',
            specialist_user_id='dt-output-owner',
            content_types=['production_table'],
            time_window_payload={'mode': 'recent_days', 'days': 30},
            priority='high',
            status='active',
            created_by_id=1,
        )
    )
    db.commit()

    result = sample_dingtalk_message(
        db,
        channel_key='cid-production',
        sender_user_id='dt-output-owner',
        message_text='每日产量表已发',
        file_name='每日产量.xlsx',
        message_time=datetime(2026, 6, 25, 8, 10, tzinfo=timezone.utc),
        content_type='production_table',
        trace_id='trace-sampling-001',
    )
    db.commit()

    assert result.matched is True
    assert result.priority == 'high'
    evidence = db.query(MultimodalEvidence).one()
    assert evidence.evidence_type == 'dingtalk_file'
    assert evidence.payload['sampling_priority'] == 'high'


def test_missing_specialist_does_not_promote_to_high_priority() -> None:
    db = _db()
    db.add(
        HermesDingTalkSamplingRule(
            rule_key='daily-production',
            channel_key='cid-production',
            specialist_user_id='dt-output-owner',
            content_types=['production_table'],
            time_window_payload={'mode': 'recent_days', 'days': 30},
            priority='high',
            status='active',
            created_by_id=1,
        )
    )
    db.commit()

    result = sample_dingtalk_message(
        db,
        channel_key='cid-production',
        sender_user_id='dt-other-user',
        message_text='每日产量表已发',
        file_name='每日产量.xlsx',
        message_time=datetime(2026, 6, 25, 8, 10, tzinfo=timezone.utc),
        content_type='production_table',
        trace_id='trace-sampling-002',
    )

    assert result.matched is False
    assert result.priority == 'low'
    assert db.query(MultimodalEvidence).count() == 0
```

- [ ] **Step 2: Run failing sampling tests**

```powershell
python -m pytest backend/tests/test_hermes_dingtalk_sampling_service.py -q
```

Expected: fail because service does not exist.

- [ ] **Step 3: Implement sampling service**

Create `backend/app/services/hermes_dingtalk_sampling_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from sqlalchemy.orm import Session

from app.core.redaction import redact_secret_text
from app.models.agent_communication import MultimodalEvidence
from app.models.hermes_factory_brain import HermesDingTalkSamplingRule


@dataclass(frozen=True, slots=True)
class DingTalkSamplingResult:
    matched: bool
    priority: str
    evidence_id: int | None
    rule_key: str | None


def sample_dingtalk_message(
    db: Session,
    *,
    channel_key: str,
    sender_user_id: str,
    message_text: str,
    file_name: str | None,
    message_time: datetime,
    content_type: str,
    trace_id: str,
) -> DingTalkSamplingResult:
    rule = (
        db.query(HermesDingTalkSamplingRule)
        .filter(
            HermesDingTalkSamplingRule.status == 'active',
            HermesDingTalkSamplingRule.channel_key == str(channel_key or '').strip(),
            HermesDingTalkSamplingRule.specialist_user_id == str(sender_user_id or '').strip(),
        )
        .order_by(HermesDingTalkSamplingRule.id.asc())
        .first()
    )
    if rule is None or content_type not in list(rule.content_types or []):
        return DingTalkSamplingResult(matched=False, priority='low', evidence_id=None, rule_key=None)

    payload = {
        'trace_id': trace_id,
        'channel_key': redact_secret_text(channel_key),
        'sender_user_id': redact_secret_text(sender_user_id),
        'message_time': message_time.isoformat(),
        'content_type': content_type,
        'file_name': redact_secret_text(file_name or ''),
        'file_hash': _hash_file_name(file_name),
        'sampling_rule_key': rule.rule_key,
        'sampling_priority': rule.priority,
        'time_window': rule.time_window_payload or {},
    }
    evidence = MultimodalEvidence(
        evidence_type='dingtalk_file' if file_name else 'dingtalk_text',
        recognized_text=redact_secret_text(message_text),
        confirmation_status='specialist_sampled',
        payload=payload,
    )
    db.add(evidence)
    db.flush()
    return DingTalkSamplingResult(matched=True, priority=rule.priority, evidence_id=evidence.id, rule_key=rule.rule_key)


def _hash_file_name(file_name: str | None) -> str | None:
    clean = str(file_name or '').strip()
    if not clean:
        return None
    return sha256(clean.encode('utf-8')).hexdigest()
```

- [ ] **Step 4: Run sampling tests**

```powershell
python -m pytest backend/tests/test_hermes_dingtalk_sampling_service.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/hermes_dingtalk_sampling_service.py backend/tests/test_hermes_dingtalk_sampling_service.py
git commit -m "feat: sample authorized DingTalk evidence"
```

---

## Task 6: Routed RAG Knowledge Units

**Files:**
- Create: `backend/app/services/hermes_rag_router_service.py`
- Modify: `backend/app/services/hermes_rag_service.py`
- Test: `backend/tests/test_hermes_rag_router_service.py`

- [ ] **Step 1: Write failing RAG router tests**

Create `backend/tests/test_hermes_rag_router_service.py`:

```python
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.hermes_factory_brain import HermesKnowledgeUnit
from app.services.hermes_rag_router_service import route_knowledge_request


def _db() -> Session:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_routes_2050_electricity_question_to_metric_process_case_units() -> None:
    db = _db()
    db.add_all(
        [
            HermesKnowledgeUnit(
                unit_key='metric-electricity-per-ton',
                layer='field',
                unit_type='metric',
                title='吨电耗定义',
                content='吨电耗 = 用电量 / 对应产量。',
                status='active',
            ),
            HermesKnowledgeUnit(
                unit_key='process-cold-rolling',
                layer='general_industry',
                unit_type='process',
                title='冷轧工艺',
                content='冷轧会受压下率、道次、退火状态影响。',
                status='active',
            ),
            HermesKnowledgeUnit(
                unit_key='case-2050-high-energy',
                layer='site_case',
                unit_type='case',
                title='2050 吨电耗异常案例',
                content='2050 吨电耗异常时先核对产量分母、开机时间和停机说明。',
                status='active',
            ),
        ]
    )
    db.commit()

    result = route_knowledge_request(db, query='2050 今天吨电耗为什么高？', business_date=date(2026, 6, 25))

    assert result.domain == 'process_quality'
    assert result.object_key == '2050'
    assert result.metric == 'electricity_per_ton'
    assert [item.unit_type for item in result.units] == ['metric', 'process', 'case']


def test_daily_dynamic_numbers_are_not_returned_as_knowledge() -> None:
    db = _db()
    db.add(
        HermesKnowledgeUnit(
            unit_key='bad-daily-number',
            layer='site_case',
            unit_type='daily_fact',
            title='6月19日总产量',
            content='6月19日总产量 366 吨。',
            status='active',
        )
    )
    db.commit()

    result = route_knowledge_request(db, query='今天总产量是多少？', business_date=date(2026, 6, 25))

    assert result.units == []
    assert result.excluded_units[0].unit_type == 'daily_fact'
```

- [ ] **Step 2: Run failing RAG tests**

```powershell
python -m pytest backend/tests/test_hermes_rag_router_service.py -q
```

Expected: fail because service does not exist.

- [ ] **Step 3: Implement RAG router**

Create `backend/app/services/hermes_rag_router_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models.hermes_factory_brain import HermesKnowledgeUnit


@dataclass(frozen=True, slots=True)
class RoutedKnowledgeResult:
    domain: str
    object_key: str | None
    metric: str | None
    knowledge_types: list[str]
    units: list[HermesKnowledgeUnit]
    excluded_units: list[HermesKnowledgeUnit]


def route_knowledge_request(db: Session, *, query: str, business_date: date) -> RoutedKnowledgeResult:
    clean = str(query or '').strip()
    object_key = _object_key(clean)
    metric = _metric(clean)
    domain = _domain(clean, metric)
    knowledge_types = _knowledge_types(clean, metric)
    rows = (
        db.query(HermesKnowledgeUnit)
        .filter(HermesKnowledgeUnit.status == 'active')
        .order_by(HermesKnowledgeUnit.id.asc())
        .all()
    )
    excluded = [row for row in rows if row.unit_type == 'daily_fact']
    allowed = [
        row
        for row in rows
        if row.unit_type in knowledge_types and row.unit_type != 'daily_fact' and _matches(row, clean, object_key, metric)
    ]
    return RoutedKnowledgeResult(
        domain=domain,
        object_key=object_key,
        metric=metric,
        knowledge_types=knowledge_types,
        units=allowed,
        excluded_units=excluded,
    )


def _object_key(text: str) -> str | None:
    for value in ('1650', '1850', '2050'):
        if value in text:
            return value
    return None


def _metric(text: str) -> str | None:
    if '吨电耗' in text or '电耗' in text:
        return 'electricity_per_ton'
    if '气耗' in text:
        return 'gas_per_ton'
    if '成品率' in text:
        return 'yield_rate'
    return None


def _domain(text: str, metric: str | None) -> str:
    if metric or any(token in text for token in ('工艺', '质量', '异常')):
        return 'process_quality'
    if any(token in text for token in ('合同', '发货', '库存', '交付')):
        return 'operations'
    return 'production'


def _knowledge_types(text: str, metric: str | None) -> list[str]:
    types: list[str] = []
    if metric:
        types.append('metric')
    if any(token in text for token in ('2050', '1850', '1650', '冷轧', '热轧', '退火')):
        types.append('process')
    if any(token in text for token in ('为什么', '异常', '高', '低')):
        types.append('case')
    return types or ['rule', 'field', 'output_format']


def _matches(unit: HermesKnowledgeUnit, text: str, object_key: str | None, metric: str | None) -> bool:
    haystack = f'{unit.title}\n{unit.content}'
    if unit.unit_type == 'metric' and metric == 'electricity_per_ton' and '电耗' in haystack:
        return True
    if unit.unit_type == 'process' and any(token in haystack for token in ('冷轧', object_key or '')):
        return True
    if unit.unit_type == 'case' and (object_key is None or object_key in haystack):
        return True
    return any(token in haystack for token in text.split() if token)
```

- [ ] **Step 4: Run RAG router tests**

```powershell
python -m pytest backend/tests/test_hermes_rag_router_service.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/hermes_rag_router_service.py backend/tests/test_hermes_rag_router_service.py
git commit -m "feat: route Hermes RAG by knowledge type"
```

---

## Task 7: Fact Priority and Visible Conflict Decisions

**Files:**
- Create: `backend/app/services/hermes_fact_priority_service.py`
- Test: `backend/tests/test_hermes_fact_priority_service.py`

- [ ] **Step 1: Write failing conflict tests**

Create `backend/tests/test_hermes_fact_priority_service.py`:

```python
from app.services.hermes_fact_priority_service import choose_fact_value


def test_root_owner_value_wins_over_all_sources() -> None:
    result = choose_fact_value(
        field_key='total_output_daily',
        candidates=[
            {'source_type': 'mes_wms', 'value': 359.8, 'source_label': 'MES'},
            {'source_type': 'hub', 'value': 361.0, 'source_label': '数据中枢'},
            {'source_type': 'dingtalk_specialist', 'value': 366.0, 'source_label': '每日产量.xlsx'},
            {'source_type': 'root_owner', 'value': 367.0, 'source_label': '张兆嘉确认'},
        ],
    )

    assert result.value == 367.0
    assert result.source_type == 'root_owner'
    assert len(result.conflicts) == 3
    assert '采用 root_owner 来源' in result.reason


def test_dingtalk_specialist_wins_over_hub_and_mes_with_visible_conflicts() -> None:
    result = choose_fact_value(
        field_key='total_output_daily',
        candidates=[
            {'source_type': 'mes_wms', 'value': 359.8, 'source_label': 'MES'},
            {'source_type': 'hub', 'value': 361.0, 'source_label': '数据中枢'},
            {'source_type': 'dingtalk_specialist', 'value': 366.0, 'source_label': '每日产量.xlsx'},
        ],
    )

    assert result.value == 366.0
    assert result.source_type == 'dingtalk_specialist'
    assert [item['value'] for item in result.conflicts] == [359.8, 361.0]
    assert result.suggested_action == 'mark_hub_field_for_review'


def test_rag_is_never_current_fact_source() -> None:
    result = choose_fact_value(
        field_key='total_output_daily',
        candidates=[
            {'source_type': 'rag', 'value': 366.0, 'source_label': '历史案例'},
        ],
    )

    assert result.value is None
    assert result.status == 'missing_current_fact'
```

- [ ] **Step 2: Run failing conflict tests**

```powershell
python -m pytest backend/tests/test_hermes_fact_priority_service.py -q
```

Expected: fail because service does not exist.

- [ ] **Step 3: Implement priority service**

Create `backend/app/services/hermes_fact_priority_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PRIORITY = {
    'root_owner': 1,
    'dingtalk_specialist': 2,
    'hub': 3,
    'mes_wms': 4,
    'rag': 99,
    'history_report': 99,
    'output_skill': 99,
}


@dataclass(frozen=True, slots=True)
class FactDecision:
    field_key: str
    value: Any
    source_type: str | None
    source_label: str | None
    status: str
    conflicts: list[dict[str, Any]]
    reason: str
    suggested_action: str | None


def choose_fact_value(field_key: str, candidates: list[dict[str, Any]]) -> FactDecision:
    current_candidates = [
        item
        for item in candidates
        if item.get('source_type') not in {'rag', 'history_report', 'output_skill'}
    ]
    if not current_candidates:
        return FactDecision(
            field_key=field_key,
            value=None,
            source_type=None,
            source_label=None,
            status='missing_current_fact',
            conflicts=[],
            reason='RAG、历史日报和输出 skill 不能作为当前事实来源。',
            suggested_action='collect_current_fact',
        )
    ranked = sorted(current_candidates, key=lambda item: PRIORITY.get(str(item.get('source_type')), 50))
    selected = ranked[0]
    conflicts = [
        {
            'source_type': item.get('source_type'),
            'source_label': item.get('source_label'),
            'value': item.get('value'),
        }
        for item in ranked[1:]
        if item.get('value') != selected.get('value')
    ]
    source_type = str(selected.get('source_type'))
    suggested_action = 'mark_hub_field_for_review' if source_type == 'dingtalk_specialist' and conflicts else None
    return FactDecision(
        field_key=field_key,
        value=selected.get('value'),
        source_type=source_type,
        source_label=selected.get('source_label'),
        status='selected_with_conflicts' if conflicts else 'selected',
        conflicts=conflicts,
        reason=f'采用 {source_type} 来源，按日报事实优先级选择。',
        suggested_action=suggested_action,
    )
```

- [ ] **Step 4: Run conflict tests**

```powershell
python -m pytest backend/tests/test_hermes_fact_priority_service.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/hermes_fact_priority_service.py backend/tests/test_hermes_fact_priority_service.py
git commit -m "feat: choose Hermes facts with visible conflicts"
```

---

## Task 8: LangChain Tool Registry and Model Degradation

**Files:**
- Create: `backend/app/services/hermes_langchain_model.py`
- Create: `backend/app/services/hermes_langchain_tools.py`
- Test: `backend/tests/test_hermes_langchain_tools.py`

- [ ] **Step 1: Write failing LangChain tests**

Create `backend/tests/test_hermes_langchain_tools.py`:

```python
import httpx

from app.services.hermes_langchain_model import FactoryBrainModelUnavailable, invoke_factory_brain_model
from app.services.hermes_langchain_tools import HermesToolAdapters, build_tool_registry, require_tool


def _fake_tool(**kwargs: object) -> dict[str, object]:
    return {'status': 'ok', 'request': kwargs}


def test_tool_registry_exposes_only_allowed_tools() -> None:
    adapters = HermesToolAdapters(
        hub_query=_fake_tool,
        mes_wms_read=_fake_tool,
        dingtalk_evidence=_fake_tool,
        rag_route=_fake_tool,
        history_report=_fake_tool,
        output_skill_alignment=_fake_tool,
        long_term_rules=_fake_tool,
        codex_construction=_fake_tool,
    )
    registry = build_tool_registry(adapters)

    assert set(registry.keys()) == {
        'hub_query',
        'mes_wms_read',
        'dingtalk_evidence',
        'rag_route',
        'history_report',
        'output_skill_alignment',
        'long_term_rules',
        'codex_construction',
    }
    assert require_tool('hub_query', registry)(business_date='2026-06-25')['status'] == 'ok'


def test_model_401_becomes_degraded_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={'error': {'message': 'Codex token refresh failed with status 401'}})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    try:
        invoke_factory_brain_model(
            messages=[{'role': 'user', 'content': '在干嘛'}],
            api_base='https://example.invalid',
            api_key='expired',
            model='codex-temp',
            client=client,
        )
    except FactoryBrainModelUnavailable as exc:
        assert exc.user_message == '模型服务暂不可用，Hermes 已降级为只读数据查询模式。'
    else:
        raise AssertionError('expected FactoryBrainModelUnavailable')
```

- [ ] **Step 2: Run failing tests**

```powershell
python -m pytest backend/tests/test_hermes_langchain_tools.py -q
```

Expected: fail because services do not exist.

- [ ] **Step 3: Implement model degradation wrapper**

Create `backend/app/services/hermes_langchain_model.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class FactoryBrainModelUnavailable(RuntimeError):
    user_message: str
    cause: str


def invoke_factory_brain_model(
    *,
    messages: list[dict[str, str]],
    api_base: str,
    api_key: str,
    model: str,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    payload = {'model': model, 'messages': messages, 'temperature': 0.2}
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    url = f'{api_base.rstrip("/")}/chat/completions'
    http_client = client or httpx.Client(timeout=20)
    try:
        response = http_client.post(url, json=payload, headers=headers)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise FactoryBrainModelUnavailable(
                user_message='模型服务暂不可用，Hermes 已降级为只读数据查询模式。',
                cause='model_auth_401',
            ) from exc
        raise
    return response.json()
```

- [ ] **Step 4: Implement tool registry**

Create `backend/app/services/hermes_langchain_tools.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping


ToolCallable = Callable[..., object]


@dataclass(frozen=True, slots=True)
class HermesToolAdapters:
    hub_query: ToolCallable
    mes_wms_read: ToolCallable
    dingtalk_evidence: ToolCallable
    rag_route: ToolCallable
    history_report: ToolCallable
    output_skill_alignment: ToolCallable
    long_term_rules: ToolCallable
    codex_construction: ToolCallable


def build_tool_registry(adapters: HermesToolAdapters) -> dict[str, ToolCallable]:
    return {
        'hub_query': adapters.hub_query,
        'mes_wms_read': adapters.mes_wms_read,
        'dingtalk_evidence': adapters.dingtalk_evidence,
        'rag_route': adapters.rag_route,
        'history_report': adapters.history_report,
        'output_skill_alignment': adapters.output_skill_alignment,
        'long_term_rules': adapters.long_term_rules,
        'codex_construction': adapters.codex_construction,
    }


def require_tool(name: str, registry: Mapping[str, ToolCallable]) -> ToolCallable:
    if name not in registry:
        raise ValueError(f'unregistered_hermes_tool:{name}')
    return registry[name]
```

- [ ] **Step 5: Run LangChain tests**

```powershell
python -m pytest backend/tests/test_hermes_langchain_tools.py -q
```

Expected: pass.

- [ ] **Step 6: Confirm production adapter task boundary**

Task 14 creates `build_production_tool_adapters(...)` and passes those adapters into `build_tool_registry(...)`. This task only establishes the typed registry contract and the model degradation wrapper.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/services/hermes_langchain_model.py backend/app/services/hermes_langchain_tools.py backend/tests/test_hermes_langchain_tools.py
git commit -m "feat: add Hermes LangChain tool registry"
```

---

## Task 9: LangGraph StateGraph and Postgres Checkpoint Setup

**Files:**
- Create: `backend/app/services/hermes_langgraph_app.py`
- Create: `backend/scripts/setup_langgraph_checkpoint.py`
- Test: `backend/tests/test_hermes_langgraph_app.py`

- [ ] **Step 1: Write failing LangGraph tests**

Create `backend/tests/test_hermes_langgraph_app.py`:

```python
from app.services.hermes_langgraph_app import build_factory_brain_graph, initial_factory_brain_state


def test_initial_state_records_input_and_trace() -> None:
    state = initial_factory_brain_state(
        trace_id='trace-graph-001',
        text='产量出来了吗',
        actor_user_id=1,
        channel='dingtalk_group',
    )

    assert state['trace_id'] == 'trace-graph-001'
    assert state['input_text'] == '产量出来了吗'
    assert state['state_trace'][0] == 'received'


def test_graph_runs_to_replied_with_stub_nodes() -> None:
    graph = build_factory_brain_graph(checkpointer=None)
    state = initial_factory_brain_state(
        trace_id='trace-graph-002',
        text='产量出来了吗',
        actor_user_id=1,
        channel='dingtalk_group',
    )

    result = graph.invoke(state)

    assert result['status'] == 'replied'
    assert result['state_trace'][-1] == 'reply_to_dingtalk'
    assert 'Hermes 已收到' in result['response_text']
```

- [ ] **Step 2: Run failing graph tests**

```powershell
python -m pytest backend/tests/test_hermes_langgraph_app.py -q
```

Expected: fail because graph service does not exist.

- [ ] **Step 3: Implement graph app**

Create `backend/app/services/hermes_langgraph_app.py`:

```python
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph


class FactoryBrainState(TypedDict, total=False):
    trace_id: str
    input_text: str
    actor_user_id: int | None
    channel: str
    status: str
    intent: dict[str, Any]
    tool_trace: list[dict[str, Any]]
    state_trace: list[str]
    response_text: str


def initial_factory_brain_state(*, trace_id: str, text: str, actor_user_id: int | None, channel: str) -> FactoryBrainState:
    return {
        'trace_id': trace_id,
        'input_text': text,
        'actor_user_id': actor_user_id,
        'channel': channel,
        'status': 'received',
        'tool_trace': [],
        'state_trace': ['received'],
    }


def build_factory_brain_graph(*, checkpointer: object | None):
    builder = StateGraph(FactoryBrainState)
    builder.add_node('identify_actor', _identify_actor)
    builder.add_node('classify_intent', _classify_intent)
    builder.add_node('load_soul_rules_knowledge', _load_soul_rules_knowledge)
    builder.add_node('plan_task', _plan_task)
    builder.add_node('route_tools', _route_tools)
    builder.add_node('collect_evidence', _collect_evidence)
    builder.add_node('reason_about_conflicts', _reason_about_conflicts)
    builder.add_node('generate_response', _generate_response)
    builder.add_node('persist_memory_and_audit', _persist_memory_and_audit)
    builder.add_node('reply_to_dingtalk', _reply_to_dingtalk)
    builder.add_edge(START, 'identify_actor')
    builder.add_edge('identify_actor', 'classify_intent')
    builder.add_edge('classify_intent', 'load_soul_rules_knowledge')
    builder.add_edge('load_soul_rules_knowledge', 'plan_task')
    builder.add_edge('plan_task', 'route_tools')
    builder.add_edge('route_tools', 'collect_evidence')
    builder.add_edge('collect_evidence', 'reason_about_conflicts')
    builder.add_edge('reason_about_conflicts', 'generate_response')
    builder.add_edge('generate_response', 'persist_memory_and_audit')
    builder.add_edge('persist_memory_and_audit', 'reply_to_dingtalk')
    builder.add_edge('reply_to_dingtalk', END)
    return builder.compile(checkpointer=checkpointer)


def _advance(state: FactoryBrainState, node: str, **extra: Any) -> FactoryBrainState:
    return {
        **state,
        **extra,
        'state_trace': [*list(state.get('state_trace') or []), node],
    }


def _identify_actor(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'identify_actor', status='identified_actor')


def _classify_intent(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'classify_intent', intent={'intent_type': 'contextual_intent'})


def _load_soul_rules_knowledge(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'load_soul_rules_knowledge')


def _plan_task(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'plan_task')


def _route_tools(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'route_tools', tool_trace=[{'tool': 'hub_query', 'status': 'planned'}])


def _collect_evidence(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'collect_evidence')


def _reason_about_conflicts(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'reason_about_conflicts')


def _generate_response(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'generate_response', response_text='Hermes 已收到，我正在按工厂大脑链路处理。')


def _persist_memory_and_audit(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'persist_memory_and_audit')


def _reply_to_dingtalk(state: FactoryBrainState) -> FactoryBrainState:
    return _advance(state, 'reply_to_dingtalk', status='replied')
```

- [ ] **Step 4: Add checkpoint setup script**

Create `backend/scripts/setup_langgraph_checkpoint.py`:

```python
from __future__ import annotations

from langgraph.checkpoint.postgres import PostgresSaver

from app.config import settings


def main() -> None:
    db_uri = str(settings.DATABASE_URL)
    with PostgresSaver.from_conn_string(db_uri) as checkpointer:
        checkpointer.setup()
    print('langgraph checkpoint schema ready')


if __name__ == '__main__':
    main()
```

- [ ] **Step 5: Run graph tests**

```powershell
python -m pytest backend/tests/test_hermes_langgraph_app.py -q
```

Expected: pass.

- [ ] **Step 6: Run checkpoint script in a development Postgres environment**

Do not run this against SQLite.

```powershell
cd backend
python scripts/setup_langgraph_checkpoint.py
```

Expected: `langgraph checkpoint schema ready`.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/services/hermes_langgraph_app.py backend/scripts/setup_langgraph_checkpoint.py backend/tests/test_hermes_langgraph_app.py
git commit -m "feat: add Hermes LangGraph backbone"
```

---

## Task 10: Orchestrator and AgentRun Persistence

**Files:**
- Create: `backend/app/services/hermes_factory_brain_orchestrator.py`
- Test: `backend/tests/test_hermes_factory_brain_orchestrator.py`

- [ ] **Step 1: Write failing orchestrator tests**

Create `backend/tests/test_hermes_factory_brain_orchestrator.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.base import Base
from app.models.system import User
from app.services.hermes_factory_brain_orchestrator import run_factory_brain_turn


def _db() -> Session:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_orchestrator_persists_inbox_and_agent_run() -> None:
    db = _db()
    user = User(id=1, username='admin', password_hash='x', name='张兆嘉', role='admin', is_active=True)
    db.add(user)
    db.commit()

    result = run_factory_brain_turn(
        db,
        text='产量出来了吗',
        channel='dingtalk_group',
        group_id='cid-root',
        sender_external_id='dt-root',
        current_user=user,
        trace_id='trace-factory-brain-001',
        source_payload={'messageId': 'msg-001'},
    )
    db.commit()

    assert result.trace_id == 'trace-factory-brain-001'
    assert result.status == 'replied'
    assert db.query(ChatInboxMessage).one().text == '产量出来了吗'
    run = db.query(AgentRun).one()
    assert run.result_payload['factory_brain']['state_trace'][-1] == 'reply_to_dingtalk'
```

- [ ] **Step 2: Run failing orchestrator tests**

```powershell
python -m pytest backend/tests/test_hermes_factory_brain_orchestrator.py -q
```

Expected: fail because orchestrator does not exist.

- [ ] **Step 3: Implement orchestrator**

Create `backend/app/services/hermes_factory_brain_orchestrator.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.redaction import filter_sensitive_mapping
from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.system import User
from app.services.hermes_langgraph_app import build_factory_brain_graph, initial_factory_brain_state


@dataclass(frozen=True, slots=True)
class FactoryBrainTurnResult:
    trace_id: str
    status: str
    answer: str
    chat_inbox_id: int
    agent_run_id: int
    result_payload: dict[str, Any]


def run_factory_brain_turn(
    db: Session,
    *,
    text: str,
    channel: str,
    group_id: str | None,
    sender_external_id: str | None,
    current_user: User,
    trace_id: str | None,
    source_payload: dict[str, Any] | None,
) -> FactoryBrainTurnResult:
    clean_trace_id = str(trace_id or '').strip() or uuid4().hex
    clean_text = str(text or '').strip()
    inbox = ChatInboxMessage(
        channel=str(channel or '').strip() or 'internal',
        group_id=str(group_id or '').strip() or None,
        sender_external_id=str(sender_external_id or '').strip() or None,
        text=clean_text,
        agent_code='factory_brain',
        trace_id=clean_trace_id,
        source_payload=filter_sensitive_mapping(source_payload or {}),
    )
    db.add(inbox)
    db.flush()

    graph = build_factory_brain_graph(checkpointer=None)
    state = initial_factory_brain_state(
        trace_id=clean_trace_id,
        text=clean_text,
        actor_user_id=getattr(current_user, 'id', None),
        channel=inbox.channel,
    )
    graph_result = graph.invoke(state)
    answer = str(graph_result.get('response_text') or 'Hermes 已收到。')
    result_payload = {
        'factory_brain': {
            'status': graph_result.get('status'),
            'state_trace': graph_result.get('state_trace') or [],
            'tool_trace': graph_result.get('tool_trace') or [],
            'intent': graph_result.get('intent') or {},
        }
    }
    run = AgentRun(
        trace_id=clean_trace_id,
        agent_code='factory_brain',
        chat_inbox_id=inbox.id,
        status='answered',
        status_color='green',
        answer=answer,
        rag_citation_count=0,
        result_payload=result_payload,
    )
    db.add(run)
    db.flush()
    return FactoryBrainTurnResult(
        trace_id=clean_trace_id,
        status=str(graph_result.get('status') or 'replied'),
        answer=answer,
        chat_inbox_id=inbox.id,
        agent_run_id=run.id,
        result_payload=result_payload,
    )
```

- [ ] **Step 4: Run orchestrator tests**

```powershell
python -m pytest backend/tests/test_hermes_factory_brain_orchestrator.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/hermes_factory_brain_orchestrator.py backend/tests/test_hermes_factory_brain_orchestrator.py
git commit -m "feat: persist Hermes factory brain turns"
```

---

## Task 11: DingTalk Inbound Factory Brain Lane

**Files:**
- Modify: `backend/app/routers/dingtalk.py`
- Modify: `backend/app/routers/hermes.py`
- Test: `backend/tests/test_dingtalk_factory_brain_inbound.py`

- [ ] **Step 1: Write failing route tests**

Create `backend/tests/test_dingtalk_factory_brain_inbound.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models.agent_communication import AgentRun, ChatInboxMessage
from app.models.base import Base
from app.models.system import User


def _install_db_override():
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine)

    def fake_get_db():
        yield db

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = fake_get_db
    return db, previous


def _restore(previous, db: Session) -> None:
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)
    db.close()


def test_dingtalk_inbound_uses_factory_brain_when_enabled(monkeypatch) -> None:
    db, previous = _install_db_override()
    db.add(
        User(
            id=1,
            username='root-owner',
            password_hash='x',
            name='张兆嘉',
            role='admin',
            is_admin=True,
            is_active=True,
            dingtalk_user_id='dt-root',
            dingtalk_union_id='union-root',
        )
    )
    db.commit()
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_FACTORY_BRAIN_ENABLED', True, raising=False)
    monkeypatch.setattr('app.routers.dingtalk.settings.HERMES_DINGTALK_INBOUND_TOKEN', 'hermes-token', raising=False)

    try:
        client = TestClient(app)
        response = client.post(
            '/api/v1/dingtalk/agent-inbound',
            headers={'x-dingtalk-inbound-token': 'hermes-token'},
            json={
                'conversationId': 'cid-root',
                'senderStaffId': 'dt-root',
                'senderUnionId': 'union-root',
                'text': {'content': '产量出来了吗'},
                'agentCode': 'factory_dispatch',
                'traceId': 'trace-dingtalk-factory-brain-001',
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['agent_code'] == 'factory_brain'
        assert payload['status'] == 'replied'
        assert db.query(ChatInboxMessage).one().agent_code == 'factory_brain'
        assert db.query(AgentRun).one().agent_code == 'factory_brain'
    finally:
        _restore(previous, db)
```

- [ ] **Step 2: Run failing route test**

```powershell
python -m pytest backend/tests/test_dingtalk_factory_brain_inbound.py -q
```

Expected: fail because DingTalk route does not call factory brain.

- [ ] **Step 3: Add route branch in dingtalk.py**

Modify `backend/app/routers/dingtalk.py` inside `dingtalk_agent_inbound`, after user resolution and before `handle_agent_command`:

```python
    if bool(getattr(settings, 'HERMES_FACTORY_BRAIN_ENABLED', False)):
        from app.services.hermes_factory_brain_orchestrator import run_factory_brain_turn

        try:
            factory_result = run_factory_brain_turn(
                db,
                text=text,
                channel='dingtalk_group',
                group_id=group_id,
                sender_external_id=_clean_text(_first_payload_value(payload, 'senderStaffId', 'senderId', 'senderUserId', 'userid', 'userId')),
                current_user=user,
                trace_id=trace_id,
                source_payload=payload,
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        return {
            'trace_id': factory_result.trace_id,
            'agent_code': 'factory_brain',
            'status': factory_result.status,
            'answer': factory_result.answer,
            'chat_inbox_id': factory_result.chat_inbox_id,
            'agent_run_id': factory_result.agent_run_id,
        }
```

Keep existing fallback path unchanged for `HERMES_FACTORY_BRAIN_ENABLED=false`.

- [ ] **Step 4: Add Hermes router status**

Modify `backend/app/routers/hermes.py`:

```python
from app.config import settings


@router.get('/factory-brain/status')
def hermes_factory_brain_status() -> dict[str, object]:
    return {
        'enabled': bool(settings.HERMES_FACTORY_BRAIN_ENABLED),
        'model_provider': settings.HERMES_FACTORY_BRAIN_MODEL_PROVIDER,
        'checkpoint_mode': settings.HERMES_LANGGRAPH_CHECKPOINT_MODE,
    }
```

- [ ] **Step 5: Run route tests**

```powershell
python -m pytest backend/tests/test_dingtalk_factory_brain_inbound.py backend/tests/test_dingtalk_agent_inbound_route.py -q
```

Expected: new test passes and existing DingTalk inbound tests still pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/routers/dingtalk.py backend/app/routers/hermes.py backend/tests/test_dingtalk_factory_brain_inbound.py
git commit -m "feat: route DingTalk messages to Hermes factory brain"
```

---

## Task 12: Codex Construction Service

**Files:**
- Create: `backend/app/services/hermes_codex_construction_service.py`
- Test: `backend/tests/test_hermes_codex_construction_service.py`

- [ ] **Step 1: Write failing construction tests**

Create `backend/tests/test_hermes_codex_construction_service.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.hermes_factory_brain import HermesCodexConstructionRun
from app.models.system import User
from app.services.hermes_codex_construction_service import request_codex_construction


def _db() -> Session:
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_root_owner_can_request_heavy_construction() -> None:
    db = _db()
    user = User(id=1, username='root', password_hash='x', name='张兆嘉', role='admin', is_admin=True, is_active=True)
    db.add(user)
    db.commit()

    result = request_codex_construction(
        db,
        actor=user,
        request_text='直接修好并部署',
        trace_id='trace-codex-heavy-001',
        construction_type='heavy',
    )
    db.commit()

    assert result.status == 'requested'
    assert db.query(HermesCodexConstructionRun).one().authorization_level == 'root_owner'


def test_non_root_owner_cannot_request_construction() -> None:
    db = _db()
    user = User(id=2, username='manager', password_hash='x', name='经理', role='manager', is_manager=True, is_active=True)
    db.add(user)
    db.commit()

    result = request_codex_construction(
        db,
        actor=user,
        request_text='帮我改代码',
        trace_id='trace-codex-denied-001',
        construction_type='light',
    )

    assert result.status == 'denied'
    assert db.query(HermesCodexConstructionRun).count() == 0
```

- [ ] **Step 2: Run failing construction tests**

```powershell
python -m pytest backend/tests/test_hermes_codex_construction_service.py -q
```

Expected: fail because service does not exist.

- [ ] **Step 3: Implement construction service**

Create `backend/app/services/hermes_codex_construction_service.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.redaction import redact_secret_text
from app.models.hermes_factory_brain import HermesCodexConstructionRun
from app.models.system import User


@dataclass(frozen=True, slots=True)
class CodexConstructionRequestResult:
    status: str
    run_id: int | None
    message: str


def request_codex_construction(
    db: Session,
    *,
    actor: User,
    request_text: str,
    trace_id: str,
    construction_type: str,
) -> CodexConstructionRequestResult:
    if not bool(getattr(actor, 'is_admin', False)):
        return CodexConstructionRequestResult(
            status='denied',
            run_id=None,
            message='只有 root_owner 可以触发 Codex 施工。',
        )
    run = HermesCodexConstructionRun(
        trace_id=trace_id,
        request_text=redact_secret_text(request_text),
        construction_type=construction_type,
        authorization_level='root_owner',
        status='requested',
        payload={
            'steps_required': ['plan', 'execute', 'test', 'deploy_or_report', 'rollback_note'],
            'construction_type': construction_type,
        },
        requested_by_id=actor.id,
    )
    db.add(run)
    db.flush()
    return CodexConstructionRequestResult(
        status='requested',
        run_id=run.id,
        message='Codex 施工请求已记录，等待执行器接管。',
    )
```

- [ ] **Step 4: Run construction tests**

```powershell
python -m pytest backend/tests/test_hermes_codex_construction_service.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/hermes_codex_construction_service.py backend/tests/test_hermes_codex_construction_service.py
git commit -m "feat: record root-owner Codex construction requests"
```

---

## Task 13: Acceptance Harness for Three Scenarios

**Files:**
- Create: `backend/app/services/hermes_factory_brain_harness.py`
- Create: `backend/scripts/hermes_factory_brain_cli.py`
- Test: `backend/tests/test_hermes_factory_brain_acceptance.py`

- [ ] **Step 1: Write failing acceptance tests**

Create `backend/tests/test_hermes_factory_brain_acceptance.py`:

```python
from app.services.hermes_factory_brain_harness import evaluate_factory_brain_response


def test_daily_report_acceptance_requires_conflicts_and_sources() -> None:
    result = evaluate_factory_brain_response(
        scenario='daily_report',
        response_text='工厂大脑判断单\n正式日报正文\n各车间明细\n数据来源：数据中枢、钉钉专项文件。\n冲突：总产量。',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok'},
            {'tool': 'dingtalk_evidence', 'status': 'ok'},
            {'tool': 'output_skill_alignment', 'status': 'ok'},
        ],
    )

    assert result.passed is True
    assert result.score >= 0.8


def test_anomaly_acceptance_requires_process_knowledge_and_current_fact() -> None:
    result = evaluate_factory_brain_response(
        scenario='anomaly_analysis',
        response_text='2050 吨电耗偏高。原因排序：产量分母、开机时间、停机说明。建议动作：核对班次。',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok'},
            {'tool': 'rag_route', 'status': 'ok', 'knowledge_types': ['metric', 'process', 'case']},
            {'tool': 'dingtalk_evidence', 'status': 'ok'},
        ],
    )

    assert result.passed is True


def test_business_question_acceptance_requires_contract_and_delivery() -> None:
    result = evaluate_factory_brain_response(
        scenario='business_question',
        response_text='今日生产和发货暂不影响合同交付。已核对生产、库存、发货、合同、余合同。',
        tool_trace=[
            {'tool': 'hub_query', 'status': 'ok', 'facts': ['production', 'inventory', 'delivery', 'contract']},
        ],
    )

    assert result.passed is True
```

- [ ] **Step 2: Run failing acceptance tests**

```powershell
python -m pytest backend/tests/test_hermes_factory_brain_acceptance.py -q
```

Expected: fail because harness service does not exist.

- [ ] **Step 3: Implement harness**

Create `backend/app/services/hermes_factory_brain_harness.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FactoryBrainHarnessResult:
    scenario: str
    passed: bool
    score: float
    missing: list[str]


def evaluate_factory_brain_response(
    *,
    scenario: str,
    response_text: str,
    tool_trace: list[dict[str, Any]],
) -> FactoryBrainHarnessResult:
    checks = _checks_for_scenario(scenario)
    missing = [item for item in checks if not _check(item, response_text, tool_trace)]
    score = round((len(checks) - len(missing)) / max(1, len(checks)), 4)
    return FactoryBrainHarnessResult(
        scenario=scenario,
        passed=score >= 0.8,
        score=score,
        missing=missing,
    )


def _checks_for_scenario(scenario: str) -> list[str]:
    if scenario == 'daily_report':
        return ['judgment', 'formal_report', 'workshop_detail', 'sources', 'conflicts', 'output_skill_alignment']
    if scenario == 'anomaly_analysis':
        return ['current_fact', 'process_knowledge', 'reason_order', 'suggested_action']
    if scenario == 'business_question':
        return ['production', 'inventory', 'delivery', 'contract']
    return ['response']


def _check(name: str, response_text: str, tool_trace: list[dict[str, Any]]) -> bool:
    if name == 'judgment':
        return '工厂大脑判断单' in response_text
    if name == 'formal_report':
        return '正式日报正文' in response_text
    if name == 'workshop_detail':
        return '各车间明细' in response_text
    if name == 'sources':
        return '数据来源' in response_text or any(item.get('tool') == 'dingtalk_evidence' for item in tool_trace)
    if name == 'conflicts':
        return '冲突' in response_text
    if name == 'output_skill_alignment':
        return any(item.get('tool') == 'output_skill_alignment' and item.get('status') == 'ok' for item in tool_trace)
    if name == 'current_fact':
        return any(item.get('tool') == 'hub_query' and item.get('status') == 'ok' for item in tool_trace)
    if name == 'process_knowledge':
        return any(item.get('tool') == 'rag_route' and 'process' in item.get('knowledge_types', []) for item in tool_trace)
    if name == 'reason_order':
        return '原因排序' in response_text
    if name == 'suggested_action':
        return '建议动作' in response_text
    if name in {'production', 'inventory', 'delivery', 'contract'}:
        return any(name in item.get('facts', []) for item in tool_trace)
    return bool(response_text.strip())
```

- [ ] **Step 4: Add smoke CLI**

Create `backend/scripts/hermes_factory_brain_cli.py`:

```python
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('scenario', choices=['daily_report', 'anomaly_analysis', 'business_question'])
    parser.add_argument('--text', required=True)
    args = parser.parse_args()
    print(f'Hermes factory brain smoke: scenario={args.scenario} text={args.text}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 5: Run acceptance tests and CLI smoke**

```powershell
python -m pytest backend/tests/test_hermes_factory_brain_acceptance.py -q
python backend/scripts/hermes_factory_brain_cli.py daily_report --text "生成 6月19日正式日报"
```

Expected:

```text
Hermes factory brain smoke: scenario=daily_report text=生成 6月19日正式日报
```

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/hermes_factory_brain_harness.py backend/scripts/hermes_factory_brain_cli.py backend/tests/test_hermes_factory_brain_acceptance.py
git commit -m "feat: add Hermes factory brain acceptance harness"
```

---

## Task 14: Wire Real Tool Adapters in Vertical Slices

**Files:**
- Modify: `backend/app/services/hermes_langchain_tools.py`
- Modify: `backend/app/services/hermes_langgraph_app.py`
- Test: existing tests plus new assertions in:
  - `backend/tests/test_hermes_langchain_tools.py`
  - `backend/tests/test_hermes_langgraph_app.py`
  - `backend/tests/test_hermes_factory_brain_acceptance.py`

- [ ] **Step 1: Add tests for production tool adapters**

Extend `backend/tests/test_hermes_langchain_tools.py`:

```python
from app.services.hermes_langchain_tools import build_production_tool_adapters


def test_hub_query_tool_returns_structured_payload(db_session) -> None:
    registry = build_tool_registry(build_production_tool_adapters(db_session))

    result = registry['hub_query'](business_date='2026-06-25', query_type='production')

    assert 'status' in result
    assert 'source' in result
    assert result['source'] == 'data_hub'
    assert 'request' in result
    assert 'facts' in result
```

- [ ] **Step 2: Run the focused tool test**

```powershell
python -m pytest backend/tests/test_hermes_langchain_tools.py::test_hub_query_tool_returns_structured_payload -q
```

Expected: fail because `build_production_tool_adapters` does not exist.

- [ ] **Step 3: Implement production adapters**

Modify `backend/app/services/hermes_langchain_tools.py`:

```python
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_communication import MultimodalEvidence
from app.models.reports import DailyReport
from app.services.hermes_codex_construction_service import request_codex_construction
from app.services.hermes_data_audit_service import HermesDataAuditService
from app.services.hermes_long_term_rule_service import list_active_rules
from app.services.hermes_mes_read_service import HermesMesReadService
from app.services.rag_service import query_knowledge
from app.services.report import template_daily_report


def _parse_business_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _request_payload(kwargs: dict[str, object]) -> dict[str, str]:
    return {key: str(value) for key, value in kwargs.items()}


def _string_list(value: object, default: list[str]) -> list[str]:
    if value is None or value == '':
        return default
    if isinstance(value, str):
        return [item.strip() for item in value.split(',') if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    return [str(value)]


def _hub_query_tool(*, db: Session, **kwargs: object) -> dict[str, object]:
    business_date = _parse_business_date(kwargs.get('business_date'))
    payload = template_daily_report.build_template_daily_report_payload(db, target_date=business_date)
    return {
        'status': payload.get('status', 'ok'),
        'source': 'data_hub',
        'request': _request_payload(kwargs),
        'facts': payload.get('facts') or payload.get('hermes_fact_bundle') or {},
    }


def _mes_wms_read_tool(*, mes_read_service: HermesMesReadService | None, **kwargs: object) -> dict[str, object]:
    if mes_read_service is None:
        return {
            'status': 'unavailable',
            'source': 'mes_wms_readonly',
            'request': _request_payload(kwargs),
            'facts': {},
            'reason': 'mes_read_service_missing',
        }
    business_date = _parse_business_date(kwargs.get('business_date'))
    query_keys = _string_list(kwargs.get('query_keys'), ['workshop_process_records', 'finished_inbound_records'])
    return {
        'status': 'ok',
        'source': 'mes_wms_readonly',
        'request': _request_payload(kwargs),
        'facts': mes_read_service.read_sources(
            business_date=business_date,
            query_keys=query_keys,
            workshop_name=str(kwargs.get('workshop_name') or '').strip() or None,
        ),
    }


def _dingtalk_evidence_tool(*, db: Session, **kwargs: object) -> dict[str, object]:
    limit = max(1, min(int(kwargs.get('limit') or 20), 100))
    rows = db.query(MultimodalEvidence).order_by(MultimodalEvidence.id.desc()).limit(limit).all()
    return {
        'status': 'ok',
        'source': 'dingtalk_evidence',
        'request': _request_payload(kwargs),
        'facts': [
            {
                'id': row.id,
                'source_type': row.source_type,
                'source_ref': row.source_ref,
                'created_at': row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
    }


def _rag_route_tool(*, db: Session, current_user: object | None, **kwargs: object) -> dict[str, object]:
    result = query_knowledge(
        db,
        query=str(kwargs.get('query') or kwargs.get('text') or ''),
        limit=int(kwargs.get('limit') or 5),
        user=current_user,
        workshop=str(kwargs.get('workshop') or '').strip() or None,
        machine_code=str(kwargs.get('machine_code') or '').strip() or None,
    )
    return {'status': 'ok', 'source': 'rag', 'request': _request_payload(kwargs), 'facts': result}


def _history_report_tool(*, db: Session, **kwargs: object) -> dict[str, object]:
    business_date = _parse_business_date(kwargs.get('business_date'))
    reports = db.query(DailyReport).filter(DailyReport.report_date == business_date).all()
    return {
        'status': 'ok',
        'source': 'daily_reports',
        'request': _request_payload(kwargs),
        'facts': [
            {
                'id': report.id,
                'workshop_id': report.workshop_id,
                'status': report.report_status,
                'final_text_summary': report.final_text_summary,
                'report_data': report.report_data,
            }
            for report in reports
        ],
    }


def _output_skill_alignment_tool(*, db: Session, output_skill_root: str | Path | None, **kwargs: object) -> dict[str, object]:
    service = HermesDataAuditService(db, output_skill_root=output_skill_root)
    run = service.create_run(
        business_date=_parse_business_date(kwargs.get('business_date')),
        fields=_string_list(kwargs.get('fields'), []),
        mes_query_keys=_string_list(kwargs.get('mes_query_keys'), []),
    )
    return {'status': run.status, 'source': 'output_skill_alignment', 'request': _request_payload(kwargs), 'facts': {'run_id': run.id}}


def _long_term_rules_tool(*, db: Session, **kwargs: object) -> dict[str, object]:
    rules = list_active_rules(db)
    category = str(kwargs.get('category') or '').strip()
    if category:
        rules = [rule for rule in rules if (rule.scope_payload or {}).get('domain') == category]
    return {
        'status': 'ok',
        'source': 'long_term_rules',
        'request': _request_payload(kwargs),
        'facts': [
            {
                'rule_key': rule.rule_key,
                'raw_text': rule.raw_text,
                'structured_rule': rule.structured_rule,
                'scope_payload': rule.scope_payload,
                'priority': rule.priority,
            }
            for rule in rules
        ],
    }


def _codex_construction_tool(*, db: Session, current_user: object | None, **kwargs: object) -> dict[str, object]:
    if current_user is None:
        return {'status': 'denied', 'source': 'codex_construction', 'request': _request_payload(kwargs), 'facts': {'message': '缺少 root_owner 身份'}}
    result = request_codex_construction(
        db,
        actor=current_user,
        request_text=str(kwargs.get('raw_text') or kwargs.get('text') or ''),
        trace_id=str(kwargs.get('trace_id') or ''),
        construction_type=str(kwargs.get('construction_type') or 'light'),
    )
    return {'status': result.status, 'source': 'codex_construction', 'request': _request_payload(kwargs), 'facts': {'run_id': result.run_id, 'message': result.message}}


def build_production_tool_adapters(
    db: Session,
    *,
    mes_read_service: HermesMesReadService | None = None,
    current_user: object | None = None,
    output_skill_root: str | Path | None = None,
) -> HermesToolAdapters:
    return HermesToolAdapters(
        hub_query=partial(_hub_query_tool, db=db),
        mes_wms_read=partial(_mes_wms_read_tool, mes_read_service=mes_read_service),
        dingtalk_evidence=partial(_dingtalk_evidence_tool, db=db),
        rag_route=partial(_rag_route_tool, db=db, current_user=current_user),
        history_report=partial(_history_report_tool, db=db),
        output_skill_alignment=partial(_output_skill_alignment_tool, db=db, output_skill_root=output_skill_root),
        long_term_rules=partial(_long_term_rules_tool, db=db),
        codex_construction=partial(_codex_construction_tool, db=db, current_user=current_user),
    )
```

Adapter ownership:

- `hub_query` reads `template_daily_report.build_template_daily_report_payload`.
- `mes_wms_read` reads `HermesMesReadService.read_sources`; WMS can share this adapter until a dedicated WMS read service exists.
- `dingtalk_evidence` reads `MultimodalEvidence`.
- `rag_route` calls `rag_service.query_knowledge`.
- `history_report` reads `DailyReport`.
- `output_skill_alignment` calls `HermesDataAuditService.create_run`.
- `long_term_rules` calls `list_active_rules`.
- `codex_construction` calls `request_codex_construction`.

- [ ] **Step 4: Run tests after each tool replacement**

```powershell
python -m pytest backend/tests/test_hermes_langchain_tools.py backend/tests/test_hermes_langgraph_app.py -q
```

Expected: pass after each small replacement.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/hermes_langchain_tools.py backend/app/services/hermes_langgraph_app.py backend/tests/test_hermes_langchain_tools.py backend/tests/test_hermes_langgraph_app.py
git commit -m "feat: wire Hermes factory brain tools"
```

---

## Task 15: Production Readiness, Regression, and Deployment Notes

**Files:**
- Create: `docs/superpowers/reports/2026-06-25-hermes-factory-brain-readiness.md`
- Modify: `docs/superpowers/plans/2026-06-25-hermes-factory-brain-upgrade-plan.md` only if a completed task needs a checked box update.

- [ ] **Step 1: Run focused backend tests**

```powershell
python -m pytest `
  backend/tests/test_hermes_factory_brain_config.py `
  backend/tests/test_hermes_factory_brain_models.py `
  backend/tests/test_hermes_long_term_rule_service.py `
  backend/tests/test_hermes_factory_brain_intent_service.py `
  backend/tests/test_hermes_dingtalk_sampling_service.py `
  backend/tests/test_hermes_rag_router_service.py `
  backend/tests/test_hermes_fact_priority_service.py `
  backend/tests/test_hermes_langchain_tools.py `
  backend/tests/test_hermes_langgraph_app.py `
  backend/tests/test_hermes_factory_brain_orchestrator.py `
  backend/tests/test_hermes_codex_construction_service.py `
  backend/tests/test_dingtalk_factory_brain_inbound.py `
  backend/tests/test_hermes_factory_brain_acceptance.py `
  -q --tb=short
```

Expected: all pass.

- [ ] **Step 2: Run existing high-risk regressions**

```powershell
python -m pytest `
  backend/tests/test_dingtalk_agent_inbound_route.py `
  backend/tests/test_agent_command_rag_route.py `
  backend/tests/test_rag_routes.py `
  backend/tests/test_hermes_data_audit_service.py `
  backend/tests/test_hermes_mes_read_service.py `
  backend/tests/test_dingtalk_service.py `
  -q --tb=short
```

Expected: all pass.

- [ ] **Step 3: Run full backend suite**

```powershell
python -m pytest backend/tests -q --tb=short
```

Expected: full backend suite passes. Existing skips are acceptable if unchanged.

- [ ] **Step 4: Run frontend build if any config surface changed**

```powershell
cd frontend
npm test -- --run
npm run build
```

Expected: tests and build pass.

- [ ] **Step 5: Create readiness report**

Create `docs/superpowers/reports/2026-06-25-hermes-factory-brain-readiness.md` after the commands above finish. Set `状态` to `ready` only when every required command passes. Set it to `blocked` when any command fails, and write the failed command and error summary under `阻塞项`.

```markdown
# Hermes Factory Brain Readiness Report

日期：2026-06-25

## 状态

ready

## 已验证

- 配置门禁
- 持久化模型
- Soul.md
- 长期规则
- 钉钉四条件采样
- RAG 路由
- 事实优先级和冲突展示
- LangChain 工具注册
- LangGraph 状态图
- DingTalk 入站分流
- Codex 施工记录
- 三场景 Harness

## 关键命令

- `python -m pytest backend/tests/test_hermes_factory_brain_config.py backend/tests/test_hermes_factory_brain_models.py backend/tests/test_hermes_long_term_rule_service.py backend/tests/test_hermes_factory_brain_intent_service.py backend/tests/test_hermes_dingtalk_sampling_service.py backend/tests/test_hermes_rag_router_service.py backend/tests/test_hermes_fact_priority_service.py backend/tests/test_hermes_langchain_tools.py backend/tests/test_hermes_langgraph_app.py backend/tests/test_hermes_factory_brain_orchestrator.py backend/tests/test_hermes_codex_construction_service.py backend/tests/test_dingtalk_factory_brain_inbound.py backend/tests/test_hermes_factory_brain_acceptance.py -q --tb=short`: pass
- `python -m pytest backend/tests/test_dingtalk_agent_inbound_route.py backend/tests/test_agent_command_rag_route.py backend/tests/test_rag_routes.py backend/tests/test_hermes_data_audit_service.py backend/tests/test_hermes_mes_read_service.py backend/tests/test_dingtalk_service.py -q --tb=short`: pass
- `python -m pytest backend/tests -q --tb=short`: pass
- `cd frontend; npm test -- --run; npm run build`: pass
- `python backend/scripts/hermes_factory_brain_cli.py --scenario daily_report --business-date 2026-06-19`: pass

## 阻塞项

- 无

## 生产开关

- `HERMES_FACTORY_BRAIN_ENABLED=false` 初始部署
- checkpoint schema setup 完成后再开启
- 首小时观察 `agent_runs`、`chat_inbox`、`external_message_logs` 和应用日志

## 回滚方式

1. 设置 `HERMES_FACTORY_BRAIN_ENABLED=false`
2. 确认 DingTalk 入站回落到旧 `handle_agent_command`
3. 若需要代码回滚，revert 本功能分支 commit
4. 新增表保留，不删除生产数据
```

If one command fails, change `状态` to `blocked`, replace `无` with the exact blocker, and do not mark the plan complete.

- [ ] **Step 6: Commit readiness report**

```powershell
git add docs/superpowers/reports/2026-06-25-hermes-factory-brain-readiness.md
git commit -m "docs: record Hermes factory brain readiness"
```

---

## Self-Review

### Spec Coverage

- Full-factory brain positioning: Task 4, Task 9, Task 10, Task 13.
- Phase-one three domains: Task 4 and Task 13.
- Three acceptance scenarios: Task 13.
- Natural-language task instruction: Task 4.
- Long-term rules: Task 3.
- DingTalk four-condition sampling: Task 5.
- Specialist DingTalk evidence priority: Task 7.
- Conflict transparency: Task 7 and Task 13.
- Routed RAG and six knowledge units: Task 6.
- RAG daily-fact boundary: Task 6.
- LangChain native tool layer: Task 8 and Task 14.
- LangGraph native state graph: Task 9.
- PostgreSQL checkpoint setup: Task 9.
- Codex construction layer: Task 12.
- Model 401 degradation: Task 8.
- Soul.md: Task 3.
- Soul/rules/RAG separation: Task 2 and Task 3.
- Existing fallback lane preservation: Task 11.

### Placeholder Scan

This plan avoids open-ended implementation language. Each task defines exact files, tests, commands, and concrete code slices. Task 14 names the real adapter file, tests, source services, and output shape.

### Type Consistency

Shared types:

- `FactoryBrainIntent` is introduced in Task 4 and consumed by later services.
- `FactoryBrainState` is introduced in Task 9 and persisted by Task 10.
- `HermesLongTermRule`, `HermesDingTalkSamplingRule`, `HermesKnowledgeUnit`, `HermesSoulProfile`, and `HermesCodexConstructionRun` are introduced in Task 2 and used consistently by service tasks.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-25-hermes-factory-brain-upgrade-plan.md`.

Two execution options:

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope, leverage, failure visibility | 1 | CLEAR | Selected vertical factory-brain lane; rejected minimal command patch and full rewrite; added dream-state delta, not-in-scope list, existing-code leverage map, and rollout gate. |
| Codex Review | `/codex review` | Independent second opinion | 0 | NOT RUN | Skipped for this optimization pass; no outside-model changes were applied. |
| Eng Review | `/plan-eng-review` | Architecture, tests, reliability | 1 | CLEAR | Added architecture diagram, shadow data paths, named error/rescue registry, failure modes registry, test coverage diagram, observability gate, and parallelization plan. |
| Design Review | `/plan-design-review` | User-facing interaction quality | 1 | CLEAR | No new UI scope; optimized DingTalk conversation states, partial-data behavior, conflict copy, permission copy, and degraded-mode user experience. |
| DX Review | `/plan-devex-review` | Operator and implementer experience | 1 | CLEAR | Added operator persona, 10-minute local smoke target, one-command CLI path, trace-id expectation, and "产量出来了吗" magical moment. |

- **UNRESOLVED:** 0
- **VERDICT:** CEO + ENG + DESIGN + DX CLEARED. The plan is ready for subagent-driven implementation. The main remaining risk is execution discipline: every task must keep the new review-hardening gates, not only the original feature checklist.
