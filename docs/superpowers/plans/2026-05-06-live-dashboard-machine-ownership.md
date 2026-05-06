# Live Dashboard Machine Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在管理端实时态势页新增“机列归属率”视图，把今日产出按已绑定真实机列与未绑定填报口径拆开展示。

**Architecture:** 复用 `aggregation.workshops[].machines[]`，在 `managementCommandCenter.js` 增加纯函数汇总机列归属比例；`LiveDashboard.vue` 只消费该 helper 并渲染一个轻量进度条，不新增接口、不改后端数据结构。测试先覆盖 helper 计算，再用前端合同测试锁定页面入口和标签。

**Tech Stack:** Vue 3 Composition API, native `node:test`, existing scoped CSS and dashboard formatter helpers.

---

### Task 1: Helper Contract

**Files:**
- Modify: `frontend/tests/managementCommandCenter.test.js`
- Modify: `frontend/src/utils/managementCommandCenter.js`

- [ ] **Step 1: Write the failing helper test**

Add `buildMachineOwnershipSummary` to the import list in `frontend/tests/managementCommandCenter.test.js`, then add:

```js
test('buildMachineOwnershipSummary separates bound output from unbound fill output', () => {
  const summary = buildMachineOwnershipSummary([
    {
      workshop_name: '2050冷轧车间',
      machines: [
        {
          machine_id: 5021,
          machine_name: '1#轧机',
          machine_binding_status: 'bound',
          day_total: { output: 50000, input: 53000 },
        },
        {
          machine_id: -5003,
          machine_name: '未绑定机列 / 夜班',
          day_total: { output: 74110, input: 78100 },
        },
      ],
    },
    {
      workshop_name: '精整车间',
      machines: [
        {
          machine_id: -8003,
          machine_name: '未绑定机列 / 夜班',
          machineBindingStatus: 'unbound',
          day_total: { output: 46350, input: 48700 },
        },
        {
          machine_id: 8008,
          machine_name: '无产出机列',
          machine_binding_status: 'bound',
          day_total: { output: 0, input: 1200 },
        },
      ],
    },
  ])

  assert.equal(summary.totalOutput, 170460)
  assert.equal(summary.boundOutput, 50000)
  assert.equal(summary.unboundOutput, 120460)
  assert.equal(summary.machineCount, 3)
  assert.equal(summary.boundMachineCount, 1)
  assert.equal(summary.unboundMachineCount, 2)
  assert.equal(summary.ownershipRate, 29.33)
  assert.equal(summary.unboundRate, 70.67)
  assert.equal(summary.needsBinding, true)
})
```

- [ ] **Step 2: Run the red test**

Run:

```bash
npm --prefix frontend test -- managementCommandCenter.test.js
```

Expected: failure because `buildMachineOwnershipSummary` is not exported.

- [ ] **Step 3: Implement the helper**

Add to `frontend/src/utils/managementCommandCenter.js` after `buildUnboundFillSummary`:

```js
export function buildMachineOwnershipSummary(workshops = []) {
  const summary = {
    totalOutput: 0,
    boundOutput: 0,
    unboundOutput: 0,
    boundMachineCount: 0,
    unboundMachineCount: 0,
  }

  workshops.forEach((workshop) => {
    const machines = workshop.machines || []
    machines.forEach((machine) => {
      const output = numberValue(machine.day_total?.output ?? machine.dayTotal?.output)
      if (output <= 0) return
      summary.totalOutput += output
      if (isUnboundMachine(machine)) {
        summary.unboundOutput += output
        summary.unboundMachineCount += 1
      } else {
        summary.boundOutput += output
        summary.boundMachineCount += 1
      }
    })
  })

  const totalOutput = Number(summary.totalOutput.toFixed(2))
  const boundOutput = Number(summary.boundOutput.toFixed(2))
  const unboundOutput = Number(summary.unboundOutput.toFixed(2))
  const machineCount = summary.boundMachineCount + summary.unboundMachineCount

  return {
    totalOutput,
    boundOutput,
    unboundOutput,
    boundMachineCount: summary.boundMachineCount,
    unboundMachineCount: summary.unboundMachineCount,
    machineCount,
    ownershipRate: totalOutput > 0 ? Number(((boundOutput / totalOutput) * 100).toFixed(2)) : 0,
    unboundRate: totalOutput > 0 ? Number(((unboundOutput / totalOutput) * 100).toFixed(2)) : 0,
    needsBinding: unboundOutput > 0,
  }
}
```

