<template>
  <section class="xt-summary-hero" data-testid="manage-summary-hero">
    <div class="xt-summary-hero__bar" />
    <div class="xt-summary-hero__body">
      <div class="xt-summary-hero__head">
        <div class="xt-summary-hero__caption">
          <span class="xt-summary-hero__pill">AI 总览</span>
          <span class="xt-summary-hero__date">{{ formattedDate }}</span>
        </div>
        <button
          v-if="hasFull"
          type="button"
          class="xt-summary-hero__toggle"
          @click="open = !open"
          :aria-expanded="open"
        >
          {{ open ? '收起' : '展开完整日报' }}
          <span class="xt-summary-hero__chev" :class="{ 'is-open': open }" aria-hidden="true">›</span>
        </button>
      </div>
      <p v-if="lead" class="xt-summary-hero__lead">{{ lead }}</p>
      <p v-else class="xt-summary-hero__lead xt-summary-hero__lead--muted">日报正文尚未生成</p>
      <Transition name="xt-hero-expand">
        <div v-if="open && rest" class="xt-summary-hero__rest">{{ rest }}</div>
      </Transition>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import dayjs from 'dayjs'

const props = defineProps({
  text: { type: String, default: '' },
  date: { type: String, default: '' },
  metrics: { type: Object, default: () => ({}) }
})

const open = ref(false)

function splitLead(raw) {
  const s = String(raw || '').trim()
  if (!s) return { lead: '', rest: '' }
  const parts = s.split(/\n{2,}|(?<=[。！？])\s+/)
  if (parts.length <= 1) {
    if (s.length > 120) {
      return { lead: s.slice(0, 110) + '…', rest: s }
    }
    return { lead: s, rest: '' }
  }
  const head = parts.slice(0, 2).join(' ')
  const tail = parts.slice(2).join(' ')
  return { lead: head, rest: tail }
}

const split = computed(() => splitLead(props.text))
const lead = computed(() => split.value.lead)
const rest = computed(() => split.value.rest)
const hasFull = computed(() => !!rest.value)

const formattedDate = computed(() => {
  if (!props.date) return ''
  const d = dayjs(props.date)
  return `${d.month() + 1}月${d.date()}日 · ${['日', '一', '二', '三', '四', '五', '六'][d.day()]}`
})
</script>

<style scoped>
.xt-summary-hero {
  display: grid;
  grid-template-columns: 4px 1fr;
  gap: var(--xt-space-3);
  background: linear-gradient(135deg, var(--xt-bg-panel) 0%, var(--xt-bg-panel-soft) 100%);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  padding: var(--xt-space-3) var(--xt-space-4);
  position: relative;
  overflow: hidden;
}
.xt-summary-hero__bar {
  width: 4px; height: 100%;
  background: linear-gradient(180deg, var(--xt-primary, #1f6feb) 0%, var(--xt-success, #3ba55c) 100%);
  border-radius: 2px;
  align-self: stretch;
}
.xt-summary-hero__body { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.xt-summary-hero__head {
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--xt-space-2);
}
.xt-summary-hero__caption { display: flex; align-items: center; gap: var(--xt-space-2); }
.xt-summary-hero__pill {
  display: inline-flex; align-items: center;
  padding: 1px 8px;
  background: var(--xt-primary, #1f6feb);
  color: #fff;
  font-size: 11px; font-weight: 800; letter-spacing: 0.04em;
  border-radius: var(--xt-radius-pill);
}
.xt-summary-hero__date {
  font-size: var(--xt-text-xs); color: var(--xt-text-muted); font-weight: 700;
}
.xt-summary-hero__toggle {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 10px;
  background: transparent;
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-pill);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs); font-weight: 700;
  cursor: pointer;
  transition: border-color 120ms ease;
}
.xt-summary-hero__toggle:hover { border-color: var(--xt-border-strong); color: var(--xt-text); }
.xt-summary-hero__chev { font-size: 12px; transition: transform 160ms ease; }
.xt-summary-hero__chev.is-open { transform: rotate(90deg); }
.xt-summary-hero__lead {
  margin: 0;
  font-size: var(--xt-text-md);
  font-weight: 600;
  line-height: 1.65;
  color: var(--xt-text);
  letter-spacing: -0.005em;
}
.xt-summary-hero__lead--muted { color: var(--xt-text-muted); font-weight: 500; }
.xt-summary-hero__rest {
  margin-top: var(--xt-space-2);
  padding-top: var(--xt-space-2);
  border-top: 1px dashed var(--xt-border);
  font-size: var(--xt-text-sm);
  line-height: 1.7;
  color: var(--xt-text-secondary);
  white-space: pre-wrap;
}
.xt-hero-expand-enter-active,
.xt-hero-expand-leave-active { transition: opacity 180ms ease, transform 180ms ease; }
.xt-hero-expand-enter-from,
.xt-hero-expand-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
