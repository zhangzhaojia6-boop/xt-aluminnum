# Aluminum Bypass

铝业旁路系统当前已经进入“手机端填报主入口 + Agent 自动校验汇总 + 观察/实施分层 + 企业微信单入口优先 + 历史系统端口保留”的阶段。

## 当前定位

1. 班长手机端填报优先
2. 企业微信 H5 / 浏览器 `/mobile` 单入口优先
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
3. 企业微信身份入口优先，历史系统端口继续保留
4. 手机端真实图片上传
5. 未报 / 迟报识别与催报记录

## 当前入口

- 前端首页：[https://localhost/](https://localhost/)
- 手机填报唯一入口：[https://localhost/mobile](https://localhost/mobile)
- 探活检查：[https://localhost/healthz](https://localhost/healthz)
- 就绪检查：[https://localhost/readyz](https://localhost/readyz)
- 后端 OpenAPI 文档：[http://localhost:8000/docs](http://localhost:8000/docs)

## 快速启动

开发联调：

```bash
docker compose up -d --build
```

生产覆盖验证：

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## GitHub / 上云前封装准备

1. 当前仓库已经具备后续封装所需的基础资产：`.env.example`、`docker-compose.yml`、`docker-compose.prod.yml`、`.github/workflows/ci.yml`。
2. 当前代码工作区还需要补正式 GitHub 托管动作：初始化或接回 Git 仓库、绑定远端、确认默认分支与发布分支策略。
3. 上 GitHub 前只提交代码、文档和示例配置，生产 `.env`、真实密钥、企业微信凭据和数据库口令继续留在本地或云端密钥管理里。
4. 上云前先按本仓库基线跑通后端测试、前端构建、Compose 就绪检查，再补域名、SSL、生产环境变量和云主机/容器编排。
5. Phase 1 的上线口径保持不变：先跑通“岗位直录 + 智能体自动处理 + 驾驶舱直达”，GitHub 与云端只是交付包装层，不改变业务主线。
6. 一个车间快速试跑建议先接 GitHub 远端，再上云主机；这样云端后续只需要 `git pull` 就能更新，不必反复手工传代码包。

## Phase 2 首版发布说明

1. 双端分离：`/mobile` 只服务主操与专项 owner，`/review/*` 只服务管理员与管理层。
2. 填报端继续朝“极简滑屏工作台”收口：少字、少说明、像手机切屏一样左右滑动完成录入。
3. 审阅端继续朝“流程追踪运行面板”收口：先看数据从哪来、流到哪、哪里卡住，再看结果和风险。
4. AI 感主要体现在接力结构、流程追踪和结果摘要，不靠大段 AI 说明文案刷屏。

## 文档索引

- [项目记忆](./memory.md)
- [长期 AI 产品体系总规范](./docs/longterm-ai-product-system-spec.md)
- [试点上线前 QA / Readiness Checklist](./docs/pilot-readiness-checklist.md)
- [Workflow Rollout](./docs/workflow-rollout.md)
- [MES API Sync Contract Phase 1](./docs/mes-api-sync-contract-phase1.md)
- [MES Phase 1 字段映射表](./docs/mes-field-mapping-table-phase1.md)
- [MES API 联调对接清单](./docs/mes-api-integration-checklist.md)
- [MES API 未就绪期间的两周施工计划](./docs/mes-api-two-week-prep-plan.md)
- [角色矩阵与首批 SOP 设计](./docs/superpowers/specs/2026-04-06-role-matrix-and-sops-design.md)
- [API 体系分层规范](./docs/api-system-lane-spec.md)
- [CLI / Scripts / Rollout Lane Spec](./docs/cli-rollout-lane-spec.md)
- [长期 AI Skill System 规范](./docs/longterm-ai-skill-system-spec.md)

## 当前结论

系统当前已达到“本地可运行 + 开工门已通过 + 可进入角色与 UI 语义收口施工”阶段：

1. 用户端只能访问自己有权操作的数据
2. 观察/实施端只处理授权范围内的异常、配置与运行门禁
3. 管理端默认展示聚合结果，不默认暴露原始填报编辑
4. 企业微信入口与 `/mobile` 主链路已经收口，历史系统端口仅作为兼容保留
5. 手机端图片上传与催报记录已经打通
