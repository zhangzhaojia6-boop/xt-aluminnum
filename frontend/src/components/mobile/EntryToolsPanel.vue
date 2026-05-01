<template>
  <el-card v-if="hasContent" class="panel mobile-card" data-testid="entry-secondary-sections">
    <template #header>工具与记录</template>
    <el-collapse class="mobile-collapse">
      <el-collapse-item v-if="hasOcrRecord" title="拍照记录" name="ocr">
        <div class="mobile-static-grid">
          <div class="mobile-static-chip">
            <span>识别记录</span>
            <strong>#{{ ocrState.submissionId }}</strong>
          </div>
          <div class="mobile-static-chip">
            <span>状态</span>
            <strong>{{ ocrState.verified ? '已核对' : '待核对' }}</strong>
          </div>
        </div>
        <div v-if="ocrState.imageUrl" class="mobile-ocr-preview">
          <img :src="ocrState.imageUrl" alt="识别留存图片">
        </div>
        <div class="mobile-actions">
          <el-button plain @click="$emit('ocr-recapture')">重新拍照</el-button>
        </div>
      </el-collapse-item>

      <el-collapse-item v-if="previousStageOutput" title="前序来料快照" name="previous">
        <div class="mobile-history-grid">
          <div>
            <span>来源车间</span>
            <strong>{{ previousStageOutput.workshop || '-' }}</strong>
          </div>
          <div>
            <span>产出重量</span>
            <strong>{{ formatNumber(previousStageOutput.output_weight) }}</strong>
          </div>
          <div>
            <span>产出规格</span>
            <strong>{{ previousStageOutput.output_spec || '-' }}</strong>
          </div>
          <div>
            <span>完成时间</span>
            <strong>{{ formatDateTime(previousStageOutput.completed_at) }}</strong>
          </div>
        </div>
      </el-collapse-item>

      <el-collapse-item v-if="readonlyItems.length" title="系统字段" name="readonly">
        <div class="mobile-static-grid">
          <div v-for="item in readonlyItems" :key="item.name" class="mobile-static-chip">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </el-collapse-item>

      <el-collapse-item v-if="showBatchPaste" title="批量粘贴" name="batch">
        <div class="mobile-history-note">制表符分列，每行一卷。</div>
        <div class="mobile-field mobile-field-wide">
          <el-input
            :model-value="batchText"
            type="textarea"
            :rows="6"
            placeholder="示例：批次号〔制表符〕上机重量〔制表符〕下机重量..."
            :disabled="disabled"
            @update:model-value="$emit('update:batchText', $event)"
          />
        </div>
        <div class="mobile-actions">
          <el-button :disabled="disabled" @click="$emit('apply-batch')">载入队列</el-button>
          <div class="mobile-history-note">队列 {{ batchQueueLength }} 卷</div>
        </div>
      </el-collapse-item>
    </el-collapse>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'
import { formatNumber, formatDateTime } from '../../utils/display.js'

const props = defineProps({
  ocrState: { type: Object, default: null },
  hasOcrContext: { type: Boolean, default: false },
  previousStageOutput: { type: Object, default: null },
  readonlyItems: { type: Array, default: () => [] },
  showBatchPaste: { type: Boolean, default: false },
  batchText: { type: String, default: '' },
  batchQueueLength: { type: Number, default: 0 },
  disabled: { type: Boolean, default: false },
})

defineEmits(['ocr-recapture', 'update:batchText', 'apply-batch'])

const hasOcrRecord = computed(() => Boolean(props.hasOcrContext && props.ocrState))
const hasContent = computed(() => Boolean(
  hasOcrRecord.value ||
  props.previousStageOutput ||
  props.readonlyItems.length ||
  props.showBatchPaste
))
</script>
