<template>
  <section class="xt-event-timeline">
    <div class="xt-event-timeline__summary" v-if="events.length > 0">
      {{ formattedDate }} 共 {{ totalCount }} 件，<span v-if="openCount > 0">未结 {{ openCount }}</span><span v-else>全部已处理</span>
    </div>
    <p v-if="events.length === 0" class="xt-event-timeline__empty">{{ formattedDate }} 当日无异常</p>
    <ol v-else class="xt-event-timeline__list">
      <li v-for="evt in events" :key="evt.id" class="xt-event-timeline__row">
        <EventCard :event="evt" @open="onOpen" />
      </li>
    </ol>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import EventCard from './EventCard.vue'

const props = defineProps({
  events: { type: Array, default: () => [] },
  totalCount: { type: Number, default: 0 },
  openCount: { type: Number, default: 0 },
  targetDate: { type: String, default: '' }
})

const router = useRouter()

const formattedDate = computed(() => {
  if (!props.targetDate) return ''
  const d = dayjs(props.targetDate)
  return `${d.month() + 1} 月 ${d.date()} 日`
})

function onOpen(event) {
  if (event && event.detailRoute) router.push(event.detailRoute)
}
</script>

<style scoped>
.xt-event-timeline {
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  display: flex;
  flex-direction: column;
}
.xt-event-timeline__summary {
  padding: var(--xt-space-2) var(--xt-space-3);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  border-bottom: 1px solid var(--xt-border);
}
.xt-event-timeline__empty {
  margin: 0;
  padding: var(--xt-space-6) var(--xt-space-3);
  text-align: center;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-sm);
}
.xt-event-timeline__list { list-style: none; margin: 0; padding: 0; }
.xt-event-timeline__row { border-bottom: 1px solid var(--xt-border); }
.xt-event-timeline__row:last-child { border-bottom: 0; }
</style>
