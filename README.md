# Aluminum Bypass

铝业旁路系统当前已经进入“独立填报端 `/entry` + 管理审阅端 `/manage` + Agent 自动校验汇总 + 浏览器 / 钉钉试跑优先 + 历史系统端口兼容”的阶段。

## 当前定位

1. 岗位手机端 `/entry` 填报优先
2. 钉钉 H5 / 浏览器 `/entry` 单入口优先
3. 观察与实施工作台负责异常处置、配置维护和运行门禁
4. 管理端优先看聚合结果和驾驶舱，不重建人工统计中间层
5. Excel / CSV 导入退居补录和兜底路径

## 当前落地策略

1. Phase 1 先由主操手工录入当前班次原始值，系统自动校验、汇总、催报并推送领导驾驶舱。
2. 扫码补数和随行卡自动带数属于下一阶段增强能力，本阶段只保留接口和组件资产，不进入默认操作路径。
3. MES 接口保留为后续阶段能力；Phase 1 不以 MES 联调作为上线前提。

## 本轮新增重点

1. 管理端、观察/实施端、用户端三端隔离
2. 用户端之间按 `workshop + team + owner_user_id` 硬隔离
3. 钉钉身份入口优先，历史系统端口继续保留
4. 手机端真实图片上传
5. 未报 / 迟报识别与催报记录

## 当前入口

- 前端首页：[https://localhost/](https://localhost/)
- 手机填报主入口：[https://localhost/entry](https://localhost/entry)
- 管理审阅主入口：[https://localhost/manage](https://localhost/manage)
- 兼容入口：[https://localhost/mobile](https://localhost/mobile) 会重定向到 `/entry`
- 探活检查：[https://localhost/healthz](https://localhost/healthz)
- 就绪检查：[https://localhost/readyz](https://localhost/readyz)
- 后端 OpenAPI 文档：[http://localhost:8000/docs](http://localhost:8000/docs)

## 快速启动

**本地开发：**

```bash
# 配置本地环境（使用 SQLite）
cp backend/.env.example backend/.env

# 启动后端
cd backend
uvicorn app.main:app --reload

# 启动前端
cd frontend
npm run dev
```

**生产部署：**

详见 [数据中枢云服务器部署 Runbook](./docs/deploy/runbook.md)

**Docker Compose（未来计划）：**

```bash
docker compose up -d --build
```

生产覆盖验证：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## 云端快速上线闸门（推荐）

云主机常用执行链路：

```bash
git remote -v
git pull
cp .env.example .env
./scripts/deploy_trial.sh
./scripts/go_live_gate.sh https://你的域名
```

说明：

1. `deploy_trial.sh` 做 compose 检查、启动和首轮 `check_trial_stack`。
2. `go_live_gate.sh` 做 `stack / pilot / AI / role-smoke / rollback` 一体化校验。
3. 只有 `GO_LIVE_READY=true` 才建议对现场交付。

更省心的一键入口：

```bash
./scripts/launch_cloud_trial.sh https://你的域名 --pull --skip-ai
```

说明：

1. 默认只跑 `deploy_trial` 与 `go_live_gate`，避免误改本地未提交内容。
2. 加 `--pull` 时会先执行 `git pull`。
3. 仅演练可用 `./scripts/launch_cloud_trial.sh --dry-run`。

## GitHub / 上云前封装准备

1. 当前仓库已经具备后续封装所需的基础资产：`.env.example`、`docker-compose.yml`、`docker-compose.prod.yml`、`.github/workflows/ci.yml`。
2. 当前仓库已可用于“初始化或接回 Git 仓库”流程（`origin` 可见），上云常规流程建议为云机 `git pull` 拉取更新，再按部署脚本执行。
3. 上 GitHub 前只提交代码、文档和示例配置，生产 `.env`、真实密钥、钉钉凭据和数据库口令继续留在本地或云端密钥管理里。
4. 上云前先按本仓库基线跑通后端测试、前端构建、Compose 就绪检查，再补域名、SSL、生产环境变量和云主机/容器编排。
5. Phase 1 的上线口径保持不变：先跑通“岗位直录 + 智能体自动处理 + 驾驶舱直达”，GitHub 与云端只是交付包装层，不改变业务主线。
6. 一个车间快速试跑建议先接 GitHub 远端，再上云主机；这样云端后续只需要 `git pull` 就能更新，不必反复手工传代码包。

## Phase 2 首版发布说明

1. 双端分离：`/entry` 只服务主操与专项 owner，`/manage/*` 只服务管理员与管理层；`/mobile`、`/review/*` 仅作历史兼容。
2. 填报端继续朝“极简滑屏工作台”收口：少字、少说明、像手机切屏一样左右滑动完成录入。
3. 审阅端继续朝“流程追踪运行面板”收口：先看数据从哪来、流到哪、哪里卡住，再看结果和风险。
4. AI 感主要体现在接力结构、流程追踪和结果摘要，不靠大段 AI 说明文案刷屏。

## 文档索引

- [旧项目记忆归档](./docs/archive/root-md-2026-06-27/memory.md)
- [项目文档入口](./docs/README.md)
- [产品方向：软件做减法，智能体做加法](./docs/product-direction.md)
- [当前 PRD：Hermes 真实证据闭环与数据中枢减量增强](./docs/software-minus-agent-plus-prd.md)
- [智能体工作指南](./docs/agent-operating-guide.md)
- [系统与界面设计方向](./docs/system-design-direction.md)
- [Hermes 事实来源地图](./docs/hermes/fact-source-map.md)
- [数据中枢冻结与候选删除登记表](./docs/datahub-deprecation-register.md)
- [系统理解合并版](./docs/system-understanding-consolidated-2026-06-14.md)
- [如果从第一天重来：初始 PRD / AGENTS / DESIGN 与下一步 PRD](./docs/superpowers/plans/2026-06-27-retro-initial-prd-agents-design-and-next-prd.md)
- [MES API 联调对接清单](./docs/mes-api-integration-checklist.md)
- [API 体系分层规范](./docs/api-system-lane-spec.md)
- [CLI / Scripts / Rollout Lane Spec](./docs/cli-rollout-lane-spec.md)

## 当前结论

系统当前已达到“本地可运行 + 关键验证基线已通过 + 可进入发布冻结与单车间试跑准备”阶段：

1. 用户端只能访问自己有权操作的数据
2. 观察/实施端只处理授权范围内的异常、配置与运行门禁
3. 管理端默认展示聚合结果，不默认暴露原始填报编辑
4. 钉钉入口与 `/entry` 主链路已经收口，历史系统端口仅作为兼容保留
5. 手机端图片上传与催报记录已经打通
