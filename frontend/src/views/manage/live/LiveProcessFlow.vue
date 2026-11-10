<template>
  <section class="live-process-flow" aria-label="生产流转总览">
    <header class="live-process-flow__head">
      <div>
        <span>生产流转总览</span>
        <strong>按实时聚合推进</strong>
      </div>
      <div class="live-process-flow__tools">
        <div v-if="can3D" class="live-process-flow__switch" role="group" aria-label="生产流转视图">
          <button type="button" :aria-pressed="view === '2d'" @click="setView('2d')">2D</button>
          <button type="button" :aria-pressed="view === '3d'" data-testid="live-flow-3d" @click="setView('3d')">3D</button>
        </div>
        <em>缺数据不计 0</em>
      </div>
    </header>

    <div v-if="view === '3d'" class="live-process-flow__stage" data-testid="live-flow-stage">
      <div ref="canvasHost" class="live-process-flow__canvas" />
      <span
        v-for="block in nodeBlocks"
        v-show="labels[block.key]?.visible"
        :key="block.key"
        class="live-process-flow__label"
        :class="{ 'is-empty': !block.hasData }"
        :style="labelStyle(block.key)"
        data-testid="live-flow-label"
      >
        <span>{{ block.label }}</span>
        <strong>{{ block.valueText }}</strong>
      </span>
    </div>

    <div v-else class="live-process-flow__rail">
      <article
        v-for="(item, index) in items"
        :key="item.key"
        class="live-process-flow__node"
        :class="`is-${item.tone}`"
      >
        <b>{{ index + 1 }}</b>
        <div class="live-process-flow__body">
          <span>{{ item.stage }}</span>
          <strong data-xt-numeric>
            <AnimatedMetricValue :value="item.valueText" />
          </strong>
          <small>{{ item.source }}</small>
        </div>
        <dl>
          <div>
            <dt>机列</dt>
            <dd>{{ item.machineCount }} 台</dd>
          </div>
          <div>
            <dt>待绑定</dt>
            <dd>{{ item.pendingMachineCount }} 台</dd>
          </div>
          <div>
            <dt>废料</dt>
            <dd>{{ item.scrapText }}</dd>
          </div>
        </dl>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'

import AnimatedMetricValue from './AnimatedMetricValue.vue'
import { LINE_PLAN, buildProcessLineBlocks } from '../../../utils/process-line-layout.js'
import { supportsWebGL } from '../../../utils/webgl-support.js'

const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})

const VIEW_KEY = 'xt-live-flow-view'
const can3D = ref(false)
const view = ref('2d')
const canvasHost = ref(null)
const labels = ref({})
const scene = shallowRef(null)

const blocks = computed(() => buildProcessLineBlocks(props.items))
const nodeBlocks = computed(() => blocks.value.filter((block) => block.isWorkshop))

function labelStyle(key) {
  const position = labels.value[key]
  return position ? { left: `${position.left}px`, top: `${position.top}px` } : {}
}

function readColor(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return /^#[0-9a-f]{6}$/i.test(value) ? value : fallback
}

function remember(next) {
  try {
    localStorage.setItem(VIEW_KEY, next)
  } catch {
    // 本地存储不可用时只是不记住选择
  }
}

function dropScene() {
  scene.value?.destroy()
  scene.value = null
}

function fallbackTo2D(reason) {
  dropScene()
  view.value = '2d'
  if (reason) console.warn('[生产流转] 改用 2D：', reason)
}

async function setView(next) {
  remember(next)
  if (next === view.value) return
  if (next === '2d') return fallbackTo2D()
  view.value = '3d'
  try {
    const { createFactoryScene } = await import('../../../components/factory/factory-scene.js')
    await nextTick()
    if (view.value !== '3d' || !canvasHost.value) return
    scene.value = createFactoryScene(canvasHost.value, {
      colors: {
        ground: readColor('--xt-bg-panel-soft', '#f4f6f9'),
        data: readColor('--xt-primary', '#003890'),
        empty: readColor('--xt-border', '#d0d5dd'),
        building: readColor('--xt-border', '#d0d5dd'),
        edge: '#ffffff'
      },
      animate: true,
      plan: LINE_PLAN,
      cameraPosition: [0, 20, 24],
      cameraTarget: [0, 0, 0],
      distance: [18, 60],
      onLabels: (next) => { labels.value = next },
      onLost: () => fallbackTo2D('WebGL 上下文丢失')
    })
    scene.value.update(blocks.value)
  } catch (error) {
    fallbackTo2D(error?.message || '3D 加载失败')
  }
}

