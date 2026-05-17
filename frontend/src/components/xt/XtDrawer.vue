<template>
  <Teleport to="body">
    <Transition name="xt-drawer">
      <div v-if="modelValue" class="xt-drawer-overlay" @click.self="close">
        <aside 
          ref="drawerRef"
          class="xt-drawer" 
          :class="[`xt-drawer--${side}`, `xt-drawer--${size}`]" 
          role="dialog" 
          :aria-label="title"
        >
          <header class="xt-drawer__header">
            <h2 class="xt-drawer__title">{{ title }}</h2>
            <button class="xt-drawer__close" aria-label="Close" @click="close">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M4 4L12 12M12 4L4 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
              </svg>
            </button>
          </header>
          <div class="xt-drawer__body">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="xt-drawer__footer">
            <slot name="footer" />
          </footer>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'
import { useFocusTrap } from '../../composables/useFocusTrap'

defineOptions({ name: 'XtDrawer' })

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: ''
  },
  side: {
    type: String,
    default: 'right',
    validator: v => ['left', 'right'].includes(v)
  },
  size: {
    type: String,
    default: 'normal',
    validator: v => ['narrow', 'normal', 'wide'].includes(v)
  }
})

const drawerRef = ref(null)
useFocusTrap(drawerRef)

const emit = defineEmits(['update:modelValue'])
const close = () => emit('update:modelValue', false)
</script>

<style scoped>
.xt-drawer-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(2px);
}

.xt-drawer {
  position: fixed;
  top: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-xl);
}

.xt-drawer--right { right: 0; }
.xt-drawer--left { left: 0; }

.xt-drawer--narrow { width: 320px; }
.xt-drawer--normal { width: 480px; }
.xt-drawer--wide { width: 640px; }

.xt-drawer__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--xt-space-4) var(--xt-space-5);
  border-bottom: 1px solid var(--xt-border-light);
}

.xt-drawer__title {
  margin: 0;
  color: var(--xt-text);
  font-size: var(--xt-text-lg);
  font-weight: 850;
}

.xt-drawer__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: var(--xt-radius-sm);
  background: transparent;
  color: var(--xt-text-muted);
  cursor: pointer;
}

.xt-drawer__close:hover {
  background: var(--xt-bg-hover);
  color: var(--xt-text);
}

.xt-drawer__body {
  flex: 1;
  overflow-y: auto;
  padding: var(--xt-space-5);
}

.xt-drawer__footer {
  padding: var(--xt-space-4) var(--xt-space-5);
  border-top: 1px solid var(--xt-border-light);
}

.xt-drawer-enter-active,
.xt-drawer-leave-active {
  transition: opacity var(--xt-motion-normal) var(--xt-ease);
}

.xt-drawer-enter-active .xt-drawer,
.xt-drawer-leave-active .xt-drawer {
  transition: transform var(--xt-motion-normal) var(--xt-ease);
}

.xt-drawer-enter-from,
.xt-drawer-leave-to {
  opacity: 0;
}

.xt-drawer-enter-from .xt-drawer--right,
.xt-drawer-leave-to .xt-drawer--right {
  transform: translateX(100%);
}

.xt-drawer-enter-from .xt-drawer--left,
.xt-drawer-leave-to .xt-drawer--left {
  transform: translateX(-100%);
}
</style>
