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
  position: relative;
  display: grid;
  grid-template-columns: 5px 1fr;
  gap: var(--xt-space-3);
  padding: var(--xt-space-4);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 26%, var(--xt-border-ink));
  border-radius: var(--xt-radius-xl);
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--xt-primary) 20%, transparent), transparent 34%),
    linear-gradient(135deg, color-mix(in srgb, var(--xt-bg-ink-panel) 90%, var(--xt-bg-panel)), var(--xt-bg-ink));
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, var(--xt-text-inverse) 8%, transparent),
    0 12px 28px color-mix(in srgb, var(--xt-bg-ink) 42%, transparent);
  overflow: hidden;
}

.xt-summary-hero::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(90deg, transparent, color-mix(in srgb, var(--xt-primary) 16%, transparent), transparent),
    linear-gradient(color-mix(in srgb, var(--xt-text-inverse) 4%, transparent) 50%, transparent 50%);
  background-size: auto, 100% 4px;
  opacity: 0.45;
}

.xt-summary-hero__bar {
  width: 5px;
  height: 100%;
  align-self: stretch;
  border-radius: var(--xt-radius-pill);
  background: linear-gradient(180deg, var(--xt-primary), var(--xt-success));
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--xt-text-inverse) 16%, transparent);
}

.xt-summary-hero__body {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-2);
  min-width: 0;
}

.xt-summary-hero__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-2);
}

.xt-summary-hero__caption {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
}

.xt-summary-hero__pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 9px;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 52%, transparent);
  border-radius: var(--xt-radius-pill);
  background: color-mix(in srgb, var(--xt-primary) 20%, transparent);
  color: var(--xt-text-inverse);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
}

.xt-summary-hero__date {
  color: color-mix(in srgb, var(--xt-text-inverse) 54%, transparent);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.xt-summary-hero__toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 11px;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 22%, var(--xt-border-ink));
  border-radius: var(--xt-radius-pill);
  background: color-mix(in srgb, var(--xt-bg-ink-panel) 62%, transparent);
  color: color-mix(in srgb, var(--xt-text-inverse) 68%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 800;
  cursor: pointer;
  transition:
    border-color 120ms ease,
    color 120ms ease,
    transform 120ms ease;
}

.xt-summary-hero__toggle:hover {
  border-color: color-mix(in srgb, var(--xt-primary) 58%, var(--xt-border-ink));
  color: var(--xt-text-inverse);
}

.xt-summary-hero__toggle:active {
  transform: scale(0.97);
}

.xt-summary-hero__chev {
  font-size: 12px;
  transition: transform 160ms ease;
}

.xt-summary-hero__chev.is-open {
  transform: rotate(90deg);
}

.xt-summary-hero__lead {
  margin: 0;
  color: var(--xt-text-inverse);
  font-size: var(--xt-text-md);
  font-weight: 700;
  line-height: 1.72;
  letter-spacing: -0.005em;
}

.xt-summary-hero__lead--muted {
  color: color-mix(in srgb, var(--xt-text-inverse) 50%, transparent);
  font-weight: 600;
}

.xt-summary-hero__rest {
  margin-top: var(--xt-space-2);
  padding-top: var(--xt-space-2);
  border-top: 1px dashed color-mix(in srgb, var(--xt-primary) 22%, var(--xt-border-ink));
  color: color-mix(in srgb, var(--xt-text-inverse) 72%, transparent);
  font-size: var(--xt-text-sm);
  line-height: 1.72;
  white-space: pre-wrap;
}

.xt-hero-expand-enter-active,
.xt-hero-expand-leave-active {
  transition: opacity 180ms ease, transform 180ms ease;
}

.xt-hero-expand-enter-from,
.xt-hero-expand-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (prefers-reduced-motion: reduce) {
  .xt-summary-hero__toggle,
  .xt-hero-expand-enter-active,
  .xt-hero-expand-leave-active {
    transition: none;
  }
}
</style>
