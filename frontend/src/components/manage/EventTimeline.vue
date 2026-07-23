<template>
  <section class="xt-event-timeline">
    <div class="xt-event-timeline__summary" v-if="events.length > 0">
      {{ formattedDate }} 共 {{ totalCount }} 条原始异常，归并为 {{ events.length }} 项，
      <span v-if="openCount > 0">未结 {{ openCount }} 条</span><span v-else>全部已处理</span>
    </div>
    <p v-if="events.length === 0" class="xt-event-timeline__empty">{{ formattedDate }} 当日无异常</p>
    <ol v-else class="xt-event-timeline__list">
      <li v-for="evt in events" :key="evt.id" class="xt-event-timeline__row">
        <EventCard :event="evt" @open="onOpen" />
        <div v-if="evt.sourceEvents?.length > 1" class="xt-event-timeline__sources">
          <button
            type="button"
            class="xt-event-timeline__source-toggle"
            :aria-expanded="isExpanded(evt.id)"
            @click="toggleSources(evt.id)"
          >
            <span>{{ isExpanded(evt.id) ? '收起原始记录' : '查看原始记录' }}</span>
            <small>
              {{ evt.rawCount }} 条
              <template v-if="evt.traceIds?.length"> · {{ evt.traceIds.length }} 个追踪编号</template>
            </small>
          </button>
          <ol v-if="isExpanded(evt.id)" class="xt-event-timeline__source-list">
            <li
              v-for="(sourceEvent, sourceIndex) in evt.sourceEvents"
              :key="`${sourceEvent.id}:${sourceIndex}`"
            >
              <EventCard :event="sourceEvent" @open="onOpen" />
            </li>
          </ol>
        </div>
      </li>
    </ol>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
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
const expandedIds = ref(new Set())

const formattedDate = computed(() => {
  if (!props.targetDate) return ''
  const d = dayjs(props.targetDate)
  return `${d.month() + 1} 月 ${d.date()} 日`
})

function onOpen(event) {
  if (event && event.detailRoute) router.push(event.detailRoute)
}

function isExpanded(id) {
  return expandedIds.value.has(id)
}

function toggleSources(id) {
  const next = new Set(expandedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedIds.value = next
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
.xt-event-timeline__sources {
  border-top: 1px solid color-mix(in srgb, var(--xt-border) 76%, transparent);
  background: color-mix(in srgb, var(--xt-bg-panel-soft) 72%, transparent);
}
.xt-event-timeline__source-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-2);
  width: 100%;
  min-height: 36px;
  padding: var(--xt-space-1) var(--xt-space-3) var(--xt-space-1) 132px;
  border: 0;
  background: transparent;
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-weight: 800;
  text-align: left;
  cursor: pointer;
}
.xt-event-timeline__source-toggle:hover {
  background: color-mix(in srgb, var(--xt-color-accent) 7%, transparent);
}
.xt-event-timeline__source-toggle small {
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
}
.xt-event-timeline__source-list {
  list-style: none;
  margin: 0;
  padding: 0 0 var(--xt-space-2) 108px;
}
.xt-event-timeline__source-list > li {
  border-top: 1px solid color-mix(in srgb, var(--xt-border) 58%, transparent);
}
.xt-event-timeline__source-list :deep(.xt-event-card) {
  min-height: 48px;
}
@media (max-width: 720px) {
  .xt-event-timeline__source-toggle {
    padding-left: var(--xt-space-3);
  }
  .xt-event-timeline__source-list {
    padding-left: var(--xt-space-3);
  }
}
</style>
