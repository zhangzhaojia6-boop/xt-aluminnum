# 去统计流与 Hermes 自成长 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让数据中枢取消人工统计中间流程，并通过可靠填报、唯一字段合同、Hermes 主动闭环、系统判定开停机和 7 日影子验收达到可正式切换标准。

**Architecture:** 复用 `/entry`、`/manage`、DailyFactBundle、AgentEvent、Outbox 和现有钉钉/MES 链路。每个阶段形成独立可部署闭环；第一阶段只增强现有 `UnifiedEntryForm`，后续阶段不得提前混入。

**Tech Stack:** Vue 3、IndexedDB、FastAPI、SQLAlchemy、PostgreSQL/SQLite、APScheduler、NousResearch Hermes、DingTalk Stream、pytest、Node test、Playwright。

---

## 文件结构

第一阶段直接修改：

- `frontend/src/views/mobile/UnifiedEntryForm.vue`：接入草稿、弱网队列、精准补录和性能遥测。
- `frontend/src/composables/useLocalDraft.js`：保证页面离开前立即保存。
- `frontend/src/utils/unifiedEntryReliability.js`：精准字段过滤和可靠重试记录的纯函数。
- `frontend/tests/unifiedEntryReliability.test.js`：第一阶段前端行为测试。
- `backend/app/services/mobile_report/summary.py`：卷级重复请求返回既有记录。
- `backend/tests/test_mobile_submit_with_locked_fields.py`：卷级重试幂等测试。

后续阶段按顺序修改：

- `backend/app/services/report/daily_report_field_contract.py`：127 字段唯一合同读取与版本校验。
- `backend/app/services/report/daily_fact_gap_closure_service.py`：合同驱动的责任人、容差和升级策略。
- `backend/app/services/dingtalk_agent_inbound_service.py`：聊天补录候选与确认。
- `backend/app/services/machine_state_inference_service.py`：MES 动态节拍和系统判定开停机。
- `frontend/src/views/manage/TodayPage.vue`、`frontend/src/views/manage/AlertsPage.vue`：首屏关键链和异常优先体验。

## 阶段 1：真实基线与 `/entry/fill` 可靠性

### Task 1: 固化第一阶段前端行为

**Files:**
- Create: `frontend/src/utils/unifiedEntryReliability.js`
- Create: `frontend/tests/unifiedEntryReliability.test.js`

- [x] **Step 1: 写精准字段和重试记录失败测试**

```javascript
test('filterEntryGroups only keeps requested fields', () => {
  const groups = [{ label: '日报', fields: [{ name: 'output' }, { name: 'energy' }] }]
  assert.deepEqual(filterEntryGroups(groups, ['energy']), [
    { label: '日报', fields: [{ name: 'energy' }] },
  ])
})

test('buildEntryRetryRecord keeps one stable dedupe key', () => {
  const record = buildEntryRetryRecord({
    submitTarget: 'owner_daily',
    payload: { business_date: '2026-08-14', data: { energy: 1 } },
    draftKey: 'draft:owner:2026-08-14',
  })
  assert.equal(record.url, '/mobile/owner-daily')
  assert.equal(record.dedupeKey, 'unified-entry:owner_daily:draft:owner:2026-08-14')
})
```

- [x] **Step 2: 运行测试并确认红灯**

Run: `cd frontend && npm test -- --test-name-pattern="filterEntryGroups|buildEntryRetryRecord"`

Expected: FAIL，模块 `unifiedEntryReliability.js` 不存在。

- [x] **Step 3: 实现最小纯函数**

```javascript
const TARGET_URLS = {
  coil_entry: '/mobile/coil-entry',
  owner_daily: '/mobile/owner-daily',
  shift_report: '/mobile/report/submit',
}

export function filterEntryGroups(groups, requestedFields) {
  const requested = new Set(requestedFields || [])
  if (!requested.size) return groups || []
  return (groups || [])
    .map((group) => ({
      ...group,
      fields: (group.fields || []).filter((field) => requested.has(field.name)),
    }))
    .filter((group) => group.fields.length)
}

export function buildEntryRetryRecord({ submitTarget, payload, draftKey }) {
  return {
    type: 'http',
    method: 'post',
    url: TARGET_URLS[submitTarget],
    body: payload,
    dedupeKey: `unified-entry:${submitTarget}:${draftKey}`,
    clearDraftKey: draftKey,
  }
}
```

- [x] **Step 4: 运行前端单元测试**

Run: `cd frontend && npm test`

Expected: 全部通过。

