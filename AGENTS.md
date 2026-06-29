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

方向封档基线：

- 数据中枢做减法：减少入口、页面、重复服务和过期文档噪音。
- 软件界面收口成大仪表盘：管理端优先围绕 `/manage` 做一个可查来源、可看异常、可追 trace 的大仪表盘，不再随意新开门户。
- 智能体做加法：在 NousResearch Hermes 基础上增强 Hermes 智能体层，重点增强理解、查证、冲突判断、trace、任务闭环。
- MES 是外部生产系统和数据库来源，不是本产品名字。涉及 MES 数据时，优先保证 MES 数据库只读读取链路通畅，并验证读取、投影、来源追踪都能跑通。

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

## 5. Codex Environment Authority

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
