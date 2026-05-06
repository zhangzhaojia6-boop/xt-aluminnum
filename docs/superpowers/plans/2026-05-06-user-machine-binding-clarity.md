# User Machine Binding Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让管理端用户配置在绑定机列时直接显示机列是否已被账号占用，降低机列主操账号误绑定风险。

**Architecture:** 复用 `/master/equipment` 已返回的 `bound_username` 和 `bound_user_name` 字段，不新增接口、不改数据模型。只在 `UserManagement.vue` 的机列筛选和编辑弹窗下拉选项中增加占用状态展示，并用现有前端合同测试锁住入口。

**Tech Stack:** Vue 3 Composition API, Element Plus select option slot, native `node:test`, existing scoped CSS.

---

### Task 1: Frontend Contract

**Files:**
- Modify: `frontend/tests/userDingtalkSync.test.js`

- [x] **Step 1: Write the failing contract test**

Add assertions that the user management page has a machine binding owner formatter and a visible option owner row:

```js
test('user management machine selector shows occupying account in machine options', () => {
  assert.match(userManagementSource, /formatMachineBindingOwner/)
  assert.match(userManagementSource, /machine-option__owner/)
  assert.match(userManagementSource, /已占用/)
  assert.match(userManagementSource, /bound_user_name|boundUserName/)
  assert.match(userManagementSource, /bound_username|boundUsername/)
})
```

- [x] **Step 2: Run the red test**

Run:

```bash
npm --prefix frontend test -- userDingtalkSync.test.js
```

Expected: fails until `UserManagement.vue` exposes the formatter and option markup.

### Task 2: User Management UI

**Files:**
- Modify: `frontend/src/views/master/UserManagement.vue`

- [x] **Step 1: Render rich machine options**

Keep the existing `:label="formatMachineLabel(machine)"` for search and selected value, and add an `el-option` default slot in both machine select controls:

```vue
<div class="machine-option">
  <span class="machine-option__name">{{ formatMachineLabel(machine) }}</span>
  <span v-if="formatMachineBindingOwner(machine)" class="machine-option__owner">已占用 · {{ formatMachineBindingOwner(machine) }}</span>
  <span v-else class="machine-option__owner is-empty">空闲</span>
</div>
```

- [x] **Step 2: Add the owner formatter**

Add:

```js
function formatMachineBindingOwner(machine) {
  const name = machine.bound_user_name || machine.boundUserName
  const username = machine.bound_username || machine.boundUsername
  if (name && username) return `${name} / ${username}`
  return name || username || ''
}
```

- [x] **Step 3: Add compact scoped CSS**

Use small, stable rows inside dropdown options:

```css
.machine-option {
  display: grid;
  gap: 2px;
  min-width: 0;
  padding: 2px 0;
  line-height: 1.25;
}
```

Finish the style with an owner line, an empty state color, and no nested cards.

### Task 3: Verification and Deploy

**Files:**
- Modify if test count changes: `docs/deploy/current-state.md`
- Modify if test count changes: `docs/发布冻结基线清单.md`
- Modify if test count changes: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [x] **Step 1: Run local verification**

Run:

```bash
npm --prefix frontend test -- userDingtalkSync.test.js
npm --prefix frontend test
npm --prefix frontend run build
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_current_deploy_state_tracks_current_head_and_validation_evidence -q
git diff --check
```

- [ ] **Step 2: Commit and push**

Run:

```bash
git status --short
git add frontend/tests/userDingtalkSync.test.js frontend/src/views/master/UserManagement.vue docs/superpowers/plans/2026-05-06-user-machine-binding-clarity.md
git commit -m "feat: 优化机列绑定账号可见性"
git push origin main
```

- [ ] **Step 3: Deploy and verify production**

Run on ECS:

```bash
cd /srv/aluminum-bypass
./scripts/deploy_systemd_host.sh --pull http://8.140.218.13
```

Then verify the production user-management asset contains `machine-option__owner` and `已占用`, and `/readyz` remains `status=ready`.
