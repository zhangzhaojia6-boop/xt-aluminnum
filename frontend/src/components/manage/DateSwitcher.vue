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
  const todayIso = dayjs().format('YYYY-MM-DD')
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
      isFuture: d.isAfter(dayjs(), 'day')
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
  const d = dayjs().add(deltaDays, 'day').format('YYYY-MM-DD')
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
.xt-date-switcher { position: relative; display: flex; align-items: center; gap: var(--xt-space-2); }
.xt-date-switcher__btn,
.xt-date-switcher__refresh,
.xt-date-switcher__label {
  min-height: 36px;
  padding: 0 var(--xt-space-3);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  background: var(--xt-bg-panel);
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  cursor: pointer;
  transition: border-color 120ms ease, background 120ms ease;
}
.xt-date-switcher__btn:hover:not(:disabled),
.xt-date-switcher__refresh:hover:not(:disabled),
.xt-date-switcher__label:hover { border-color: var(--xt-border-strong); }
.xt-date-switcher__btn:disabled,
.xt-date-switcher__refresh:disabled { opacity: 0.5; cursor: not-allowed; }
.xt-date-switcher__label {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: var(--xt-text-md); font-weight: 800; color: var(--xt-text);
}
.xt-date-switcher__label.is-open { border-color: var(--xt-primary, var(--xt-color-accent)); }
.xt-date-switcher__caret { font-size: 10px; color: var(--xt-text-muted); }
.xt-date-switcher__dot { width: 8px; height: 8px; border-radius: 50%; }
.xt-date-switcher__dot.is-green { background: var(--xt-color-success); }
.xt-date-switcher__dot.is-yellow { background: var(--xt-color-warning); }
.xt-date-switcher__dot.is-red { background: var(--xt-color-danger); }

.xt-cal-pop {
  position: absolute;
  top: calc(100% + 6px);
  left: 36px;
  z-index: 60;
  width: 280px;
  padding: var(--xt-space-3);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.12), 0 2px 6px rgba(15, 23, 42, 0.06);
  display: flex; flex-direction: column; gap: var(--xt-space-2);
}
.xt-cal-pop__head {
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--xt-space-2);
}
.xt-cal-pop__title { font-size: var(--xt-text-sm); font-weight: 800; color: var(--xt-text); }
.xt-cal-pop__nav {
  width: 28px; height: 28px;
  display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid var(--xt-border); border-radius: var(--xt-radius-sm);
  background: transparent; color: var(--xt-text-secondary);
  cursor: pointer;
}
.xt-cal-pop__nav:hover { border-color: var(--xt-border-strong); color: var(--xt-text); }

.xt-cal-pop__weekdays {
  display: grid; grid-template-columns: repeat(7, 1fr);
  font-size: 11px; color: var(--xt-text-muted); font-weight: 700;
  text-align: center;
}
.xt-cal-pop__weekdays span { padding: 4px 0; }
.xt-cal-pop__grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
.xt-cal-pop__cell {
  height: 30px;
  border: 1px solid transparent;
  border-radius: var(--xt-radius-sm);
  background: transparent;
  font-size: var(--xt-text-xs); font-weight: 700;
  color: var(--xt-text);
  cursor: pointer;
  font-variant-numeric: tabular-nums;
  transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
}
.xt-cal-pop__cell:hover:not(:disabled) { background: var(--xt-bg-panel-soft); border-color: var(--xt-border); }
.xt-cal-pop__cell.is-out { color: var(--xt-text-muted); opacity: 0.55; }
.xt-cal-pop__cell.is-today { color: var(--xt-primary, var(--xt-color-accent)); }
.xt-cal-pop__cell.is-selected {
  background: var(--xt-primary, #1f6feb);
  color: #fff;
  border-color: var(--xt-primary, #1f6feb);
}
.xt-cal-pop__cell.is-future { color: var(--xt-text-muted); opacity: 0.4; cursor: not-allowed; }

.xt-cal-pop__quick {
  display: flex; gap: 6px; justify-content: space-between;
  padding-top: var(--xt-space-2);
  border-top: 1px dashed var(--xt-border);
}
.xt-cal-pop__quick-btn {
  flex: 1;
  padding: 4px 0;
  background: transparent;
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-sm);
  color: var(--xt-text-secondary);
  font-size: 11px; font-weight: 700;
  cursor: pointer;
}
.xt-cal-pop__quick-btn:hover { border-color: var(--xt-border-strong); color: var(--xt-text); }
.xt-cal-pop__quick-btn--accent { color: var(--xt-primary, var(--xt-color-accent)); border-color: var(--xt-primary, var(--xt-color-accent)); }

.xt-cal-pop-enter-active,
.xt-cal-pop-leave-active { transition: opacity 140ms ease, transform 140ms ease; }
.xt-cal-pop-enter-from,
.xt-cal-pop-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
