# Phase 2 · 自动化闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 5 个确定性 agent + AI 助手 + 班长视图三件事真正构成"零人工中转"闭环：业务方在管理端把规则阈值按车间调整、班长在一屏内组织本班完整性、管理者从异常一键调 agent 处置。

**Architecture:** 把 `backend/app/rules/thresholds.py` 的 Python 常量迁移到 `RuleConfig` 表（车间维度），通过 `rule_config_service` 提供热加载读取，validator/reconciler agent 改为按车间 code 取值；新增 `assistant_action_service` 把 AI 助手生成的 `suggested_actions[]` 路由到 agent.execute() 并写 pilot_observability；新增 `team_lead_service` 聚合"排班 vs 出勤 vs 已报 vs 退回 vs 催报"五维数据，给班长一个屏幕。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, Vue 3, Pinia, node:test

---

## Scope

In scope:

- 新表 `rule_configs(id, scope_type, scope_key, key, value, value_type, version, updated_by, updated_at)`，scope 维度先支持 `factory` / `workshop`。
- 现有 `MIN_WEIGHT / MAX_SINGLE_SHIFT_WEIGHT / MIN_ATTENDANCE / MAX_ATTENDANCE / MAX_ELECTRICITY_DAILY / MAX_GAS_DAILY / RECONCILIATION_TOLERANCE_PERCENT` 全部迁入；`thresholds.py` 保留为默认 fallback 字典。
- `validator.py` / `reconciler.py` 取阈值时通过 `rule_config_service.get_threshold(key, workshop_code=...)`。
- 主数据中心新增"规则配置"标签页（admin only），可按车间编辑阈值；保存即热加载（无需重启）。
- 退回原因里追加 `[规则:rule.key@workshop_code]` 标签，便于审计。
- AI 助手 `ai_briefing_service.generate_briefing` 输出加 `suggested_actions[]`，每条形如 `{action: 'call_validator'|'call_reconciler'|'call_reminder', target_type, target_id, label, reason}`。
- 新 `services/assistant_action_service.py` 提供 `execute_action(db, user, action_payload)`，路由到对应 agent.execute() 并强制写 pilot_observability。
- 新 router `/api/v1/assistant/actions`（POST）调用上述服务；admin/manager only。
- `AiWorkstation.vue` 在每条异常摘要旁渲染"一键处置"按钮组（最多 3 个 action）。
- 新视图 `frontend/src/views/team/TeamLeadShell.vue`：单页五象限"排班 vs 出勤 vs 已报 vs 退回 vs 催报次数"，挂在 `/team-lead`，team_leader 角色登录默认进。
- 新 `services/team_lead_service.py`：聚合给 TeamLeadShell 用的数据。

Out of scope:

- 不引入规则 DSL（when/then/severity/action）——本轮只做"阈值键值对"。
- 不做规则版本回滚 UI（DB 表里 version 字段仅留痕）。
- 不做"代提"功能（C 列里的非星标项）。
- 不做 reminder 智能化策略（reminder agent 仍按现有规则跑）。
- 不改钉钉 H5（留给 Phase 3）。

---

## Task 1: 规则可配置化

**Files:**

- New: `backend/alembic/versions/00XX_create_rule_configs.py`
- New: `backend/app/models/rule_config.py`
- New: `backend/app/services/rule_config_service.py`
- New: `backend/app/routers/rule_configs.py`
- Modify: `backend/app/rules/thresholds.py`（保留为 fallback dict）
- Modify: `backend/app/rules/validation.py`（按 workshop_code 取值）
- Modify: `backend/app/agents/reconciler.py`（同上）
- Modify: `backend/app/agents/validator.py`（把 workshop_code 透传给 evaluate_auto_confirm）
- Modify: `frontend/src/views/master/WorkshopTemplateConfig.vue` 或新增 `RuleConfigCenter.vue`
- Test: `backend/tests/test_rule_config_service.py`
- Test: `backend/tests/test_validation_with_workshop_threshold.py`
- Test: `backend/tests/test_rule_configs_router.py`

- [ ] **Step 1: 写失败测试**

- 默认 fallback：DB 表空时，`get_threshold('MIN_WEIGHT')` 返回 `thresholds.py` 里的常量。
- 厂级覆盖：`scope_type='factory'` 行存在时，先取它。
- 车间覆盖：`scope_type='workshop', scope_key='LZ01'` 存在时优先于厂级。
- 热加载：调 `set_threshold(...)` 后，下一次 `get_threshold` 立即拿到新值（带 30s in-process cache，可手动 invalidate）。
- validator 用车间阈值：把 `LZ01` 的 `MAX_SINGLE_SHIFT_WEIGHT` 改成 50，提交一份 51 吨的 LZ01 报告会被退回；提交一份 51 吨的 LZ02 报告（用默认 30）也会被退回。
- 退回 reason 里包含 `[规则:MAX_SINGLE_SHIFT_WEIGHT@LZ01]`。

- [ ] **Step 2: RED**

```powershell
python -m pytest backend/tests/test_rule_config_service.py backend/tests/test_validation_with_workshop_threshold.py backend/tests/test_rule_configs_router.py -q
```

