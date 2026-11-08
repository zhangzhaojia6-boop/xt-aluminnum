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
  connectionText: {
    type: String,
    default: '',
  },
})

const connectionText = computed(() => {
  if (props.connectionText) return props.connectionText
  if (props.streamStatus === 'open') return '实时连接正常'
  if (props.streamStatus === 'connecting') return '接口核验中 · 快照兜底'
  if (props.streamStatus === 'reconnecting') return '正在重连'
  return '连接待核'
})
</script>

<style scoped>
.live-event-rail {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  padding: 16px;
  background: transparent;

}

.live-event-rail::before {
  position: absolute;
  inset: 0;
  background: transparent;
  opacity: 0.7;
  content: "";
  pointer-events: none;
}

.live-section-head,
.live-event-rail__list,
.live-event-rail__empty {
  position: relative;
  z-index: 1;
}

.live-section-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 14px;
}

.live-section-head span {
  color: var(--xt-text);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.14em;
}

.live-section-head strong {
  display: block;
  margin-top: 3px;
  color: var(--xt-text);
  font-size: 18px;
}

.live-section-head em {
  color: var(--xt-text-secondary);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
  font-style: normal;
  font-size: 12px;
}

.live-event-rail__list {
  display: grid;
  gap: 10px;
}

.live-event-rail__list article {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--xt-border);
  border-left: 3px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
  padding: 11px 12px;
}

.live-event-rail__list article::after {
  position: absolute;
  top: 0;
  right: 12px;
  left: 12px;
  height: 1px;
  background: transparent;
  content: "";
}

.live-event-rail__list article.is-warning {
  border-left-color: var(--xt-border);
}

.live-event-rail__list article.is-danger {
  border-left-color: var(--xt-border);
}

.live-event-rail__list span,
.live-event-rail__list strong {
  position: relative;
  z-index: 1;
  display: block;
}

.live-event-rail__list span {
  color: var(--xt-text-secondary);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.live-event-rail__list strong {
  margin-top: 5px;
  color: var(--xt-text);
  font-size: 13px;
  line-height: 1.4;
}

.live-event-rail__empty {
  display: grid;
  min-height: 220px;
  place-items: center;
  color: var(--xt-text-secondary);
}

</style>
