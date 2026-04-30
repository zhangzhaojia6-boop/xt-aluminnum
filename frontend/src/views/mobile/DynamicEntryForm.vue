<template>
  <div class="mobile-shell mobile-shell--entry-form" data-testid="dynamic-entry-form">
  <el-result
      v-if="loadError"
      icon="error"
      :title="loadError"
      sub-title="请检查网络连接后重试，或联系管理员。"
    >
      <template #extra>
        <el-button type="primary" :loading="loading" @click="loadPage">重试加载</el-button>
      </template>
    </el-result>

    <template v-else>
    <div class="mobile-top" :style="isOwnerOnlyMode ? { '--role-color': roleColor } : {}">
      <div>
        <div v-if="false" class="mobile-kicker">04 填报流程页</div>
        <h1>{{ isOwnerOnlyMode ? ownerModeConfig.title : '批次号填报' }}</h1>
      </div>
      <div v-if="isOwnerOnlyMode" class="entry-role-badge" :style="{ background: roleColor }"></div>
    </div>

    <el-alert
      v-if="currentShift.ownership_note"
      :title="currentShift.ownership_note"
      type="warning"
      show-icon
      :closable="false"
      class="panel"
    />

    <el-alert
      v-if="readOnlyCreatorBanner"
      :title="readOnlyCreatorBanner"
      type="info"
      show-icon
      :closable="false"
      class="panel"
    />

    <div v-if="loading" class="mobile-inline-state panel">
      <p>正在加载填报页面…</p>
      <el-button type="primary" :loading="loading" class="mobile-inline-action" @click="loadPage">重试加载</el-button>
    </div>

    <div
      v-if="template && !currentShift.can_submit"
      class="mobile-inline-state panel"
    >
      <p>当前账号暂时无法填报。</p>
      <p>{{ currentShift.ownership_note || '请联系管理员。' }}</p>
      <div class="mobile-recovery-actions">
        <el-button type="primary" plain class="mobile-inline-action" @click="loadPage">刷新状态</el-button>
        <el-button plain class="mobile-inline-action" @click="goHistory">查看历史</el-button>
      </div>
    </div>

    <div
      v-else-if="template && currentShift.can_submit"
      class="panel entry-summary-strip"
      data-testid="entry-summary-strip"
    >
      <div class="entry-summary-strip__facts">
        <span v-for="item in summaryFacts" :key="item">{{ item }}</span>
      </div>
    </div>

    <el-card v-if="template && showFastEntryHelper" class="panel mobile-card">
      <template #header>连续录入</template>
      <div class="mobile-dynamic-summary">
        <div class="mobile-summary-chip">
          <span>已提交</span>
          <strong>{{ submittedCount }}</strong>
          <span>卷</span>
        </div>
        <div class="mobile-summary-chip">
          <span>待处理队列</span>
          <strong>{{ batchQueue.length }}</strong>
          <span>卷</span>
        </div>
      </div>
      <div class="mobile-actions">
        <el-button
          v-if="canContinueNext"
          type="primary"
          plain
          size="large"
          @click="continueNextCoil"
        >
          继续下一卷
        </el-button>
      </div>
    </el-card>

    <MobileSwipeWorkspace
      v-if="template && currentShift.can_submit"
      v-model:active-key="currentStepKey"
      :pages="visibleStepItems"
    >
      <template #work_order>
        <el-card v-if="!isOwnerOnlyMode" class="panel mobile-card" data-testid="entry-work-order-card">
          <template #header>基础识别</template>
          <div class="mobile-form-grid">
            <div class="mobile-field mobile-field-wide">
              <label>
                <span class="mobile-required">*</span>
                批次号
              </label>
              <div class="mobile-inline-actions">
                <el-input
                  v-model="trackingCardNo"
                  placeholder="批次号 / 扫码"
                  :disabled="lookupLoading"
                  @keyup.enter="lookupTrackingCard"
                />
                <el-button :loading="lookupLoading" @click="lookupTrackingCard">读取</el-button>
                <el-button plain @click="handleScanClick">相机扫码</el-button>
              </div>
            </div>

            <div class="mobile-field">
              <label>
                <span class="mobile-required" v-if="equipmentOptions.length">*</span>
                机台
              </label>
              <div v-if="isMachineBound" class="mobile-static-value">
                {{ boundMachine?.name || boundMachine?.code || currentShift.machine_name || '-' }}
              </div>
              <el-select
                v-else
                v-model="formState.machine_id"
                placeholder="选择机台"
                clearable
                filterable
                :disabled="isEntryEditingDisabled"
              >
                <el-option
                  v-for="item in equipmentOptions"
                  :key="item.id"
                  :label="item.name || item.code"
                  :value="item.id"
                />
              </el-select>
            </div>

            <div v-if="currentWorkOrder && workOrderSummaryItems.length" class="mobile-field mobile-field-wide">
              <label>当前卷</label>
              <div class="mobile-static-grid">
                <div v-for="item in workOrderSummaryItems" :key="item.label" class="mobile-static-chip">
                  <span>{{ item.label }}</span>
                  <strong>{{ item.value }}</strong>
                </div>
              </div>
            </div>
          </div>
        </el-card>

        <el-card v-if="!isOwnerOnlyMode" class="panel mobile-card entry-external-trace-card" data-testid="entry-mes-trace-card">
          <template #header>外部系统线索</template>
          <div class="entry-external-trace">
            <span>前工序事实</span>
            <span>后工序同步</span>
            <span>不补后续码</span>
          </div>
        </el-card>

        <el-card v-if="!isOwnerOnlyMode && isSlowTempo" class="panel mobile-card">
          <template #header>本班交接</template>
          <div class="mobile-field mobile-field-wide">
            <label>本班状态</label>
            <el-radio-group v-model="completionMode" :disabled="isEntryEditingDisabled">
              <el-radio-button value="in_progress">继续录入</el-radio-button>
              <el-radio-button value="completed">本班完工</el-radio-button>
            </el-radio-group>
          </div>
          <div v-if="currentWorkOrder && historyEntries.length" class="mobile-history-list">
            <div class="mobile-section-title">前序记录</div>
            <div v-for="item in historyEntries" :key="item.id" class="mobile-history-item">
              <div class="mobile-history-main">
                <div>
                  <div class="mobile-history-title">
                    {{ item.business_date }} / {{ item.shift_id ? `班次 ${item.shift_id}` : '未标记班次' }}
                  </div>
                  <div class="mobile-history-meta">
                    状态：{{ formatStatusLabel(item.entry_status) }} / {{ item.entry_type === 'completed' ? '本班完工' : '接续中' }}
                  </div>
                </div>
                <el-tag :type="item.entry_type === 'completed' ? 'success' : 'warning'" effect="light">
                  {{ item.entry_type === 'completed' ? '完工' : '接续' }}
                </el-tag>
              </div>
              <div class="mobile-static-grid">
                <div
                  v-for="summary in summarizeHistoryEntry(item)"
                  :key="`${item.id}-${summary.label}`"
                  class="mobile-static-chip"
                >
                  <span>{{ summary.label }}</span>
                  <strong>{{ summary.value }}</strong>
                </div>
              </div>
            </div>
          </div>
          <div v-else-if="currentWorkOrder" class="mobile-placeholder">暂无记录。</div>
        </el-card>
      </template>

      <template #core>
        <el-card class="panel mobile-card" data-testid="entry-core-form">
          <template #header>{{ isOwnerOnlyMode ? ownerModeConfig.coreCardTitle : '填写' }}</template>
          <div class="mobile-dynamic-form">
            <template v-if="isOwnerOnlyMode">
              <section
                v-for="section in ownerCoreSections"
                :key="`core-${section.title}`"
                class="mobile-dynamic-section"
              >
                <div class="mobile-section-title">{{ section.title }}</div>
                <div class="mobile-form-grid">
                  <div
                    v-for="field in section.fields"
                    :key="`${section.title}-${field.name}`"
                    :class="['mobile-field', field.name === 'operator_notes' ? 'mobile-field-wide' : '']"
                  >
                    <label class="mobile-field-label">
                      <span>
                        <span v-if="isFieldRequired(field)" class="mobile-required">*</span>
                        {{ displayFieldLabel(field) }}
                        <span v-if="field.unit" class="mobile-field-unit">({{ field.unit }})</span>
                      </span>
                      <el-button
                        v-if="isVoiceFieldSupported(field)"
                        text
                        type="primary"
                        size="small"
                        :disabled="isEntryEditingDisabled"
                        @click.stop="toggleVoicePrefill(field)"
                      >
                        {{ voiceListeningField === field.name ? '停止语音' : '语音录入' }}
                      </el-button>
                      <span
                        v-if="ocrMetaForField(field.name)"
                        :class="['mobile-ocr-badge', `is-${confidenceTone(ocrMetaForField(field.name)?.confidence)}`]"
                      >
                        {{ confidenceLabel(ocrMetaForField(field.name)?.confidence) }}
                      </span>
                    </label>
                    <el-time-picker
                      v-if="field.type === 'time'"
                      v-model="formValues[field.name]"
                      value-format="HH:mm:ss"
                      format="HH:mm"
                      placeholder="选择时间"
                      :disabled="isEntryEditingDisabled"
                      class="mobile-time-picker"
                    />
                    <el-input
                      v-else
                      v-model="formValues[field.name]"
                      :type="field.type === 'textarea' ? 'textarea' : 'text'"
                      :rows="field.type === 'textarea' ? 3 : undefined"
                      :inputmode="field.type === 'number' ? 'decimal' : 'text'"
                    :placeholder="fieldPlaceholder(field)"
                    :disabled="isEntryEditingDisabled"
                  />
                </div>
              </div>
            </section>
            </template>

            <section v-else-if="entryFields.length" class="mobile-dynamic-section">
              <div class="mobile-section-title">{{ isOwnerOnlyMode ? '本班原始值' : '本卷原始值' }}</div>
              <div class="mobile-form-grid">
                <div
                  v-for="field in entryFields"
                  :key="field.name"
                  :class="['mobile-field', field.name === 'operator_notes' ? 'mobile-field-wide' : '']"
                >
                  <label class="mobile-field-label">
                    <span>
                      <span v-if="isFieldRequired(field)" class="mobile-required">*</span>
                      {{ displayFieldLabel(field) }}
                      <span v-if="field.unit" class="mobile-field-unit">({{ field.unit }})</span>
                    </span>
                    <el-button
                      v-if="isVoiceFieldSupported(field)"
                      text
                      type="primary"
                      size="small"
                      :disabled="isEntryEditingDisabled"
                      @click.stop="toggleVoicePrefill(field)"
                    >
                      {{ voiceListeningField === field.name ? '停止语音' : '语音录入' }}
                    </el-button>
                    <span
                      v-if="ocrMetaForField(field.name)"
                      :class="['mobile-ocr-badge', `is-${confidenceTone(ocrMetaForField(field.name)?.confidence)}`]"
                    >
                      {{ confidenceLabel(ocrMetaForField(field.name)?.confidence) }}
                    </span>
                  </label>
                  <el-time-picker
                    v-if="field.type === 'time'"
                    v-model="formValues[field.name]"
                    value-format="HH:mm:ss"
                    format="HH:mm"
                    placeholder="选择时间"
                    :disabled="isEntryEditingDisabled"
                    class="mobile-time-picker"
                  />
                  <el-input
                    v-else
                    v-model="formValues[field.name]"
                    :type="field.type === 'textarea' ? 'textarea' : 'text'"
                    :rows="field.type === 'textarea' ? 3 : undefined"
                    :inputmode="field.type === 'number' ? 'decimal' : 'text'"
                    :placeholder="fieldPlaceholder(field)"
                    :disabled="isEntryEditingDisabled"
                  />
                </div>
              </div>
            </section>
          </div>

          <div v-if="!isOwnerOnlyMode" class="mobile-dynamic-summary mobile-dynamic-summary--footer">
            <div class="mobile-summary-chip">
              <span>自动成材率</span>
              <strong :class="yieldClass">{{ yieldDisplay }}</strong>
            </div>
          </div>
        </el-card>
      </template>

      <template #supplemental>
        <el-card class="panel mobile-card">
          <template #header>{{ supplementalCardTitle }}</template>
          <div class="mobile-dynamic-form">
            <template v-if="isOwnerOnlyMode">
              <section
                v-for="section in ownerSupplementalSections"
                :key="`supplemental-${section.title}`"
                class="mobile-dynamic-section"
              >
                <div class="mobile-section-title">{{ section.title }}</div>
                <div class="mobile-form-grid">
                  <div v-for="field in section.fields" :key="`${section.title}-${field.name}`" class="mobile-field">
                    <label class="mobile-field-label">
                      <span>
                        <span v-if="isFieldRequired(field)" class="mobile-required">*</span>
                        {{ displayFieldLabel(field) }}
                        <span v-if="field.unit" class="mobile-field-unit">({{ field.unit }})</span>
                      </span>
                      <el-button
                        v-if="isVoiceFieldSupported(field)"
                        text
                        type="primary"
                        size="small"
                        :disabled="isEntryEditingDisabled"
                        @click.stop="toggleVoicePrefill(field)"
                      >
                        {{ voiceListeningField === field.name ? '停止语音' : '语音录入' }}
                      </el-button>
                      <span
                        v-if="ocrMetaForField(field.name)"
                        :class="['mobile-ocr-badge', `is-${confidenceTone(ocrMetaForField(field.name)?.confidence)}`]"
                      >
                        {{ confidenceLabel(ocrMetaForField(field.name)?.confidence) }}
                      </span>
                    </label>
                    <el-input
                      v-model="formValues[field.name]"
                      :inputmode="field.type === 'number' ? 'decimal' : 'text'"
                      :placeholder="fieldPlaceholder(field)"
                      :disabled="isEntryEditingDisabled"
                    />
                  </div>
                </div>
              </section>
            </template>

            <section v-else-if="shiftFields.length" class="mobile-dynamic-section">
              <div class="mobile-section-title">{{ isOwnerOnlyMode ? '岗位归档字段' : '班末补充确认' }}</div>
              <div class="mobile-form-grid">
                <div v-for="field in shiftFields" :key="field.name" class="mobile-field">
                  <label class="mobile-field-label">
                    <span>
                      <span v-if="isFieldRequired(field)" class="mobile-required">*</span>
                      {{ displayFieldLabel(field) }}
                      <span v-if="field.unit" class="mobile-field-unit">({{ field.unit }})</span>
                    </span>
                    <el-button
                      v-if="isVoiceFieldSupported(field)"
                      text
                      type="primary"
                      size="small"
                      :disabled="isEntryEditingDisabled"
                      @click.stop="toggleVoicePrefill(field)"
                    >
                      {{ voiceListeningField === field.name ? '停止语音' : '语音录入' }}
                    </el-button>
                    <span
                      v-if="ocrMetaForField(field.name)"
                      :class="['mobile-ocr-badge', `is-${confidenceTone(ocrMetaForField(field.name)?.confidence)}`]"
                    >
                      {{ confidenceLabel(ocrMetaForField(field.name)?.confidence) }}
                    </span>
                  </label>
                  <el-input
                    v-model="formValues[field.name]"
                    :inputmode="field.type === 'number' ? 'decimal' : 'text'"
                    :placeholder="fieldPlaceholder(field)"
                    :disabled="isEntryEditingDisabled"
                  />
                </div>
              </div>
            </section>

            <section v-if="operatorConfirmationFields.length" class="mobile-dynamic-section">
              <div class="mobile-section-title">异常与班末确认</div>
              <div class="mobile-form-grid">
                <div v-for="field in operatorConfirmationFields" :key="field.name" class="mobile-field mobile-field-wide">
                  <label class="mobile-field-label">
                    <span>
                      <span v-if="isFieldRequired(field)" class="mobile-required">*</span>
                      {{ displayFieldLabel(field) }}
                    </span>
                  </label>
                  <el-input
                    v-model="formValues[field.name]"
                    type="textarea"
                    :rows="3"
                    :placeholder="fieldPlaceholder(field)"
                    :disabled="isEntryEditingDisabled"
                  />
                </div>
              </div>
            </section>

            <section v-if="extraFields.length" class="mobile-dynamic-section">
              <div class="mobile-section-title">{{ isOwnerOnlyMode ? '补录字段' : '车间字段' }}</div>
              <div class="mobile-form-grid">
                <div v-for="field in extraFields" :key="field.name" class="mobile-field">
                  <label class="mobile-field-label">
                    <span>
                      <span v-if="isFieldRequired(field)" class="mobile-required">*</span>
                      {{ displayFieldLabel(field) }}
                      <span v-if="field.unit" class="mobile-field-unit">({{ field.unit }})</span>
                    </span>
                    <el-button
                      v-if="isVoiceFieldSupported(field)"
                      text
                      type="primary"
                      size="small"
                      :disabled="isEntryEditingDisabled"
                      @click.stop="toggleVoicePrefill(field)"
                    >
                      {{ voiceListeningField === field.name ? '停止语音' : '语音录入' }}
                    </el-button>
                    <span
                      v-if="ocrMetaForField(field.name)"
                      :class="['mobile-ocr-badge', `is-${confidenceTone(ocrMetaForField(field.name)?.confidence)}`]"
                    >
                      {{ confidenceLabel(ocrMetaForField(field.name)?.confidence) }}
                    </span>
                  </label>
                  <el-input
                    v-model="formValues[field.name]"
                    :inputmode="field.type === 'number' ? 'decimal' : 'text'"
                    :placeholder="fieldPlaceholder(field)"
                    :disabled="isEntryEditingDisabled"
                  />
                </div>
              </div>
            </section>

            <section v-if="machineFields.length" class="mobile-dynamic-section">
              <div class="mobile-section-title">机台字段</div>
              <div class="mobile-form-grid">
                <div v-for="field in machineFields" :key="field.name" class="mobile-field">
                  <label class="mobile-field-label">
                    <span>
                      <span v-if="isFieldRequired(field)" class="mobile-required">*</span>
                      {{ displayFieldLabel(field) }}
                      <span v-if="field.unit" class="mobile-field-unit">({{ field.unit }})</span>
                    </span>
                    <el-button
                      v-if="isVoiceFieldSupported(field)"
                      text
                      type="primary"
                      size="small"
                      :disabled="isEntryEditingDisabled"
                      @click.stop="toggleVoicePrefill(field)"
                    >
                      {{ voiceListeningField === field.name ? '停止语音' : '语音录入' }}
                    </el-button>
                  </label>
                  <el-input
                    v-model="formValues[field.name]"
                    :inputmode="field.type === 'number' ? 'decimal' : 'text'"
                    :placeholder="fieldPlaceholder(field)"
                    :disabled="isEntryEditingDisabled"
                  />
                </div>
              </div>
            </section>

            <section v-if="qcFields.length" class="mobile-dynamic-section">
              <div class="mobile-section-title">质检字段</div>
              <div class="mobile-form-grid">
                <div v-for="field in qcFields" :key="field.name" class="mobile-field">
                  <label class="mobile-field-label">
                    <span>
                      <span v-if="isFieldRequired(field)" class="mobile-required">*</span>
                      {{ displayFieldLabel(field) }}
                    </span>
                    <el-button
                      v-if="isVoiceFieldSupported(field)"
                      text
                      type="primary"
                      size="small"
                      :disabled="isEntryEditingDisabled"
                      @click.stop="toggleVoicePrefill(field)"
                    >
                      {{ voiceListeningField === field.name ? '停止语音' : '语音录入' }}
                    </el-button>
                    <span
                      v-if="ocrMetaForField(field.name)"
                      :class="['mobile-ocr-badge', `is-${confidenceTone(ocrMetaForField(field.name)?.confidence)}`]"
                    >
                      {{ confidenceLabel(ocrMetaForField(field.name)?.confidence) }}
                    </span>
                  </label>
                  <el-input
                    v-model="formValues[field.name]"
                    :inputmode="field.type === 'number' ? 'decimal' : 'text'"
                    :placeholder="fieldPlaceholder(field)"
                    :disabled="isEntryEditingDisabled"
                  />
                </div>
              </div>
            </section>
          </div>

          <div v-if="!hasSupplementalFields" class="mobile-placeholder">
            无需补充。
          </div>
        </el-card>
      </template>

      <template #review>
        <el-card class="panel mobile-card">
          <template #header>确认提交</template>
          <div class="mobile-static-grid">
            <div v-for="item in reviewSummaryItems" :key="item.label" class="mobile-static-chip">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </el-card>

        <el-card v-if="hasSecondaryContent" class="panel mobile-card" data-testid="entry-secondary-sections">
          <template #header>工具与记录</template>
          <el-collapse class="mobile-collapse">
        <el-collapse-item v-if="hasOcrContext" title="拍照记录" name="ocr">
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
            <el-button plain @click="goOcrCapture">重新拍照</el-button>
          </div>
        </el-collapse-item>

        <el-collapse-item v-if="currentWorkOrder?.previous_stage_output" title="前序来料快照" name="previous">
          <div class="mobile-history-grid">
            <div>
              <span>来源车间</span>
              <strong>{{ currentWorkOrder.previous_stage_output.workshop || '-' }}</strong>
            </div>
            <div>
              <span>产出重量</span>
              <strong>{{ formatNumber(currentWorkOrder.previous_stage_output.output_weight) }}</strong>
            </div>
            <div>
              <span>产出规格</span>
              <strong>{{ currentWorkOrder.previous_stage_output.output_spec || '-' }}</strong>
            </div>
            <div>
              <span>完成时间</span>
              <strong>{{ formatDateTime(currentWorkOrder.previous_stage_output.completed_at) }}</strong>
            </div>
          </div>
        </el-collapse-item>

        <el-collapse-item v-if="readonlyDisplayItems.length" title="系统字段" name="readonly">
          <div class="mobile-static-grid">
            <div v-for="item in readonlyDisplayItems" :key="item.name" class="mobile-static-chip">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </el-collapse-item>

        <el-collapse-item v-if="template && isFastTempo && !isOwnerOnlyMode" title="批量粘贴" name="batch">
          <div class="mobile-history-note">制表符分列，每行一卷。</div>
          <div class="mobile-field mobile-field-wide">
            <el-input
              v-model="batchText"
              type="textarea"
              :rows="6"
              placeholder="示例：批次号〔制表符〕上机重量〔制表符〕下机重量..."
              :disabled="isEntryEditingDisabled"
            />
          </div>
          <div class="mobile-actions">
            <el-button :disabled="isEntryEditingDisabled" @click="applyBatchPaste">载入队列</el-button>
            <div class="mobile-history-note">队列 {{ batchQueue.length }} 卷</div>
          </div>
        </el-collapse-item>
          </el-collapse>
        </el-card>
      </template>
    </MobileSwipeWorkspace>

    <div v-if="template && currentShift.can_submit" class="mobile-sticky-actions">
      <div class="mobile-sticky-actions__meta">
        <span v-if="autoSavedLabel" class="mobile-draft-indicator">{{ autoSavedLabel }}</span>
      </div>
      <div class="mobile-sticky-actions__buttons">
        <el-button
          v-if="!isFirstStep"
          size="large"
          :disabled="loading || saving || submitting"
          @click="goPrevStep"
        >
          上一步
        </el-button>
        <el-button
          size="large"
          :disabled="!canOperate || postSubmitLocked"
          :loading="saving"
          @click="saveDraft"
        >
          保存草稿
        </el-button>
        <el-button
          v-if="!isReviewStep"
          type="primary"
          size="large"
          :disabled="loading || saving || submitting"
          @click="goNextStep"
        >
          下一步
        </el-button>
        <el-button
          v-else
          type="primary"
          size="large"
          :disabled="submitButtonDisabled"
          :loading="submitting"
          @click="submitEntry"
        >
          正式提交
        </el-button>
      </div>
    </div>

    <el-dialog
      v-model="restoreDialogVisible"
      title="恢复未提交草稿"
      width="92%"
      destroy-on-close
      append-to-body
    >
      <p class="mobile-dialog-copy">
        发现未提交的草稿，是否恢复？
        <span v-if="restoreDraftSavedAt">上次暂存于 {{ restoreDraftSavedAt }}</span>
      </p>
      <template #footer>
        <el-button @click="discardDraft">放弃</el-button>
        <el-button type="primary" @click="restoreDraft">恢复</el-button>
      </template>
    </el-dialog>

    </template>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { useLocalDraft } from '../../composables/useLocalDraft'