- [ ] **Step 3: 建表 + service**

- Alembic migration：`rule_configs` 表，唯一约束 `(scope_type, scope_key, key)`。
- `rule_config_service` 提供：`get_threshold(key, workshop_code=None) -> float|int`、`set_threshold(...)`、`list_for_scope(scope_type, scope_key)`、`invalidate_cache()`。
- 30 秒 TTL 内存 cache，`set_threshold` 后清；不引入 redis。

- [ ] **Step 4: 接进规则与 agent**

- `rules/thresholds.py` 保留为 `DEFAULT_THRESHOLDS: dict[str, float] = {...}`，旧 `MIN_WEIGHT` 等顶层常量改为 `DEFAULT_THRESHOLDS['MIN_WEIGHT']` 的别名以兼容。
- `validation.py` 顶部 import 改成 `from app.services import rule_config_service`，所有比较改为 `rule_config_service.get_threshold('MIN_WEIGHT', workshop_code=workshop_code)`。
- `reconciler.py` 把 `RECONCILIATION_TOLERANCE_PERCENT` 同样接入。
- 退回 reason 在 `validation.py` 报错文案末尾追加 `[规则:KEY@scope]`。

- [ ] **Step 5: Router + 前端编辑**

- `GET /api/v1/rule-configs?scope_type=workshop&scope_key=LZ01`
- `PUT /api/v1/rule-configs/{id}`（admin only）
- 前端 `RuleConfigCenter.vue` 表单：左侧选车间（含"全厂默认"），右侧 7 行阈值；保存即生效。
- 不加 helperText / tooltip / description。

- [ ] **Step 6: GREEN**

```powershell
python -m pytest backend/tests/test_rule_config_service.py backend/tests/test_validation_with_workshop_threshold.py backend/tests/test_rule_configs_router.py backend/tests/test_agent_validator.py backend/tests/test_agent_reconciler.py -q
npm --prefix frontend test
```

- [ ] **Step 7: Commit**

Commit message: `feat: 校验阈值按车间可配置`

---

## Task 2: AI 助手"建议→一键处置"回环

**Files:**

- Modify: `backend/app/services/ai_briefing_service.py`
- New: `backend/app/services/assistant_action_service.py`
- New: `backend/app/routers/assistant_actions.py`
- Modify: `backend/app/routers/__init__.py`
- Modify: `frontend/src/views/ai/AiWorkstation.vue`
- Modify: `frontend/src/api/ai.js` 或新增 `frontend/src/api/assistant-actions.js`
- Test: `backend/tests/test_ai_briefing_actions.py`
- Test: `backend/tests/test_assistant_action_service.py`
- Test: `backend/tests/test_assistant_actions_router.py`
- Test: `frontend/tests/aiWorkstationActions.test.js`

- [ ] **Step 1: 写失败测试**

- `generate_briefing` 输出每个 anomaly item 至少一条 `suggested_actions`，每条带 `{action, target_type, target_id, label, reason}`。
- 退回类异常 → `call_validator(report_id=...)` 与 `call_reminder(shift_config_id=..., target_date=...)`。
- 投入产出差异类异常 → `call_reconciler(target_date=...)`。
- 当 anomaly 不可机器处置时（如纯观察类） → `suggested_actions=[]`。
- `assistant_action_service.execute_action(db, user, payload)`：
  - admin/manager 才允许；其他角色 raise 403。
  - 路由到对应 `agent.execute(...)` 并写 `pilot_observability` 事件 `assistant_action_invoked`。
  - 返回 `{decisions: [...]}`。
- POST `/api/v1/assistant/actions` 端到端跑通。

- [ ] **Step 2: RED**

```powershell
python -m pytest backend/tests/test_ai_briefing_actions.py backend/tests/test_assistant_action_service.py backend/tests/test_assistant_actions_router.py -q
npm --prefix frontend test -- frontend/tests/aiWorkstationActions.test.js
```

- [ ] **Step 3: 实现 suggested_actions 生成**

- 在 `ai_briefing_service` 内部加 `_build_suggested_actions(anomaly) -> list[dict]`，按 anomaly type 派发；不调 LLM，纯规则。
- 输出 schema 加进 `briefing.items[i].suggested_actions`，与现有字段并存。

- [ ] **Step 4: 实现 assistant_action_service + router**

- service 内部维护一个 `ACTION_REGISTRY: dict[str, Callable]`，把 action 名映射到 `validator_agent.execute / reconciler_agent.execute / reminder_agent.execute / aggregator_agent.execute` 的"窄函数"包装。
- 每次调用必写 `pilot_observability_service.log_pilot_event('assistant_action_invoked', user_id=..., action=..., target=...)`，无论成功失败。
- router 鉴权：复用既有 `Depends(get_current_user)`，在 `routers/assistant_actions.py` 内新增私有 `_require_admin_or_manager(current_user)`（参考 `routers/master.py:48` `_require_admin` 的模式，允许 `role in {'admin','manager'}`）；payload 校验用 pydantic schema。

- [ ] **Step 5: 前端一键处置按钮**

