# Live Dashboard Output Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在管理端实时态势第一屏新增产量分布条，让管理者直接看到今天卷级直录/本地聚合产量主要落在哪些车间和机列。

**Architecture:** 不新增 API、不引入图表库；前端从现有 `aggregation.workshops` 计算前 5 个有产量的机列分布，`LiveDashboard.vue` 渲染紧凑横向条和未绑定标记。计算逻辑放在 `frontend/src/utils/managementCommandCenter.js`，便于 Node 测试覆盖。

**Tech Stack:** Vue 3 + scoped CSS + Node test；沿用现有 design system 和 `formatWeight()`。

---

## Tasks

- [x] 前端 TDD：在 `frontend/tests/managementCommandCenter.test.js` 增加 `buildOutputDistribution()` 测试，覆盖排序、占比、未绑定机列。
- [x] 前端实现：在 `frontend/src/utils/managementCommandCenter.js` 新增 `buildOutputDistribution()`。
- [x] 页面 TDD：在 `managementCommandCenter.test.js` 静态断言 `LiveDashboard.vue` 包含 `live-output-distribution`、`卷级直录分布`、`outputDistributionRows`。
- [x] 页面实现：在 `frontend/src/views/reports/LiveDashboard.vue` 的 MES 状态条后加入产量分布条，并补桌面/移动响应式 CSS。
- [ ] 验证、提交、部署并确认线上前端资产包含 `卷级直录分布`。

## Verification

```powershell
npm --prefix frontend test -- managementCommandCenter.test.js
python -m pytest backend/tests -m frontend_contract -q
npm --prefix frontend run build
git diff --check
```