### Task 2: 接入草稿、精准补录、弱网队列和遥测

**Files:**
- Modify: `frontend/src/composables/useLocalDraft.js`
- Modify: `frontend/src/views/mobile/UnifiedEntryForm.vue`
- Test: `frontend/tests/offlineResilience.test.js`
- Test: `frontend/tests/unifiedEntryReliability.test.js`

- [x] **Step 1: 增加离开页面立即落盘测试**

在 `frontend/tests/offlineResilience.test.js` 读取源码并断言 `pagehide`、`visibilitychange` 和 `persistSnapshot` 已接入。

- [x] **Step 2: 运行测试并确认红灯**

Run: `cd frontend && npm test -- --test-name-pattern="pagehide"`

Expected: FAIL，当前 composable 只在 500ms 防抖后保存。

- [x] **Step 3: 让草稿在页面隐藏或离开时立即保存**

在 `useLocalDraft` 中绑定 `pagehide` 和 `visibilitychange`；页面隐藏时调用 `persistSnapshot()`，卸载时先保存再解绑。`localStorage.setItem` 使用 `try/catch`，存储失败时保留当前页面数据且不打断输入。

- [x] **Step 4: 在主入口复用可靠能力**

`UnifiedEntryForm.vue` 必须完成：

1. `visibleGroups = filterEntryGroups(groups.value, requestedEntryFields.value)`。
2. 模板和可见必填校验使用 `visibleGroups`。
3. 草稿快照保存 `form`、`specParts` 和不含图片二进制的质量字段。
4. 数据加载完成后检查可恢复草稿。
5. 网络错误时调用 `enqueuePendingRequest(buildEntryRetryRecord(...))`。
6. 正常成功后清理草稿。
7. 班次提交直接调用 `/mobile/report/submit`，不再先调用 `/mobile/report/save`。
8. 使用现有 `usePerformance('UnifiedEntryForm')`，并记录 `entry_ready_ms`、`entry_submit_ms` 和 `entry_queued_ms`。
9. 页面显示“已自动暂存”或“等待网络恢复”，不把排队状态写成提交成功。

- [x] **Step 5: 运行前端测试和构建**

Run: `cd frontend && npm test && npm run build`

Expected: 测试通过，生产构建成功。

### Task 3: 修复卷级提交的服务端幂等重试

**Files:**
- Modify: `backend/app/services/mobile_report/summary.py`
- Test: `backend/tests/test_mobile_submit_with_locked_fields.py`

- [x] **Step 1: 写重复提交失败测试**

用同一用户、随行卡、业务日期、班次和相同 payload 连续调用两次 `/api/v1/mobile/coil-entry`，断言两次响应均为 200、返回同一个 `id`，数据库只有一条 `mobile_coil`。

- [x] **Step 2: 运行测试并确认红灯**

Run: `cd backend && python -m pytest tests/test_mobile_submit_with_locked_fields.py -q`

Expected: 第二次请求因唯一约束失败。

- [x] **Step 3: 返回既有卷记录**

`create_coil_entry` 在创建前按 `work_order_id + shift_id + business_date` 查询既有记录：

- 同一创建人重复请求：返回既有记录。
- 不同创建人命中既有记录：返回 409，不泄露或覆盖事实。
- 新请求：保持原创建和班次聚合链路。

- [x] **Step 4: 运行后端定向测试**

Run: `cd backend && python -m pytest tests/test_mobile_submit_with_locked_fields.py tests/test_mobile_report_service.py tests/test_mobile_daily_fact_gap_refresh.py -q`

Expected: 全部通过。

### Task 4: 第一阶段浏览器与生产门禁

**Files:**
- Modify only if a discovered defect requires it: `frontend/e2e/compose-smoke.spec.js`

- [x] **Step 1: 运行静态检查**

Run: `uvx ruff check backend/app/services/mobile_report/summary.py backend/tests/test_mobile_submit_with_locked_fields.py`

Expected: All checks passed。

实际：本次改动未增加 Ruff 问题，目标文件与当前 HEAD 均为 39 条历史发现；全文件清零不属于本阶段的外溢重构。

- [ ] **Step 2: 运行容器和 Playwright 门禁**

Run: GitHub CI `frontend-build + backend-tests + compose-smoke`。

Expected: 三个 job 全部 success。

- [x] **Step 3: 验证移动端真实行为**

验证普通入口显示完整表单；带 `business_date` 和 `entry_fields` 的任务链接只显示目标字段；断网提交显示等待重试；恢复网络后队列清空；重复提交只产生一条记录。