import { isRetryableNetworkError, useRetryQueue } from '../../composables/useRetryQueue'
import { fetchEquipment } from '../../api/master.js'
import {
  createWorkOrder,
  createWorkOrderEntry,
  fetchCurrentShift,
  fetchWorkshopTemplate,
  findWorkOrderByTrackingCard,
  submitWorkOrderEntry,
  updateWorkOrder,
  updateWorkOrderEntry,
  verifyOcrFields
} from '../../api/mobile.js'
import { useAuthStore } from '../../stores/auth.js'
import { formatDateTime, formatNumber, formatStatusLabel } from '../../utils/display.js'
import {
  buildMobileTransitionMapping,
  describeTransitionRoleBucket
} from '../../utils/mobileTransition.js'
import { SUBMIT_COOLDOWN_MS, isWithinSubmitCooldown } from '../../utils/submitGuard.js'
import MobileSwipeWorkspace from '../../components/mobile/MobileSwipeWorkspace.vue'

const OCR_STORAGE_PREFIX = 'aluminum-ocr-submission:'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { enqueuePendingRequest } = useRetryQueue()

const loading = ref(true)
const loadError = ref(null)
const lookupLoading = ref(false)
const saving = ref(false)
const submitting = ref(false)
const submittedCount = ref(0)
const batchText = ref('')
const batchQueue = ref([])
const trackingCardNo = ref('')
const template = ref(null)
const equipmentOptions = ref([])
const currentWorkOrder = ref(null)
const currentEntry = ref(null)
const ocrState = reactive({
  submissionId: null,
  imageUrl: '',
  rawText: '',
  fields: {},
  verified: false
})
const voiceListeningField = ref('')
const currentShift = reactive({
  business_date: '',
  shift_id: null,
  shift_code: '',
  shift_name: '',
  workshop_id: null,
  workshop_name: '',
  workshop_type: '',
  machine_id: null,
  machine_code: '',
  machine_name: '',
  machine_custom_fields: [],
  is_machine_bound: false,
  team_name: '',
  leader_name: '',
  ownership_note: '',
  can_submit: false
})
const formState = reactive({
  business_date: String(route.params.businessDate || ''),
  shift_id: route.params.shiftId ? Number(route.params.shiftId) : null,
  machine_id: null
})
const formValues = reactive({})
const completionMode = ref('in_progress')
const justSubmitted = ref(false)
const lastSubmitTime = ref(0)
const submitCooldownActive = ref(false)
const entryCreateIdempotencyKey = ref(buildClientUuid())
let submitCooldownTimer = null

