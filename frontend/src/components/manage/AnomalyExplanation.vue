<template>
  <section class="xt-anomaly-explanation" data-testid="anomaly-explanation" :aria-label="`${businessDate} 异常说明`">
    <div v-if="loading" class="xt-anomaly-explanation__skeleton" aria-hidden="true" />

    <template v-else-if="editing">
      <header class="xt-anomaly-explanation__head">
        <h2>{{ businessDate }} 异常说明</h2>
        <span v-if="savedText" class="xt-anomaly-explanation__meta" role="status">{{ savedText }}</span>
      </header>
      <textarea
        v-model="draft"
        class="xt-anomaly-explanation__input"
        :maxlength="MAX_LENGTH"
        rows="3"
        aria-label="异常说明"
        @input="dirty = true"
      />
      <div class="xt-anomaly-explanation__actions">
        <span v-if="draft.length >= COUNTER_FROM" class="xt-anomaly-explanation__meta">{{ draft.length }} / {{ MAX_LENGTH }}</span>
        <span v-if="errorText" class="xt-anomaly-explanation__error" role="alert">{{ errorText }}</span>
        <button v-if="record.content" type="button" class="xt-anomaly-explanation__ghost" :disabled="saving" @click="cancelEdit">取消</button>
        <button type="button" class="xt-anomaly-explanation__save" :disabled="saving || !draft.trim()" @click="save">
          {{ saving ? '保存中' : '保存' }}
        </button>
      </div>
    </template>

    <template v-else-if="record.content">
      <button
        type="button"
        class="xt-anomaly-explanation__summary"
        :aria-expanded="expanded"
        @click="expanded = !expanded"
      >
        <strong>{{ businessDate }} 异常说明</strong>
        <span class="xt-anomaly-explanation__text" :class="{ 'is-expanded': expanded }">{{ record.content }}</span>
        <span class="xt-anomaly-explanation__meta">{{ authorLine }}</span>
      </button>
      <button v-if="record.can_edit" type="button" class="xt-anomaly-explanation__ghost" @click="startEdit">修改</button>
    </template>

    <p v-else-if="!failed" class="xt-anomaly-explanation__empty">{{ businessDate }} 还没有异常说明</p>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { onBeforeRouteLeave } from 'vue-router'

import { fetchAnomalyNote, saveAnomalyNote } from '../../api/daily-anomaly-notes.js'

const props = defineProps({
  businessDate: { type: String, required: true },
})

const MAX_LENGTH = 2000
const COUNTER_FROM = 1800

const record = ref({ content: '', can_edit: false })
const loading = ref(false)
const failed = ref(false)
const saving = ref(false)
const editing = ref(false)
const expanded = ref(false)
const dirty = ref(false)
const draft = ref('')
const errorText = ref('')
const savedText = ref('')
// 切换日期时按日期保留草稿，回来还在
const drafts = new Map()

const authorLine = computed(() => {
  const parts = [record.value.author_name, record.value.updated_at && dayjs(record.value.updated_at).format('MM-DD HH:mm')]
  return parts.filter(Boolean).join(' · ')
})

function rememberDraft(date) {
  if (dirty.value) drafts.set(date, draft.value)
}

async function load(date) {
  loading.value = true
  failed.value = false
  errorText.value = ''
  savedText.value = ''
  expanded.value = false
  try {
    record.value = await fetchAnomalyNote(date)
  } catch {
    record.value = { content: '', can_edit: false }
    failed.value = true
  } finally {
    loading.value = false
  }
  const kept = drafts.get(date)
  dirty.value = kept !== undefined
  draft.value = kept ?? record.value.content
  editing.value = record.value.can_edit && (dirty.value || !record.value.content)
}

function startEdit() {
  draft.value = record.value.content
  editing.value = true
}

function cancelEdit() {
  drafts.delete(props.businessDate)
  dirty.value = false
  errorText.value = ''
  editing.value = false
}

