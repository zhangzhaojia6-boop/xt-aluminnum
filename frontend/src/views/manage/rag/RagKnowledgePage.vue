<template>
  <section class="xt-rag" data-testid="rag-knowledge-page" data-visual-pass="stitch-industrial-rag">
    <header class="xt-rag__hero">
      <div>
        <span>文本附件入库</span>
        <h1>知识库资料</h1>
      </div>
      <div class="xt-rag__actions">
        <input ref="fileInput" type="file" accept=".txt,.md,.csv,.json,.log" @change="handleFilePicked" />
        <button type="button" :disabled="uploading" @click="openFilePicker">
          {{ uploading ? '上传中' : '上传文本附件' }}
        </button>
      </div>
    </header>

    <div v-if="loading" class="xt-rag__state">数据加载中</div>
    <div v-else-if="errorText" class="xt-rag__state is-error">
      <span>{{ errorText }}</span>
      <button type="button" @click="loadDocuments">重试</button>
    </div>

    <section class="xt-rag__metrics" aria-label="知识库指标">
      <article v-for="card in metricCards" :key="card.key">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.meta }}</small>
      </article>
    </section>

    <section class="xt-rag__grid">
      <article class="xt-rag__panel is-wide">
        <header>
          <h2>文档清单</h2>
          <span>{{ documents.length }} 份</span>
        </header>
        <div v-if="documents.length === 0" class="xt-rag__empty">暂无资料</div>
        <div v-else class="xt-rag__table-wrap">
          <table>
            <thead>
              <tr>
                <th>文件名</th>
                <th>编码</th>
                <th>切片数</th>
                <th>上传时间</th>
                <th>状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in documents" :key="item.id" :class="{ 'is-selected': selectedDocument?.id === item.id }">
                <td>
                  <button type="button" class="xt-rag__link" @click="selectDocument(item.id)">{{ item.filename }}</button>
                  <small>{{ formatBytes(item.file_size) }}</small>
                </td>
                <td>{{ item.encoding || '-' }}</td>
                <td>{{ displayNumber(item.chunk_count) }}</td>
                <td>{{ formatTime(item.created_at) }}</td>
                <td>
                  <span class="xt-rag__tag" :class="{ 'is-muted': item.status !== 'active' }">
                    <i></i>{{ item.status === 'active' ? '可检索' : '停用' }}
                  </span>
                </td>
                <td>
                  <button type="button" class="xt-rag__ghost" @click="selectDocument(item.id)">查看</button>
                  <button type="button" class="xt-rag__danger" @click="removeDocument(item.id)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="xt-rag__panel">
        <header>
          <h2>切片预览</h2>
          <span>{{ chunks.length }} 段</span>
        </header>
        <div v-if="!selectedDocument" class="xt-rag__empty">请选择文档</div>
        <div v-else class="xt-rag__detail">
          <b>{{ selectedDocument.filename }}</b>
          <span>{{ selectedDocument.encoding }} / {{ displayNumber(selectedDocument.chunk_count) }} 段</span>
        </div>
        <ol v-if="chunks.length > 0" class="xt-rag__chunks">
          <li v-for="chunk in chunks.slice(0, 6)" :key="chunk.id">
            <span>#{{ chunk.chunk_index + 1 }} {{ chunk.source_ref }}</span>
            <p>{{ chunk.content }}</p>
          </li>
        </ol>
      </article>

      <article class="xt-rag__panel is-query">
        <header>
          <h2>测试问答</h2>
          <span>{{ queryRunning ? '检索中' : '文本检索' }}</span>
        </header>
        <textarea v-model="queryText" rows="4" placeholder="输入问题"></textarea>
        <button type="button" :disabled="queryRunning" @click="runQuery">
          {{ queryRunning ? '查询中' : '开始查询' }}
        </button>
      </article>

      <article class="xt-rag__panel is-wide">
        <header>
          <h2>回答生成区</h2>
          <span>{{ citations.length }} 条来源</span>
        </header>
        <div v-if="!queryResult" class="xt-rag__empty">暂无查询</div>
        <div v-else class="xt-rag__answer">{{ queryResult.answer }}</div>
        <div class="xt-rag__sources">
          <h3>知识来源</h3>
          <div v-if="citations.length === 0" class="xt-rag__empty is-compact">暂无来源</div>
          <ol v-else>
            <li v-for="item in citations" :key="`${item.document_id}-${item.chunk_index}`">
              <b>{{ item.filename }}</b>
              <span>{{ item.source_ref }}</span>
            </li>
          </ol>
        </div>
      </article>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import {
  deleteRagDocument,
  fetchRagDocument,
  fetchRagDocuments,
  queryRagKnowledge,
  uploadRagDocument
} from '../../../api/rag.js'
import { formatApiErrorMessage } from '../../../api/index.js'

const loading = ref(false)
const uploading = ref(false)
const queryRunning = ref(false)
const errorText = ref('')
const documents = ref([])
const selectedDocument = ref(null)
const chunks = ref([])
const queryText = ref('')
const queryResult = ref(null)
const fileInput = ref(null)

