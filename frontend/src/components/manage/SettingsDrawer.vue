<template>
  <el-drawer
    :model-value="open"
    direction="rtl"
    size="360px"
    title="设置"
    class="xt-settings-drawer-panel"
    @update:model-value="emit('update:open', $event)"
  >
    <nav class="xt-settings-drawer" aria-label="管理端设置">
      <section v-for="group in groups" :key="group.label" class="xt-settings-drawer__group">
        <h3 class="xt-settings-drawer__group-label">{{ group.label }}</h3>
        <RouterLink
          v-for="item in group.items"
          :key="item.path"
          :to="item.path"
          class="xt-settings-drawer__item"
          :class="{ 'is-frozen': item.frozen }"
          @click="closeDrawer"
        >
          <span>{{ item.title }}</span>
          <small v-if="item.frozen">冻结</small>
        </RouterLink>
      </section>
    </nav>
  </el-drawer>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import { settingsDrawerGroups } from '../../config/manage-settings-drawer.js'
import { useAuthStore } from '../../stores/auth'

defineProps({
  open: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:open'])
const auth = useAuthStore()
const groups = computed(() => settingsDrawerGroups(auth))

function closeDrawer() {
  emit('update:open', false)
}
</script>

<style scoped>
.xt-settings-drawer {
  display: grid;
  gap: var(--xt-space-4);
  padding: var(--xt-space-1) var(--xt-space-2) var(--xt-space-3);
}

.xt-settings-drawer__group {
  display: grid;
  gap: var(--xt-space-1);
}

.xt-settings-drawer__group-label {
  margin: 0;
  padding: 0 var(--xt-space-2);
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  font-weight: 850;
  letter-spacing: 0;
}

.xt-settings-drawer__item {
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-2);
  padding: 0 var(--xt-space-3);
  border-radius: var(--xt-radius-md);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  font-weight: 700;
  text-decoration: none;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-settings-drawer__item:active {
  transform: scale(0.98);
}

@media (hover: hover) {
  .xt-settings-drawer__item:hover {
    background: var(--xt-bg-panel-soft);
    color: var(--xt-text);
  }
}

.xt-settings-drawer__item small {
  flex: 0 0 auto;
  padding: 1px var(--xt-space-2);
  border-radius: var(--xt-radius-pill);
  background: rgba(102, 112, 133, 0.1);
  color: var(--xt-text-muted);
  font-size: 10px;
  font-weight: 850;
}
</style>
