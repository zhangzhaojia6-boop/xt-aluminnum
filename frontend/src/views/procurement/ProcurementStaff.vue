<template>
  <section class="pc-staff">
    <h1>办理人</h1>
    <ProcurementAssignments v-if="meta.can_manage" :roles="meta.assignable_roles || {}" />
    <p v-else class="pc-staff__denied">只有管理员能指派</p>
  </section>
</template>

<script setup>
import { inject } from 'vue'

import ProcurementAssignments from './ProcurementAssignments.vue'

const meta = inject('procurementMeta')
</script>

<style scoped>
.pc-staff { display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px; max-width: 760px; }
.pc-staff h1 { margin: 0; font-size: 28px; font-weight: 600; }
.pc-staff__denied { margin: 0; color: var(--xt-text-muted); }
</style>
