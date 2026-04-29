<template>
  <span class="xt-status" :class="[`xt-status--${resolvedTone}`]">
    <span class="xt-status__dot" />
    <slot>{{ resolvedText }}</slot>
  </span>
</template>

<script setup>
import { computed } from 'vue'

defineOptions({ name: 'XtStatus' })

const props = defineProps({
  value: {
    type: [String, Boolean, Number],
    default: ''
  },
  text: {
    type: String,
    default: ''
  },
  tone: {
    type: String,
    default: '',
    validator: value => !value || ['neutral', 'primary', 'success', 'warning', 'danger', 'info'].includes(value)
  }
})

const statusMap = {
  true: ['success', '正常'],
  false: ['neutral', '未启用'],
  active: ['success', '启用'],
  inactive: ['neutral', '停用'],
  enabled: ['success', '启用'],
  disabled: ['neutral', '停用'],
  success: ['success', '成功'],
  warning: ['warning', '预警'],
  danger: ['danger', '异常'],
  error: ['danger', '失败'],
  pending: ['warning', '待处理'],
  processing: ['primary', '处理中'],
  info: ['info', '信息']
}

const normalizedValue = computed(() => String(props.value).toLowerCase())
const resolvedTone = computed(() => props.tone || statusMap[normalizedValue.value]?.[0] || 'neutral')
const resolvedText = computed(() => props.text || statusMap[normalizedValue.value]?.[1] || String(props.value || '未知'))
</script>

<style scoped>
.xt-status {
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-1);
  min-height: 22px;
  padding: 0 var(--xt-space-2);
  border: 1px solid transparent;
  border-radius: 999px;
  font-size: var(--xt-text-xs);
  font-weight: 800;
  white-space: nowrap;
}

.xt-status__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.xt-status--neutral { color: var(--xt-gray-600); background: var(--xt-gray-100); border-color: var(--xt-border-light); }
.xt-status--primary { color: var(--xt-primary); background: var(--xt-primary-light); border-color: rgba(11, 99, 246, 0.18); }
.xt-status--success { color: var(--xt-success); background: var(--xt-success-light); border-color: rgba(22, 138, 85, 0.18); }
.xt-status--warning { color: var(--xt-warning); background: var(--xt-warning-light); border-color: rgba(183, 121, 31, 0.20); }
.xt-status--danger { color: var(--xt-danger); background: var(--xt-danger-light); border-color: rgba(194, 65, 52, 0.18); }
.xt-status--info { color: var(--xt-info); background: var(--xt-info-light); border-color: rgba(37, 99, 235, 0.16); }
</style>