- 在 `AiWorkstation.vue` 异常 item 渲染处加 `<el-button-group>`，最多 3 个按钮，文案用 `action.label`。
- 点击调 `POST /api/v1/assistant/actions`，loading 期间禁用按钮，成功后刷新当前 briefing。
- 非 admin/manager 不渲染按钮组。

- [ ] **Step 6: GREEN + 浏览器**

```powershell
python -m pytest backend/tests/test_ai_briefing_actions.py backend/tests/test_assistant_action_service.py backend/tests/test_assistant_actions_router.py -q
npm --prefix frontend test
npm --prefix frontend run build
```

浏览器核验：admin 登录 → AI 助手页 → 点一条异常的"一键处置" → 30 秒内异常状态变化 + pilot_observability 出现 `assistant_action_invoked` 行。

- [ ] **Step 7: Commit**

Commit message: `feat: AI 助手异常一键处置回环`

---

## Task 3: 班长一屏

**Files:**

- New: `backend/app/services/team_lead_service.py`
- New: `backend/app/routers/team_lead.py`
- Modify: `backend/app/routers/__init__.py`
- New: `frontend/src/views/team/TeamLeadShell.vue`
- New: `frontend/src/views/team/TeamLeadOverview.vue`
- Modify: `frontend/src/router/index.js`（新增 `/team-lead`，team_leader 默认 redirect 到这里）
- Modify: `frontend/src/views/Login.vue` 登录后角色路由分发
- Test: `backend/tests/test_team_lead_service.py`
- Test: `backend/tests/test_team_lead_router.py`
- Test: `frontend/tests/teamLeadShell.test.js`
- Test: `frontend/e2e/team-lead.spec.js`

- [ ] **Step 1: 写失败测试**

`team_lead_service.build_overview(db, leader_user, target_date)` 返回：

```
{
  scheduled_count, attended_count, reported_count,
  returned_count, reminder_count, escalation_count,
  pending_list: [ {workshop, shift, team, members[]} ],
  returned_list: [ {report_id, returned_reason, member} ],
  reminder_list: [ {shift, count, last_at} ],
  shift_health: 'green' | 'yellow' | 'red',
}
```

健康度：`returned_count / scheduled_count > 0.2` → red；`pending_count > 0` 但比例 ≤ 0.2 → yellow；其余 green。

- [ ] **Step 2: RED**

```powershell
python -m pytest backend/tests/test_team_lead_service.py backend/tests/test_team_lead_router.py -q
npm --prefix frontend test -- frontend/tests/teamLeadShell.test.js
```

- [ ] **Step 3: 实现 service**

- 复用现有：`AttendanceSchedule` 拿排班、`MobileShiftReport` 拿提交、`MobileReminderRecord` 拿催报。
- 一次 SQL 聚合，避免 N+1。
- 仅返回该 leader 的车间/班组范围（`User.workshop_id`、`User.team_id`）。

- [ ] **Step 4: 实现路由 + 前端**

- `GET /api/v1/team-lead/overview?date=...`，team_leader / deputy_leader / admin 可访问。
- `TeamLeadShell.vue` 用既有 xt-tokens 网格：左上"排班/出勤"、右上"已报/退回"、左下"待催"、右下"健康度"，5 个区块同一屏内可见，无需滚动。
- 不加 helperText / 营销文案；区块只有数字 + 列表。
- 默认 30s 自动刷新；右上角小刷新按钮。

- [ ] **Step 5: 角色路由分发**

- Login 成功后判断 `user.role === 'team_leader' || 'deputy_leader'` → `router.replace('/team-lead')`。
- 管理者仍走原管理端入口。

- [ ] **Step 6: GREEN + 浏览器 + e2e**

```powershell
python -m pytest backend/tests/test_team_lead_service.py backend/tests/test_team_lead_router.py -q
npm --prefix frontend test
npm --prefix frontend run e2e -- frontend/e2e/team-lead.spec.js
npm --prefix frontend run build
```

浏览器核验：以 team_leader 登录 → 直接进 `/team-lead` → 五象限渲染 → 点"未报"列表能跳到对应 worker 详情。

- [ ] **Step 7: Commit**

Commit message: `feat: 班长一屏组织班次完整性`

---

## Rollback Plan

- Task 1：`rule_configs` 表是 additive；如果车间阈值导致大面积误退，admin 删除该车间所有行即回到 fallback。
- Task 2：`/assistant/actions` router 单独可下线；前端按钮加 feature flag `ASSISTANT_ACTIONS_ENABLED`，默认 true。
- Task 3：`/team-lead` 路由独立；如果 team_leader 反馈不适应，登录分发改回原入口即可，TeamLeadShell.vue 保留为 admin 可达页。

---

## Success Criteria

- [ ] admin 在前端调一次某车间的 `MAX_SINGLE_SHIFT_WEIGHT`，无重启即对该车间下一份提交生效；其他车间不受影响。
- [ ] AI 助手页随机一条异常，admin 一键处置后 30 秒内可见状态变更；pilot_observability 全留痕。
- [ ] team_leader 登录直达 `/team-lead`，五象限有数；shift_health=red 时颜色提示生效。
- [ ] Phase 1 全部 success criteria 仍维持。