const OPERATOR_CONFIRMATION_FIELD = {
  name: 'operator_notes',
  label: '异常说明 / 班末补充确认',
  type: 'textarea',
  required: false,
  target: 'entry',
  hint: ''
}

const entryFields = computed(() => template.value?.entry_fields || [])
const shiftFields = computed(() => template.value?.shift_fields || [])
const workshopExtraFields = computed(() => template.value?.extra_fields || [])
const machineFields = computed(() =>
  (currentShift.machine_custom_fields || []).map((field, index) => ({
    ...field,
    name: field.name,
    label: field.name === 'operator_notes' ? '备注' : (field.label || field.name),
    type: field.type || 'number',
    unit: field.unit || '',
    required: Boolean(field.required),
    target: 'extra',
    source: 'machine',
    sort_order: Number(field.sort_order ?? index)
  }))
)
const extraFields = computed(() => workshopExtraFields.value)
const qcFields = computed(() => template.value?.qc_fields || [])
const existingEditableFieldNames = computed(() => new Set([
  ...entryFields.value,
  ...shiftFields.value,
  ...workshopExtraFields.value,
  ...machineFields.value,
  ...qcFields.value
].map((field) => field.name)))
const operatorConfirmationFields = computed(() => {
  if (isOwnerOnlyMode.value) return []
  if (existingEditableFieldNames.value.has(OPERATOR_CONFIRMATION_FIELD.name)) return []
  return [OPERATOR_CONFIRMATION_FIELD]
})
const editableFields = computed(() => [
  ...entryFields.value,
  ...shiftFields.value,
  ...operatorConfirmationFields.value,
  ...workshopExtraFields.value,
  ...machineFields.value,
  ...qcFields.value
])
const batchEditableFields = computed(() => [...entryFields.value])
const readonlyFields = computed(() => template.value?.readonly_fields || [])
const hasSupplementalFields = computed(() => Boolean(
  shiftFields.value.length ||
  operatorConfirmationFields.value.length ||
  extraFields.value.length ||
  machineFields.value.length ||
  qcFields.value.length
))
const hasShiftConfirmationFields = computed(() => Boolean(shiftFields.value.length || operatorConfirmationFields.value.length))
const isSlowTempo = computed(() => template.value?.tempo === 'slow')
const isFastTempo = computed(() => template.value?.tempo === 'fast')
const isMachineBound = computed(() => Boolean(currentShift.is_machine_bound || auth.isMachineBound))
const boundMachine = computed(() => {
  const machineId = currentShift.machine_id || auth.machineContext?.machine_id
  if (!machineId) return null
  return equipmentOptions.value.find((item) => Number(item.id) === Number(machineId)) || {
    id: machineId,
    code: currentShift.machine_code || auth.machineContext?.machine_code || '',
    name: currentShift.machine_name || auth.machineContext?.machine_name || ''
  }
})
const transitionMapping = computed(() => buildMobileTransitionMapping({
  role: auth.role,
  isMachineBound: isMachineBound.value,
  reportStatus: currentEntry.value?.entry_status || currentShift.report_status,
}))
const roleBucketMeta = computed(() => describeTransitionRoleBucket(transitionMapping.value.role_bucket))
const ROLE_COLOR_MAP = {
  shift_leader: 'var(--m-role-operator)',
  energy_stat: 'var(--m-role-energy)',
  maintenance_lead: 'var(--m-role-maintenance)',
  hydraulic_lead: 'var(--m-role-hydraulic)',
  consumable_stat: 'var(--m-role-consumable)',
  qc: 'var(--m-role-qc)',
  weigher: 'var(--m-role-weigher)',
  utility_manager: 'var(--m-role-utility)',
  inventory_keeper: 'var(--m-role-inventory)',
  contracts: 'var(--m-role-contracts)',
}
const roleColor = computed(() => ROLE_COLOR_MAP[transitionMapping.value.role_bucket] || 'var(--m-role-operator)')
const ownerOnlyRoleBuckets = ['contracts', 'inventory_keeper', 'utility_manager', 'energy_stat', 'maintenance_lead', 'hydraulic_lead', 'consumable_stat']
const isOwnerOnlyMode = computed(() => ownerOnlyRoleBuckets.includes(transitionMapping.value.role_bucket))
const OWNER_MODE_CONFIG = {
  inventory_keeper: {
    title: '填出入库',
    coreCardTitle: '今日进出',
    coreStepTitle: '进出',
    supplementalCardTitle: '结存复核',
    supplementalStepTitle: '结存',
    coreSections: [
      {
        title: '今日入库',
        fieldNames: [
          'storage_inbound_weight',
          'storage_inbound_area',
          'plant_to_park_inbound_weight',
          'park_to_storage_inbound_weight',
        ],
      },
      {
        title: '今日发货',
        fieldNames: [
          'shipment_weight',
          'shipment_area',
          'month_to_date_shipment_weight',
          'month_to_date_shipment_area',
        ],
      },
    ],
    supplementalSections: [
      {
        title: '结存与备料',
        fieldNames: [
          'month_to_date_inbound_weight',
          'month_to_date_inbound_area',
          'consignment_weight',
          'finished_inventory_weight',
          'shearing_prepared_weight',
        ],
      },
    ],
  },
  utility_manager: {
    title: '填水电气',
    coreCardTitle: '介质录入',
    coreStepTitle: '介质',
    supplementalCardTitle: '水量补录',
    supplementalStepTitle: '用水',
    coreSections: [
      {
        title: '用电',
        fieldNames: [
          'total_electricity_kwh',
          'new_plant_electricity_kwh',
          'park_electricity_kwh',
        ],
      },
      {
        title: '天然气',
        fieldNames: [
          'cast_roll_gas_m3',
          'smelting_gas_m3',
          'heating_furnace_gas_m3',
          'boiler_gas_m3',
          'total_gas_m3',
        ],
      },
    ],
    supplementalSections: [
      {
        title: '用水',
        fieldNames: ['groundwater_ton', 'tap_water_ton'],
      },
    ],
  },
  contracts: {
    title: '填合同',
    coreCardTitle: '合同进度',
    coreStepTitle: '合同',
    supplementalCardTitle: '投料补录',
    supplementalStepTitle: '投料',
    coreSections: [
      {
        title: '当日合同',
        fieldNames: ['daily_contract_weight', 'daily_hot_roll_contract_weight'],
      },
      {
        title: '月累计与余合同',
        fieldNames: [
          'month_to_date_contract_weight',
          'month_to_date_hot_roll_contract_weight',
          'remaining_contract_weight',
          'remaining_hot_roll_contract_weight',
          'remaining_contract_delta_weight',
        ],
      },
    ],
    supplementalSections: [
      {
        title: '投料与坯料',
        fieldNames: [
          'billet_inventory_weight',
          'daily_input_weight',
          'month_to_date_input_weight',
        ],
      },
    ],
  },
  energy_stat: {
    title: '填能耗',
    coreCardTitle: '能耗录入',
    coreStepTitle: '能耗',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [
      { title: '电耗与气耗', fieldNames: ['energy_kwh', 'gas_m3'] },
    ],
    supplementalSections: [],
  },
  maintenance_lead: {
    title: '报停机',
    coreCardTitle: '停机录入',
    coreStepTitle: '停机',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [
      { title: '停机记录', fieldNames: ['downtime_minutes', 'downtime_reason'] },
    ],
    supplementalSections: [],
  },
  hydraulic_lead: {
    title: '报油耗',
    coreCardTitle: '耗油录入',
    coreStepTitle: '耗油',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [
      { title: '液压油与齿轮油', fieldNames: ['hydraulic_oil_32', 'hydraulic_oil_46', 'gear_oil'] },
    ],
    supplementalSections: [],
  },
  consumable_stat: {
    title: '报辅材',
    coreCardTitle: '辅材录入',
    coreStepTitle: '辅材',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [],
    supplementalSections: [],
  },
  qc: {
    title: '填质检',
    coreCardTitle: '质检录入',
    coreStepTitle: '质检',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [
      { title: '质检结论', fieldNames: ['qc_grade', 'qc_notes'] },
    ],
    supplementalSections: [],
  },
  weigher: {
    title: '核重量',
    coreCardTitle: '核实重量',
    coreStepTitle: '称重',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [
      { title: '核实重量', fieldNames: ['verified_input_weight', 'verified_output_weight'] },
    ],
    supplementalSections: [],
  },
}
const defaultOwnerModeConfig = {
  title: roleBucketMeta.value.title,
  coreCardTitle: '补录',
  coreStepTitle: '本班',
  supplementalCardTitle: '补录字段',
  supplementalStepTitle: '补录',
  coreSections: [],
  supplementalSections: [],
}
const CONSUMABLE_SECTIONS_BY_WORKSHOP = {
  casting: [
    { title: '铸轧辅材', fieldNames: ['liquefied_gas_per_ton', 'titanium_wire_per_ton', 'steel_strip_per_ton', 'magnesium_per_ton', 'manganese_per_ton', 'iron_per_ton', 'copper_per_ton'] },
  ],
  hot_roll: [
    { title: '热轧辅材', fieldNames: ['hot_roll_emulsion_per_ton'] },
  ],
  cold_roll: [
    { title: '冷轧辅材', fieldNames: ['rolling_oil_per_ton', 'filter_agent_per_ton', 'diatomite_per_ton', 'white_earth_per_ton', 'filter_cloth_daily', 'high_temp_tape_daily', 'regen_oil_out', 'regen_oil_in'] },
  ],
  finishing: [
    { title: '精整辅材', fieldNames: ['rolling_oil_per_ton', 'd40_per_ton', 'steel_plate_per_ton', 'steel_strip_per_ton', 'steel_buckle_per_ton', 'high_temp_tape_daily'] },
  ],
}
const ownerModeConfig = computed(() => {
  const bucket = transitionMapping.value.role_bucket
  if (bucket === 'consumable_stat') {
    const workshopType = currentShift.workshop_type || bootstrap.value?.workshop_type || 'casting'
    const base = OWNER_MODE_CONFIG[bucket]
    return {
      ...base,
      coreSections: CONSUMABLE_SECTIONS_BY_WORKSHOP[workshopType] || CONSUMABLE_SECTIONS_BY_WORKSHOP.casting,
    }
  }
  return OWNER_MODE_CONFIG[bucket] || defaultOwnerModeConfig
})
const ownerOnlyEditableFields = computed(() => [
  ...entryFields.value,
  ...shiftFields.value,
  ...extraFields.value,
  ...machineFields.value,
  ...qcFields.value,
])
const ownerSectionBundle = computed(() => {
  if (!isOwnerOnlyMode.value) {
    return { core: [], supplemental: [] }
  }

  const fieldMap = new Map(ownerOnlyEditableFields.value.map((field) => [field.name, field]))
  const usedFieldNames = new Set()
  const buildSections = (definitions = []) =>
    definitions
      .map((section) => {
        const fields = section.fieldNames
          .map((name) => fieldMap.get(name))
          .filter(Boolean)
        fields.forEach((field) => usedFieldNames.add(field.name))
        return { title: section.title, fields }
      })
      .filter((section) => section.fields.length)

  const core = buildSections(ownerModeConfig.value.coreSections)
  const supplemental = buildSections(ownerModeConfig.value.supplementalSections)
  const leftovers = ownerOnlyEditableFields.value.filter((field) => !usedFieldNames.has(field.name))
  if (leftovers.length) {
    supplemental.push({ title: '其他补录', fields: leftovers })
  }

  return { core, supplemental }
})
const ownerCoreSections = computed(() => ownerSectionBundle.value.core)
const ownerSupplementalSections = computed(() => ownerSectionBundle.value.supplemental)
const currentStepKey = ref('work_order')
const visibleStepItems = computed(() => {
  const items = []
  if (!isOwnerOnlyMode.value) {
    items.push({ key: 'work_order', title: '批次号' })
  }
  items.push({ key: 'core', title: isOwnerOnlyMode.value ? ownerModeConfig.value.coreStepTitle : '本卷' })
  if (isOwnerOnlyMode.value ? ownerSupplementalSections.value.length : hasSupplementalFields.value) {
    items.push({ key: 'supplemental', title: isOwnerOnlyMode.value ? ownerModeConfig.value.supplementalStepTitle : (hasShiftConfirmationFields.value ? '班末' : '补充') })
  }
  items.push({ key: 'review', title: '提交' })
  return items
})
const currentStepIndex = computed(() => {
  const index = visibleStepItems.value.findIndex((item) => item.key === currentStepKey.value)
  return index >= 0 ? index : 0
})
const isFirstStep = computed(() => currentStepIndex.value <= 0)
const isReviewStep = computed(() => currentStepKey.value === 'review')
const summaryFacts = computed(() => [
  formState.business_date || '-',
  currentShift.shift_name || currentShift.shift_code || '-',
  isOwnerOnlyMode.value ? '本班补录' : '本卷录入'
])
const readOnlyByCreator = computed(() => {
  if (!currentEntry.value?.created_by_user_id || !auth.user?.id) return false
  return Number(currentEntry.value.created_by_user_id) !== Number(auth.user.id)
})
const readOnlyCreatorBanner = computed(() => {
  if (!readOnlyByCreator.value) return ''
  const creatorName = currentEntry.value?.created_by_user_name || '其他用户'
  return `此条目由 ${creatorName} 创建，您仅可查看`
})
const canOperate = computed(() => Boolean(template.value) && Boolean(currentShift.can_submit) && !loading.value && !readOnlyByCreator.value)
const isEntryEditingDisabled = computed(() =>
  loading.value || saving.value || submitting.value || !currentShift.can_submit || postSubmitLocked.value || readOnlyByCreator.value
)
const postSubmitLocked = computed(() => justSubmitted.value && !currentEntry.value)
const submitButtonDisabled = computed(() => !canOperate.value || submitting.value || postSubmitLocked.value || submitCooldownActive.value)
const canContinueNext = computed(() => isFastTempo.value && (justSubmitted.value || batchQueue.value.length > 0))
const showFastEntryHelper = computed(() => Boolean(
  !isOwnerOnlyMode.value &&
  isFastTempo.value &&
  (submittedCount.value || batchQueue.value.length || canContinueNext.value)
))
const entryType = computed(() => (isSlowTempo.value ? completionMode.value : 'completed'))
const yieldRate = computed(() => {
  const inputWeight = toNumber(formValues.input_weight)
  const outputWeight = toNumber(formValues.output_weight)
  if (inputWeight === null || outputWeight === null || inputWeight <= 0) return null
  return Number(((outputWeight / inputWeight) * 100).toFixed(2))
})
const yieldDisplay = computed(() => (yieldRate.value === null ? '-' : `${yieldRate.value.toFixed(2)}%`))
const filledEditableFieldCount = computed(() =>
  editableFields.value.filter((field) => !isEmptyValue(normalizeFieldValue(field, formValues[field.name]))).length
)
const yieldClass = computed(() => {
  if (yieldRate.value === null) return 'yield-pill yield-pill--neutral'
  if (yieldRate.value >= 98) return 'yield-pill yield-pill--good'
  if (yieldRate.value >= 95) return 'yield-pill yield-pill--warn'
  return 'yield-pill yield-pill--danger'
})
const historyEntries = computed(() => {
  const entries = currentWorkOrder.value?.entries || []
  if (!entries.length) return []
  return [...entries]
    .filter((item) => item.id !== currentEntry.value?.id)
    .sort((left, right) => {
      const leftKey = `${left.business_date || ''}-${left.id || 0}`
      const rightKey = `${right.business_date || ''}-${right.id || 0}`
      return rightKey.localeCompare(leftKey)
    })
})
const readonlyDisplayItems = computed(() =>
  readonlyFields.value
    .map((field) => {
      const value = resolveReadonlyFieldValue(field)
      if (isEmptyValue(value)) return null
      return {
        name: field.name,
        label: displayFieldLabel(field),
        value: formatFieldValueForDisplay(field, value)
      }
    })
    .filter(Boolean)
)
const workOrderSummaryItems = computed(() => {
  if (!template.value) return []
  const items = editableFields.value
    .filter((field) => field.target === 'work_order')
    .map((field) => {
      const rawValue = currentWorkOrder.value ? currentWorkOrder.value[field.name] : formValues[field.name]
      if (isEmptyValue(rawValue)) return null
      return {
        label: displayFieldLabel(field),
        value: formatFieldValueForDisplay(field, rawValue)
      }
    })
    .filter(Boolean)
  return items
})
const supplementalCardTitle = computed(() => {
  if (isOwnerOnlyMode.value) return ownerModeConfig.value.supplementalCardTitle
  if (hasShiftConfirmationFields.value) return '班末确认'
  return '补充字段'
})
const batchColumnLabels = computed(() =>
  ['批次号', ...batchEditableFields.value.map((field) => displayFieldLabel(field))].join(' / ')
)

