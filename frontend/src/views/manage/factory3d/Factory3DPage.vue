<template>
  <section class="xt-factory3d" data-testid="manage-factory-3d">
    <header class="xt-factory3d__hero">
      <h1>3D 工厂</h1>
      <DateSwitcher
        :model-value="snapshot.targetDate.value"
        :loading="snapshot.loading.value"
        :freshness="snapshot.freshnessStatus.value"
        @step="snapshot.stepDate"
        @refresh="snapshot.load"
        @pick="(d) => snapshot.targetDate.value = d"
      />
    </header>

    <div class="xt-factory3d__legend" aria-hidden="true">
      <span><i class="is-data" />有产量</span>
      <span><i class="is-empty" />无数据</span>
      <span>柱高按工序组内比较</span>
    </div>

    <div class="xt-factory3d__stage" data-testid="factory-stage" :data-mode="mode">
      <span v-if="dataError" class="xt-factory3d__error" data-testid="factory-data-error">数据未加载</span>
      <div v-if="mode === '3d'" ref="canvasHost" class="xt-factory3d__canvas" data-testid="factory-canvas" />

      <template v-if="mode === '3d'">
        <component
          :is="block.workshopId ? 'button' : 'span'"
          v-for="block in labelledBlocks"
          v-show="labels[block.key]?.visible"
          :key="block.key"
          class="xt-factory3d__label"
          :class="{ 'is-empty': !block.hasData, 'is-annex': !block.isWorkshop, 'is-hover': hoveredKey === block.key }"
          :type="block.workshopId ? 'button' : undefined"
          :style="labelStyle(block.key)"
          data-testid="factory-label"
          @click="open(block)"
        >
          <span>{{ block.label }}</span>
          <strong v-if="block.isWorkshop">{{ formatTons(block.tons) }}</strong>
        </component>
      </template>

      <div v-else-if="mode === '2d'" class="xt-factory3d__plan" data-testid="factory-plan">
        <component
          :is="block.workshopId ? 'button' : 'div'"
          v-for="block in model.blocks"
          :key="block.key"
          class="xt-factory3d__plot"
          :class="{ 'is-data': block.hasData, 'is-building': !block.isWorkshop }"
          :type="block.workshopId ? 'button' : undefined"
          :style="plotStyle(block)"
          data-testid="factory-label"
          @click="open(block)"
        >
          <span>{{ block.label }}</span>
          <strong v-if="block.isWorkshop">{{ formatTons(block.tons) }}</strong>
        </component>
      </div>
    </div>

    <section v-if="model.offMap.length" class="xt-factory3d__offmap" aria-labelledby="factory-offmap-title">
      <h2 id="factory-offmap-title">其他车间</h2>
      <ul>
        <li v-for="item in model.offMap" :key="item.name">
          <button v-if="item.workshopId" type="button" @click="open(item)">
            <span>{{ item.name }}</span><strong>{{ formatTons(item.tons) }}</strong>
          </button>
          <template v-else>
            <span>{{ item.name }}</span><strong>{{ formatTons(item.tons) }}</strong>
          </template>
        </li>
      </ul>
    </section>

    <table class="xt-factory3d__sr">
      <caption>各车间当日产量（吨）</caption>
      <tbody>
        <tr v-for="block in workshopBlocks" :key="block.key">
          <th scope="row">{{ block.label }}</th>
          <td>{{ formatTons(block.tons) }}</td>
        </tr>
        <tr v-for="item in model.offMap" :key="item.name">
          <th scope="row">{{ item.name }}</th>
          <td>{{ formatTons(item.tons) }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import { useDashboardSnapshot } from '../../../composables/useDashboardSnapshot.js'
import { buildFactoryModel, formatTons } from '../../../utils/factory-layout.js'

const router = useRouter()
const snapshot = useDashboardSnapshot()
snapshot.load()

const mode = ref('loading')
const canvasHost = ref(null)
const labels = ref({})
const scene = shallowRef(null)
const hoveredKey = ref(null)
const dataError = computed(() => Boolean(snapshot.lastError.value) && !(snapshot.productionLane.value || []).length)

const model = computed(() => buildFactoryModel(snapshot.productionLane.value || []))
const workshopBlocks = computed(() => model.value.blocks.filter((block) => block.isWorkshop))
const labelledBlocks = computed(() => model.value.blocks)

function labelStyle(key) {
  const position = labels.value[key]
  return position ? { left: `${position.left}px`, top: `${position.top}px` } : {}
}

function plotStyle(block) {
  return {
    left: `${(block.x / 935) * 100}%`,
    top: `${(block.y / 570) * 100}%`,
    width: `${(block.w / 935) * 100}%`,
    height: `${(block.h / 570) * 100}%`
  }
}

function open(item) {
  if (!item.workshopId) return
  router.push({ name: 'manage-workshop-dashboard', query: { workshop_id: item.workshopId } })
}

function readColor(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return /^#[0-9a-f]{6}$/i.test(value) ? value : fallback
}

function fallbackTo2D(reason) {
  scene.value?.destroy()
  scene.value = null
  mode.value = '2d'
  if (reason) console.warn('[3D 工厂] 改用 2D：', reason)
}

onMounted(async () => {
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  if (reducedMotion) return fallbackTo2D()
  try {
    const { createPlantScene, supportsWebGL } = await import('../../../components/factory/plant-scene.js')
    if (!supportsWebGL()) return fallbackTo2D('WebGL 不可用')
    mode.value = '3d'
    await nextTick()
    scene.value = createPlantScene(canvasHost.value, {
      colors: {
        ground: readColor('--xt-bg-depth', '#0a1424'),
        roof: readColor('--xt-roof', '#2a5fa8'),
        hover: readColor('--xt-primary-hover', '#6aa2ff')
      },
      animate: true,
      onSelect: open,
      onHover: (key) => { hoveredKey.value = key },
      onLabels: (next) => { labels.value = next },
      onLost: () => fallbackTo2D('WebGL 上下文丢失')
    })
    scene.value.update(model.value.blocks)
  } catch (error) {
    fallbackTo2D(error?.message || '3D 加载失败')
  }
})

watch(model, (next) => scene.value?.update(next.blocks))

onBeforeUnmount(() => scene.value?.destroy())
</script>

<style scoped>
.xt-factory3d {
  display: grid;
  gap: 16px;
  color: var(--xt-text);
}

.xt-factory3d__hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.xt-factory3d__hero h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
}

