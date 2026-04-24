const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const outDir = path.resolve('tmp', 'visual-audit');
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const owner = await browser.newContext({ baseURL: 'http://127.0.0.1:5173', viewport: { width: 430, height: 932 } });
  const page = await owner.newPage();
  await page.goto('/login');
  await page.getByTestId('login-username').fill(process.env.PLAYWRIGHT_OWNER_USERNAME || 'CPK-A-INV');
  await page.getByTestId('login-password').fill(process.env.PLAYWRIGHT_OWNER_PASSWORD || '506371');
  await page.getByTestId('login-submit').click();
  await page.waitForURL(/\/mobile$/);
  await page.waitForTimeout(8000);

  const btn = page.getByTestId('mobile-go-report');
  const count = await btn.count();
  console.log('mobile-go-report count:', count);
  await page.screenshot({ path: path.join(outDir, 'mobile-owner-home-waited.png'), fullPage: true });

  if (count > 0) {
    await btn.click();
    await page.waitForTimeout(2000);
    console.log('url after click:', page.url());
    await page.screenshot({ path: path.join(outDir, 'mobile-owner-entry-form.png'), fullPage: true });
  }

  await owner.close();
  await browser.close();
})();