const hasOcrContext = computed(() => Boolean(ocrState.submissionId))
const hasSecondaryContent = computed(() => Boolean(
  hasOcrContext.value ||
  currentWorkOrder.value?.previous_stage_output ||
  readonlyDisplayItems.value.length ||
  isFastTempo.value
))
const reviewSummaryItems = computed(() => {
  const items = [
    { label: isOwnerOnlyMode.value ? '岗位归档' : '批次号', value: activeTrackingCardNo.value || '-' },
    { label: '班次', value: currentShift.shift_name || currentShift.shift_code || '-' },
    {
      label: isOwnerOnlyMode.value ? '岗位' : (isMachineBound.value ? '机台' : '班组'),
      value: isOwnerOnlyMode.value
        ? roleBucketMeta.value.title
        : (boundMachine.value?.name || currentShift.machine_name || currentShift.team_name || '-')
    },
    { label: '已填', value: `${filledEditableFieldCount.value}/${editableFields.value.length}` },
    { label: '提交方式', value: isSlowTempo.value ? (completionMode.value === 'completed' ? '本班完工' : '本班接续') : '本班完工' }
  ]

  if (!isOwnerOnlyMode.value && yieldRate.value !== null) {
    items.splice(4, 0, { label: '成材率', value: yieldDisplay.value })
  }

  return items
})
const localDraftScope = computed(() => ({
  workshopId: currentShift.workshop_id || '',
  shiftId: formState.shift_id || '',
  businessDate: formState.business_date || '',
  machineId: formState.machine_id || currentShift.machine_id || '',
  trackingCardNo: trackingCardNo.value || ''
}))
const localDraftSnapshot = computed(() => ({
  trackingCardNo: trackingCardNo.value,
  formState: {
    business_date: formState.business_date,
    shift_id: formState.shift_id,
    machine_id: formState.machine_id
  },
  formValues: { ...formValues },
  completionMode: completionMode.value,
  currentWorkOrder: currentWorkOrder.value,
  currentEntry: currentEntry.value,
  batchQueue: [...batchQueue.value],
  batchText: batchText.value,
  ocrState: {
    submissionId: ocrState.submissionId,
    imageUrl: ocrState.imageUrl,
    rawText: ocrState.rawText,
    fields: { ...ocrState.fields },
    verified: ocrState.verified
  },
  entryCreateIdempotencyKey: entryCreateIdempotencyKey.value
}))
const {
  autoSavedLabel,
  checkForRestorableDraft,
  clearDraft: clearLocalDraft,
  currentDraftKey,
  discardDraft,
  restoreDialogVisible,
  restoreDraft,
  restoreDraftSavedAt
} = useLocalDraft({
  scope: localDraftScope,
  snapshot: localDraftSnapshot,
  applyDraft: applyLocalDraft,
  enabled: computed(() => Boolean(template.value) && Boolean(currentShift.workshop_id)),
  isMeaningful: isMeaningfulLocalDraft
})

