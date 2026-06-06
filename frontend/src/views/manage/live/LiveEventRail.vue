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
  border: 1px solid rgba(0, 242, 255, 0.17);
  border-radius: 18px;
  padding: 16px;
  background:
    linear-gradient(180deg, rgba(8, 33, 58, 0.82), rgba(3, 15, 28, 0.94)),
    radial-gradient(circle at 20% 0%, rgba(0, 242, 255, 0.14), transparent 42%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.live-event-rail::before {
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(180deg, rgba(225, 253, 255, 0.035) 0 1px, transparent 1px 8px);
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
  color: rgba(116, 245, 255, 0.72);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
}

.live-section-head strong {
  display: block;
  margin-top: 3px;
  color: rgba(225, 253, 255, 0.94);
  font-size: 18px;
}

.live-section-head em {
  color: rgba(185, 223, 235, 0.62);
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
  border: 1px solid rgba(0, 242, 255, 0.12);
  border-left: 3px solid rgba(0, 242, 255, 0.52);
  border-radius: 10px;
  background: rgba(2, 16, 31, 0.74);
  padding: 11px 12px;
}

.live-event-rail__list article::after {
  position: absolute;
  top: 0;
  right: 12px;
  left: 12px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(0, 242, 255, 0.16), transparent);
  content: "";
}

.live-event-rail__list article.is-warning {
  border-left-color: #ffab00;
}

.live-event-rail__list article.is-danger {
  border-left-color: #ff5d4d;
}

.live-event-rail__list span,
.live-event-rail__list strong {
  position: relative;
  z-index: 1;
  display: block;
}

.live-event-rail__list span {
  color: rgba(185, 223, 235, 0.58);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.live-event-rail__list strong {
  margin-top: 5px;
  color: rgba(225, 253, 255, 0.88);
  font-size: 13px;
  line-height: 1.4;
}

.live-event-rail__empty {
  display: grid;
  min-height: 220px;
  place-items: center;
  color: rgba(185, 223, 235, 0.68);
}

</style>
