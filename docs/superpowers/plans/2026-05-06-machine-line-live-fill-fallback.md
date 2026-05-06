# Machine-Line Live Fill Fallback Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让管理端车间机列页不再因为现场填报缺少 `equipment_id` 而显示空白，至少能把今日 `mobile_coil_agg` 实时填报按车间/班次归入“未绑定机列”，同时提示需要补机列绑定。

**Architecture:** 不改变正式日报确认口径，不补写历史业务数据。`factory_command_service.list_machine_lines()` 在本地填报 fallback 下继续优先按 `equipment_id` 聚合；当 `equipment_id` 为空时，按 `workshop_id + shift_config_id` 生成稳定的未绑定机列行。前端 `MachineLineScreen.vue` 复用现有数据，加轻量 SVG/条形视觉，突出实时流入、停滞、来源和绑定缺口。

**Tech Stack:** FastAPI + SQLAlchemy + pytest；Vue 3 + scoped CSS + SVG；不新增依赖。

## Tasks

- [x] 增加后端测试：`mobile_coil_agg` 且 `equipment_id=None` 时 `list_machine_lines()` 返回“未绑定机列”行。
- [x] 实现本地填报 fallback 的未绑定机列聚合，并保留已绑定机列聚合行为。
- [x] 增加前端契约测试：车间机列页包含实时条形/SVG 视觉、来源、未绑定机列提示。
- [x] 优化 `MachineLineScreen.vue`，把纯文本列表升级为可扫描的机列实时卡片。
- [x] 跑聚焦测试、前端测试、构建、全量回归、线上部署验证。

## Verification

```powershell
python -m pytest backend/tests/test_factory_command_service.py::test_factory_lists_fall_back_to_unbound_live_machine_lines -q
npm --prefix frontend test -- factoryCommandScreens.test.js
npm --prefix frontend test
npm --prefix frontend run build
python -m pytest backend/tests -q --durations=10
git diff --check
```
