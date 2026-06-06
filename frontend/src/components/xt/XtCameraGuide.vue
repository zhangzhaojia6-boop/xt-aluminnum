<template>
  <div v-if="visible" class="xt-camera-guide" @click="dismiss">
    <div class="xt-camera-guide__content panel">
      <div class="xt-camera-guide__icon">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M3 7V5C3 3.89543 3.89543 3 5 3H7M17 3H19C20.1046 3 21 3.89543 21 5V7M21 17V19C21 20.1046 20.1046 21 19 21H17M7 21H5C3.89543 21 3 20.1046 3 19V17" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          <path d="M7 12H17" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          <circle cx="12" cy="12" r="2" fill="currentColor"/>
        </svg>
      </div>
      <div class="xt-camera-guide__frame" aria-hidden="true" />
      <div class="xt-camera-guide__actions">
        <el-button type="primary" @click="dismiss">开始扫码</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const visible = ref(true)

const dismiss = () => {
  visible.value = false
  localStorage.setItem('xt-camera-guide-seen', 'true')
}

if (typeof localStorage !== 'undefined' && localStorage.getItem('xt-camera-guide-seen')) {
  visible.value = false
}
</script>

<style scoped>
.xt-camera-guide {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.85);
}

.xt-camera-guide__content {
  max-width: 320px;
  text-align: center;
  padding: 32px;
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-primary-border);
  box-shadow: 0 12px 28px rgba(0, 12, 28, 0.28);
}

.xt-camera-guide__icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 20px;
  color: var(--xt-primary);
}

.xt-camera-guide__frame {
  width: 200px;
  height: 200px;
  margin: 0 auto 24px;
  border: 1px solid var(--xt-primary-border);
  border-radius: var(--xt-radius-lg);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--xt-primary) 18%, transparent);
}

.xt-camera-guide__actions .el-button {
  width: 100%;
  height: 48px;
  border-radius: var(--xt-radius-lg);
  font-weight: 900;
}
</style>