const totalChunks = computed(() => documents.value.reduce((total, item) => total + Number(item.chunk_count || 0), 0))
const citations = computed(() => queryResult.value?.citations || [])

const metricCards = computed(() => [
  { key: 'documents', label: '文档总数', value: displayNumber(documents.value.length), meta: '已入库资料' },
  { key: 'chunks', label: '知识切片', value: displayNumber(totalChunks.value), meta: '文本检索范围' },
  { key: 'query', label: '最近查询', value: queryResult.value ? displayNumber(citations.value.length) : '—', meta: '来源命中' },
  { key: 'engine', label: '检索状态', value: loading.value ? '读取中' : '就绪', meta: '数据库文本检索' }
])

function displayNumber(value) {
  const number = Number(value || 0)
  return Number.isFinite(number) ? number.toLocaleString('zh-CN') : '0'
}

function formatBytes(value) {
  const number = Number(value || 0)
  if (number >= 1024 * 1024) return `${(number / 1024 / 1024).toFixed(1)} MB`
  if (number >= 1024) return `${(number / 1024).toFixed(1)} KB`
  return `${number} B`
}

function formatTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', { hour12: false })
}

function openFilePicker() {
  fileInput.value?.click()
}

async function loadDocuments() {
  loading.value = true
  errorText.value = ''
  try {
    const payload = await fetchRagDocuments()
    documents.value = payload.items || []
    if (!selectedDocument.value && documents.value.length > 0) {
      await selectDocument(documents.value[0].id)
    }
    if (selectedDocument.value && !documents.value.some((item) => item.id === selectedDocument.value.id)) {
      selectedDocument.value = null
      chunks.value = []
    }
  } catch (error) {
    errorText.value = formatApiErrorMessage(error)
  } finally {
    loading.value = false
  }
}

async function selectDocument(documentId) {
  errorText.value = ''
  try {
    const payload = await fetchRagDocument(documentId)
    selectedDocument.value = payload.document
    chunks.value = payload.chunks || []
  } catch (error) {
    errorText.value = formatApiErrorMessage(error)
  }
}

async function handleFilePicked(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  uploading.value = true
  errorText.value = ''
  try {
    const uploaded = await uploadRagDocument(file)
    await loadDocuments()
    await selectDocument(uploaded.id)
  } catch (error) {
    errorText.value = formatApiErrorMessage(error)
  } finally {
    uploading.value = false
  }
}

async function removeDocument(documentId) {
  errorText.value = ''
  try {
    await deleteRagDocument(documentId)
    if (selectedDocument.value?.id === documentId) {
      selectedDocument.value = null
      chunks.value = []
    }
    await loadDocuments()
  } catch (error) {
    errorText.value = formatApiErrorMessage(error)
  }
}

async function runQuery() {
  if (!queryText.value.trim()) {
    errorText.value = '请输入问题'
    return
  }
  queryRunning.value = true
  errorText.value = ''
  try {
    queryResult.value = await queryRagKnowledge({ query: queryText.value.trim(), limit: 5 })
  } catch (error) {
    errorText.value = formatApiErrorMessage(error)
  } finally {
    queryRunning.value = false
  }
}

onMounted(loadDocuments)
</script>

<style scoped>
.xt-rag {
  --rag-bg: #131314;
  --rag-panel: #1f1f20;
  --rag-panel-high: #2a2a2b;
  --rag-border: rgba(184, 134, 11, 0.34);
  --rag-gold: #d3a646;
  --rag-text: #eee9de;
  --rag-muted: #bfb39f;
  --rag-red: #8b1e1e;
  display: grid;
  gap: var(--xt-space-4);
  min-height: calc(100vh - var(--xt-topbar-height) - var(--xt-space-10));
  color: var(--rag-text);
}

.xt-rag__hero,
.xt-rag__metrics article,
.xt-rag__panel,
.xt-rag__state {
  border: 1px solid var(--rag-border);
  border-radius: 0;
  background:
    linear-gradient(180deg, rgba(184, 134, 11, 0.09), transparent 34%),
    linear-gradient(135deg, rgba(31, 31, 32, 0.98), rgba(19, 19, 20, 0.98));
  box-shadow: inset 0 1px 0 rgba(238, 233, 222, 0.06);
}

.xt-rag__hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--xt-space-4);
  min-height: 128px;
  padding: var(--xt-space-5);
}

.xt-rag__hero span,
.xt-rag__panel header span,
.xt-rag__metrics span {
  color: var(--rag-gold);
  font-size: var(--xt-text-xs);
  font-weight: 900;
  letter-spacing: 0.14em;
}

.xt-rag__hero h1 {
  margin: var(--xt-space-2) 0 0;
  color: var(--rag-text);
  font-family: "Noto Serif SC", "Songti SC", serif;
  font-size: clamp(2rem, 4vw, 3.2rem);
  letter-spacing: 0.08em;
}

.xt-rag__actions {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
}

.xt-rag__actions input {
  display: none;
}

