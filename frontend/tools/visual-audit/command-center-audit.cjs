const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const repoRoot = path.resolve(__dirname, '..', '..', '..');
const referenceManifestPath = path.join(repoRoot, 'docs', 'ui-reference', 'REFERENCE_MANIFEST.md');
const targetReferenceImageDir = path.join(repoRoot, 'docs', 'ui-reference', 'highres');
const expectedReferenceImages = [
  '01-overview.png',
  '02-login.png',
  '03-entry-home.png',
  '04-entry-flow.png',
  '05-factory-board.png',
  '06-ingestion-mapping.png',
  '07-review-tasks.png',
  '08-reports-delivery.png',
  '09-quality-alerts.png',
  '10-cost-benefit.png',
  '11-ai-control.png',
  '12-ops-observability.png',
  '13-governance.png',
  '14-master-template.png',
  '15-entry-responsive.png',
];
const targetReferenceImage = process.env.REFERENCE_UI_TARGET_IMAGE
  ? path.resolve(process.cwd(), process.env.REFERENCE_UI_TARGET_IMAGE)
  : path.join(targetReferenceImageDir, expectedReferenceImages[0]);
const targetAlignmentSpec = {
  expectedPanelCount: expectedReferenceImages.length,
};

const referencePanelChecks = [
  { moduleNumber: '01', targetPanel: '01-overview', referenceImage: '01-overview.png', screenshot: '01-overview.png', label: '01 target panel maps to system overview' },
  { moduleNumber: '02', targetPanel: '02-login', referenceImage: '02-login.png', screenshot: '02-login.png', label: '02 target panel maps to login handoff' },
  { moduleNumber: '03', targetPanel: '03-entry-home', referenceImage: '03-entry-home.png', screenshot: '03-entry-home.png', label: '03 target panel maps to entry home' },
  { moduleNumber: '04', targetPanel: '04-entry-flow', referenceImage: '04-entry-flow.png', screenshot: '04-entry-flow.png', label: '04 target panel maps to entry flow' },
  { moduleNumber: '05', targetPanel: '05-factory-board', referenceImage: '05-factory-board.png', screenshot: '05-factory-board.png', label: '05 target panel maps to factory board' },
  { moduleNumber: '06', targetPanel: '06-ingestion-mapping', referenceImage: '06-ingestion-mapping.png', screenshot: '06-ingestion-mapping.png', label: '06 target panel maps to ingestion center' },
  { moduleNumber: '07', targetPanel: '07-review-tasks', referenceImage: '07-review-tasks.png', screenshot: '07-review-tasks.png', label: '07 target panel maps to review center' },
  { moduleNumber: '08', targetPanel: '08-reports-delivery', referenceImage: '08-reports-delivery.png', screenshot: '08-reports-delivery.png', label: '08 target panel maps to reports center' },
  { moduleNumber: '09', targetPanel: '09-quality-alerts', referenceImage: '09-quality-alerts.png', screenshot: '09-quality-alerts.png', label: '09 target panel maps to quality alerts' },
  { moduleNumber: '10', targetPanel: '10-cost-benefit', referenceImage: '10-cost-benefit.png', screenshot: '10-cost-benefit.png', label: '10 target panel maps to cost center' },
  { moduleNumber: '11', targetPanel: '11-ai-control', referenceImage: '11-ai-control.png', screenshot: '11-ai-control.png', label: '11 target panel maps to AI control' },
  { moduleNumber: '12', targetPanel: '12-ops-observability', referenceImage: '12-ops-observability.png', screenshot: '12-ops-observability.png', label: '12 target panel maps to ops reliability' },
  { moduleNumber: '13', targetPanel: '13-governance', referenceImage: '13-governance.png', screenshot: '13-governance.png', label: '13 target panel maps to governance' },
  { moduleNumber: '14', targetPanel: '14-master-template', referenceImage: '14-master-template.png', screenshot: '14-master-template.png', label: '14 target panel maps to master data' },
  { moduleNumber: '15', targetPanel: '15-entry-responsive', referenceImage: '15-entry-responsive.png', screenshot: '15-entry-responsive.png', label: '15 target panel maps to responsive entry' },
];

function readPngSize(filePath) {
  if (!fs.existsSync(filePath)) return null;
  const buffer = fs.readFileSync(filePath);
  if (buffer.length < 24 || buffer.toString('ascii', 1, 4) !== 'PNG') return null;
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20),
  };
}

