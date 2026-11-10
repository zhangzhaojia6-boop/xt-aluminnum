<template>
  <section class="xt-fact-band" data-testid="today-fact-actions" aria-label="事实行动摘要">
    <div class="xt-fact-band__head">
      <h2>还缺 <b>{{ open }}</b> 项事实，日报暂不发送</h2>
      <RouterLink class="xt-today__fact-action-link" :to="to" :aria-label="linkLabel">
        查看 <el-icon><ArrowRight /></el-icon>
      </RouterLink>
    </div>

    <div class="xt-fact-band__ticks" role="img" :aria-label="`共 ${total} 项，已有 ${have} 项`">
      <i
        v-for="(tone, index) in ticks"
        :key="index"
        :class="`is-${tone}`"
        :style="{ animationDelay: `${index * 5}ms` }"
      />
    </div>

    <ul class="xt-fact-band__legend">
      <li v-for="item in legend" :key="item.key"><i :class="`is-${item.key}`" />{{ item.label }} <b>{{ item.count }}</b></li>
    </ul>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'

const props = defineProps({
  total: { type: Number, default: 127 },
  open: { type: Number, required: true },
  manual: { type: Number, default: 0 },
  recheck: { type: Number, default: 0 },
  dependency: { type: Number, default: 0 },
  to: { type: [String, Object], required: true },
  linkLabel: { type: String, default: '打开事实待办' }
})

const have = computed(() => Math.max(props.total - props.open, 0))
const legend = computed(() => [
  { key: 'have', label: '已有', count: have.value },
  { key: 'manual', label: '缺来源', count: props.manual },
  { key: 'recheck', label: '系统复查', count: props.recheck },
  { key: 'dependency', label: '等上游数据', count: props.dependency }
])
const ticks = computed(() => {
  const tones = []
  for (const item of legend.value) {
    for (let index = 0; index < item.count && tones.length < props.total; index += 1) tones.push(item.key)
  }
  while (tones.length < props.total) tones.push('dependency')
  return tones
})
</script>

<style scoped>
.xt-fact-band { display: grid; gap: 24px; padding: 32px 40px; border-radius: 4px; background: var(--xt-primary-solid, var(--xt-primary)); color: #fff; }
.xt-fact-band__head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px 24px; }
.xt-fact-band h2 { margin: 0; font-size: 20px; font-weight: 400; }
.xt-fact-band h2 b { font-size: 40px; font-weight: 600; font-variant-numeric: tabular-nums; }
.xt-today__fact-action-link { display: inline-flex; align-items: center; gap: 4px; color: #fff; font-size: 14px; text-decoration: none; }
.xt-fact-band__ticks { display: grid; grid-template-columns: repeat(127, minmax(0, 1fr)); gap: 2px; height: 32px; }
.xt-fact-band__ticks i { display: block; border-radius: 1px; transform-origin: bottom; animation: xt-tick-in 420ms cubic-bezier(0.16, 1, 0.3, 1) backwards; }
.is-have { background: #fff; }
.is-manual { background: #f2b84b; }
.is-recheck { background: rgba(255, 255, 255, 0.5); }
.is-dependency { background: rgba(255, 255, 255, 0.2); }
.xt-fact-band__legend { display: flex; flex-wrap: wrap; gap: 8px 32px; margin: 0; padding: 0; list-style: none; font-size: 14px; }
.xt-fact-band__legend li { display: inline-flex; align-items: center; gap: 8px; }
.xt-fact-band__legend i { width: 10px; height: 10px; border-radius: 2px; }
.xt-fact-band__legend b { font-weight: 600; font-variant-numeric: tabular-nums; }
@keyframes xt-tick-in { from { transform: scaleY(0); } }
@media (max-width: 700px) {
  .xt-fact-band { padding: 24px 20px; }
  .xt-fact-band__ticks { gap: 1px; height: 28px; }
  .xt-fact-band__legend { gap: 8px 20px; }
}
@media (prefers-reduced-motion: reduce) {
  .xt-fact-band__ticks i { animation: none; }
}
</style>
