<template>
  <div class="xt-skeleton" :class="{ 'is-animated': animated }">
    <div v-if="loading" class="xt-skeleton__content">
      <slot name="template">
        <div class="xt-skeleton__row" v-for="i in rows" :key="i">
          <div class="xt-skeleton__item" :style="{ width: itemWidth(i) }"></div>
        </div>
      </slot>
      <!-- Scan line animation matching industrial.css -->
      <div class="xt-scan-line"></div>
    </div>
    <slot v-else></slot>
  </div>
</template>

<script setup>
defineProps({
  loading: Boolean,
  animated: {
    type: Boolean,
    default: true
  },
  rows: {
    type: Number,
    default: 3
  }
})

const itemWidth = (i) => {
  if (i === 1) return '40%'
  if (i === 3) return '60%'
  return '90%'
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
  gap: 12px;
  padding: 16px;
}

.xt-skeleton__item {
  height: 16px;
  background: var(--xt-bg-panel-soft, rgba(255, 255, 255, 0.05));
  border-radius: 4px;
}

.is-animated .xt-skeleton__item {
  background: linear-gradient(
    90deg,
    var(--xt-bg-panel-soft) 25%,
    rgba(255, 255, 255, 0.08) 37%,
    var(--xt-bg-panel-soft) 63%
  );
  background-size: 400% 100%;
  animation: xt-skeleton-loading 1.4s ease infinite;
}

@keyframes xt-skeleton-loading {
  0% { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}
</style>
