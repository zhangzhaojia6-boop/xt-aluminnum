<template>
  <Teleport to="body">
    <Transition name="xt-fade">
      <div v-if="visible" class="xt-search" @click.self="close">
        <div class="xt-search__panel" role="dialog" aria-modal="true" aria-label="全局搜索">
          <div class="xt-search__input-wrap">
            <input
              ref="inputRef"
              v-model="query"
              class="xt-search__input"
              type="search"
              placeholder="搜索功能、页面或数据"
              @keydown.down.prevent="move(1)"
              @keydown.up.prevent="move(-1)"
              @keydown.enter.prevent="selectActive"
              @keydown.esc.prevent="close"
            />
            <kbd class="xt-search__kbd">Esc</kbd>
          </div>
          <div class="xt-search__results">
            <button
              v-for="(item, index) in filteredItems"
              :key="item.key || item.path || item.title"
              type="button"
              class="xt-search__item"
              :class="{ 'is-active': index === activeIndex }"
              @mouseenter="activeIndex = index"
              @click="selectItem(item)"
            >
              <span class="xt-search__item-title">{{ item.title }}</span>
              <span v-if="item.group" class="xt-search__item-hint">{{ item.group }}</span>
            </button>
            <div v-if="!filteredItems.length" class="xt-search__empty">未找到匹配结果</div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

defineOptions({ name: 'XtSearch' })

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  items: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue', 'select', 'close'])
const query = ref('')
const activeIndex = ref(0)
const inputRef = ref(null)

const visible = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value)
})

const filteredItems = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  if (!keyword) return props.items
  return props.items.filter(item => [item.title, item.group, item.path].filter(Boolean).some(value => String(value).toLowerCase().includes(keyword)))
})

watch(visible, value => {
  if (!value) return
  activeIndex.value = 0
  nextTick(() => inputRef.value?.focus())
})

watch(filteredItems, () => {
  activeIndex.value = 0
})

onMounted(() => window.addEventListener('keydown', handleShortcut))
onBeforeUnmount(() => window.removeEventListener('keydown', handleShortcut))

function handleShortcut(event) {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    visible.value = true
  }
}

function move(step) {
  if (!filteredItems.value.length) return
  activeIndex.value = (activeIndex.value + step + filteredItems.value.length) % filteredItems.value.length
}

function selectActive() {
  const item = filteredItems.value[activeIndex.value]
  if (item) selectItem(item)
}

function selectItem(item) {
  emit('select', item)
  close()
}

function close() {
  visible.value = false
  query.value = ''
  emit('close')
}
</script>

<style scoped>
.xt-search {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  align-items: start;
  justify-items: center;
  padding-top: 12vh;
  background: rgba(17, 24, 39, 0.36);
  backdrop-filter: blur(8px);
}

.xt-search__panel {
  width: min(640px, calc(100vw - 32px));
  overflow: hidden;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-lg);
}

.xt-search__input-wrap {
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  padding: var(--xt-space-4);
  border-bottom: 1px solid var(--xt-border-light);
}

.xt-search__input {
  min-width: 0;
  flex: 1;
  border: 0;
  color: var(--xt-text);
  font-size: var(--xt-text-lg);
  outline: none;
}

.xt-search__kbd {
  padding: 2px 6px;
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-sm);
  color: var(--xt-text-muted);
  font-size: 11px;
}

.xt-search__results {
  max-height: 360px;
  overflow-y: auto;
  padding: var(--xt-space-2);
}

.xt-search__item {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3);
  border: 0;
  border-radius: var(--xt-radius-md);
  background: transparent;
  text-align: left;
}

.xt-search__item.is-active,
.xt-search__item:hover {
  background: var(--xt-primary-light);
}

.xt-search__item-title {
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
}

.xt-search__item-hint {
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
}

.xt-search__empty {
  padding: var(--xt-space-8);
  color: var(--xt-text-muted);
  text-align: center;
}
</style>
