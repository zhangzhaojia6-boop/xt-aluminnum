<template>
  <aside class="live-event-rail" aria-label="实时事件">
    <header class="live-section-head">
      <div>
        <span>事件流</span>
        <strong>{{ connectionText }}</strong>
      </div>
      <em>{{ lastEventAt || '等待事件' }}</em>
    </header>

    <div v-if="events.length" class="live-event-rail__list">
      <article v-for="event in events" :key="`${event.title}-${event.text}`" :class="`is-${event.tone}`">
        <span>{{ event.title }}</span>
        <strong>{{ event.text }}</strong>
      </article>
    </div>
    <div v-else class="live-event-rail__empty">暂无异常事件</div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  events: {
    type: Array,
    default: () => [],
  },
  streamStatus: {
    type: String,
    default: 'idle',
  },
  lastEventAt: {
    type: String,
    default: '',
  },
})

const connectionText = computed(() => {
  if (props.streamStatus === 'open') return '实时连接正常'
  if (props.streamStatus === 'connecting') return '正在连接'
  if (props.streamStatus === 'reconnecting') return '正在重连'
  return '连接待核'
})
</script>
