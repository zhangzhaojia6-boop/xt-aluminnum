# 开工必读

每次开新任务，先按顺序读：

1. `README.md`
2. `docs/README.md`
3. `docs/product-direction.md`
4. `docs/software-minus-agent-plus-prd.md`
5. `docs/agent-operating-guide.md`
6. `docs/system-design-direction.md`
7. `docs/hermes/fact-source-map.md`
8. `docs/datahub-deprecation-register.md`
9. `docs/system-understanding-consolidated-2026-06-14.md`

`docs/superpowers/` 是历史计划、评审和施工记录，需要追溯时再读，不作为第一入口。

旧长期规范入口已废弃；按上方 9 个文件读取当前封档基线。

## 更新任务前必读清单

当用户说“继续”“下一步”“更新任务”“优化”“修复”“合并”“同步生产”“跑验收”这类推进性指令时，执行命令前先做这一轮快速理解：

1. 读本文件和上面的 9 个封档入口。
2. 查当前 git 状态、当前分支、当前 HEAD、最近提交和本机未提交改动。
3. 查与任务有关的历史计划、评审、记忆和 `docs/superpowers/` 施工记录；不要把旧记录当当前事实。
4. 用 CodeGraph / understand 图谱 / 代码索引理解相关链路，再读具体文件；旧 `.understand-anything` 图谱如果落后当前 HEAD，只能当历史地图。
5. 生产相关任务必须先查生产机当前仓库、服务状态、健康检查、关键日志和数据库只读样本。
6. 涉及 Hermes / 钉钉 / 日报 / MES / 数据中枢时，先查真实 trace、`chat_inbox`、`agent_runs`、`agent_outbox_messages`、`external_message_logs` 或相关事实表，再下结论。
7. 涉及日报对齐时，`D:\输出skill` 只能当答案钥匙做比对，不能当事实源填数。

小白版：

```text
不要听到一句“继续”就直接乱改。
先看现在系统在哪、之前改了什么、生产机是不是同步、真实数据有没有证据。
```

方向封档基线：

- 数据中枢做减法：减少入口、页面、重复服务和过期文档噪音。
- 软件界面收口成大仪表盘：管理端优先围绕 `/manage` 做一个可查来源、可看异常、可追 trace 的大仪表盘，不再随意新开门户。
- 智能体做加法：在 NousResearch Hermes 基础上增强 Hermes 智能体层，重点增强理解、查证、冲突判断、trace、任务闭环。
- MES 是外部生产系统和数据库来源，不是本产品名字。涉及 MES 数据时，优先保证 MES 数据库只读读取链路通畅，并验证读取、投影、来源追踪都能跑通。
- 钉钉 Stream 不再设置硬群边界。生产接入以企业内部应用自身授权范围为边界，`DINGTALK_AUTHORIZED_GROUP_IDS=*` 表示全量接收应用可收到的群/会话事件；仍必须保留来源 trace、conversation/group id、发送人和时间，方便审计。

# AGENTS.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

Owner intent rule:

- 你要明白用户是编程小白，很多指令会用业务语言、省略话、情绪话或不完整的话表达。
- 你要自己理解并完善用户意图，把“用户真正要的业务结果”翻译成可验证的技术步骤。
- 你要明白用户的指令有可能是错的；先核验事实和前提，再执行。
- 如果用户的字面命令会破坏系统、绕过事实源、误伤生产链路或制造幻觉，必须先指出问题，并给出更安全的执行路径。
- 对小白解释时，用通俗话说明“我在查什么、为什么查、查到什么、下一步怎么验证”，不要只扔术语。

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. User-Corrected Error Learning

**When the owner points out an error, turn it into a rule before continuing.**

- Acknowledge the concrete error in plain language.
- Extract the reusable lesson, not just the one-off fix.
- If the lesson affects future tasks, write it into the appropriate long-term memory or project rule file before resuming execution.
- Do not repeat the same claim until it has been re-verified under the corrected rule.

