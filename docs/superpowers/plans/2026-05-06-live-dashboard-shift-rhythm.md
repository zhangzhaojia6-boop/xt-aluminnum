# Live Dashboard Shift Rhythm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在管理端实时态势第一屏新增班次产量节奏，让管理者直接看出今日卷级直录产量主要来自哪些班次。

**Architecture:** 不新增 API、不引入图表库；前端从现有 `aggregation.workshops[].machines[].shifts` 汇总班次产量，`LiveDashboard.vue` 渲染紧凑横向节奏条。计算逻辑放在 `frontend/src/utils/managementCommandCenter.js`，由 Node 测试覆盖排序、占比和机列数。

**Tech Stack:** Vue 3 + scoped CSS + Node test；沿用现有 design system、`formatWeight()` 和 tabular number 口径。

---

## Tasks

- [x] 前端 TDD：在 `frontend/tests/managementCommandCenter.test.js` 增加 `buildShiftOutputRhythm()` 测试，覆盖班次汇总、排序、占比、机列数。
- [x] 前端实现：在 `frontend/src/utils/managementCommandCenter.js` 新增 `buildShiftOutputRhythm()`。
- [x] 页面 TDD：在 `managementCommandCenter.test.js` 静态断言 `LiveDashboard.vue` 包含 `live-shift-rhythm`、`班次产量节奏`、`shiftOutputRhythmRows`。
- [x] 页面实现：在 `frontend/src/views/reports/LiveDashboard.vue` 的卷级直录分布下加入班次节奏条，并补桌面/移动响应式 CSS。
- [ ] 验证、提交、部署并确认线上前端资产包含 `班次产量节奏`。

## Verification

```powershell
npm --prefix frontend test -- managementCommandCenter.test.js
python -m pytest backend/tests -m frontend_contract -q
npm --prefix frontend run build
git diff --check
```
