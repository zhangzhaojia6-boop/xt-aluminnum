<template>
  <div class="xt-notification">
    <button type="button" class="xt-notification__trigger" aria-label="通知" @click="panelVisible = !panelVisible">
      <span class="xt-notification__bell">●</span>
      <span v-if="unreadCount" class="xt-notification__badge">{{ badgeText }}</span>
    </button>
    <Transition name="xt-rise">
      <div v-if="panelVisible" class="xt-notification__panel">
        <div class="xt-notification__header">
          <span>通知</span>
          <button v-if="unreadCount" type="button" class="xt-notification__read" @click="$emit('read-all')">全部已读</button>
        </div>
        <div class="xt-notification__list">
          <button
            v-for="item in notifications"
            :key="item.id"
            type="button"
            class="xt-notification__item"
            :class="{ 'is-unread': !item.read }"
            @click="$emit('click', item)"
          >
            <span v-if="!item.read" class="xt-notification__dot" />
            <span class="xt-notification__content">
              <span class="xt-notification__title">{{ item.title }}</span>
              <span v-if="item.time" class="xt-notification__time">{{ item.time }}</span>
            </span>
          </button>
          <div v-if="!notifications.length" class="xt-notification__empty">暂无通知</div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

defineOptions({ name: 'XtNotification' })

const props = defineProps({
  notifications: {
    type: Array,
    default: () => []
  },
  unreadCount: {
    type: Number,
    default: 0
  }
})

defineEmits(['click', 'read-all'])

const panelVisible = ref(false)
const badgeText = computed(() => (props.unreadCount > 99 ? '99+' : String(props.unreadCount)))
</script>

<style scoped>
.xt-notification {
  position: relative;
}

.xt-notification__trigger {
  position: relative;
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 1px solid var(--xt-border);
  border-radius: 50%;
  color: var(--xt-text-secondary);
  background: var(--xt-bg-panel);
}

.xt-notification__bell {
  width: 10px;
  height: 10px;
  border: 2px solid currentColor;
  border-radius: 50%;
  color: currentColor;
  font-size: 0;
}

.xt-notification__badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border: 2px solid var(--xt-bg-panel);
  border-radius: 999px;
  color: var(--xt-text-inverse);
  background: var(--xt-danger);
  font-size: 10px;
  font-weight: 700;
  line-height: 14px;
}

.xt-notification__panel {
  position: absolute;
  top: calc(100% + var(--xt-space-2));
  right: 0;
  z-index: 500;
  width: 320px;
  max-width: calc(100vw - 32px);
  overflow: hidden;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-lg);
}

.xt-notification__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3) var(--xt-space-4);
  border-bottom: 1px solid var(--xt-border-light);
  font-size: var(--xt-text-sm);
  font-weight: 700;
}

.xt-notification__read {
  border: 0;
  color: var(--xt-primary);
  background: transparent;
  font-size: var(--xt-text-xs);
}

.xt-notification__list {
  max-height: 340px;
  overflow-y: auto;
}

.xt-notification__item {
  display: flex;
  width: 100%;
  align-items: flex-start;
  gap: var(--xt-space-2);
  padding: var(--xt-space-3) var(--xt-space-4);
  border: 0;
  background: transparent;
  text-align: left;
}

.xt-notification__item:hover {
  background: var(--xt-gray-50);
}

.xt-notification__item.is-unread {
  background: var(--xt-primary-light);
}

.xt-notification__dot {
  width: 6px;
  height: 6px;
  margin-top: 6px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: var(--xt-primary);
}

.xt-notification__content {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.xt-notification__title {
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
}

.xt-notification__time {
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
}

.xt-notification__empty {
  padding: var(--xt-space-8);
  color: var(--xt-text-muted);
  text-align: center;
  font-size: var(--xt-text-sm);
}
</style>
