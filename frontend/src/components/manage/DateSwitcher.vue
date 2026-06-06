<!-- frontend/src/components/manage/DateSwitcher.vue -->
<template>
  <div class="xt-date-switcher" data-testid="manage-date-switcher" ref="rootRef">
    <button
      type="button"
      class="xt-date-switcher__btn"
      :disabled="loading"
      @click="emit('step', -1)"
      aria-label="前一天"
    >‹</button>
    <button
      type="button"
      class="xt-date-switcher__label"
      :class="{ 'is-open': open }"
      @click="open = !open"
      :aria-expanded="open"
    >
      <span>{{ formatted }}</span>
      <span class="xt-date-switcher__caret" aria-hidden="true">▾</span>
    </button>
    <button
      type="button"
      class="xt-date-switcher__btn"
      :disabled="loading"
      @click="emit('step', 1)"
      aria-label="后一天"
    >›</button>
    <button
      type="button"
      class="xt-date-switcher__refresh"
      :disabled="loading"
      @click="emit('refresh')"
    >刷新</button>
    <span
      v-if="freshness"
      class="xt-date-switcher__dot"
      :class="`is-${freshness}`"
      :aria-label="`同步状态 ${freshness}`"
    />

    <Transition name="xt-cal-pop">
      <div v-if="open" class="xt-cal-pop" role="dialog" aria-label="选择日期">
        <header class="xt-cal-pop__head">
          <button type="button" class="xt-cal-pop__nav" @click="navMonth(-1)" aria-label="上一月">‹</button>
          <span class="xt-cal-pop__title">{{ viewYear }} 年 {{ viewMonth + 1 }} 月</span>
          <button type="button" class="xt-cal-pop__nav" @click="navMonth(1)" aria-label="下一月">›</button>
        </header>
        <div class="xt-cal-pop__weekdays">
          <span v-for="w in WEEKDAYS" :key="w">{{ w }}</span>
        </div>
        <div class="xt-cal-pop__grid">
          <button
            v-for="cell in cells"
            :key="cell.key"
            type="button"
            class="xt-cal-pop__cell"
            :class="{
              'is-out': cell.outOfMonth,
              'is-today': cell.isToday,
              'is-selected': cell.isSelected,
              'is-future': cell.isFuture
            }"
            :disabled="cell.isFuture"
            @click="pick(cell.iso)"
          >{{ cell.day }}</button>
        </div>
        <footer class="xt-cal-pop__quick">
          <button type="button" class="xt-cal-pop__quick-btn" @click="pickQuick(-1)">昨日</button>
          <button type="button" class="xt-cal-pop__quick-btn" @click="pickQuick(-7)">7 天前</button>
          <button type="button" class="xt-cal-pop__quick-btn" @click="pickQuick(-30)">30 天前</button>
          <button type="button" class="xt-cal-pop__quick-btn xt-cal-pop__quick-btn--accent" @click="pickQuick(0)">今天</button>
        </footer>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { inferBusinessDate } from '../../utils/shiftClock'

const props = defineProps({
  modelValue: { type: String, required: true },
  loading: { type: Boolean, default: false },
  freshness: { type: String, default: null }
})
const emit = defineEmits(['step', 'refresh', 'pick'])

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

const formatted = computed(() => {
  const d = dayjs(props.modelValue)
  return `${d.month() + 1}月${d.date()}日 日报`
})

const open = ref(false)
const rootRef = ref(null)

const viewYear = ref(dayjs(props.modelValue).year())
const viewMonth = ref(dayjs(props.modelValue).month())

watch(() => props.modelValue, (next) => {
  const d = dayjs(next)
  viewYear.value = d.year()
  viewMonth.value = d.month()
})

function navMonth(delta) {
  const d = dayjs(`${viewYear.value}-${String(viewMonth.value + 1).padStart(2, '0')}-01`).add(delta, 'month')
  viewYear.value = d.year()
  viewMonth.value = d.month()
}

