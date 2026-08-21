# Gap Notification Routing And Business Day Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 精准分发缺失事实补录任务、消除补录页定向打开闪动，并阻止钉钉证据跨业务日污染事实包，同时保留完整 trace。

**Architecture:** 复用 `CommunicationChannel.metadata_payload` 表达显式责任关系，按通道拆分 outbox；未解析任务回退现有管理通道。`DailyFactBundle` 恢复业务日过滤，原始证据留在审计层；前端只改变字段定位的可见滚动行为。

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3, Node test runner, DingTalk work notice, existing AgentEvent/Outbox audit chain.

---

### Task 1: 隔离跨业务日钉钉候选

**Files:**
- Modify: `backend/app/services/report/daily_fact_bundle.py`
- Modify: `backend/tests/test_daily_fact_bundle_service.py`

- [ ] **Step 1: 写失败测试**

把显式日期不匹配、其他业务日的“今日”消息、无可靠时间可归属消息的预期改为：目标日事实包不包含它们的 candidate conflict；同时调用 `query_dingtalk_evidence(..., include_outside_business_context=True)` 断言原始证据仍可审计。另加一条无正文日期但 `created_at` 落入目标业务窗口的消息，断言它只在该业务日可见、在相邻业务日不可见，防串日但不把识别规则做死。

- [ ] **Step 2: 验证 RED**

Run: `python -m pytest backend/tests/test_daily_fact_bundle_service.py -k "date_mismatch or other_business_day or without_safe_business_date" -q`

Expected: 旧实现仍把跨日消息写进 `bundle["conflicts"]`，测试失败。

- [ ] **Step 3: 最小实现**

删除 `_apply_dingtalk_supplements` 调用中的 `include_outside_business_context=True`，使用服务默认的业务日过滤；不修改证据表、不删除全量审计参数。

- [ ] **Step 4: 验证 GREEN**

Run: `python -m pytest backend/tests/test_daily_fact_bundle_service.py backend/tests/test_hermes_dingtalk_evidence_service.py -q`

Expected: PASS。

### Task 2: 按显式组织责任拆分工作通知

**Files:**
- Create: `backend/app/services/report/daily_fact_notification_routing.py`
- Modify: `backend/app/services/report/daily_fact_gap_closure_service.py`
- Modify: `backend/tests/test_daily_fact_gap_closure_service.py`

- [ ] **Step 1: 写专项负责人失败测试**

注册两个绑定到 `factory_dispatch` 的真实工作通知通道，metadata 分别声明 `daily_fact_owner_roles=["quality_owner"]` 与 `["energy_chief"]`。同步两个缺项后断言生成两个 outbox，每条只含对应角色 assignment，事件保存各自目标和 outbox trace。

- [ ] **Step 2: 最小实现专项路由**

新增纯路由服务 `resolve_daily_fact_notification_routes(db, assignments=...) -> {"routes": [...], "unresolved": [...]}`：读取已绑定、active、非 dry-run 的 `dingtalk_work_notice` 通道；按 `daily_fact_fields` 再按 `daily_fact_owner_roles` 匹配 assignment；每个 route 保存 channel 对象、字段子集和 `routing_status`。管理员兜底只认 `metadata_payload.daily_fact_admin_fallback=true`，不能从普通专项通道里按优先级猜一个。

- [ ] **Step 3: 写车间主任与回退失败测试**

用 `daily_fact_fields=["hot_roll_daily"]` 验证车间主任只收到热轧字段；未配置的 `foundry_daily` 只进入显式 `daily_fact_admin_fallback=true` 的管理回退通道，并在事件/outbox payload 标记 `routing_status=unresolved`。再验证仅有专项负责人通道但没有显式兜底时，未解析任务不会误发给专项负责人。

- [ ] **Step 4: 拆分 outbox 并保留 trace**

让 closure service 对每个目标单独 queue；返回兼容字段 `outbox_message_id` 和新增 `outbox_message_ids`。事件记录本轮 target keys、outbox ids、recipient organization metadata，作为审计快照；现有管理员通道需要补上显式 fallback metadata。

- [ ] **Step 5: 写路由变化去重失败测试**

第一次只有管理回退，第二次增加显式责任通道，断言新通道得到一条 outbox，而旧管理通道复用原 outbox；第三次状态不变全部复用。

- [ ] **Step 6: 实现目标签名去重**

不新增事件级去重状态机。每个通道使用 `business_date + notification_state + 该通道 assignment signature` 作为 dedupe key，继续复用 `queue_bound_message` 现有的 agent + channel + dedupe key 去重和 31 天窗口。

- [ ] **Step 7: 定向验证**

