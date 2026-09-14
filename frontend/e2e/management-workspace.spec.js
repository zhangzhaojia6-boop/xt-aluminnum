import { test, expect } from '@playwright/test'
import { setupReviewSessionAndMocks } from './helpers/review-mocks'
import fs from 'node:fs'

test('assistant failure is visible and never replaced by a legacy echo', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  let legacyCalls = 0
  await page.route('**/api/v1/ai/assistant/conversations', route => route.fulfill({
    json: route.request().method() === 'POST' ? { id: 'failed-chat' } : [],
  }))
  await page.route('**/api/v1/ai/assistant/conversations/*/messages', route => route.fulfill({
    status: 503, json: { detail: '证据读取暂时不可用' },
  }))
  await page.route('**/api/v1/ai/chat', route => {
    legacyCalls++
    return route.fulfill({ contentType: 'text/event-stream', body: 'data: {"type":"text","content":"收到：核查日报"}\n\n' })
  })
  await page.goto('/manage/today')
  await expect(page.getByTestId('manage-today')).toBeVisible()
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('xt:open-ai-assistant', {
    detail: { question: '核查日报', scope: { type: 'route', key: '/manage/today' } },
  })))
  const drawer = page.getByTestId('ai-assistant-drawer')
  await expect(drawer).toContainText('生成失败，请稍后重试')
  await expect(drawer).not.toContainText('收到：核查日报')
  expect(legacyCalls).toBe(0)
  await expect(drawer.locator('textarea')).toBeEnabled()
})

test('stopping an assistant answer cancels its pending request', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  await page.route('**/api/v1/ai/runtime', route => route.fulfill({ json: { llm_configured: false } }))
  const pending = []
  let aborted = 0
  page.on('requestfailed', request => {
    if (request.url().includes('/ai/assistant/conversations/') && request.url().endsWith('/messages')) aborted++
  })
  await page.route('**/api/v1/ai/assistant/conversations', route => route.fulfill({
    json: route.request().method() === 'POST' ? { id: 'stopped-chat' } : [],
  }))
  await page.route('**/api/v1/ai/assistant/conversations/*/messages', route => {
    if (route.request().method() === 'POST') pending.push(route)
    else return route.fulfill({ json: [] })
  })
  await page.goto('/manage/ai-assistant')
  const workstation = page.getByTestId('ai-workstation-page')
  await expect(workstation).toBeVisible()
  await workstation.locator('textarea').fill('核查生产异常')
  await workstation.getByRole('button', { name: '发送', exact: true }).click()
  await expect.poll(() => pending.length).toBe(1)
  await workstation.getByRole('button', { name: '停止', exact: true }).click()
  await expect.poll(() => aborted).toBe(1)
  await expect(workstation).toContainText('已停止')
})

test('a contextual question is sent once when the assistant first loads', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  const sent = []
  await page.route('**/api/v1/ai/assistant/conversations', async (route) => {
    await route.fulfill({ json: route.request().method() === 'POST' ? { id: 'workspace-chat' } : [] })
  })
  await page.route('**/api/v1/ai/assistant/conversations/*/messages', async (route) => {
    if (route.request().method() === 'POST') sent.push(route.request().postDataJSON())
    await route.fulfill({ json: { answer: { answer: '已收到核查请求' } } })
  })
  await page.goto('/manage/today')
  await expect(page.getByTestId('manage-today')).toBeVisible()
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('xt:open-ai-assistant', {
    detail: { question: '核查昨日缺报', scope: { type: 'route', key: '/manage/today' } },
  })))
  await expect(page.getByTestId('ai-assistant-drawer')).toBeVisible()
  await expect.poll(() => sent.length).toBe(1)
  expect(sent[0].content).toBe('核查昨日缺报')
  await expect(page.getByTestId('ai-assistant-drawer')).toContainText('已收到核查请求')
  await page.getByRole('button', { name: '关闭 AI 助手' }).click()
  await page.locator('.xt-manage__assistant-trigger').click()
  await expect(page.getByTestId('ai-assistant-drawer')).toBeVisible()
  expect(sent).toHaveLength(1)
})

test('management workspace remains usable across desktop and narrow screens', async ({ page }, testInfo) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await setupReviewSessionAndMocks(page)
  await page.goto('/manage/today?target_date=2026-05-22')
  await expect(page.getByTestId('manage-today')).toBeVisible()
  await expect(page.getByTestId('manage-kpi-bar')).toContainText('234.6')
  for (const width of [1440, 1280, 390]) {
    await page.setViewportSize({ width, height: 960 })
    await page.screenshot({ path: testInfo.outputPath(`workspace-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  }
  if (process.env.DESIGN_PRETEXT_PATH) {
    await page.setViewportSize({ width: 1440, height: 960 })
    const preview = await page.evaluate(() => {
      const css = [...document.styleSheets].map(sheet => [...sheet.cssRules].map(rule => rule.cssText).join('\n')).join('\n')
      const app = document.querySelector('#app').cloneNode(true)
      return { css, html: app.outerHTML }
    })
    const pretext = fs.readFileSync(process.env.DESIGN_PRETEXT_PATH, 'utf8')
    const layoutCode = `await document.fonts.ready;
      document.querySelectorAll('.xt-today__event-card p').forEach(el => {
        el.contentEditable = 'true';
        const measure = () => {
          const font = getComputedStyle(el).font;
          el.style.minHeight = layout(prepare(el.textContent, font), el.clientWidth, 20).height + 'px';
        };
        new ResizeObserver(measure).observe(el);
        el.addEventListener('input', measure);
      });`
    const moduleCode = pretext.replace(/export\{[^}]+\};?\s*$/, 'const prepare = X1, layout = Z1;')
    fs.mkdirSync('.tmp/design', { recursive: true })
    fs.writeFileSync('.tmp/design/finalized.html', `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>管理工作台 · 设计预览</title><style>${preview.css}</style></head><body>${preview.html}<script type="module">${moduleCode}\n${layoutCode}</script></body></html>`)
  }
  await page.setViewportSize({ width: 390, height: 960 })
  await page.getByRole('button', { name: '打开导航', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '管理端移动导航' })).toBeVisible()
  await page.getByRole('button', { name: '关闭导航', exact: true }).click()
  await page.setViewportSize({ width: 1440, height: 960 })
  await page.locator('.xt-today__below-fold').scrollIntoViewIfNeeded()
  await expect(page.locator('.xt-today__below-fold canvas').first()).toBeVisible()
  expect(errors).toEqual([])
})

test('daily results render before a delayed management summary', async ({ page }, testInfo) => {
  await setupReviewSessionAndMocks(page)
  await page.route('**/api/v1/dashboard/factory-director**', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 3500))
    await route.fallback()
  })
  const started = Date.now()
  await page.goto('/manage/today?target_date=2026-05-22')
  await expect(page.getByTestId('manage-kpi-bar')).toContainText('234.6', { timeout: 10000 })
  const elapsed = Date.now() - started
  await testInfo.attach('daily-first-visible-ms', { body: String(elapsed), contentType: 'text/plain' })
  console.log(`DAILY_FIRST_VISIBLE_MS=${elapsed}`)
  if (process.env.DASHBOARD_BASELINE !== '1') expect(elapsed).toBeLessThan(3500)
})
