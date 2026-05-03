# Execution Plan (ExecPlan)

> This is a living document. Codex updates it as tasks progress.
> Use this file to plan complex features before implementation.

## Current Plan: 数据中枢优化三阶段（不联调 MES）

### Goal
把现有"手填 + 投影骨架 + 5 个确定性 agent + 钉钉占位"这套自洽闭环打磨到极致。不等 MES，先把现状跑通、跑顺、跑快。

### Design Decisions
- Agent 维持确定性执行器形态，不引入 LLM 自由代理
- 工人入口收敛到钉钉 H5（先真打通免登录），企业微信用户消息通道整体下线
- 保留 `adapters/wecom/group_bot.py` 作为输出 publisher lane
- MES 投影空时，工厂指挥中心回退到 `ShiftProductionData` 聚合（不白屏）
- 校验阈值按车间维度可配置，`thresholds.py` 降级为 fallback
- AI 助手从"摘要展示"升级为"建议 + 一键调 agent"
- 三阶段必须串行推进，前一阶段 success criteria 不达标不进下一阶段

### Phases

**Phase 1 · 地基清理**（先做，3–5 天）
详见 `docs/superpowers/plans/2026-05-03-phase1-foundation-cleanup.md`
- Task 1: Pytest 收集与回归全绿
- Task 2: Readyz 硬阻断降级（空绑定、空排班 → warning）
- Task 3: 拆除企业微信用户消息路径（保留群机器人 publisher）
- Task 4: 工厂指挥中心 7 屏回退到手填口径

**Phase 2 · 自动化闭环**（Phase 1 合入后，~1 周）
详见 `docs/superpowers/plans/2026-05-03-phase2-automation-closure.md`
- Task 1: 规则阈值按车间可配置（DB 存 + 热加载）
- Task 2: AI 助手异常"建议→一键处置"回环
- Task 3: 班长一屏（排班/出勤/已报/退回/催报 五象限）

**Phase 3 · 工人入口升级**（Phase 2 合入后，~1 周）
详见 `docs/superpowers/plans/2026-05-03-phase3-worker-entry-upgrade.md`
- Task 1: 钉钉 H5 免登录闭环 + 工作通知真实发送
- Task 2: 扫码即填（本地 `coil_snapshots` 登记替代 MES 投影）

### Files to Modify
按阶段查看对应 plan 文件。

### Completion Criteria
- [ ] Phase 1 全部 success criteria 达成
- [ ] Phase 2 全部 success criteria 达成
- [ ] Phase 3 全部 success criteria 达成
- [ ] 试点车间一周，工人-班长-管理者三端零人工中转运转

### Notes
- MES 联调不在本轮范围，plan 完成后再评估何时开 Phase 4（MES 真联调）
- 每阶段合入后更新 `memory/project_mission.md` 的完成进度
- 星标项全部在这三个 phase 里；非星标项（一键代提、双录校验、reminder 智能化等）作为 backlog 不列入

---

## Plan Template

When starting a new plan, replace the "Current Plan" section with:

```markdown
## Current Plan: [Feature Name]

### Goal
What we're building and why.

### Design Decisions
Key architectural choices and trade-offs.

### Tasks
- [ ] Task 1 — description
- [ ] Task 2 — description
- [ ] Task 3 — description

### Files to Modify
- `path/to/file.py` — what changes
- `path/to/component.vue` — what changes

### Completion Criteria
- [ ] Tests pass
- [ ] Build succeeds
- [ ] Migration works
- [ ] Manually verified

### Notes
Discoveries, blockers, or context gathered during implementation.
```

## Completed Plans

_Archive finished plans here with date and summary._
