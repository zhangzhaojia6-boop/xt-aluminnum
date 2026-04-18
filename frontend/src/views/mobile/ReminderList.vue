<template>
  <div class="mobile-reminder-list">
    <div v-if="!items.length" class="mobile-placeholder">{{ emptyText }}</div>
    <div v-else class="mobile-reminder-items">
      <div v-for="item in items" :key="item.id" class="mobile-history-item">
        <div class="mobile-history-main">
          <div>
            <div class="mobile-history-title">{{ formatReminderTypeLabel(item.reminder_type) }}</div>
            <div class="mobile-history-meta">
              状态：{{ formatStatusLabel(item.reminder_status) }} · 渠道：{{ item.reminder_channel || '-' }}
            </div>
          </div>
          <el-tag type="warning" effect="light">第 {{ item.reminder_count || 0 }} 次</el-tag>
        </div>
        <div class="mobile-history-note">
          最近催报时间：{{ item.last_reminded_at || '-' }}
        </div>
        <div v-if="item.note" class="mobile-history-note">{{ item.note }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { formatReminderTypeLabel, formatStatusLabel } from '../../utils/display'

defineProps({
  items: {
    type: Array,
    default: () => []
  },
  emptyText: {
    type: String,
    default: '当前没有提醒记录。'
  }
})
</script>
