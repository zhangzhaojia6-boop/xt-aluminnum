# CLAUDE.md
## gstack
Use /browse from gstack for all web browsing. Never use mcp__claude-in-chrome__* tools.
Available skills: /office-hours, /plan-ceo-review, /plan-eng-review, /plan-design-review,
/design-consultation, /design-shotgun, /design-html, /review, /ship, /land-and-deploy,
/canary, /benchmark, /browse, /open-gstack-browser, /qa, /qa-only, /design-review,
/setup-browser-cookies, /setup-deploy, /setup-gbrain, /sync-gbrain, /retro, /investigate, /document-release,
/codex, /cso, /autoplan, /pair-agent, /careful, /freeze, /guard, /unfreeze, /gstack-upgrade, /learn.

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

## Product naming

- Canonical system name: `鑫泰铝业 数据中枢`.
- Use `数据中枢` as the product/system identity in UI, specs, plans, docs, and user-facing copy.
- Do not call this product a `MES` system. `MES` may appear only as an external production system, data source, integration adapter, or boundary explanation.

## Agent division of labor

Claude Code (Opus) 是设计者与决策者——负责前端视觉设计、交互品质、产品方向判断和架构决策。所有涉及审美、用户体验、界面构图、品牌调性的工作由 Claude Code 亲自完成，不可委托。

Codex 是执行者——承接明确定义的后端逻辑、数据处理、批量重构、测试编写、脚手架搭建等不依赖视觉判断的编码任务。Codex 接收精确的 spec 和验收标准，按要求交付，不做设计决策。

原则：设计权不下放，执行力不浪费。Claude Code 出图纸，Codex 砌砖。

## Frontend rules

- Build production UI, not a demo.
- 前端品质是本项目的核心竞争力。每一个页面、每一个组件都必须达到可交付给真实用户的水准——不是"能用"，而是"好用且好看"。
- 视觉标杆：Claude Code 自身的 UI 品质。拒绝一切模板感、AI 味、GPT 风格的默认输出。字体要讲究，间距要呼吸，颜色要克制，动效要有意义。
- Do not add explanatory copy, helper text, marketing text, or onboarding text unless explicitly requested.
- Do not introduce schema or component props named:
  `description`, `explanation`, `helperText`, `tooltip`, `note`, `rationale`.
- Follow existing repository patterns and design system.
- Keep diffs minimal.
- After changes, run typecheck/lint/tests relevant to the touched files.

## 语言规则

- 与用户对话时使用中文。代码注释、commit message、变量名保持英文。
- 技术术语可以用英文原文，但解释和讨论用中文。

## 云端同步规则

- 跟云端 (`8.140.218.13` /srv/aluminum-bypass/) 同步代码只走 git 仓库：本地 commit → push 到 main → 云端 `git pull` → 重启服务 / 重建前端 dist。
- 禁止用 `scp` / `rsync` / 直接编辑云端文件 / 把本地未提交内容拷贝过去等任何绕开 git 的同步路径，避免本地与云端漂移。
- 一次性脚本 (临时 reset / 数据修复 / 巡检脚本) 也要先入库 (放 `scripts/` 或同等位置) 再 push，不要在云端就地写或本地不提交就 scp。
- 云端只允许执行：`git pull`、`pip install`、`npm run build`、`alembic upgrade`、`systemctl restart aluminum-bypass`、`nginx -s reload` 这一类幂等的部署动作。
- 紧急回滚：`git revert` 一笔新提交后 push，不要在云端 `git reset --hard` 制造分叉。

## 表达规则

- 跟用户讲话用大白话，不要堆术语。能用"账号"就别说"user 实体"，能说"先不动"就别说"保持现状"。
- 一句话能说清就一句话，不要分三段。
- 不要罗列我没问的可能性。我问你 A 怎么做，就告诉我 A，不要顺手把 B、C、D 都列出来"供我参考"。
- 选项题用最少的字给我看清楚，不要每个选项配三行解释。
- 工厂里实际怎么说，就跟我怎么说。"班长""主操""电工""过磅"这些直接用，不要翻译成 `shift_leader / machine_operator / energy_stat / weigher` 再讲一遍。
- 拿不准的事直接问，不要先假设三种情况再排除。

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