onMounted(() => {
  const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const narrow = window.matchMedia?.('(max-width: 900px)').matches
  can3D.value = !reducedMotion && !narrow && supportsWebGL()
  let saved = null
  try {
    saved = localStorage.getItem(VIEW_KEY)
  } catch {
    saved = null
  }
  if (can3D.value && saved === '3d') setView('3d')
})

watch(blocks, (next) => scene.value?.update(next))

onBeforeUnmount(dropScene)
</script>

<style scoped>
.live-process-flow {
  position: relative;
  z-index: 1;
  overflow: hidden;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  padding: 15px;
  background: transparent;

}

.live-process-flow__head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 13px;
}

.live-process-flow__head span {
  color: var(--xt-text);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.14em;
}

.live-process-flow__head strong {
  display: block;
  margin-top: 3px;
  color: var(--xt-text);
  font-size: 19px;
}

.live-process-flow__head em {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-style: normal;
  font-weight: 600;
}

.live-process-flow__tools {
  display: flex;
  align-items: center;
  gap: 12px;
}

.live-process-flow__switch {
  display: inline-flex;
  overflow: hidden;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
}

.live-process-flow__switch button {
  min-width: 44px;
  min-height: 32px;
  border: 0;
  background: var(--xt-bg-panel);
  color: var(--xt-text-secondary);
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.live-process-flow__switch button[aria-pressed='true'] {
  background: var(--xt-primary);
  color: #fff;
}

.live-process-flow__stage {
  position: relative;
  height: 280px;
  overflow: hidden;
  border-radius: 4px;
}

.live-process-flow__canvas,
.live-process-flow__canvas :deep(canvas) {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.live-process-flow__label {
  position: absolute;
  display: grid;
  justify-items: center;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.92);
  color: var(--xt-text);
  font-size: 12px;
  line-height: 1.3;
  white-space: nowrap;
  transform: translate(-50%, -100%);
  pointer-events: none;
}

.live-process-flow__label strong {
  color: var(--xt-primary);
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}

.live-process-flow__label.is-empty strong {
  color: var(--xt-text-muted);
}

.live-process-flow__rail {
  display: grid;
  grid-template-columns: repeat(6, minmax(150px, 1fr));
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 2px;
  scrollbar-width: thin;
}

.live-process-flow__node {
  position: relative;
  min-width: 150px;
  display: grid;
  gap: 10px;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  padding: 12px;
  background: transparent;
  transition: border-color 160ms ease, transform 160ms ease;
}

.live-process-flow__node::after {
  position: absolute;
  top: 50%;
  right: -11px;
  width: 12px;
  height: 1px;
  background: transparent;
  content: "";
}

.live-process-flow__node:last-child::after {
  display: none;
}

.live-process-flow__node:hover {
  border-color: var(--xt-border);
  transform: translateY(-1px);
}

.live-process-flow__node b {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border-radius: 4px;
  background: transparent;
  color: var(--xt-text);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
  font-size: 12px;
}

.live-process-flow__body span,
.live-process-flow__body strong,
.live-process-flow__body small {
  display: block;
}

.live-process-flow__body span {
  color: var(--xt-text);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.live-process-flow__body strong {
  margin-top: 7px;
  color: var(--xt-text);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
  font-size: clamp(20px, 2vw, 30px);
  line-height: 1;
}

.live-process-flow__body small {
  margin-top: 7px;
  color: var(--xt-text-secondary);
  font-size: 11px;
}

.live-process-flow dl {
  display: grid;
  gap: 5px;
  margin: 0;
}

.live-process-flow dl div {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  border-top: 1px solid var(--xt-border);
  padding-top: 5px;
}

.live-process-flow dt,
.live-process-flow dd {
  margin: 0;
  font-size: 11px;
}

.live-process-flow dt {
  color: var(--xt-text-secondary);
}

.live-process-flow dd {
  color: var(--xt-text);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
}

.live-process-flow__node.is-warning {
  border-color: var(--xt-border);
}

.live-process-flow__node.is-warning b,
.live-process-flow__node.is-warning .live-process-flow__body strong {
  color: var(--xt-text);
}

.live-process-flow__node.is-muted {
  border-color: var(--xt-border);
}

.live-process-flow__node.is-muted b,
.live-process-flow__node.is-muted .live-process-flow__body strong {
  color: var(--xt-text-secondary);
}

@media (max-width: 1180px) {
  .live-process-flow__rail {
    grid-template-columns: repeat(3, minmax(150px, 1fr));
  }
}

@media (max-width: 720px) {
  .live-process-flow__head {
    align-items: flex-start;
    flex-direction: column;
  }

  .live-process-flow__rail {
    grid-template-columns: repeat(2, minmax(148px, 1fr));
  }
}

@media (prefers-reduced-motion: reduce) {
  .live-process-flow__node {
    transition: none;
  }
}
</style>