- [ ] **Step 4: Run the helper test**

Run:

```bash
npm --prefix frontend test -- managementCommandCenter.test.js
```

Expected: pass.

### Task 2: Live Dashboard View

**Files:**
- Modify: `frontend/tests/managementCommandCenter.test.js`
- Modify: `frontend/src/views/reports/LiveDashboard.vue`

- [ ] **Step 1: Lock the page contract**

Add these assertions to `LiveDashboard first screen uses management-readable labels`:

```js
assert.match(liveDashboardSource, /机列归属率/)
assert.match(liveDashboardSource, /live-machine-ownership/)
assert.match(liveDashboardSource, /machineOwnershipSummary/)
assert.match(liveDashboardSource, /buildMachineOwnershipSummary/)
```

- [ ] **Step 2: Run the red contract test**

Run:

```bash
npm --prefix frontend test -- managementCommandCenter.test.js
```

Expected: failure until the Vue page imports and renders the new section.

- [ ] **Step 3: Render the ownership chart**

In `LiveDashboard.vue`, import `buildMachineOwnershipSummary`, add:

```js
const machineOwnershipSummary = computed(() => buildMachineOwnershipSummary(sortedWorkshops.value))
```

Render a compact `live-machine-ownership` section after `live-unbound-fill` and before `live-output-distribution`, showing `机列归属率`, bound/unbound counts, a two-segment bar, ownership percentage, unbound output, and producing machine count.

- [ ] **Step 4: Style the chart**

Add scoped CSS near `.live-unbound-fill` and `.live-output-distribution`. Use existing command tokens, stable grid dimensions, no nested cards, no marketing copy, and mobile grid fallback at the existing responsive breakpoints.

- [ ] **Step 5: Run the contract test**

Run:

```bash
npm --prefix frontend test -- managementCommandCenter.test.js
```

Expected: pass.

### Task 3: Verification, Docs, Deploy

**Files:**
- Modify if test count changes: `docs/deploy/current-state.md`
- Modify if test count changes: `docs/发布冻结基线清单.md`
- Modify if test count changes: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [ ] **Step 1: Run local verification**

Run:

```bash
npm --prefix frontend test
python -m pytest backend/tests -m frontend_contract -q
python -m pytest backend/tests -q --durations=10
npm --prefix frontend run build
git diff --check
```

Expected: all pass.

- [ ] **Step 2: Update deployment evidence docs**

`npm --prefix frontend test` increases from 117 to 118 and backend full-suite evidence increases to 674 passed in this task; update the matching documented assertions.

- [ ] **Step 3: Commit and push**

Run:

```bash
git status --short
git add frontend/tests/managementCommandCenter.test.js frontend/src/utils/managementCommandCenter.js frontend/src/views/reports/LiveDashboard.vue docs/superpowers/plans/2026-05-06-live-dashboard-machine-ownership.md docs/deploy/current-state.md docs/发布冻结基线清单.md backend/tests/test_quick_cloud_trial_docs_and_ops.py
git commit -m "feat: 增加机列归属率视图"
git push origin main
```

- [ ] **Step 4: Deploy and verify production**

Run on ECS:

```bash
cd /srv/aluminum-bypass
./scripts/deploy_systemd_host.sh --pull http://8.140.218.13
```

Then verify production assets and browser DOM contain `机列归属率`, `live-machine-ownership`, and no horizontal overflow at desktop `1440x900` and mobile `390x844`.
