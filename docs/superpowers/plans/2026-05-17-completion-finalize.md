# 数据中枢 完全体收口方案 — E2E + 对比度 + 上线

**Date:** 2026-05-17
**Executor:** Codex（后端 / 测试 / 集成）
**Base:** `D:\zzj Claude code\aluminum-bypass`
**Branch:** `main`（直推）
**Status snapshot:** commit `2e5c455`（前端 F1-F5 落地+返修），后端 `8082db2` 已封盘

## 当前状态

- 后端 947 测试全绿，生产 main@a57af67 门禁 ok=true
- 前端 vite build 2.44s，dist/sw.js 生成，单元测试 233 全过
- E2E spec 35 个，Playwright 配置但**未实跑过**（缺 globalSetup、storageState、webServer、浏览器二进制）
- 对比度（plan F5 验收点 3）未审计
- 工作树干净，未 push 到远端

## 约束

- 不引入新前端依赖（除 `@axe-core/playwright` 用于对比度审计）
- 不改后端 API 契约
- 不改业务逻辑，仅补测试基础设施 + 修测试中暴露的真实缺陷
- 每个任务独立可提交
- 所有任务在 `D:\zzj Claude code\aluminum-bypass` 工作目录，PowerShell + Bash 共存
- 失败两次同方案立刻停下来汇报，不要堆补丁

---

## E1. Playwright 跑通基础设施

**目标：** `npx playwright test --project=chromium` 能从零启动到出报告，不依赖外部已运行的服务

**交付物：**
- `frontend/e2e/global-setup.js`：HTTP 调后端 `/api/v1/auth/login`，把 token 写入 storageState（含 cookies + localStorage `xt_access_token` / `xt_refresh_token`）
- `frontend/playwright.config.js` 改：
  - 去掉无条件 `storageState`，改为只在 `projects[0].use.storageState` 指定
  - 加 `globalSetup: './e2e/global-setup.js'`
  - 加 `webServer`：自动起 `vite preview --port 4173` + 后端 uvicorn（用 `commands` 数组，前后端各一）
  - `baseURL` 默认值改 `http://localhost:4173`
  - 配置 `projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }, { name: 'mobile', use: { ...devices['Pixel 5'] } }]`
- `frontend/e2e/.auth/.gitignore`（忽略 `*.json`）
- `frontend/e2e/fixtures/auth.js` 删掉自维护逻辑（globalSetup 接管），保留 `expect` 重导出
- `backend/scripts/start_e2e_backend.ps1` 和 `.sh`：用 SQLite + 临时 DB 起 uvicorn（端口 8000）

**实现要点：**
```javascript
// global-setup.js 核心
import { request } from '@playwright/test'
const ctx = await request.newContext({ baseURL: 'http://localhost:8000' })
const r = await ctx.post('/api/v1/auth/login', { data: { username, password } })
const { access_token, refresh_token } = await r.json()
fs.writeFileSync(authFile, JSON.stringify({
  cookies: [],
  origins: [{
    origin: 'http://localhost:4173',
    localStorage: [
      { name: 'xt_access_token', value: access_token },
      { name: 'xt_refresh_token', value: refresh_token },
    ],
  }],
}))
```

**验收：**
1. `cd frontend && npx playwright install chromium`（仅一次）
2. `npx playwright test --project=chromium e2e/login-hud.spec.js`：3/3 通过
3. `npx playwright test --project=chromium e2e/dashboard-executive.spec.js`：通过（证 storageState 工作）
4. 报告输出到 `playwright-report/index.html`，无 webServer 启动错误

---

## E2. 全量 E2E 实跑 + 缺陷分类

**目标：** 跑完全部 35 个 spec，把红的归三类：测试老化、真实缺陷、环境问题

**前置：** E1 完成

**步骤：**
1. `npx playwright test --project=chromium --reporter=list,json --output=test-results` 全量
2. 收集 `test-results.json` 失败明细，按文件分组
3. 对每个失败 spec 判断：
   - **A. 测试老化**（选择器 / API 路径与代码不匹配）：直接修测试到匹配现状
   - **B. 真实缺陷**（功能确实坏了）：列入 E4，**不要**为了通过测试改代码
   - **C. 环境问题**（数据缺失、外部依赖）：在 spec 加 `test.skip()` 加注释 `// skip: needs <X>`