Run: `python -m pytest backend/tests/test_daily_fact_gap_closure_service.py backend/tests/test_agent_communication_service.py -q`

Expected: PASS。

### Task 3: 消除工作通知补录页可见滚动

**Files:**
- Modify: `frontend/src/views/mobile/UnifiedEntryForm.vue`
- Modify: `frontend/tests/businessDateDefaults.test.js`

- [ ] **Step 1: 写失败测试**

断言通知字段定位仍调用 `scrollIntoView` 和 `focus({ preventScroll: true })`，但禁止 `behavior: 'smooth'`，要求使用 `behavior: 'auto'`。

- [ ] **Step 2: 验证 RED**

Run: `node --test frontend/tests/businessDateDefaults.test.js`

Expected: FAIL，旧源码仍为 smooth。

- [ ] **Step 3: 最小实现**

只把指定字段的滚动行为改为 `auto`，不改变日期校验、字段解析、表单加载和焦点逻辑。

- [ ] **Step 4: 验证 GREEN 与构建**

Run: `node --test frontend/tests/businessDateDefaults.test.js`

Run: `npm --prefix frontend run build`

Expected: PASS，构建成功。

然后用通知 deep link 手动打开一次本地或生产 `/entry/fill`，观察页面一次稳定呈现且自动落到指定字段；不为此新建重型 e2e。

### Task 4: 生产组织配置与端到端验收

**Files:**
- Create: `docs/superpowers/reports/2026-08-21-gap-notification-routing-production-acceptance.md`

- [ ] **Step 1: 评审并合并**

逐任务做 spec review 和 code quality review；运行相关后端测试、前端定向测试和构建，确认 diff 只覆盖三条需求。

- [ ] **Step 2: 配置显式责任通道**

从钉钉通讯录只读取得目标 userid，以“明确部门 + 明确人员”为依据向生产 `communication_channels` 增加或更新工作通知通道，并绑定 `factory_dispatch`。metadata 写明姓名、组织路径、责任和字段/owner role；有歧义的岗位不猜，保留管理员回退和异常 trace。

- [ ] **Step 3: 部署与只读预演**

在生产后端目录运行以下只读预演，直接调用路由服务解析现有 open events，不调用 queue 或 dispatcher：

```bash
.venv/bin/python - <<'PY'
from app.database import get_sessionmaker
from app.models.agent_communication import AgentEvent
from app.services.report.daily_fact_notification_routing import resolve_daily_fact_notification_routes
with get_sessionmaker()() as db:
    events = db.query(AgentEvent).filter(AgentEvent.event_type == 'daily_fact_gap', AgentEvent.status.in_(('new','open','pending'))).all()
    assignments = [dict(event.payload or {}) for event in events if (event.payload or {}).get('human_action_required')]
    result = resolve_daily_fact_notification_routes(db, assignments=assignments)
    print({
        'routes': [
            {
                'channel_id': item['channel'].id,
                'channel_name': item['channel'].name,
                'routing_status': item['routing_status'],
                'fields': [assignment['field'] for assignment in item['assignments']],
            }
            for item in result['routes']
        ],
        'unresolved_fields': [item['field'] for item in result['unresolved']],
    })
PY
```

核对目标数、每人字段子集、未解析字段和 dedupe 输入，不发送真实消息。

- [ ] **Step 4: 真实浏览器验收**

用通知 deep link 打开 `/entry/fill`，验证页面一次稳定呈现、定位正确字段、业务日正确、无跨日草稿恢复。测试只读打开，不提交生产表单。

- [ ] **Step 5: 生产事实包验收**

对最近两个相邻业务日运行：

```bash
cd backend
.venv/bin/python scripts/check_daily_report_output_skill_alignment.py \
  --output-skill-root /mnt/d/输出skill \
  --date 2026-08-19 --date 2026-08-20 \
  --reference-mode compare --full-differences --json
```

确认同一 undated evidence 不再跨日出现；再用 `query_dingtalk_evidence(..., include_outside_business_context=True)` 按原 evidence id 验证审计仍可读取。

- [ ] **Step 6: 真实发送最小样本**

仅向已明确绑定的一个专项负责人和一个车间主任各发送一条真实工作通知，核对 `AgentEvent -> Outbox -> ExternalMessageLog`、收件人字段子集、provider message id 和 dedupe。发送前遵守真实外发确认边界。

- [ ] **Step 7: 落地报告并同步**

记录精确 git SHA、CI、生产 SHA、服务/readyz、组织映射覆盖率、未解析岗位、浏览器结果和回滚点；推送并确认本机、origin、生产一致。