function buildClientUuid() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `entry-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function requestErrorMessage(error, fallback = '提交失败') {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item).join('; ')
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || fallback
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }
  return error?.message || fallback
}

function ocrStorageKey(submissionId) {
  return `${OCR_STORAGE_PREFIX}${submissionId}`
}

function buildOwnerOnlyTrackingCardNo() {
  const workshopCode = String(currentShift.workshop_code || currentShift.workshop_id || 'WS').trim().toUpperCase()
  const businessDate = String(formState.business_date || currentShift.business_date || '').replace(/-/g, '')
  const shiftCode = String(currentShift.shift_code || formState.shift_id || 'SHIFT').trim().toUpperCase()
  return normalizeTrackingCard(`OWNER-${workshopCode}-${businessDate}-${shiftCode}-${transitionMapping.value.role_bucket}`)
}

const activeTrackingCardNo = computed(() => {
  if (isOwnerOnlyMode.value) {
    return buildOwnerOnlyTrackingCardNo()
  }
  return normalizeTrackingCard(trackingCardNo.value)
})

function ocrMetaForField(fieldName) {
  return ocrState.fields?.[fieldName] || null
}

function confidenceTone(confidence) {
  if (confidence === null || confidence === undefined) return 'warn'
  if (confidence >= 0.85) return 'good'
  if (confidence >= 0.6) return 'warn'
  return 'danger'
}

function confidenceLabel(confidence) {
  if (confidence === null || confidence === undefined) return '待核对'
  return `${Math.round(confidence * 100)}%`
}

function isVoiceFieldSupported(_field) {
  return false
}

function toggleVoicePrefill(_field) {
  voiceListeningField.value = ''
}

function clearOcrState({ clearStorage = false } = {}) {
  if (clearStorage && ocrState.submissionId) {
    sessionStorage.removeItem(ocrStorageKey(ocrState.submissionId))
  }
  ocrState.submissionId = null
  ocrState.imageUrl = ''
  ocrState.rawText = ''
  ocrState.fields = {}
  ocrState.verified = false
}

function clearSubmitCooldownTimer() {
  if (submitCooldownTimer) {
    clearTimeout(submitCooldownTimer)
    submitCooldownTimer = null
  }
}

function startSubmitCooldown() {
  lastSubmitTime.value = Date.now()
  submitCooldownActive.value = true
  clearSubmitCooldownTimer()
  submitCooldownTimer = setTimeout(() => {
    submitCooldownActive.value = false
    submitCooldownTimer = null
  }, SUBMIT_COOLDOWN_MS)
}

function isCurrentStep(stepKey) {
  return currentStepKey.value === stepKey
}

function goNextStep() {
  const normalized = activeTrackingCardNo.value
  if (currentStepKey.value === 'work_order' && !isOwnerOnlyMode.value && !normalized) {
    ElMessage.warning('请先录入或读取批次号')
    return
  }
  const next = visibleStepItems.value[currentStepIndex.value + 1]
  if (!next) return
  currentStepKey.value = next.key
}

function goPrevStep() {
  const prev = visibleStepItems.value[currentStepIndex.value - 1]
  if (!prev) return
  currentStepKey.value = prev.key
}

function goHistory() {
  router.push({ name: 'mobile-report-history' })
}

watch(visibleStepItems, (steps) => {
  if (!steps.some((item) => item.key === currentStepKey.value)) {
    currentStepKey.value = steps[0]?.key || 'work_order'
  }
}, { immediate: true })

function normalizeTrackingCard(value) {
  return String(value || '').trim().toUpperCase()
}

function ensureEntryCreateIdempotencyKey() {
  if (!entryCreateIdempotencyKey.value) {
    entryCreateIdempotencyKey.value = buildClientUuid()
  }
  return entryCreateIdempotencyKey.value
}

function isMeaningfulLocalDraft(snapshot) {
  if (!snapshot) return false
  if (normalizeTrackingCard(snapshot.trackingCardNo)) return true
  if (snapshot.formState?.machine_id) return true
  if ((snapshot.batchQueue || []).length) return true
  if (String(snapshot.batchText || '').trim()) return true
  if (snapshot.currentWorkOrder?.id || snapshot.currentEntry?.id) return true
  return Object.values(snapshot.formValues || {}).some((value) => !isEmptyValue(value))
}

function applyLocalDraft(snapshot) {
  if (!snapshot) return
  trackingCardNo.value = normalizeTrackingCard(snapshot.trackingCardNo || '')
  currentStepKey.value = isOwnerOnlyMode.value ? 'core' : 'work_order'
  formState.business_date = String(snapshot.formState?.business_date || formState.business_date || '')
  formState.shift_id = snapshot.formState?.shift_id ? Number(snapshot.formState.shift_id) : null
  formState.machine_id = snapshot.formState?.machine_id || null
  batchText.value = String(snapshot.batchText || '')
  batchQueue.value = Array.isArray(snapshot.batchQueue) ? [...snapshot.batchQueue] : []
  currentWorkOrder.value = snapshot.currentWorkOrder || null
  currentEntry.value = snapshot.currentEntry || null
  entryCreateIdempotencyKey.value = snapshot.entryCreateIdempotencyKey || buildClientUuid()
  resetFormValues()
  editableFields.value.forEach((field) => {
    formValues[field.name] = formatFieldValue(field, snapshot.formValues?.[field.name])
  })
  completionMode.value = snapshot.completionMode || (isSlowTempo.value ? 'in_progress' : 'completed')
  clearOcrState()
  ocrState.submissionId = snapshot.ocrState?.submissionId || null
  ocrState.imageUrl = snapshot.ocrState?.imageUrl || ''
  ocrState.rawText = snapshot.ocrState?.rawText || ''
  ocrState.fields = snapshot.ocrState?.fields || {}
  ocrState.verified = Boolean(snapshot.ocrState?.verified)
}

function emptyFieldValue(field) {
  if (field.type === 'number') return null
  return ''
}

function resetFormValues({ keepHeader = false } = {}) {
  const previousHeaderValues = {}
  editableFields.value.forEach((field) => {
    if (keepHeader && field.target === 'work_order') {
      previousHeaderValues[field.name] = formValues[field.name]
    }
  })
  Object.keys(formValues).forEach((key) => {
    delete formValues[key]
  })
  editableFields.value.forEach((field) => {
    formValues[field.name] = keepHeader && field.target === 'work_order'
      ? previousHeaderValues[field.name] ?? emptyFieldValue(field)
      : emptyFieldValue(field)
  })
  completionMode.value = isSlowTempo.value ? 'in_progress' : 'completed'
}

function initializeTemplateForm() {
  currentStepKey.value = 'work_order'
  resetFormValues()
  entryCreateIdempotencyKey.value = buildClientUuid()
  if (equipmentOptions.value.length === 1 && !formState.machine_id) {
    formState.machine_id = equipmentOptions.value[0].id
  }
}

function loadOcrFromStorage() {
  clearOcrState()
  const submissionId = Number(route.query.ocr_submission_id || 0)
  if (!submissionId) return
  const raw = sessionStorage.getItem(ocrStorageKey(submissionId))
  if (!raw) return

  try {
    const payload = JSON.parse(raw)
    ocrState.submissionId = submissionId
    ocrState.imageUrl = payload.image_url || ''
    ocrState.rawText = payload.raw_text || ''
    ocrState.fields = payload.fields || {}
    ocrState.verified = Boolean(payload.status === 'verified' || payload.verified)

    editableFields.value.forEach((field) => {
      const meta = payload.fields?.[field.name]
      if (!meta || meta.value === null || meta.value === undefined || meta.value === '') return
      if (isEmptyValue(formValues[field.name])) {
        formValues[field.name] = formatFieldValue(field, meta.value)
      }
    })
  } catch {
    clearOcrState({ clearStorage: true })
  }
}

function toNumber(value) {
  if (value === '' || value === null || value === undefined) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function isEmptyValue(value) {
  if (value === null || value === undefined) return true
  if (typeof value === 'string') return value.trim() === ''
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === 'object') return Object.keys(value).length === 0
  return false
}

const SAFE_EXPRESSION_PATTERN = /^[A-Za-z0-9_+\-*/().%\s]+$/

function operatorPrecedence(operator) {
  if (operator === '+' || operator === '-') return 1
  if (operator === '*' || operator === '/' || operator === '%') return 2
  return 0
}

function applyMathOperator(values, operator) {
  if (values.length < 2) return false
  const right = Number(values.pop())
  const left = Number(values.pop())
  let result = null

  if (operator === '+') result = left + right
  else if (operator === '-') result = left - right
  else if (operator === '*') result = left * right
  else if (operator === '/') result = right === 0 ? null : left / right
  else if (operator === '%') result = right === 0 ? null : left % right

  if (result === null || !Number.isFinite(result)) return false
  values.push(result)
  return true
}

function safeEvaluate(expression, variables) {
  const source = String(expression || '').trim()
  if (!source || !SAFE_EXPRESSION_PATTERN.test(source)) return null

  const tokens = source.match(/[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|[()+\-*/%]/g) || []
  if (!tokens.length) return null

  const values = []
  const operators = []
  let previousTokenType = 'start'

  for (const token of tokens) {
    if (/^\d+(?:\.\d+)?$/.test(token)) {
      values.push(Number(token))
      previousTokenType = 'value'
      continue
    }

    if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(token)) {
      values.push(Number(variables[token] ?? 0))
      previousTokenType = 'value'
      continue
    }

    if (token === '(') {
      operators.push(token)
      previousTokenType = '('
      continue
    }

    if (token === ')') {
      while (operators.length && operators[operators.length - 1] !== '(') {
        if (!applyMathOperator(values, operators.pop())) return null
      }
      if (operators.length === 0 || operators.pop() !== '(') return null
      previousTokenType = 'value'
      continue
    }

    if ('+-*/%'.includes(token)) {
      if (token === '-' && (previousTokenType === 'start' || previousTokenType === 'operator' || previousTokenType === '(')) {
        values.push(0)
      }

      while (
        operators.length &&
        operators[operators.length - 1] !== '(' &&
        operatorPrecedence(operators[operators.length - 1]) >= operatorPrecedence(token)
      ) {
        if (!applyMathOperator(values, operators.pop())) return null
      }
      operators.push(token)
      previousTokenType = 'operator'
      continue
    }

    return null
  }

  while (operators.length) {
    const operator = operators.pop()
    if (operator === '(' || operator === ')') return null
    if (!applyMathOperator(values, operator)) return null
  }

  if (values.length !== 1) return null
  const finalValue = Number(values[0])
  return Number.isFinite(finalValue) ? finalValue : null
}

function normalizeFieldValue(field, rawValue) {
  if (rawValue === null || rawValue === undefined || rawValue === '') return null
  if (field.type === 'number') return toNumber(rawValue)
  if (field.type === 'time') {
    const text = String(rawValue)
    if (!text.trim()) return null
    return text.length === 5 ? `${text}:00` : text
  }
  return String(rawValue).trim()
}

function formatFieldValue(field, rawValue) {
  if (rawValue === null || rawValue === undefined) return emptyFieldValue(field)
  if (field.type === 'time') return String(rawValue).slice(0, 8)
  return rawValue
}

function formatFieldValueForDisplay(field, rawValue) {
  if (rawValue === null || rawValue === undefined || rawValue === '') return '-'
  if (field.type === 'number') {
    const digits = Number.isInteger(Number(rawValue)) ? 0 : 2
    const formatted = formatNumber(rawValue, digits)
    return field.unit ? `${formatted} ${field.unit}` : formatted
  }
  if (field.type === 'time') return String(rawValue).slice(0, 5)
  return String(rawValue)
}

function displayFieldLabel(field) {
  if (!field) return ''
  if (field.name === 'operator_notes') return '备注'
  return field.label || field.name || ''
}

function fieldPlaceholder(field) {
  const label = displayFieldLabel(field)
  if (field.type === 'number') return '数字'
  if (field.type === 'time') return '时间'
  return label || '填写'
}

function resolvePersistedFieldValue(field, workOrder = currentWorkOrder.value, entry = currentEntry.value) {
  if (field.target === 'work_order') return workOrder?.[field.name] ?? null
  if (field.target === 'entry') return entry?.[field.name] ?? null
  if (field.target === 'extra') return entry?.extra_payload?.[field.name] ?? null
  if (field.target === 'qc') return entry?.qc_payload?.[field.name] ?? null
  return null
}

function resolveFieldValueByName(fieldName) {
  const editableField = editableFields.value.find((field) => field.name === fieldName)
  if (editableField) {
    const normalized = normalizeFieldValue(editableField, formValues[fieldName])
    if (!isEmptyValue(normalized)) return normalized
    const persisted = resolvePersistedFieldValue(editableField)
    if (!isEmptyValue(persisted)) return persisted
  }

  const readonlyField = readonlyFields.value.find((field) => field.name === fieldName)
  if (readonlyField) {
    const persisted = resolvePersistedFieldValue(readonlyField)
    if (!isEmptyValue(persisted)) return persisted
  }

  if (currentEntry.value?.extra_payload?.[fieldName] !== undefined) return currentEntry.value.extra_payload[fieldName]
  if (currentEntry.value?.qc_payload?.[fieldName] !== undefined) return currentEntry.value.qc_payload[fieldName]
  if (currentEntry.value?.[fieldName] !== undefined) return currentEntry.value[fieldName]
  if (currentWorkOrder.value?.[fieldName] !== undefined) return currentWorkOrder.value[fieldName]
  return null
}

function computeReadonlyFieldValue(field) {
  if (!field.compute) return null

  const identifiers = [...new Set(String(field.compute).match(/[A-Za-z_][A-Za-z0-9_]*/g) || [])]
  if (!identifiers.length) return null

  const valuesByName = Object.fromEntries(
    identifiers.map((name) => [name, toNumber(resolveFieldValueByName(name))])
  )

  if (field.name === 'yield_rate') {
    const inputWeight = valuesByName.input_weight
    const outputWeight = valuesByName.output_weight
    if (inputWeight === null || outputWeight === null || inputWeight <= 0) return null
  } else if (field.name === 'scrap_weight') {
    if (valuesByName.input_weight === null || valuesByName.output_weight === null) return null
    if (valuesByName.spool_weight === null) valuesByName.spool_weight = 0
  }

  const result = safeEvaluate(field.compute, valuesByName)
  if (result === null || !Number.isFinite(result)) return null
  return Number(result.toFixed(2))
}

function resolveReadonlyFieldValue(field) {
  const persisted = resolvePersistedFieldValue(field)
  if (!isEmptyValue(persisted)) return persisted
  return computeReadonlyFieldValue(field)
}

function hydrateFormFromWorkOrder(workOrder) {
  currentWorkOrder.value = workOrder
  const matchingEntries = (workOrder.entries || []).filter((item) => {
      if (formState.shift_id && item.shift_id && Number(item.shift_id) !== Number(formState.shift_id)) return false
      return String(item.business_date || '') === String(formState.business_date || '')
    })
  const draftEntry = matchingEntries.find((item) => item.entry_status === 'draft') || null
  const latestEntry = [...matchingEntries]
    .sort((left, right) => {
      const leftKey = `${left.submitted_at || left.updated_at || ''}-${left.id || 0}`
      const rightKey = `${right.submitted_at || right.updated_at || ''}-${right.id || 0}`
      return rightKey.localeCompare(leftKey)
    })
    .at(0) || null

  currentEntry.value = draftEntry || latestEntry
  resetFormValues()

  editableFields.value.forEach((field) => {
    const persistedValue = resolvePersistedFieldValue(field, workOrder, currentEntry.value)
    formValues[field.name] = formatFieldValue(field, persistedValue)
  })

  if (currentEntry.value?.machine_id) {
    formState.machine_id = currentEntry.value.machine_id
  }
  entryCreateIdempotencyKey.value = currentEntry.value?.id ? '' : buildClientUuid()
  if (currentEntry.value?.entry_type) {
    completionMode.value = currentEntry.value.entry_type
  } else {
    completionMode.value = isSlowTempo.value ? 'in_progress' : 'completed'
  }
}

async function refreshWorkOrder() {
  const normalized = activeTrackingCardNo.value
  if (!normalized) return
  const payload = await findWorkOrderByTrackingCard(normalized)
  if (!payload) {
    currentWorkOrder.value = null
    currentEntry.value = null
    return
  }
  hydrateFormFromWorkOrder(payload)
}

async function lookupTrackingCard({ silentMissing = false } = {}) {
  const normalized = activeTrackingCardNo.value
  if (!normalized && !isOwnerOnlyMode.value) {
    ElMessage.warning('请先输入批次号')
    return
  }
  if (!isOwnerOnlyMode.value) {
    trackingCardNo.value = normalized
  }
  lookupLoading.value = true
  justSubmitted.value = false
  try {
    const payload = await findWorkOrderByTrackingCard(normalized)
    if (!payload) {
      currentWorkOrder.value = null
      currentEntry.value = null
      if (!silentMissing) {
        ElMessage.info('未找到对应工单，首次保存时会自动创建')
      }
      return
    }
    hydrateFormFromWorkOrder(payload)
    currentStepKey.value = 'core'
    ElMessage.success(isOwnerOnlyMode.value ? '已读取岗位补录草稿' : '已读取工单')
  } finally {
    lookupLoading.value = false
  }
}

function collectWorkOrderPayload() {
  const payload = {}
  editableFields.value
    .filter((field) => field.target === 'work_order')
    .forEach((field) => {
      payload[field.name] = normalizeFieldValue(field, formValues[field.name])
    })
  return payload
}

function collectEntryPayload() {
  const payload = {
    workshop_id: currentShift.workshop_id,
    machine_id: formState.machine_id || null,
    shift_id: formState.shift_id || null,
    business_date: formState.business_date,
    entry_type: entryType.value
  }
  const extraPayload = {}
  const qcPayload = {}

  editableFields.value.forEach((field) => {
    const value = normalizeFieldValue(field, formValues[field.name])
    if (field.target === 'entry') {
      payload[field.name] = value
      return
    }
    if (field.target === 'extra') {
      if (value !== null) extraPayload[field.name] = value
      return
    }
    if (field.target === 'qc') {
      if (value !== null) qcPayload[field.name] = value
    }
  })

  payload.extra_payload = extraPayload
  payload.qc_payload = qcPayload
  if (ocrState.submissionId && !currentEntry.value?.id) {
    payload.ocr_submission_id = ocrState.submissionId
  }
  return payload
}

async function persistWorkOrderHeader(requestConfig = {}) {
  const normalized = activeTrackingCardNo.value
  if (!normalized && !isOwnerOnlyMode.value) {
    ElMessage.warning('请先输入批次号')
    return null
  }
  if (!currentWorkOrder.value) {
    const created = await createWorkOrder(
      {
        tracking_card_no: normalized,
        ...collectWorkOrderPayload()
      },
      requestConfig
    )
    currentWorkOrder.value = created
    return created
  }
  if (currentWorkOrder.value.tracking_card_no !== normalized) {
    ElMessage.warning('批次号已变更，请先点击“读取”确认当前记录')
    return null
  }
  const updated = await updateWorkOrder(currentWorkOrder.value.id, collectWorkOrderPayload(), requestConfig)
  currentWorkOrder.value = updated
  return updated
}

async function verifyOcrIfNeeded(requestConfig = {}) {
  if (!ocrState.submissionId || ocrState.verified) return

  const correctedFields = {}
  editableFields.value.forEach((field) => {
    const value = normalizeFieldValue(field, formValues[field.name])
    if (value !== null) {
      correctedFields[field.name] = value
    }
  })

  const payload = await verifyOcrFields(
    {
      ocr_submission_id: ocrState.submissionId,
      corrected_fields: correctedFields,
      rejected: false
    },
    requestConfig
  )

  ocrState.verified = payload.status === 'verified'
  sessionStorage.setItem(
    ocrStorageKey(ocrState.submissionId),
    JSON.stringify({
      ocr_submission_id: ocrState.submissionId,
      image_url: ocrState.imageUrl,
      raw_text: ocrState.rawText,
      fields: ocrState.fields,
      status: payload.status,
      verified: ocrState.verified
    })
  )
}

function isFieldRequired(field) {
  if (!field.required) return false
  if (isSlowTempo.value && completionMode.value === 'in_progress') {
    return !['output_weight', 'output_spec', 'off_machine_time'].includes(field.name)
  }
  return true
}

function validateBeforeSubmit() {
  const normalized = activeTrackingCardNo.value
  if (!isOwnerOnlyMode.value && !normalized) {
    ElMessage.warning('请先输入批次号')
    return false
  }
  if (equipmentOptions.value.length && !formState.machine_id && !isOwnerOnlyMode.value) {
    ElMessage.warning('请选择机台')
    return false
  }
  const missingField = editableFields.value.find((field) => isFieldRequired(field) && isEmptyValue(formValues[field.name]))
  if (missingField) {
    ElMessage.warning(`请先填写：${displayFieldLabel(missingField)}`)
    return false
  }
  return true
}

function buildCorrectedOcrFields() {
  const correctedFields = {}
  editableFields.value.forEach((field) => {
    const value = normalizeFieldValue(field, formValues[field.name])
    if (value !== null) {
      correctedFields[field.name] = value
    }
  })
  return correctedFields
}

async function queueDynamicSubmit() {
  const normalizedTrackingCardNo = activeTrackingCardNo.value
  await enqueuePendingRequest({
    type: 'dynamic-entry-submit',
    dedupeKey: `dynamic-entry-submit:${currentShift.workshop_id || 0}:${formState.shift_id || 0}:${formState.business_date || ''}:${normalizedTrackingCardNo}`,
    clearDraftKey: currentDraftKey.value,
    payload: {
      trackingCardNo: normalizedTrackingCardNo,
      workOrderPayload: collectWorkOrderPayload(),
      entryPayload: collectEntryPayload(),
      entryId: currentEntry.value?.id || null,
      ocrSubmissionId: ocrState.submissionId,
      ocrVerified: ocrState.verified,
      correctedFields: buildCorrectedOcrFields(),
      idempotencyKey: ensureEntryCreateIdempotencyKey()
    }
  })
}

async function persistEntry(requestConfig = {}) {
  const workOrder = await persistWorkOrderHeader(requestConfig)
  if (!workOrder) return null
  await verifyOcrIfNeeded(requestConfig)
  const payload = collectEntryPayload()
  if (currentEntry.value?.id) {
    const updated = await updateWorkOrderEntry(currentEntry.value.id, payload, requestConfig)
    currentEntry.value = updated
    return updated
  }
  const created = await createWorkOrderEntry(workOrder.id, payload, {
    ...requestConfig,
    headers: {
      ...(requestConfig.headers || {}),
      'X-Idempotency-Key': ensureEntryCreateIdempotencyKey()
    }
  })
  currentEntry.value = created
  if (ocrState.submissionId) {
    sessionStorage.removeItem(ocrStorageKey(ocrState.submissionId))
  }
  return created
}

async function saveDraft() {
  if (readOnlyByCreator.value) {
    ElMessage.warning(readOnlyCreatorBanner.value || '此条目当前仅可查看')
    return
  }
  saving.value = true
  try {
    const entry = await persistEntry({ skipErrorToast: true })
    if (!entry) return
    justSubmitted.value = false
    await refreshWorkOrder()
    ElMessage.success('草稿已保存')
  } catch (error) {
    if (isRetryableNetworkError(error)) {
      ElMessage.warning('网络不可用，内容已自动暂存在本机草稿')
      return
    }
    ElMessage.error(requestErrorMessage(error, '草稿保存失败'))
  } finally {
    saving.value = false
  }
}

async function submitEntry() {
  if (submitting.value) return
  if (isWithinSubmitCooldown(lastSubmitTime.value)) return
  if (readOnlyByCreator.value) {
    ElMessage.warning(readOnlyCreatorBanner.value || '此条目当前仅可查看')
    return
  }
  if (!validateBeforeSubmit()) return
  submitting.value = true
  try {
    const savedEntry = await persistEntry({ skipErrorToast: true })
    if (!savedEntry) return
    await submitWorkOrderEntry(savedEntry.id, {}, { skipErrorToast: true })
    submittedCount.value += 1
    justSubmitted.value = true
    clearLocalDraft(currentDraftKey.value)
    entryCreateIdempotencyKey.value = ''
    await refreshWorkOrder()
    startSubmitCooldown()
    if (isFastTempo.value && !isOwnerOnlyMode.value) {
      ElMessage.success(`第${submittedCount.value}卷已提交`)
      await new Promise((resolve) => {
        setTimeout(resolve, 500)
      })
      if (justSubmitted.value) {
        await prepareNextFastEntry()
      }
      return
    }
    ElMessage.success('已提交并锁定当前角色字段')
  } catch (error) {
    if (isRetryableNetworkError(error)) {
      await queueDynamicSubmit()
      justSubmitted.value = true
      startSubmitCooldown()
      clearLocalDraft(currentDraftKey.value)
      ElMessage.success('已加入待同步队列，联网后自动同步')
      if (isFastTempo.value && !isOwnerOnlyMode.value) {
        await new Promise((resolve) => {
          setTimeout(resolve, 500)
        })
        if (justSubmitted.value) {
          await prepareNextFastEntry()
        }
      }
      return
    }
    ElMessage.error(requestErrorMessage(error, '提交失败'))
  } finally {
    submitting.value = false
  }
}

async function applyBatchRow(row) {
  currentWorkOrder.value = null
  currentEntry.value = null
  justSubmitted.value = false
  clearOcrState({ clearStorage: true })
  trackingCardNo.value = normalizeTrackingCard(row.tracking_card_no)
  resetFormValues()
  batchEditableFields.value.forEach((field) => {
    formValues[field.name] = formatFieldValue(field, row[field.name])
  })
  await lookupTrackingCard({ silentMissing: true })
}

async function prepareNextFastEntry() {
  justSubmitted.value = false
  clearLocalDraft(currentDraftKey.value)
  currentWorkOrder.value = null
  currentEntry.value = null
  currentStepKey.value = isOwnerOnlyMode.value ? 'core' : 'work_order'
  trackingCardNo.value = ''
  clearOcrState({ clearStorage: true })
  resetFormValues()
  entryCreateIdempotencyKey.value = buildClientUuid()
  if (!batchQueue.value.length) return false
  const [nextRow, ...rest] = batchQueue.value
  batchQueue.value = rest
  await applyBatchRow(nextRow)
  return true
}

async function continueNextCoil({ silent = false } = {}) {
  justSubmitted.value = false
  clearLocalDraft(currentDraftKey.value)
  currentWorkOrder.value = null
  currentEntry.value = null
  currentStepKey.value = isOwnerOnlyMode.value ? 'core' : 'work_order'
  trackingCardNo.value = ''
  clearOcrState({ clearStorage: true })
  resetFormValues()
  entryCreateIdempotencyKey.value = buildClientUuid()
  if (batchQueue.value.length) {
    const [nextRow, ...rest] = batchQueue.value
    batchQueue.value = rest
    await applyBatchRow(nextRow)
    if (silent) return
    ElMessage.success('已切换到下一卷')
    return
  }
  ElMessage.success('已清空当前卷，机台与班次信息已保留')
}

function parseBatchRow(columns) {
  const fields = batchEditableFields.value
  const row = { tracking_card_no: normalizeTrackingCard(columns[0] || '') }
  fields.forEach((field, index) => {
    row[field.name] = columns[index + 1] ?? emptyFieldValue(field)
  })
  return row
}

async function applyBatchPaste() {
  const rawText = String(batchText.value || '').trim()
  if (!rawText) {
    ElMessage.warning('请先粘贴批量数据')
    return
  }
  const rows = rawText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => parseBatchRow(line.split('\t')))
    .filter((row) => row.tracking_card_no)

  if (!rows.length) {
    ElMessage.warning('没有识别到有效的批次号')
    return
  }

  const [firstRow, ...restRows] = rows
  batchQueue.value = restRows
  await applyBatchRow(firstRow)
  currentStepKey.value = 'core'
  ElMessage.success(`已载入 ${rows.length} 卷，当前队列剩余 ${restRows.length} 卷`)
}

function summarizeHistoryEntry(entry) {
  const fields = [...entryFields.value, ...shiftFields.value, ...extraFields.value, ...machineFields.value]
  return fields
    .map((field) => {
      const rawValue =
        field.target === 'entry'
          ? entry[field.name]
          : field.target === 'extra'
            ? entry.extra_payload?.[field.name]
            : entry[field.name]
      if (isEmptyValue(rawValue)) return null
      return {
        label: displayFieldLabel(field),
        value: formatFieldValueForDisplay(field, rawValue)
      }
    })
    .filter(Boolean)
    .slice(0, 6)
}

function goOcrCapture() {
  router.push({
    name: 'mobile-ocr-capture',
    params: {
      businessDate: formState.business_date || currentShift.business_date,
      shiftId: formState.shift_id || currentShift.shift_id
    }
  })
}

function handleScanClick() {
  if (template.value?.supports_ocr) {
    goOcrCapture()
    return
  }
  ElMessage.info('请使用扫码枪或手工录入批次号。')
}

async function loadPage() {
  loading.value = true
  loadError.value = null
  try {
    const shiftPayload = await fetchCurrentShift()
    Object.assign(currentShift, shiftPayload)
    formState.business_date = String(route.params.businessDate || shiftPayload.business_date || '')
    formState.shift_id = Number(route.params.shiftId || shiftPayload.shift_id || 0) || null
    formState.machine_id = shiftPayload.machine_id || null

    const templateKey = shiftPayload.workshop_code || shiftPayload.workshop_type
    if (!templateKey) {
      loadError.value = '未找到工序模板，请联系管理员配置车间模板。'
      return
    }

    const [templatePayload, equipmentPayload] = await Promise.all([
      fetchWorkshopTemplate(templateKey),
      fetchEquipment({ workshop_id: shiftPayload.workshop_id })
    ])
    template.value = templatePayload
    const activeEquipment = (equipmentPayload || []).filter((item) => item.is_active !== false)
    equipmentOptions.value = shiftPayload.is_machine_bound && shiftPayload.machine_id
      ? activeEquipment.filter((item) => Number(item.id) === Number(shiftPayload.machine_id))
      : activeEquipment
    initializeTemplateForm()
    currentStepKey.value = isOwnerOnlyMode.value ? 'core' : 'work_order'
    if (isOwnerOnlyMode.value) {
      await refreshWorkOrder()
    }
    loadOcrFromStorage()
    checkForRestorableDraft()
  } catch (err) {
    const status = err?.response?.status
    if (status === 404) {
      loadError.value = '未找到对应的工序模板，请联系管理员配置车间模板。'
    } else {
      loadError.value = '加载填报页面失败，请刷新重试。'
    }
  } finally {
    loading.value = false
  }
}

onMounted(loadPage)

onBeforeUnmount(() => {
  clearSubmitCooldownTimer()
})
</script>

<style scoped>
.mobile-shell--entry-form {
  --entry-card-gap: 11px;
  --entry-inline-gap: 8px;
}

.mobile-shell--entry-form .mobile-top h1 {
  margin-bottom: 0;
  letter-spacing: 0;
  font-family: var(--font-display, 'SF Pro Display', system-ui);
}

.mobile-shell--entry-form :deep(.panel.mobile-card .el-card__header) {
  padding: 12px 14px 0;
}

.mobile-shell--entry-form :deep(.panel.mobile-card .el-card__body) {
  padding: 12px 14px 14px;
}

.mobile-shell--entry-form :deep(.mobile-form-grid) {
  gap: 10px;
}

.mobile-shell--entry-form :deep(.mobile-field) {
  gap: 6px;
}

.mobile-shell--entry-form :deep(.mobile-field + .mobile-field) {
  margin-top: 2px;
}

.mobile-shell--entry-form :deep(.mobile-inline-actions) {
  gap: var(--entry-inline-gap);
  flex-wrap: wrap;
}

.mobile-shell--entry-form :deep(.mobile-dynamic-section + .mobile-dynamic-section) {
  margin-top: var(--entry-card-gap);
}

.mobile-shell--entry-form :deep(.mobile-section-title) {
  margin-bottom: 8px;
  letter-spacing: 0;
}

.mobile-shell--entry-form :deep(.mobile-actions) {
  gap: var(--entry-inline-gap);
}

.mobile-shell--entry-form :deep(.mobile-sticky-actions__buttons) {
  gap: var(--entry-inline-gap);
}

.mobile-shell--entry-form :deep(.mobile-sticky-actions__buttons .el-button) {
  min-width: 0;
  min-height: 48px;
  border-radius: 12px;
}

.mobile-shell--entry-form :deep(.mobile-sticky-actions__buttons .el-button--primary) {
  box-shadow: var(--xt-shadow-sm);
  transition: box-shadow var(--xt-motion-fast) var(--xt-ease);
}

.mobile-shell--entry-form :deep(.mobile-sticky-actions__buttons .el-button--primary:hover) {
  box-shadow: var(--xt-shadow-md);
}

.mobile-shell--entry-form :deep(.panel.mobile-card) {
  border-radius: 16px;
  box-shadow: var(--shadow-card);
}

.mobile-shell--entry-form :deep(.mobile-static-chip),
.mobile-shell--entry-form :deep(.mobile-summary-chip),
.mobile-shell--entry-form :deep(.mobile-history-item),
.mobile-shell--entry-form :deep(.mobile-inline-state) {
  border-radius: 14px;
}

.mobile-shell--entry-form :deep(.mobile-static-chip strong),
.mobile-shell--entry-form :deep(.mobile-summary-chip strong) {
  letter-spacing: 0;
  font-family: var(--font-number, 'SF Pro Display', 'DIN Alternate', system-ui);
}

.mobile-shell--entry-form :deep(.mobile-inline-actions .el-button),
.mobile-shell--entry-form :deep(.mobile-actions .el-button) {
  border-radius: 12px;
}

.entry-external-trace {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--xt-space-2);
}

.entry-external-trace span {
  min-width: 0;
  padding: 9px 10px;
  overflow: hidden;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  font-weight: 850;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-shell--entry-form :deep(.mobile-inline-actions .el-button:active),
.mobile-shell--entry-form :deep(.mobile-actions .el-button:active) {
  transform: translateY(0);
}

@media (max-width: 420px) {
  .mobile-shell--entry-form :deep(.panel.mobile-card .el-card__header) {
    padding: 10px 12px 0;
  }

  .mobile-shell--entry-form :deep(.panel.mobile-card .el-card__body) {
    padding: 10px 12px 12px;
  }

  .mobile-shell--entry-form :deep(.mobile-form-grid) {
    gap: 9px;
  }
}

.entry-role-badge {
  width: 10px;
  height: 10px;
  border-radius: var(--xt-radius-pill);
  flex-shrink: 0;
}

.mobile-top[style*="--role-color"] {
  border-left: 3px solid var(--role-color);
}
</style>
