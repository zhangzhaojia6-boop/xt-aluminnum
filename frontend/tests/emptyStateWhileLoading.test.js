import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const PAGES = [
  'src/views/manage/admin/AgentManagementPage.vue',
  'src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue',
  'src/views/manage/rag/RagKnowledgePage.vue'
]

test('admin pages only claim an empty list after the first load finishes', () => {
  for (const file of PAGES) {
    const src = fs.readFileSync(path.resolve(file), 'utf8')
    const template = src.slice(src.indexOf('<template>'), src.lastIndexOf('</template>'))
    const unguarded = template.match(/v-(?:else-)?if="(?:sourceFiles|filteredSourceFiles|documents|agents|channels|evidence|events|operationApprovals|outbox|knowledgeEntries)\.length === 0"/g)
    assert.equal(unguarded, null, `${file}: ${unguarded}`)
  }
})