function addTargetImageChecks(report) {
  const imageMeta = expectedReferenceImages.map((filename) => {
    const filePath = path.join(targetReferenceImageDir, filename);
    return {
      filename,
      exists: fs.existsSync(filePath),
      size: readPngSize(filePath),
    };
  });
  const existingCount = imageMeta.filter((item) => item.exists).length;
  const meta = {
    referenceImageDir: path.relative(repoRoot, targetReferenceImageDir),
    referenceManifest: path.relative(repoRoot, referenceManifestPath),
    targetReferenceImage: path.relative(repoRoot, targetReferenceImage),
    exists: fs.existsSync(targetReferenceImage),
    manifestExists: fs.existsSync(referenceManifestPath),
    expectedPanelCount: targetAlignmentSpec.expectedPanelCount,
    actualPanelCount: existingCount,
    images: imageMeta,
  };
  report.targetImageMeta = meta;
  const ok = meta.manifestExists && existingCount === targetAlignmentSpec.expectedPanelCount && meta.exists;
  report.checks.push({
    route: 'target-reference-image',
    kind: 'target_image_meta',
    label: 'highres target reference images and manifest are readable',
    expected: `${targetAlignmentSpec.expectedPanelCount} highres panels + manifest`,
    actual: `${existingCount} highres panels, manifest=${meta.manifestExists}`,
    status: ok ? 'pass' : 'fail',
    error: ok ? '' : 'docs/ui-reference highres baseline is incomplete',
  });
}

function addReferencePanelChecks(report, outDir) {
  report.referencePanelChecks = referencePanelChecks;
  for (const item of referencePanelChecks) {
    const screenshotPath = path.join(outDir, item.screenshot);
    const referencePath = path.join(targetReferenceImageDir, item.referenceImage);
    const exists = fs.existsSync(screenshotPath);
    const referenceExists = fs.existsSync(referencePath);
    const checklistItem = referenceChecklist.find((candidate) => candidate.moduleNumber === item.moduleNumber);
    const ok = exists && referenceExists && Boolean(checklistItem);
    report.checks.push({
      route: checklistItem?.route || item.targetPanel,
      kind: 'reference_panel_alignment',
      moduleNumber: item.moduleNumber,
      targetPanel: item.targetPanel,
      referenceImage: item.referenceImage,
      screenshot: item.screenshot,
      label: item.label,
      status: ok ? 'pass' : 'fail',
      error: ok ? '' : `missing screenshot, highres image, or checklist mapping for module ${item.moduleNumber}`,
    });
  }
}

async function loginWithPassword(page) {
  await page.goto('/login');
  await page.getByTestId('login-username').fill(process.env.PLAYWRIGHT_ADMIN_USERNAME || 'admin');
  await page
    .getByTestId('login-password')
    .fill(
      process.env.PLAYWRIGHT_ADMIN_PASSWORD ||
        process.env.PLAYWRIGHT_PASSWORD ||
        process.env.INIT_ADMIN_PASSWORD ||
        'Admin#Gate2026_Strong',
    );
  const [response] = await Promise.all([
    page.waitForResponse((item) =>
      item.url().includes('/auth/login') &&
      item.request().method() === 'POST'
    ),
    page.getByTestId('login-submit').click(),
  ]);
  if (!response.ok()) {
    throw new Error(`login failed with status ${response.status()}`);
  }
  await page.waitForURL(/\/(admin|review|entry)/, { timeout: 10000 });
}

async function ensureVisible(page, report, route, selector, label) {
  const item = { route, kind: 'visible', selector, label, status: 'pass', error: '' };
  try {
    await page.waitForSelector(selector, { timeout: 10000, state: 'visible' });
  } catch (error) {
    item.status = 'fail';
    item.error = String(error?.message || error || 'unknown error');
  }
  report.checks.push(item);
}

async function ensureCountAtLeast(page, report, route, selector, minCount, label) {
  const count = await page.locator(selector).count();
  report.checks.push({
    route,
    kind: 'count_at_least',
    selector,
    label,
    expected: minCount,
    actual: count,
    status: count >= minCount ? 'pass' : 'fail',
    error: count >= minCount ? '' : `${label} count=${count}, expected>=${minCount}`,
  });
}

async function ensureTextAbsent(page, report, route, text, label) {
  const count = await page.getByText(text, { exact: false }).count();
  report.checks.push({
    route,
    kind: 'text_absent',
    text,
    label,
    expected: 0,
    actual: count,
    status: count === 0 ? 'pass' : 'fail',
    error: count === 0 ? '' : `${label} found ${count} occurrence(s) of "${text}"`,
  });
}

