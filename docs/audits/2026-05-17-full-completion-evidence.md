# 完全体验收门禁证据

**日期：** 2026-05-18
**计划：** `docs/superpowers/plans/2026-05-17-completion-finalize.md` E7
**验证实现提交：** `cc2c4c4dd59dd52aaca2a786331a2ffd06f875f3`
**门禁 JSON：** `docs/ops/full_completion_gate.json`

## 结论

- `ok=true`
- `blockers=[]`
- 后端 pytest、后端 completion gate、前端单测、前端构建、全量 Playwright、A11y 对比度、生产形态 smoke 全部通过。

## 完整 JSON

```json
{
  "ok": true,
  "checks": {
    "backend_pytest": {
      "ok": true,
      "command": "C:\\Users\\xt\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe -m pytest",
      "cwd": "backend",
      "duration_s": 172.31,
      "passed": 950,
      "failed": 0,
      "skipped": 3,
      "deselected": 124
    },
    "backend_completion_gate": {
      "ok": true,
      "mode": "audit",
      "audit": "docs\\audits\\2026-05-17-backend-completion-gate-audit.md",
      "production_command": "PYTHONPATH=. .venv/bin/python scripts/check_backend_completion_gate.py --json --dingtalk-userid admin"
    },
    "frontend_unit": {
      "ok": true,
      "command": "npm.cmd test",
      "cwd": "frontend",
      "duration_s": 2.75,
      "passed": 237,
      "failed": 0,
      "skipped": 0
    },
    "frontend_build": {
      "ok": true,
      "command": "npm.cmd run build",
      "cwd": "frontend",
      "duration_s": 2.58,
      "sw_generated": true
    },
    "playwright_e2e": {
      "ok": true,
      "command": "npx.cmd playwright test --project=chromium --project=mobile --reporter=list,json --output C:\\Users\\xt\\AppData\\Local\\Temp\\full-completion-gate-4rw54cog\\playwright-e2e",
      "cwd": "frontend",
      "duration_s": 314.93,
      "passed": 133,
      "failed": 0,
      "skipped": 3,
      "flaky": 0
    },
    "playwright_a11y": {
      "ok": true,
      "command": "npx.cmd playwright test e2e/a11y/contrast.spec.js --project=chromium --reporter=list,json --output C:\\Users\\xt\\AppData\\Local\\Temp\\full-completion-gate-4rw54cog\\playwright-a11y",
      "cwd": "frontend",
      "duration_s": 59.22,
      "passed": 12,
      "failed": 0,
      "skipped": 0,
      "flaky": 0,
      "violations": 0
    },
    "system_smoke": {
      "ok": true,
      "command": "npx.cmd playwright test e2e/compose-smoke.spec.js e2e/zd1-machine-smoke.spec.js e2e/mobile-entry-smoke.spec.js --project=chromium --reporter=list,json --output C:\\Users\\xt\\AppData\\Local\\Temp\\full-completion-gate-4rw54cog\\system-smoke",
      "cwd": "frontend",
      "duration_s": 48.37,
      "passed": 13,
      "failed": 0,
      "skipped": 0,
      "flaky": 0,
      "audit": "docs\\audits\\2026-05-17-system-smoke-audit.md"
    }
  },
  "blockers": []
}
```
