<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { buildKeyEvents } from './_keyEvents.js'

const props = defineProps({ exceptionLane: { type: Object, default: () => ({}) } })
const items = computed(() => buildKeyEvents(props.exceptionLane))
</script>

<template>
  <ul class="xt-key-events" data-testid="manage-key-events">
    <li
      v-for="item in items"
      :key="item.slot"
      class="xt-key-events__card"
      :class="{ 'is-muted': !item.active }"
      data-testid="key-event-card"
    >
      <RouterLink
        v-if="item.active"
        :to="{ path: '/manage/alerts', query: { surface: item.surface } }"
        class="xt-key-events__link"
      >
        <span class="xt-key-events__title">{{ item.label }} {{ item.count }} {{ item.unit }}</span>
        <span class="xt-key-events__chev" aria-hidden="true">›</span>
      </RouterLink>
      <div v-else class="xt-key-events__empty">{{ item.label }} 无</div>
    </li>
  </ul>
</template>

<style scoped>
.xt-key-events { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--xt-space-2); grid-template-columns: repeat(3, 1fr); }
@media (max-width: 720px) { .xt-key-events { grid-template-columns: 1fr; } }
.xt-key-events__card {
  background: var(--xt-bg-panel); border: 1px solid var(--xt-border); border-radius: var(--xt-radius-md);
  min-height: 64px; display: flex;
}
.xt-key-events__card.is-muted { background: var(--xt-bg-panel-soft); opacity: 0.7; }
.xt-key-events__link { flex: 1; display: flex; align-items: center; justify-content: space-between; padding: 0 var(--xt-space-3); text-decoration: none; color: var(--xt-text); font-weight: 800; }
.xt-key-events__empty { flex: 1; display: flex; align-items: center; padding: 0 var(--xt-space-3); color: var(--xt-text-muted); }
.xt-key-events__chev { color: var(--xt-text-muted); font-size: var(--xt-text-lg); }
</style>
