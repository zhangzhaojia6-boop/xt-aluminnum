const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const outDir = path.resolve('tmp', 'visual-audit');
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({ headless: true });

  const admin = await browser.newContext({ baseURL: 'http://127.0.0.1:5173', viewport: { width: 1512, height: 982 } });
  const ap = await admin.newPage();
  await ap.goto('/login');
  await ap.getByTestId('login-username').fill('admin');
  await ap.getByTestId('login-password').fill(process.env.PLAYWRIGHT_ADMIN_PASSWORD || process.env.PLAYWRIGHT_PASSWORD || process.env.INIT_ADMIN_PASSWORD || 'Admin#Gate2026_Strong');
  await ap.getByTestId('login-submit').click();
  await ap.waitForURL(/\/review\/factory/);
  await ap.goto('/master/workshop-template');
  await ap.waitForTimeout(1200);
  await ap.screenshot({ path: path.join(outDir, 'workshop-template-desktop.png'), fullPage: true });
  await admin.close();

  const owner = await browser.newContext({ baseURL: 'http://127.0.0.1:5173', viewport: { width: 430, height: 932 } });
  const op = await owner.newPage();
  await op.goto('/login');
  await op.getByTestId('login-username').fill(process.env.PLAYWRIGHT_OWNER_USERNAME || 'CPK-A-INV');
  await op.getByTestId('login-password').fill(process.env.PLAYWRIGHT_OWNER_PASSWORD || '506371');
  await op.getByTestId('login-submit').click();
  await op.waitForURL(/\/mobile$/);
  await op.waitForTimeout(600);
  await op.screenshot({ path: path.join(outDir, 'mobile-owner-home.png'), fullPage: true });

  const reportBtn = op.getByTestId('mobile-go-report');
  if (await reportBtn.count()) {
    await reportBtn.click();
    await op.waitForURL(/\/mobile\/report-advanced\//);
    await op.waitForTimeout(1200);
    await op.screenshot({ path: path.join(outDir, 'mobile-owner-entry-form.png'), fullPage: true });
  }

  await owner.close();
  await browser.close();
})();