.xt-factory3d__legend {
  display: flex;
  gap: 20px;
  color: var(--xt-text-secondary);
  font-size: 13px;
}

.xt-factory3d__legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.xt-factory3d__legend i {
  width: 10px;
  height: 10px;
  border-radius: 2px;
}

.xt-factory3d__legend i.is-data {
  background: var(--xt-primary);
}

.xt-factory3d__legend i.is-empty {
  background: var(--xt-border);
}

.xt-factory3d__stage {
  position: relative;
  width: 100%;
  aspect-ratio: 935 / 570;
  max-height: calc(100vh - 220px);
  min-height: 360px;
  overflow: hidden;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background-color: var(--xt-bg-depth);
  background-image:
    linear-gradient(var(--xt-grid-line, transparent) 1px, transparent 1px),
    linear-gradient(90deg, var(--xt-grid-line, transparent) 1px, transparent 1px);
  background-size: 24px 24px;
}

.xt-factory3d__error {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 2;
  padding: 2px 8px;
  border: 1px solid var(--xt-danger-border);
  border-radius: 999px;
  background: var(--xt-danger-light);
  color: var(--xt-danger);
  font-size: 12px;
}

.xt-factory3d__canvas,
.xt-factory3d__canvas :deep(canvas) {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.xt-factory3d__label {
  position: absolute;
  display: grid;
  justify-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  border: 1px solid var(--xt-border-strong);
  background: var(--xt-label-bg, rgba(255, 255, 255, 0.92));
  color: var(--xt-text);
  font: inherit;
  font-size: 12px;
  line-height: 1.3;
  white-space: nowrap;
  transform: translate(-50%, -100%);
  pointer-events: auto;
}

.xt-factory3d__label.is-annex {
  padding: 1px 8px;
  border-color: transparent;
  color: var(--xt-text-muted);
  font-size: 11px;
}

.xt-factory3d__label.is-hover {
  border-color: var(--xt-primary-hover);
}

button.xt-factory3d__label,
button.xt-factory3d__plot,
.xt-factory3d__offmap button {
  cursor: pointer;
}

.xt-factory3d__label strong {
  color: var(--xt-primary);
  font-family: var(--xt-font-mono);
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}

.xt-factory3d__label.is-empty strong {
  color: var(--xt-text-muted);
}

.xt-factory3d__plan {
  position: absolute;
  inset: 0;
}

.xt-factory3d__plot {
  position: absolute;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 2px;
  box-sizing: border-box;
  border: 1px solid var(--xt-bg-page);
  border-radius: 2px;
  background: var(--xt-border);
  color: var(--xt-text);
  font: inherit;
  font-size: 12px;
}

.xt-factory3d__plot.is-data {
  background: var(--xt-primary-solid, var(--xt-primary));
  color: #fff;
}

.xt-factory3d__plot.is-building {
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-muted);
}

.xt-factory3d__plot strong {
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}

.xt-factory3d__offmap h2 {
  margin: 0 0 8px;
  color: var(--xt-text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.xt-factory3d__offmap ul {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.xt-factory3d__offmap li > button,
.xt-factory3d__offmap li {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
}

.xt-factory3d__offmap li > button {
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: var(--xt-bg-panel);
  color: var(--xt-text);
  font: inherit;
  font-size: 13px;
}

.xt-factory3d__offmap strong {
  color: var(--xt-primary);
  font-variant-numeric: tabular-nums;
}

.xt-factory3d__sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
</style>