async function ensureEnglishSubtitleAbsent(page, report, route) {
  const bodyText = await page.locator('body').innerText().catch(() => '');
  const matches = bodyText.match(/\([A-Za-z][^)]+\)/g) || [];
  report.checks.push({
    route,
    kind: 'english_subtitle_absent',
    label: 'no English parenthetical subtitle',
    expected: 0,
    actual: matches.length,
    status: matches.length === 0 ? 'pass' : 'fail',
    error: matches.length === 0 ? '' : `found English subtitle candidates: ${matches.join(', ')}`,
  });
}

async function ensureTopRailShell(page, report, route) {
  const rail = page.locator('.cmd-shell__side').first();
  const count = await rail.count();
  if (count === 0) return;
  const box = await rail.boundingBox();
  const ok = Boolean(box) && box.height <= 120 && box.width >= 900;
  report.checks.push({
    route,
    kind: 'top_rail_shell',
    selector: '.cmd-shell__side',
    label: 'command shell uses top rail instead of left sidebar',
    expected: 'height<=120,width>=900',
    actual: box ? `height=${Math.round(box.height)},width=${Math.round(box.width)}` : 'missing-box',
    status: ok ? 'pass' : 'fail',
    error: ok ? '' : 'left sidebar residue detected',
  });
}

async function ensureFactoryReferenceDensity(page, report, route) {
  const frame = page.locator('.cmd-factory-board').first();
  const table = page.locator('.cmd-factory-table').first();
  const frameBox = await frame.boundingBox();
  const tableBox = await table.boundingBox();
  const tableOffset = frameBox && tableBox ? Math.round(tableBox.y - frameBox.y) : null;
  const topKpiCards = await page.locator('.cmd-factory-board__stats .stat-card').count();
  const tableRows = await page.locator('.cmd-factory-table tbody tr, .cmd-factory-table tfoot tr').count();
  const ok = tableOffset !== null && tableOffset <= 120 && topKpiCards === 0 && tableRows >= 6;
  report.checks.push({
    route,
    kind: 'factory_reference_density',
    selector: '.cmd-factory-table',
    label: '05 factory board is table-first like target reference panel',
    expected: 'tableOffset<=120,topKpiCards=0,tableRows>=6',
    actual: `tableOffset=${tableOffset ?? 'missing'},topKpiCards=${topKpiCards},tableRows=${tableRows}`,
    status: ok ? 'pass' : 'fail',
    error: ok ? '' : 'factory board still has loose KPI-first layout residue',
  });
}

async function ensureLayoutHook(page, report, route, selector, label) {
  const count = await page.locator(selector).count();
  report.checks.push({
    route,
    kind: 'reference_layout_hook',
    selector,
    label,
    expected: 1,
    actual: count,
    status: count >= 1 ? 'pass' : 'fail',
    error: count >= 1 ? '' : `${label} missing ${selector}`,
  });
}

const referenceChecklist = [
  { moduleNumber: '01', title: '系统总览主视图', surface: 'review', route: '/review/overview' },
  { moduleNumber: '02', title: '登录与角色入口', surface: 'public', route: '/login' },
  { moduleNumber: '03', title: '独立填报端首页', surface: 'entry', route: '/entry' },
  { moduleNumber: '04', title: '填报流程页', surface: 'entry', route: '/entry/report/*' },
  { moduleNumber: '05', title: '工厂作业看板', surface: 'review', route: '/review/factory' },
  { moduleNumber: '06', title: '数据接入与字段映射中心', surface: 'admin', route: '/admin/ingestion' },
  { moduleNumber: '07', title: '审阅中心', surface: 'review', route: '/review/tasks' },
  { moduleNumber: '08', title: '日报与交付中心', surface: 'review', route: '/review/reports' },
  { moduleNumber: '09', title: '质量与告警中心', surface: 'review', route: '/review/quality' },
  { moduleNumber: '10', title: '成本核算与效益中心', surface: 'review', route: '/review/cost-accounting' },
  { moduleNumber: '11', title: 'AI 总控中心', surface: 'review', route: '/review/brain' },
  { moduleNumber: '12', title: '系统运维与观测', surface: 'admin', route: '/admin/ops' },
  { moduleNumber: '13', title: '权限与治理中心', surface: 'admin', route: '/admin/governance' },
  { moduleNumber: '14', title: '主数据与模板中心', surface: 'admin', route: '/admin/master', templateRoute: '/admin/master/templates' },
  { moduleNumber: '15', title: '响应式录入体验', surface: 'responsive', route: '/entry' },
];