const cells = computed(() => {
  const first = dayjs(`${viewYear.value}-${String(viewMonth.value + 1).padStart(2, '0')}-01`)
  const startWeekday = first.day()
  const start = first.subtract(startWeekday, 'day')
  const todayIso = inferBusinessDate()
  const list = []
  for (let i = 0; i < 42; i += 1) {
    const d = start.add(i, 'day')
    const iso = d.format('YYYY-MM-DD')
    list.push({
      key: iso,
      iso,
      day: d.date(),
      outOfMonth: d.month() !== viewMonth.value,
      isToday: iso === todayIso,
      isSelected: iso === props.modelValue,
      isFuture: d.isAfter(dayjs(todayIso), 'day')
    })
  }
  return list
})

function pick(iso) {
  if (!iso) return
  emit('pick', iso)
  open.value = false
}

function pickQuick(deltaDays) {
  const d = dayjs(inferBusinessDate()).add(deltaDays, 'day').format('YYYY-MM-DD')
  pick(d)
}

function onClickOutside(e) {
  if (!rootRef.value) return
  if (!rootRef.value.contains(e.target)) open.value = false
}
function onEsc(e) {
  if (e.key === 'Escape') open.value = false
}

onMounted(() => {
  document.addEventListener('mousedown', onClickOutside)
  document.addEventListener('keydown', onEsc)
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onClickOutside)
  document.removeEventListener('keydown', onEsc)
})
</script>

<style scoped>
.xt-date-switcher {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
}

.xt-date-switcher__btn,
.xt-date-switcher__refresh,
.xt-date-switcher__label {
  min-height: 38px;
  padding: 0 var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 22%, var(--xt-border-ink));
  border-radius: var(--xt-radius-lg);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--xt-text-inverse) 5%, transparent), transparent),
    color-mix(in srgb, var(--xt-bg-ink-panel) 82%, var(--xt-bg-panel));
  color: var(--xt-text-inverse);
  font-size: var(--xt-text-sm);
  cursor: pointer;
  box-shadow: inset 0 1px 0 color-mix(in srgb, var(--xt-text-inverse) 8%, transparent);
  transition:
    border-color 120ms ease,
    background 120ms ease,
    transform 120ms ease;
}

.xt-date-switcher__btn:hover:not(:disabled),
.xt-date-switcher__refresh:hover:not(:disabled),
.xt-date-switcher__label:hover {
  border-color: color-mix(in srgb, var(--xt-primary) 62%, var(--xt-border-ink));
  background: color-mix(in srgb, var(--xt-primary) 14%, var(--xt-bg-ink-panel));
}

.xt-date-switcher__btn:active:not(:disabled),
.xt-date-switcher__refresh:active:not(:disabled),
.xt-date-switcher__label:active {
  transform: scale(0.96);
}

.xt-date-switcher__btn:disabled,
.xt-date-switcher__refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.xt-date-switcher__label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-md);
  font-weight: 900;
}

.xt-date-switcher__label.is-open {
  border-color: var(--xt-primary);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--xt-primary) 28%, transparent);
}

.xt-date-switcher__caret {
  color: color-mix(in srgb, var(--xt-text-inverse) 54%, transparent);
  font-size: 10px;
}

.xt-date-switcher__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 18%, transparent);
}

.xt-date-switcher__dot.is-green { background: var(--xt-color-success); color: var(--xt-color-success); }
.xt-date-switcher__dot.is-yellow { background: var(--xt-color-warning); color: var(--xt-color-warning); }
.xt-date-switcher__dot.is-red { background: var(--xt-color-danger); color: var(--xt-color-danger); }

