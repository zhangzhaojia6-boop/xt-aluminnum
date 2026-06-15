import { existsSync, readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

function source(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8')
}

test('rag knowledge page has a manage route and navigation entry', () => {
  const router = source('../src/router/index.js')
  const navigation = source('../src/config/manage-navigation.js')

  assert.match(router, /const RagKnowledgePage = \(\) => import\('\.\.\/views\/manage\/rag\/RagKnowledgePage\.vue'\)/)
  assert.match(router, /path: 'rag'/)
  assert.match(router, /name: 'manage-rag'/)
  assert.match(router, /canonical: '\/manage\/rag'/)
  assert.match(navigation, /知识库资料/)
  assert.match(navigation, /\/manage\/rag/)
})

test('rag knowledge page uses real rag API helpers', () => {
  const apiPath = new URL('../src/api/rag.js', import.meta.url)
  const pagePath = new URL('../src/views/manage/rag/RagKnowledgePage.vue', import.meta.url)
  assert.equal(existsSync(apiPath), true)
  assert.equal(existsSync(pagePath), true)

  const api = source('../src/api/rag.js')
  const page = source('../src/views/manage/rag/RagKnowledgePage.vue')

  assert.match(api, /\/rag\/documents\/upload/)
  assert.match(api, /\/rag\/documents/)
  assert.match(api, /\/rag\/query/)
  assert.match(page, /data-testid="rag-knowledge-page"/)
  assert.match(page, /uploadRagDocument/)
  assert.match(page, /fetchRagDocuments/)
  assert.match(page, /fetchRagDocument/)
  assert.match(page, /deleteRagDocument/)
  assert.match(page, /queryRagKnowledge/)
})

test('rag knowledge page exposes upload chunks query and source areas without fake data', () => {
  const page = source('../src/views/manage/rag/RagKnowledgePage.vue')

  assert.match(page, /上传文本附件/)
  assert.match(page, /文档清单/)
  assert.match(page, /切片预览/)
  assert.match(page, /测试问答/)
  assert.match(page, /知识来源/)
  assert.match(page, /selectedDocument/)
  assert.match(page, /queryResult/)
  assert.match(page, /\.xt-rag__answer\s*\{[\s\S]*white-space:\s*pre-wrap/)
  assert.doesNotMatch(page, /假数据|示例产量|机器人头像|霓虹/)
})

test('rag knowledge page validates allowed text attachments before upload', () => {
  const page = source('../src/views/manage/rag/RagKnowledgePage.vue')

  assert.match(page, /ALLOWED_RAG_EXTENSIONS/)
  for (const extension of ['.txt', '.md', '.csv', '.json', '.log']) {
    assert.match(page, new RegExp(extension.replace('.', '\\.')))
  }
  assert.match(page, /isAllowedRagFile/)
  assert.match(page, /不支持该文件类型/)
  assert.match(page, /await uploadRagDocument\(file\)/)
})