async function save() {
  saving.value = true
  errorText.value = ''
  try {
    record.value = await saveAnomalyNote(props.businessDate, draft.value)
    drafts.delete(props.businessDate)
    dirty.value = false
    editing.value = false
    savedText.value = `已保存 · ${dayjs().format('HH:mm')}`
  } catch (error) {
    const status = error?.response?.status
    if (status === 403) {
      record.value = { ...record.value, can_edit: false }
      editing.value = false
    }
    errorText.value = status === 422 ? `需要 1 到 ${MAX_LENGTH} 字` : (status === 403 ? '没有修改权限' : '保存失败，内容已保留')
  } finally {
    saving.value = false
  }
}

function warnBeforeLeave(event) {
  if (!dirty.value && drafts.size === 0) return
  event.preventDefault()
  event.returnValue = ''
}

watch(() => props.businessDate, (next, previous) => {
  if (previous) rememberDraft(previous)
  load(next)
})

onMounted(() => {
  window.addEventListener('beforeunload', warnBeforeLeave)
  load(props.businessDate)
})

onBeforeUnmount(() => window.removeEventListener('beforeunload', warnBeforeLeave))

onBeforeRouteLeave(() => {
  if (!dirty.value && drafts.size === 0) return true
  return window.confirm('异常说明还没保存，确定离开？')
})
</script>

<style scoped>
.xt-anomaly-explanation {
  display: flex;
  flex-wrap: wrap;
  gap: var(--xt-space-2) var(--xt-space-4);
  align-items: baseline;
  padding: var(--xt-space-3) 0;
  border-top: 1px solid var(--xt-border);
  border-bottom: 1px solid var(--xt-border);
}

.xt-anomaly-explanation__skeleton {
  width: 100%;
  height: 20px;
  border-radius: 2px;
  background: var(--xt-border);
  opacity: 0.5;
}

.xt-anomaly-explanation__head,
.xt-anomaly-explanation__actions {
  display: flex;
  flex: 1 1 100%;
  gap: var(--xt-space-3);
  align-items: baseline;
}

.xt-anomaly-explanation__actions {
  justify-content: flex-end;
}

.xt-anomaly-explanation h2,
.xt-anomaly-explanation__summary strong {
  margin: 0;
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  font-weight: 600;
  white-space: nowrap;
}

.xt-anomaly-explanation__summary {
  display: flex;
  flex: 1 1 0;
  gap: var(--xt-space-3);
  align-items: baseline;
  min-width: 0;
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.xt-anomaly-explanation__text {
  flex: 1 1 0;
  min-width: 0;
  overflow: hidden;
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-anomaly-explanation__text.is-expanded {
  overflow: visible;
  white-space: pre-wrap;
}

.xt-anomaly-explanation__meta,
.xt-anomaly-explanation__empty {
  margin: 0;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  white-space: nowrap;
}

.xt-anomaly-explanation__error {
  color: var(--xt-danger);
  font-size: var(--xt-text-xs);
}

.xt-anomaly-explanation__input {
  flex: 1 1 100%;
  min-height: 72px;
  padding: var(--xt-space-2);
  border: 1px solid var(--xt-border);
  border-radius: 2px;
  color: var(--xt-text);
  font: inherit;
  font-size: var(--xt-text-sm);
  resize: vertical;
}

.xt-anomaly-explanation__input:focus-visible,
.xt-anomaly-explanation button:focus-visible {
  outline: 2px solid var(--xt-primary);
  outline-offset: 2px;
}

.xt-anomaly-explanation__save,
.xt-anomaly-explanation__ghost {
  min-height: 32px;
  padding: 0 var(--xt-space-4);
  border: 1px solid var(--xt-primary);
  border-radius: 2px;
  font-size: var(--xt-text-sm);
  cursor: pointer;
}

.xt-anomaly-explanation__save {
  background: var(--xt-primary);
  color: var(--xt-text-inverse);
}

.xt-anomaly-explanation__ghost {
  background: transparent;
  color: var(--xt-primary);
}

.xt-anomaly-explanation__save:disabled,
.xt-anomaly-explanation__ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