.xt-cal-pop {
  position: absolute;
  top: calc(100% + 8px);
  left: 36px;
  z-index: 60;
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-2);
  width: 286px;
  padding: var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 28%, var(--xt-border-ink));
  border-radius: var(--xt-radius-xl);
  background:
    radial-gradient(circle at 8% 0%, color-mix(in srgb, var(--xt-primary) 18%, transparent), transparent 34%),
    color-mix(in srgb, var(--xt-bg-ink-panel) 94%, var(--xt-bg-panel));
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, var(--xt-text-inverse) 8%, transparent),
    0 12px 28px color-mix(in srgb, var(--xt-bg-ink) 56%, transparent);
}

.xt-cal-pop__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-2);
}

.xt-cal-pop__title {
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-sm);
  font-weight: 900;
}

.xt-cal-pop__nav {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border-ink));
  border-radius: var(--xt-radius-sm);
  background: transparent;
  color: color-mix(in srgb, var(--xt-text-inverse) 66%, transparent);
  cursor: pointer;
}

.xt-cal-pop__nav:hover {
  border-color: color-mix(in srgb, var(--xt-primary) 58%, var(--xt-border-ink));
  color: var(--xt-text-inverse);
}

.xt-cal-pop__weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  color: color-mix(in srgb, var(--xt-text-inverse) 46%, transparent);
  font-size: 11px;
  font-weight: 800;
  text-align: center;
}

.xt-cal-pop__weekdays span {
  padding: 4px 0;
}

.xt-cal-pop__grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
}

.xt-cal-pop__cell {
  height: 30px;
  border: 1px solid transparent;
  border-radius: var(--xt-radius-sm);
  background: transparent;
  color: color-mix(in srgb, var(--xt-text-inverse) 78%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
  transition:
    background 120ms ease,
    border-color 120ms ease,
    color 120ms ease,
    transform 120ms ease;
}

.xt-cal-pop__cell:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--xt-primary) 26%, var(--xt-border));
  background: color-mix(in srgb, var(--xt-primary) 10%, var(--xt-bg-panel-soft));
}

.xt-cal-pop__cell:active:not(:disabled) {
  transform: scale(0.95);
}

.xt-cal-pop__cell.is-out {
  color: color-mix(in srgb, var(--xt-text-inverse) 34%, transparent);
  opacity: 0.68;
}

.xt-cal-pop__cell.is-today {
  color: var(--xt-primary);
}

.xt-cal-pop__cell.is-selected {
  border-color: var(--xt-primary);
  background: color-mix(in srgb, var(--xt-primary) 82%, var(--xt-bg-ink-panel));
  color: var(--xt-text-inverse);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--xt-text-inverse) 18%, transparent);
}

.xt-cal-pop__cell.is-future {
  color: color-mix(in srgb, var(--xt-text-inverse) 30%, transparent);
  opacity: 0.45;
  cursor: not-allowed;
}

.xt-cal-pop__quick {
  display: flex;
  gap: 6px;
  justify-content: space-between;
  padding-top: var(--xt-space-2);
  border-top: 1px dashed color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border-ink));
}

.xt-cal-pop__quick-btn {
  flex: 1;
  padding: 5px 0;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border-ink));
  border-radius: var(--xt-radius-sm);
  background: transparent;
  color: color-mix(in srgb, var(--xt-text-inverse) 62%, transparent);
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
}

.xt-cal-pop__quick-btn:hover {
  border-color: color-mix(in srgb, var(--xt-primary) 58%, var(--xt-border-ink));
  color: var(--xt-text-inverse);
}

.xt-cal-pop__quick-btn--accent {
  border-color: var(--xt-primary);
  color: var(--xt-primary);
}

.xt-cal-pop-enter-active,
.xt-cal-pop-leave-active {
  transition: opacity 140ms ease, transform 140ms ease;
}

.xt-cal-pop-enter-from,
.xt-cal-pop-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (prefers-reduced-motion: reduce) {
  .xt-date-switcher__btn,
  .xt-date-switcher__refresh,
  .xt-date-switcher__label,
  .xt-cal-pop__cell,
  .xt-cal-pop-enter-active,
  .xt-cal-pop-leave-active {
    transition: none;
  }
}
</style>
