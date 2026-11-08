<template>
  <section class="pc-assign" data-testid="procurement-assignments">
    <p v-if="failed">读取失败 <button type="button" class="pc-assign__text" @click="load">重试</button></p>

    <template v-else>
      <ul class="pc-assign__roles">
        <li v-for="(label, role) in roles" :key="role">
          <span class="pc-assign__role">{{ label }}</span>
          <span class="pc-assign__people">
            <button
              v-for="row in peopleOf(role)"
              :key="row.id"
              type="button"
              class="pc-assign__person"
              :aria-label="`移除 ${row.user_name}`"
              :disabled="busy"
              @click="save(row.user_id, role, false)"
            >{{ row.user_name }} ×</button>
            <em v-if="!peopleOf(role).length">未指派</em>
          </span>
        </li>
      </ul>

      <form class="pc-assign__add" @submit.prevent="add">
        <select v-model="pickRole" aria-label="岗位" required>
          <option value="" disabled>岗位</option>
          <option v-for="(label, role) in roles" :key="role" :value="role">{{ label }}</option>
        </select>
        <select v-model="pickUser" aria-label="账号" required data-testid="pc-assign-user">
          <option value="" disabled>账号</option>
          <option v-for="user in users" :key="user.id" :value="user.id">{{ user.name }}{{ user.username && user.username !== user.name ? ` ${user.username}` : '' }}</option>
        </select>
        <button type="submit" :disabled="busy" data-testid="pc-assign-add">指派</button>
      </form>
      <p v-if="error" class="pc-assign__error" role="alert">{{ error }}</p>
    </template>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'

import { formatApiErrorMessage } from '../../api/index.js'
import { fetchProcurementAssignments, saveProcurementAssignment } from '../../api/procurement.js'
import { fetchUsersPage } from '../../api/users.js'

defineProps({ roles: { type: Object, required: true } })

const rows = ref([])
const users = ref([])
const pickRole = ref('')
const pickUser = ref('')
const failed = ref(false)
const busy = ref(false)
const error = ref('')

function peopleOf(role) {
  return rows.value.filter((row) => row.role === role)
}

async function load() {
  failed.value = false
  try {
    const [nextRows, page] = await Promise.all([fetchProcurementAssignments(), fetchUsersPage({ limit: 500 })])
    rows.value = nextRows
    users.value = page.items
  } catch {
    failed.value = true
  }
}

async function save(userId, role, enabled) {
  busy.value = true
  error.value = ''
  try {
    rows.value = await saveProcurementAssignment({ user_id: userId, role, enabled })
    return true
  } catch (err) {
    error.value = formatApiErrorMessage(err)
    return false
  } finally {
    busy.value = false
  }
}

async function add() {
  if (await save(pickUser.value, pickRole.value, true)) pickUser.value = ''
}

onMounted(load)
</script>

<style scoped>
.pc-assign__roles { margin: 0 0 16px; padding: 0; list-style: none; }
.pc-assign__roles li { display: grid; grid-template-columns: 128px minmax(0, 1fr); align-items: center; gap: 12px; min-height: 56px; padding: 6px 0; border-bottom: 1px solid var(--xt-border); }
.pc-assign__role { color: var(--xt-text-secondary); }
.pc-assign__people { display: flex; flex-wrap: wrap; gap: 8px; }
.pc-assign__people em { color: var(--xt-warning); font-style: normal; }
.pc-assign__person { min-height: 44px; padding: 0 12px; border: 1px solid var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); color: var(--xt-text); font: inherit; cursor: pointer; }
.pc-assign__add { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; gap: 8px; }
.pc-assign__add select { min-width: 0; min-height: 48px; padding: 0 10px; border: 1px solid var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); color: var(--xt-text); font: inherit; }
.pc-assign__add button { min-height: 48px; padding: 0 20px; border: 0; border-radius: 4px; background: var(--xt-primary); color: #fff; font: inherit; font-weight: 600; cursor: pointer; }
.pc-assign__text { min-height: 44px; border: 0; background: transparent; color: var(--xt-primary); font: inherit; cursor: pointer; }
.pc-assign__error { margin: 12px 0 0; color: var(--xt-danger); }
button:focus-visible, select:focus-visible { outline: 2px solid var(--xt-primary); outline-offset: 2px; }
</style>
