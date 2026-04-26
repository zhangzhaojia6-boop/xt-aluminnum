# Vercel Preview 轻测试清单

## 定位

Vercel Preview 仅用于前端视觉和交互轻测试，不替代 Phase 1 正式试跑，不替代 Linux + Docker Compose 部署，也不作为生产环境。

Preview 不承诺真实后端能力，不伪造生产数据，不作为 MES、ERP、财务结算或自动执行能力的验证环境。

## 当前分支

- `ui重构`

## 推荐部署方式

- 通过 Git 分支或 PR 触发 Vercel Preview。
- 暂不 merge `main`。
- 暂不执行生产部署。
- 暂不把 Vercel 作为 Phase 1 试跑环境。

## 推荐 Vercel 设置

本仓库根目录没有 `package.json`，前端项目位于 `frontend/`。当前仓库提供根目录 `vercel.json`，用于从仓库根目录构建前端并补齐 SPA fallback。

- Root Directory: 仓库根目录
- Framework Preset: Vite
- Install Command: `npm --prefix frontend ci`
- Build Command: `npm --prefix frontend run build`
- Output Directory: `frontend/dist`
- Node.js: 建议 22.x；Vite 8 依赖要求 Node `^20.19.0 || >=22.12.0`
- Rewrites: `/(.*)` -> `/index.html`

## 环境变量

- `VITE_API_BASE_URL`

如果没有测试后端 API，建议先不设置生产 API 地址。此时 Preview 只能用于有限的前端视觉和交互轻测，登录、真实 API 数据读取、真实写入、审批流和报表交付不能视为通过。

如需联调测试后端，应由人工明确提供测试后端地址，并在 Vercel Dashboard 的 Preview 环境变量中设置 `VITE_API_BASE_URL`。不要在仓库中写入真实 secret、生产密钥或 `.env` 内容。

## 轻测试路径

- `/login`
- `/entry`
- `/review/overview`
- `/review/brain`
- `/review/reports`
- `/review/quality`
- `/review/cost-accounting`
- `/admin/ingestion`
- `/admin/ops`
- `/admin/governance`
- `/admin/master`

## 轻测试检查项

- 导航是否可见。
- 三端入口是否清楚。
- AI 是否是一个主问答框。
- fallback/source 标识是否清楚。
- 页面是否接近高清目标图风格。
- 是否有误导性的“已成功”“已联通”“已执行”文案。
- 移动端是否不横向撑破。

## 不测试项

- 不测试真实生产写入。
- 不测试真实 MES。
- 不测试真实 ERP。
- 不测试真实财务结算。
- 不测试真实部署/回滚。
- 不测试真实 AI 自动执行。

## 推送前门禁

- `git status --short` 干净。
- `npm --prefix frontend run build` 通过。
- 全量 e2e 通过。
- 静态 pytest 通过。

## 后续命令

```powershell
git push -u origin ui重构
```

在 Vercel 中导入仓库，或等待 Git integration 生成 Preview。

打开 Preview URL 后，按本文件的轻测试路径和检查项逐项验收。