4. 输出 `docs/audits/2026-05-17-e2e-full-run-audit.md`，含：
   - 总数、绿/红/skip
   - 每个红 spec 的分类 + 一句话原因
   - A 类直接在本任务里修；B 类列出阻塞条目
5. 移动端 spec 用 `--project=mobile` 单独再跑一遍

**验收：**
- audit 文档存在
- A 类（测试老化）全部修复并绿
- C 类全部加 skip 标记
- B 类列入 E4 待修
- 至少 80% spec 绿（A+C 处理后）

---

## E3. 对比度 + 可访问性审计

**目标：** 关键页面达到 WCAG AA（4.5:1 normal text, 3:1 large text）

**交付物：**
- 装 `@axe-core/playwright`（仅 dev 依赖）
- `frontend/e2e/a11y/contrast.spec.js`：用 axe 跑以下页面：
  - `/login`、`/dashboard/executive`、`/dashboard/factory`、`/dashboard/workshop`
  - `/manage/*` 6 个 Center 页
  - `/mobile/entry`、`/mobile/shift-report`
- `docs/audits/2026-05-17-a11y-contrast-audit.md`：列每页对比度问题 + WCAG 等级
- 严重违规（normal text < 4.5:1）直接修 `frontend/src/design/xt-tokens.css`，不动其他样式
- 中等违规（3:1 ≤ x < 4.5:1）记录但不修，标 P1

**实现：**
```javascript
import AxeBuilder from '@axe-core/playwright'
const results = await new AxeBuilder({ page })
  .withTags(['wcag2aa', 'wcag21aa'])
  .include('main')
  .analyze()
expect(results.violations.filter(v => v.id === 'color-contrast')).toEqual([])
```

**约束：**
- **不**为了通过审计改 industrial.css 或 xt-hud.css 的视觉决策
- 仅在 xt-tokens.css 里调 `--xt-text-muted` 等基础 token 的明度
- 任何颜色 token 调整必须保留 HUD 风格（不要变浅蓝白底）

**验收：**
1. `npx playwright test e2e/a11y/contrast.spec.js`：所有页面 0 严重违规
2. audit 文档列出全部中等违规 + 修复优先级

---

## E4. E2E 真实缺陷修复（B 类）

**目标：** E2 报告里的真实功能缺陷全部修复

**输入：** E2 输出的 B 类清单

**约束：**
- 每个缺陷一个 commit，标题格式 `fix(<scope>): <一句话>`
- commit body 必须引用对应 spec 文件名
- 改前端先 `node --test`，改后端先 `pytest`
- 不引入新依赖
- 视觉层修复必须匹配 xt 设计系统

**验收：**
- 全部 B 类缺陷修复
- 对应 spec 重跑通过
- 后端 pytest 仍 947 通过（如有改动）
- 前端单测仍 233 通过

---

## E5. 系统级冒烟（生产形态）

**目标：** 完整启动栈，按真实用户路径走一遍

**步骤：**
1. 后端 `uvicorn app.main:app --port 8000`（用 `.env` 真实配置）
2. 前端 `npm run build && npm run preview --port 4173`
3. 用 Playwright 跑 `e2e/compose-smoke.spec.js`、`e2e/zd1-machine-smoke.spec.js`、`e2e/mobile-entry-smoke.spec.js`
4. 手动验证（用 browse 或 curl）：
   - `GET /healthz` → `{"status":"ok"}`
   - `GET /readyz` → 200
   - `POST /api/v1/auth/login` → access + refresh token
   - `POST /api/v1/telemetry/errors`（任意 payload）→ 202/200
   - `POST /api/v1/telemetry/perf` → 202/200
   - 前端访问 `/`、`/login`、`/dashboard/executive`：HTTP 200，无 console error

**交付物：**
- `docs/audits/2026-05-17-system-smoke-audit.md`：每项的 curl/响应/截图证据
- 任何 P0 问题列入 E4 修复并重跑

**验收：**
- audit 文档存在
- 所有冒烟项绿
- 无 P0/P1 残留

---

## E6. 文档同步 + 远端提交

**目标：** 工作树干净、main 与远端一致、所有变更进入 git 历史