async function captureRoute(page, report, spec, outDir) {
  await page.goto(spec.route);
  await ensureVisible(page, report, spec.route, spec.frameSelector || '.cmd-module-page', 'command page frame visible');
  await ensureVisible(page, report, spec.route, spec.selector, spec.label);
  if (spec.moduleNumber) {
    await ensureVisible(
      page,
      report,
      spec.route,
      spec.numberSelector || `.cmd-module-page__number:text("${spec.moduleNumber}")`,
      `module ${spec.moduleNumber} visible`,
    );
  }
  for (const check of spec.countChecks || []) {
    await ensureCountAtLeast(page, report, spec.route, check.selector, check.minCount, check.label);
  }
  await ensureTopRailShell(page, report, spec.route);
  if (spec.factoryDensity) {
    await ensureFactoryReferenceDensity(page, report, spec.route);
  }
  if (spec.layoutHook) {
    await ensureLayoutHook(page, report, spec.route, spec.layoutHook, `${spec.moduleNumber} target layout hook`);
  }
  await ensureEnglishSubtitleAbsent(page, report, spec.route);
  await page.waitForTimeout(300);
  if (spec.captureSelector) {
    await page.locator(spec.captureSelector).first().screenshot({ path: path.join(outDir, spec.screenshot) });
  } else {
    await page.screenshot({ path: path.join(outDir, spec.screenshot), fullPage: true });
  }
}

async function captureLogin(page, report, outDir) {
  await page.goto('/login');
  await ensureVisible(page, report, '/login', '[data-testid="login-page"]', '02 login role handoff visible');
  await ensureVisible(page, report, '/login', '.cmd-login__stage', '02 login web entry visible');
  await ensureVisible(page, report, '/login', '.cmd-login__number:text("02")', 'module 02 visible');
  await ensureCountAtLeast(page, report, '/login', '.cmd-login__role', 3, 'login role cards');
  await ensureEnglishSubtitleAbsent(page, report, '/login');
  await page.locator('.cmd-login__stage').first().screenshot({ path: path.join(outDir, '02-login.png') });
}

async function captureEntryFlow(page, report, outDir) {
  await page.goto('/entry/dynamic-entry-form');
  const route = new URL(page.url()).pathname;
  await ensureVisible(page, report, route, '[data-module="04"]', '04 entry flow visible');
  await ensureVisible(page, report, route, '.center-page', '04 entry flow web page visible');
  await ensureVisible(page, report, route, '.center-page__no:text("04")', 'module 04 visible');
  await ensureEnglishSubtitleAbsent(page, report, route);
  await page.locator('.center-page').first().screenshot({ path: path.join(outDir, '04-entry-flow.png') });
}