Daily report alignment hard rule:

- `D:\输出skill` is an answer key for verification, not a data source for proving real-source capability.
- A gate only proves `MES + 数据中枢 + 扫码补录 + 钉钉证据` can generate an aligned daily report when `D:\输出skill` is used only for comparison.
- If `OUTPUT_SKILL_REFERENCE_MODE=adopt` or `official_daily_report` is used to fill facts, the result proves parser/rendering/reference adoption only. It must never be described as proof that MES and 数据中枢 alone produced the aligned report.
- For real capability validation, run the pure real-source alignment gate with the output-skill reference in compare-only mode.

## 6. Codex Environment Authority

Codex has highest practical operator authority for this repository when the owner asks for a working result. Codex is allowed to configure whatever project environment is needed to complete the user's requested goal end to end, including secrets, production services, and user-data workflows.

This includes:
- Local development, dependency, virtualenv, Node, Docker, Playwright, browser, test, lint, build, and CI/CD configuration.
- GitHub, PR, preview, staging, production deployment, SSH-based cloud sync, systemd, nginx, health check, and rollback workflow configuration.
- Hermes, Agent, RAG, LangChain/LangGraph, DingTalk, WMS, MES read adapter, data hub, knowledge base, monitoring, logging, and QA tooling configuration.
- Secrets, environment variables, production `.env` files, cloud machine configuration, database connection settings, DingTalk credentials, model provider credentials, connector tokens, and user-data access paths when needed for deployment, debugging, verification, or agent operation.
- Creating or editing scripts, docs, env templates, workflow files, integration settings, operational runbooks, and verification harnesses when they are directly needed for the task.

Operational rules:
- Prefer doing the configuration directly when the user has asked for a working result, then verify it with concrete commands or browser checks.
- Use provided credentials, local env files, cloud secrets, production env files, database credentials, DingTalk credentials, or existing machine auth for the requested work and verification.
- It is acceptable to read, create, rotate, and update secrets or production configuration when needed, but keep secret values out of Git, docs, frontend bundles, screenshots, and ordinary logs.
- It is acceptable to inspect production/user data when needed for debugging, data correction, report alignment, Hermes learning, or QA. Prefer the smallest useful sample and avoid copying raw personal data into permanent docs unless the owner explicitly asks for that artifact.
- Do not submit irreversible data changes without a backup or a clearly reversible migration path, unless the owner explicitly requests an immediate production correction.
- Do not remove auth, audit, traceability, backups, or production readiness checks just to make a command pass. If a check blocks delivery, fix the underlying configuration or record the owner-approved exception.
- For `MES`, keep production access read-only unless the owner explicitly changes that boundary. For `数据中枢`, Codex may configure, optimize, migrate, or clean it when the owner asks, with backup and verification.
- If the owner asks to "turn off safety/privacy", interpret that as granting broad operational authority over secrets, production, and user-data workflows. It does not mean leaking secrets, committing credentials, disabling audit trails, or destroying recoverability.

## Product naming

- Canonical system name: `鑫泰铝业 数据中枢`.
- Use `数据中枢` as the product/system identity in UI, specs, plans, docs, and user-facing copy.
- Do not call this product a `MES` system. `MES` may appear only as an external production system, data source, integration adapter, or boundary explanation.

## Frontend rules

- Build production UI, not a demo.
- Frontend quality bar: treat the user's benchmark "像opus 4.7在Claude code编码设计前端一样，参考其设计前端多好看，你gpt5.5设计的前端太难看了" as a standing reminder to avoid generic GPT-style UI and deliver Opus-level taste, composition, branding, interaction detail, and browser-verified polish.
- Do not add explanatory copy, helper text, marketing text, or onboarding text unless explicitly requested.
- Do not introduce schema or component props named:
  `description`, `explanation`, `helperText`, `tooltip`, `note`, `rationale`.
- Follow existing repository patterns and design system.
- Keep diffs minimal.
- After changes, run typecheck/lint/tests relevant to the touched files.