**步骤：**
1. 更新 `MEMORY.md`（如有需要新增 E2E/对比度相关记忆）
2. 检查 `git status`，确保 audit 文档、新增配置都已提交
3. `git push origin main`
4. `gh pr list` 确认无遗漏
5. 把本 plan 的执行结果（绿/红/skip 数、修复总数）追加到 `docs/audits/2026-05-17-completion-summary.md`
6. 更新 `docs/superpowers/plans/2026-05-16-full-platform-completion.md` 末尾的"完全体定义"清单：第 8 项"测试覆盖"标记为可执行 + 实跑通过

**约束：**
- **不**用 `--no-verify`、**不** force push
- 如远端有冲突，先 pull --rebase，冲突解决后再 push
- commit 拆分原则：基础设施（E1）、缺陷修复（E4）、审计文档（E2/E3/E5）分别独立 commit

**验收：**
- `git status` 干净
- `git log origin/main..HEAD` 为空（已同步）
- audit 文档与本 plan 双向引用

---

## E7. 完全体验收门禁

**目标：** 把"系统完全没问题"翻译成可执行命令

**验收脚本：** `backend/scripts/check_full_completion_gate.py`（新建）

输出 JSON：
```json
{
  "ok": true,
  "checks": {
    "backend_pytest": { "ok": true, "passed": 947, "skipped": 3 },
    "backend_completion_gate": { "ok": true },
    "frontend_unit": { "ok": true, "passed": 233 },
    "frontend_build": { "ok": true, "duration_s": 2.44, "sw_generated": true },
    "playwright_e2e": { "ok": true, "passed": N, "failed": 0, "skipped": M },
    "playwright_a11y": { "ok": true, "violations": 0 },
    "system_smoke": { "ok": true }
  },
  "blockers": []
}
```

**实现：** Python 脚本调子进程跑各项，超时 600s/项，汇总 JSON 写到 `docs/ops/full_completion_gate.json` + stdout

**验收：**
1. `python backend/scripts/check_full_completion_gate.py` 退出码 0
2. 所有 checks ok=true，blockers=[]
3. 输出 JSON 写入 `docs/ops/full_completion_gate.json`
4. 在 `docs/audits/2026-05-17-full-completion-evidence.md` 引用 JSON 全文 + commit hash

---

## 执行顺序

```
E1 → E2 → E3 → E4 → E5 → E6 → E7
```

E2 与 E3 可并行（不冲突）。其余串行。

## Codex 执行命令

```powershell
codex exec "执行 docs/superpowers/plans/2026-05-17-completion-finalize.md 的 E1 任务，按 plan 验收标准产出，完成后报告" `
  -C "D:\zzj Claude code\aluminum-bypass" `
  -s workspace-write `
  -c model_reasoning_effort="high"
```

每个任务（E1-E7）独立执行，前一个验收通过后再发下一个。

## 失败处理

- E1 跑不通 → 不要硬上 E2，先 audit 写"E2E 基础设施缺什么"再停
- E3 大面积红 → 先只跑 `/login` 和 `/dashboard/executive` 两个，确定基线再扩
- E4 修了 5 个还有 20 个 → 中间停下来报一次进度，由用户决定继续还是冻结剩余项
- E5 冒烟红 → 立刻停，不要 push

## 不在本 plan 范围

- 钉钉通讯录权限申请（运营侧）
- APP_CONNECTION 凭据启用（运营侧）
- 试点人员 dingtalk_user_id 绑定（运营侧）
- 移动端真机测试（需要 PWA 安装到 Android 验证）
- 性能基准（plan B 备份）

---

## 执行结果（2026-05-18）

- E2 全量 E2E：Chromium `112 passed / 3 skipped / 0 failed`，Mobile `21 passed / 0 failed`；审计见 `docs/audits/2026-05-17-e2e-full-run-audit.md`。
- E3 对比度审计：`12 passed / 0 failed`，`color-contrast` 违规为 0；审计见 `docs/audits/2026-05-17-a11y-contrast-audit.md`。
- E4 B 类真实缺陷：前端单测 `237 passed`，缺陷回归 E2E `22 passed`。
- E5 生产形态冒烟：`13 passed / 0 failed`，HTTP、telemetry、关键页面与截图证据见 `docs/audits/2026-05-17-system-smoke-audit.md`。
- E6 文档同步：收口摘要见 `docs/audits/2026-05-17-completion-summary.md`。
- E7 完全体门禁：`docs/ops/full_completion_gate.json` 为 `ok=true`，`blockers=[]`；完整证据见 `docs/audits/2026-05-17-full-completion-evidence.md`。