(async () => {
  const outDir = process.env.VISUAL_AUDIT_OUTPUT_DIR
    ? path.resolve(process.cwd(), process.env.VISUAL_AUDIT_OUTPUT_DIR)
    : path.join(repoRoot, 'tmp', 'visual-audit');
  fs.mkdirSync(outDir, { recursive: true });
  const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'https://localhost';
  const report = { generatedAt: new Date().toISOString(), baseURL, referenceChecklist, checks: [] };

  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({
      baseURL,
      viewport: { width: 1512, height: 982 },
      ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();

    await captureLogin(page, report, outDir);
    await loginWithPassword(page);
    await page.waitForURL(/\/(admin|review|entry)/, { timeout: 10000 });

    const desktopRoutes = [
      {
        route: '/review/overview',
        screenshot: '01-overview.png',
        frameSelector: '[data-testid="overview-dashboard"]',
        selector: '.kpi-strip',
        label: '01 system overview visible',
        moduleNumber: '01',
        numberSelector: '.center-page__no:text("01")',
        captureSelector: '[data-testid="overview-dashboard"]',
        countChecks: [
          { selector: '.kpi-card', minCount: 7, label: 'overview kpi tiles' },
          { selector: '.action-tile', minCount: 6, label: 'overview quick entries' },
        ],
      },
      { route: '/review/factory', screenshot: '05-factory-board.png', selector: '.cmd-factory-table', label: '05 factory board visible', moduleNumber: '05', factoryDensity: true, captureSelector: '.cmd-factory-board' },
      { route: '/review/tasks', screenshot: '07-review-tasks.png', frameSelector: '[data-testid="review-task-center"]', selector: '.data-table-shell', label: '07 review center visible', moduleNumber: '07', numberSelector: '.center-page__no:text("07")', captureSelector: '[data-testid="review-task-center"]' },
      { route: '/review/reports', screenshot: '08-reports-delivery.png', selector: '.cmd-module-page__primary', label: '08 reports center visible', moduleNumber: '08', layoutHook: '.cmd-layout--report-delivery' },
      { route: '/review/quality', screenshot: '09-quality-alerts.png', selector: '.cmd-module-page__primary', label: '09 quality center visible', moduleNumber: '09', layoutHook: '.cmd-layout--quality-alerts' },
      { route: '/review/reconciliation', screenshot: '09-reconciliation.png', frameSelector: '.page-stack, body', selector: '.reconciliation-center, [data-testid="reconciliation-center"], .page-stack', label: '09 reconciliation center visible', moduleNumber: '09', numberSelector: 'body' },
      { route: '/review/cost-accounting', screenshot: '10-cost-benefit.png', selector: '.cmd-module-page__primary', label: '10 cost center visible', moduleNumber: '10', layoutHook: '.cmd-layout--cost-stack' },
      { route: '/review/brain', screenshot: '11-ai-control.png', selector: '.cmd-module-page__primary', label: '11 brain center visible', moduleNumber: '11', layoutHook: '.cmd-layout--ai-brain' },
      { route: '/admin', screenshot: '14-admin-home.png', selector: '.cmd-module-page__primary', label: 'admin home visible', moduleNumber: '14' },
      { route: '/admin/ingestion', screenshot: '06-ingestion-mapping.png', selector: '.cmd-module-page__primary', label: '06 ingestion center visible', moduleNumber: '06', layoutHook: '.cmd-layout--mapping-center', captureSelector: '.cmd-module-page' },
      { route: '/admin/ops', screenshot: '12-ops-observability.png', selector: '.cmd-module-page__primary', label: '12 ops center visible', moduleNumber: '12', layoutHook: '.cmd-layout--ops-observability' },
      { route: '/admin/governance', screenshot: '13-governance.png', selector: '.cmd-module-page__primary', label: '13 governance center visible', moduleNumber: '13', layoutHook: '.cmd-layout--governance-matrix' },
      { route: '/admin/users', screenshot: '13-admin-users.png', selector: '.cmd-module-page__primary', label: '13 users center visible', moduleNumber: '13', layoutHook: '.cmd-layout--governance-matrix' },
      { route: '/admin/master', screenshot: '14-master-template.png', selector: '.cmd-module-page__primary', label: '14 master center visible', moduleNumber: '14', layoutHook: '.cmd-layout--master-templates' },
      { route: '/admin/master/templates', screenshot: '14-admin-templates.png', selector: '.cmd-module-page__primary', label: '14 template center visible', moduleNumber: '14', layoutHook: '.cmd-layout--master-templates' },
    ];

    for (const spec of desktopRoutes) {
      await captureRoute(page, report, spec, outDir);
    }

    const mobile = await browser.newContext({
      baseURL,
      viewport: { width: 430, height: 932 },
      ignoreHTTPSErrors: true,
    });
    const mpage = await mobile.newPage();
    await loginWithPassword(mpage);
    await mpage.goto('/entry');
    await ensureVisible(mpage, report, '/entry', '[data-module="03"]', '03 entry terminal visible');
    await ensureVisible(mpage, report, '/entry', '.center-page', '03 entry terminal web page visible');
    await ensureVisible(mpage, report, '/entry', '.app-entry-shell__nav', 'entry-only nav visible');
    await ensureTextAbsent(mpage, report, '/entry', '审阅中心', 'surface boundary: fill-only nav isolation');
    await ensureTextAbsent(mpage, report, '/entry', '管理控制台', 'surface boundary: fill-only nav isolation');
    await ensureTextAbsent(mpage, report, '/entry', '移动端预览', 'mobile preview module cancelled');
    await ensureEnglishSubtitleAbsent(mpage, report, '/entry');
    await mpage.locator('.center-page').first().screenshot({ path: path.join(outDir, '03-entry-home.png') });
    await captureEntryFlow(mpage, report, outDir);
    report.checks.push({
      route: '/entry',
      kind: 'responsive_reference',
      moduleNumber: '15',
      label: '15 responsive entry experience covered',
      status: 'pass',
      error: '',
    });
    await mpage.screenshot({ path: path.join(outDir, '15-entry-responsive.png'), fullPage: true });
    await mobile.close();
    await context.close();
  } finally {
    await browser.close();
  }

  addTargetImageChecks(report);
  addReferencePanelChecks(report, outDir);
  const failed = report.checks.filter((item) => item.status === 'fail');
  report.summary = { totalChecks: report.checks.length, failedChecks: failed.length };
  fs.writeFileSync(path.join(outDir, 'audit-report.json'), JSON.stringify(report, null, 2), 'utf8');

  if (failed.length > 0) {
    console.error(`visual audit failed with ${failed.length} checks`);
    for (const item of failed) {
      console.error(`[${item.route}] ${item.label}: ${item.error}`);
    }
    process.exitCode = 1;
  }
})();