.xt-rag button {
  border: 1px solid rgba(211, 166, 70, 0.72);
  background: linear-gradient(180deg, #d4a84c, #a87510);
  color: #241800;
  cursor: pointer;
  font-weight: 900;
  padding: 0.74rem 1rem;
}

.xt-rag button:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.xt-rag__ghost,
.xt-rag__danger,
.xt-rag__link {
  background: transparent !important;
  color: var(--rag-text) !important;
}

.xt-rag__danger {
  border-color: rgba(139, 30, 30, 0.72) !important;
}

.xt-rag__link {
  border: 0 !important;
  padding: 0 !important;
  text-align: left;
}

.xt-rag__state {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding: var(--xt-space-4);
}

.xt-rag__state.is-error {
  border-color: rgba(139, 30, 30, 0.72);
}

.xt-rag__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--xt-space-3);
}

.xt-rag__metrics article {
  display: grid;
  gap: var(--xt-space-2);
  min-height: 118px;
  padding: var(--xt-space-4);
}

.xt-rag__metrics strong {
  font-family: "DIN Alternate", "Arial Narrow", sans-serif;
  font-size: clamp(2rem, 3.6vw, 3rem);
}

.xt-rag__metrics small,
.xt-rag__detail span,
.xt-rag td small,
.xt-rag__chunks span,
.xt-rag__sources span {
  color: var(--rag-muted);
}

.xt-rag__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(360px, 0.8fr);
  gap: var(--xt-space-3);
}

.xt-rag__panel {
  display: grid;
  align-content: start;
  gap: var(--xt-space-3);
  min-width: 0;
  padding: var(--xt-space-4);
}

.xt-rag__panel.is-wide {
  grid-column: span 1;
}

.xt-rag__panel.is-query {
  grid-column: 1 / -1;
}

.xt-rag__panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  border-bottom: 1px solid rgba(184, 134, 11, 0.2);
  padding-bottom: var(--xt-space-2);
}

.xt-rag__panel h2,
.xt-rag__sources h3 {
  margin: 0;
  font-family: "Noto Serif SC", "Songti SC", serif;
  letter-spacing: 0.06em;
}

.xt-rag__empty {
  border: 1px dashed rgba(184, 134, 11, 0.28);
  color: var(--rag-muted);
  padding: var(--xt-space-4);
  text-align: center;
}

.xt-rag__empty.is-compact {
  padding: var(--xt-space-2);
}

.xt-rag__table-wrap {
  overflow-x: auto;
}

.xt-rag table {
  width: 100%;
  border-collapse: collapse;
}

.xt-rag th,
.xt-rag td {
  border-bottom: 1px solid rgba(184, 134, 11, 0.17);
  padding: 0.78rem;
  text-align: left;
  vertical-align: top;
}

.xt-rag th {
  color: var(--rag-muted);
  font-size: var(--xt-text-xs);
  letter-spacing: 0.08em;
}

.xt-rag tr.is-selected td {
  background: rgba(184, 134, 11, 0.08);
}

.xt-rag__tag {
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-1);
  color: var(--rag-gold);
  font-weight: 900;
}

.xt-rag__tag i {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--rag-gold);
}

.xt-rag__tag.is-muted {
  color: #e1a6a6;
}

.xt-rag__tag.is-muted i {
  background: var(--rag-red);
}

.xt-rag__detail {
  display: grid;
  gap: var(--xt-space-1);
  border: 1px solid rgba(184, 134, 11, 0.24);
  background: rgba(0, 0, 0, 0.18);
  padding: var(--xt-space-3);
}

.xt-rag__chunks,
.xt-rag__sources ol {
  display: grid;
  gap: var(--xt-space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.xt-rag__chunks li,
.xt-rag__sources li {
  border: 1px solid rgba(184, 134, 11, 0.18);
  background: rgba(0, 0, 0, 0.16);
  padding: var(--xt-space-3);
}

.xt-rag__chunks p,
.xt-rag__answer {
  margin: var(--xt-space-2) 0 0;
  color: var(--rag-text);
  line-height: 1.75;
}

.xt-rag textarea {
  width: 100%;
  border: 1px solid rgba(184, 134, 11, 0.34);
  border-radius: 0;
  background: #101011;
  color: var(--rag-text);
  line-height: 1.7;
  padding: var(--xt-space-3);
  resize: vertical;
}

.xt-rag textarea:focus {
  border-color: var(--rag-gold);
  outline: none;
}

.xt-rag__answer {
  min-height: 92px;
  border: 1px solid rgba(184, 134, 11, 0.24);
  background: rgba(0, 0, 0, 0.16);
  padding: var(--xt-space-4);
  white-space: pre-wrap;
}

.xt-rag__sources {
  display: grid;
  gap: var(--xt-space-2);
}

@media (max-width: 1180px) {
  .xt-rag__metrics,
  .xt-rag__grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 760px) {
  .xt-rag__hero {
    align-items: stretch;
    flex-direction: column;
  }

  .xt-rag__metrics,
  .xt-rag__grid {
    grid-template-columns: 1fr;
  }

  .xt-rag__panel.is-query {
    grid-column: auto;
  }
}
</style>
