<template>
  <div class="xt-skeleton" :class="{ 'is-animated': animated }" aria-label="正在加载">
    <div v-if="showSkeleton" class="xt-skeleton__content">
      <slot name="template">
        <div v-for="i in rows" :key="i" class="xt-skeleton__row">
          <div class="xt-skeleton__item" :style="{ width: itemWidth(i) }" />
        </div>
      </slot>
    </div>
    <slot v-else />
  </div>
</template>

<script setup>
import { computed } from 'vue'

defineOptions({ name: 'XtSkeleton' })

const props = defineProps({
  loading: {
    type: Boolean,
    default: null,
  },
  animated: {
    type: Boolean,
    default: true,
  },
  rows: {
    type: Number,
    default: 3,
  },
})

const showSkeleton = computed(() => (props.loading === null ? true : props.loading))

const itemWidth = (i) => {
  if (i === 1) return '40%'
  if (i % 3 === 0) return '60%'
  if (i % 2 === 0) return '88%'
  return '100%'
}
</script>

<style scoped>
.xt-skeleton {
  position: relative;
  width: 100%;
}

.xt-skeleton__content {
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-3, 12px);
}

.xt-skeleton__row {
  display: flex;
}

.xt-skeleton__item {
  height: 16px;
  background: var(--xt-bg-panel-soft, rgba(255, 255, 255, 0.05));
  border-radius: 4px;
}

.is-animated .xt-skeleton__item {
  background: linear-gradient(
    90deg,
    var(--xt-bg-panel-soft, rgba(255, 255, 255, 0.05)) 25%,
    rgba(255, 255, 255, 0.08) 37%,
    var(--xt-bg-panel-soft, rgba(255, 255, 255, 0.05)) 63%
  );
  background-size: 400% 100%;
  animation: xt-skeleton-loading 1.4s ease infinite;
}

@keyframes xt-skeleton-loading {
  0% { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}
</style>
