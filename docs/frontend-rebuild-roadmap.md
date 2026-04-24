# 前端重构路线图（执行版）

## 总目标

在不破坏现有核心业务、权限、接口、测试闭环前提下，实现：

- 中心化信息架构
- 统一设计系统与壳层
- 独立填报端（Entry）
- 成本策略引擎（可配置）
- AI 总大脑（跨中心落点）

## 当前基线

- 已有可运行路由与权限守卫： [index.js](/D:/zzj Claude code/aluminum-bypass/frontend/src/router/index.js)
- 审阅端已有可用页面骨架： [ReviewLayout.vue](/D:/zzj Claude code/aluminum-bypass/frontend/src/views/review/ReviewLayout.vue)
- 移动填报已有完整主链路： `mobile-entry/report/advanced/ocr/attendance/history`
- 样式集中于 [styles.css](/D:/zzj Claude code/aluminum-bypass/frontend/src/styles.css)，但缺少独立 design tokens/theme/navigation 配置层

## 分阶段实施

1. Phase 0 文档冻结（已启动）
2. Phase 1 设计系统与壳层
3. Phase 2 路由元数据与导航重构
4. Phase 3 核心四页升级（登录、总览、审阅任务、数据接入）
5. Phase 4 其余中心统一骨架迁移
6. Phase 5 成本策略引擎与 AI 大脑增强
7. Phase 6 联调、验收、上线试用准备

## 改造优先级清单（按实施顺序）

1. `frontend/src/design/*` + `frontend/src/config/navigation.*`
2. `frontend/src/layout/AppShell.vue` + `frontend/src/layout/EntryShell.vue`
3. `frontend/src/router/index.js`（meta 增强 + entry 独立端 + legacy 兼容）
4. `frontend/src/views/review/ReviewLayout.vue` / `frontend/src/views/Layout.vue`
5. `frontend/src/views/Login.vue`
6. `frontend/src/views/review/OverviewCenter.vue`（新增）
7. `frontend/src/views/review/ReviewTaskCenter.vue`（新增）
8. `frontend/src/views/review/IngestionCenter.vue`（新增）
9. `frontend/src/services/costing/*` + `frontend/src/views/review/CostAccountingCenter.vue`
10. `frontend/src/stores/assistant.*` + `frontend/src/views/assistant/BrainCenter.vue`

## 风险清单

- 当前工作树在 `main` 且改动较多，合并冲突风险高
- 现有 e2e 对 route name、文案和结构有依赖，壳层重构可能导致断言失效
- 成本策略引擎缺后端专用表与接口时，需前端 mock + TODO 承接
- AI 能力需兼容 `mock` 与 `live` 两种运行态，避免 UI 假失败

## 验证策略

- 每阶段最少执行：
  - `npm --prefix frontend run build`
  - 关键路由访问冒烟（`/login` `/entry` `/review/*`）
- 大阶段完成后补：
  - `npm --prefix frontend run e2e`（可筛关键用例）
  - 视觉审计脚本（如 `frontend/tmp_visual_audit.cjs`）

