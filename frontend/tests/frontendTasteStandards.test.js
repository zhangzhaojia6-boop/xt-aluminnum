import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const surfaces = [
  {
    name: '卷级线索',
    src: readFileSync(new URL('../src/views/manage/coils/CoilTracePage.vue', import.meta.url), 'utf8')
  },
  {
    name: 'PC 终端绑定',
    src: readFileSync(new URL('../src/views/master/MesTerminalBinding.vue', import.meta.url), 'utf8')
  },
  {
    name: '系统设置',
    src: readFileSync(new URL('../src/views/manage/admin/SystemSettingsPage.vue', import.meta.url), 'utf8')
  },
  {
    name: '实时调度墙',
    src: readFileSync(new URL('../src/views/manage/live/LiveDashboardPage.vue', import.meta.url), 'utf8')
  },
  {
    name: '生产流转总览',
    src: readFileSync(new URL('../src/views/manage/live/LiveProcessFlow.vue', import.meta.url), 'utf8')
  }
]

function cssDeclarations(src, property) {
  const re = new RegExp(`${property}\\s*:\\s*([^;]+);`, 'gi')
  return [...src.matchAll(re)].map((match) => match[1].trim())
}

function firstPx(value) {
  const match = value.match(/^(\d+(?:\.\d+)?)px\b/)
  return match ? Number(match[1]) : null
}

test('management pages avoid decorative side-stripe borders', () => {
  const offenders = []

  for (const surface of surfaces) {
    for (const property of ['border-left', 'border-right']) {
      for (const value of cssDeclarations(surface.src, property)) {
        const px = firstPx(value)
        if (px !== null && px > 1) {
          offenders.push(`${surface.name}: ${property}: ${value}`)
        }
      }
    }
  }

  assert.deepEqual(offenders, [])
})

test('management pages keep industrial surfaces restrained', () => {
  for (const surface of surfaces) {
    const largeRadii = cssDeclarations(surface.src, 'border-radius')
      .map(firstPx)
      .filter((px) => px !== null && px > 24 && px < 900)

    assert.deepEqual(largeRadii, [], `${surface.name} has oversized rounded corners`)
    assert.doesNotMatch(surface.src, /background-clip\s*:\s*text/i, `${surface.name} uses gradient text`)
    assert.doesNotMatch(surface.src, /text-shadow\s*:/i, `${surface.name} uses text shadow`)
  }
})

test('management pages with motion include reduced-motion fallback', () => {
  for (const surface of surfaces) {
    if (/(transition|animation)\s*:/.test(surface.src)) {
      assert.match(surface.src, /prefers-reduced-motion/, `${surface.name} needs reduced-motion fallback`)
    }
  }
})

test('realtime dispatch header uses functional Chinese cockpit copy', () => {
  const liveSurface = surfaces.find((surface) => surface.name === '实时调度墙')

  assert.ok(liveSurface)
  assert.doesNotMatch(liveSurface.src, /FINAL STAGE|MACHINE MATRIX|DATA CREDIT/)
  assert.match(liveSurface.src, /实时流转 \/ 机列矩阵 \/ 来源核验/)
})