实际：移动端 Chromium 4 条关键用例通过，前端 755 条测试通过，后端定向 35 条通过，生产构建成功。

- [ ] **Step 4: 精确 SHA 部署并复核**

使用 `Production Sync Status` 的 deploy 模式部署数据中枢与 Hermes 精确 SHA。复核 `/readyz`、MES `fresh/success`、Hermes Stream `connected/fresh`、生产 SHA parity。

## 阶段 2：唯一 127 字段合同

### Task 5: 合同元数据统一

**Files:**
- Modify: `backend/app/services/report/daily_report_field_contract.py`
- Modify: `backend/app/services/report/daily_fact_bundle.py`
- Modify: `backend/app/routers/mobile.py`
- Test: `backend/tests/test_daily_report_field_contract.py`

- [ ] 保持规范字段数 127，并为每个字段补齐单位、适用条件、来源计划、责任角色、升级角色、业务截止时间、校验和容差。
- [ ] 让 `/mobile/entry-fields` 读取同一合同元数据，不重写表单引擎。
- [ ] 增加合同影响门禁：日报、Hermes、API 和页面引用不存在的字段时失败。
- [ ] 运行 `python -m pytest tests/test_daily_report_field_contract.py tests/test_daily_fact_bundle.py -q`。

## 阶段 3：Hermes 主动追缺与聊天补录

### Task 6: 事件驱动主动闭环

**Files:**
- Modify: `backend/app/services/report/daily_fact_gap_closure_service.py`
- Modify: `backend/app/services/dingtalk_agent_inbound_service.py`
- Modify: `backend/app/services/agent_communication_service.py`
- Test: `backend/tests/test_daily_fact_gap_closure_service.py`
- Test: `backend/tests/test_dingtalk_agent_inbound_service.py`

- [ ] 将 MES 同步、钉钉证据、补录提交和冲突变化接入同一个目标日期复核入口。
- [ ] 责任人提醒一次，10:00 未完成时升级车间负责人一次；无状态变化不重复外发。
- [ ] 聊天补录满足身份、日期、字段、单位、数值和权限条件时自动写入版本化事实。
- [ ] 高风险动作完成后发送事后摘要和撤销入口。

## 阶段 4：系统判定开停机

### Task 7: MES 动态节拍与可信度

**Files:**
- Create: `backend/app/services/machine_state_inference_service.py`
- Modify: `backend/app/tasks/mes_sync.py`
- Modify: `backend/app/services/report/daily_fact_bundle.py`
- Test: `backend/tests/test_machine_state_inference_service.py`

- [ ] 从最近 30 个有效生产日建立“设备 + 产品规格 + 班次”动态节拍。
- [ ] 过滤检修、换辊、异常日和样本不足区间。
- [ ] 输出高、中、低可信度、证据列表、策略版本和 trace。
- [ ] 只把高可信记录送入日报；中可信定向确认一次；低可信只观察。

## 阶段 5：管理大仪表盘流畅性

### Task 8: 首屏关键链

**Files:**
- Modify: `frontend/src/views/manage/TodayPage.vue`
- Modify: `frontend/src/views/manage/AlertsPage.vue`
- Modify: `frontend/src/composables/useDashboardSnapshot.js`
- Test: `frontend/tests/manageDailyReportSurface.test.js`
- Test: `frontend/tests/manageAlertsTimeline.test.js`

- [ ] 首屏只等待今日关键结果、待办和异常。
- [ ] 趋势、历史和明细按需加载。
- [ ] 关键事件实时更新并以 30 至 60 秒刷新兜底。
- [ ] 每个数字显示业务时间、来源和新鲜度。

## 阶段 6：7 日影子验收与正式切换

### Task 9: 去统计流生产门禁

**Files:**
- Create: `backend/scripts/run_statistics_free_shadow_gate.py`
- Create: `backend/tests/test_statistics_free_shadow_gate.py`
- Modify: `docs/deploy/runbook.md`

- [ ] 连续运行 7 个完整业务日，统计人员只核对最终结果。
- [ ] 验证关键字段真实来源与口径正确率 100%。
- [ ] 验证适用字段自动取得率、完整率和准确率均达到 95%。
- [ ] 验证人工抄数、汇总和催报次数为 0。
- [ ] 未达标则保留原责任流程并回到失败字段所属阶段；达标后正式停止集中统计流程。

## 执行边界

本轮只执行 Task 1 至 Task 4。Task 4 完整验收通过后，重新读取生产缺项分布并决定是否进入阶段 2。
