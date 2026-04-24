<template>
  <section
    ref="rootRef"
    class="mobile-swipe-workspace"
    data-testid="mobile-swipe-workspace"
    @pointerdown="handlePointerDown"
    @pointermove="handlePointerMove"
    @pointerup="handlePointerUp"
    @pointercancel="handlePointerUp"
    @lostpointercapture="handlePointerUp"
  >
    <div class="mobile-swipe-workspace__track" :style="trackStyle">
      <article
        v-for="page in normalizedPages"
        :key="page.key"
        class="mobile-swipe-workspace__page"
        :data-page-key="page.key"
      >
        <slot :name="page.key" />
      </article>
    </div>
    <div class="mobile-swipe-workspace__footer">
      <div class="mobile-swipe-workspace__indicator" data-testid="swipe-page-indicator">
        {{ activeIndex + 1 }} / {{ normalizedPages.length }}
      </div>
      <div class="mobile-swipe-workspace__dots">
        <button
          v-for="(page, index) in normalizedPages"
          :key="page.key"
          type="button"
          class="mobile-swipe-workspace__dot"
          :class="{ 'is-active': index === activeIndex }"
          :aria-label="page.title || page.key"
          @click="selectPage(index)"
        />
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { clampSwipeOffset, resolveSwipeSnapIndex } from '../../utils/mobileSwipe.js'

const props = defineProps({
  pages: {
    type: Array,
    default: () => []
  },
  activeKey: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:activeKey'])

const rootRef = ref(null)
const pageWidth = ref(320)
const dragState = ref({
  pointerId: null,
  startX: 0,
  deltaX: 0,
  active: false
})

const normalizedPages = computed(() => props.pages.filter((page) => page && page.key))
const activeIndex = computed(() => {
  const fallbackIndex = normalizedPages.value.length ? 0 : -1
  const currentIndex = normalizedPages.value.findIndex((page) => page.key === props.activeKey)
  return currentIndex >= 0 ? currentIndex : fallbackIndex
})

const trackStyle = computed(() => {
  const minOffset = -Math.max(normalizedPages.value.length - 1, 0) * pageWidth.value
  const baseOffset = -(activeIndex.value >= 0 ? activeIndex.value : 0) * pageWidth.value
  const offset = dragState.value.active
    ? clampSwipeOffset({
        offset: baseOffset + dragState.value.deltaX,
        min: minOffset,
        max: 0
      })
    : baseOffset

  return {
    transform: `translate3d(${offset}px, 0, 0)`,
    transition: dragState.value.active ? 'none' : 'transform 280ms cubic-bezier(0.22, 1, 0.36, 1)'
  }
})

function refreshPageWidth() {
  pageWidth.value = rootRef.value?.clientWidth || 320
}

function isInteractiveTarget(target) {
  return Boolean(target?.closest('input, textarea, select, button, a, .el-input, .el-textarea, .el-button, .el-select, .el-switch, .el-radio-group, .el-upload, [data-swipe-ignore="true"]'))
}

function handlePointerDown(event) {
  if (normalizedPages.value.length <= 1) return
  if (isInteractiveTarget(event.target)) return
  dragState.value = {
    pointerId: event.pointerId,
    startX: event.clientX,
    deltaX: 0,
    active: true
  }
  rootRef.value?.setPointerCapture?.(event.pointerId)
}

function handlePointerMove(event) {
  if (!dragState.value.active || event.pointerId !== dragState.value.pointerId) return
  dragState.value = {
    ...dragState.value,
    deltaX: event.clientX - dragState.value.startX
  }
}

function finishDrag(pointerId) {
  if (!dragState.value.active) return
  const nextIndex = resolveSwipeSnapIndex({
    currentIndex: Math.max(activeIndex.value, 0),
    deltaX: dragState.value.deltaX,
    pageWidth: pageWidth.value,
    pageCount: normalizedPages.value.length
  })
  const nextKey = normalizedPages.value[nextIndex]?.key
  dragState.value = {
    pointerId: null,
    startX: 0,
    deltaX: 0,
    active: false
  }
  if (pointerId != null) {
    rootRef.value?.releasePointerCapture?.(pointerId)
  }
  if (nextKey && nextKey !== props.activeKey) {
    emit('update:activeKey', nextKey)
  }
}

function handlePointerUp(event) {
  if (dragState.value.pointerId != null && event.pointerId !== dragState.value.pointerId) return
  finishDrag(event.pointerId)
}

function selectPage(index) {
  const nextKey = normalizedPages.value[index]?.key
  if (nextKey && nextKey !== props.activeKey) {
    emit('update:activeKey', nextKey)
  }
}

watch(normalizedPages, (pages) => {
  if (!pages.length) return
  if (!pages.some((page) => page.key === props.activeKey)) {
    emit('update:activeKey', pages[0].key)
  }
}, { immediate: true })

onMounted(() => {
  refreshPageWidth()
  window.addEventListener('resize', refreshPageWidth)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', refreshPageWidth)
})
</script>

<style scoped>
.mobile-swipe-workspace {
  display: grid;
  gap: 14px;
  overflow: hidden;
  touch-action: pan-y;
}

.mobile-swipe-workspace__track {
  display: flex;
  will-change: transform;
}

.mobile-swipe-workspace__page {
  flex: 0 0 100%;
  min-width: 100%;
  padding-right: 2px;
}

.mobile-swipe-workspace__footer,
.mobile-swipe-workspace__dots {
  display: flex;
  align-items: center;
}

.mobile-swipe-workspace__footer {
  justify-content: space-between;
  gap: 12px;
}

.mobile-swipe-workspace__indicator {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--app-muted);
}

.mobile-swipe-workspace__dots {
  gap: 8px;
}

.mobile-swipe-workspace__dot {
  width: 8px;
  height: 8px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.32);
  transition:
    transform 0.22s ease,
    background-color 0.22s ease,
    width 0.22s ease;
}

.mobile-swipe-workspace__dot.is-active {
  width: 22px;
  background: linear-gradient(90deg, #0a5bd8, #12b5cb);
}
</style>
