# Live Aggregation Mobile Shift Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让管理端实时态势主聚合直接吃到 `mobile_coil_agg` 填报段数据，未绑定设备的卷级直录也能在第一屏产量、车间、班次和临时机列中可见。

**Architecture:** 后端在 `realtime_service.build_live_aggregation()` 的本地数据 fallback 中合并 `ShiftProductionData(data_source='mobile_coil_agg')`，对 `equipment_id=None` 的行生成仅用于响应的负数 ID 临时机列，不写库。前端只补来源标签，把 `local_shift_data` 显示为卷级直录。

**Tech Stack:** FastAPI service + pytest；Vue/Node source contract；不新增依赖，不改数据库 schema。

---

## Tasks

- [x] 后端 TDD：在 `backend/tests/test_realtime_service.py` 增加未绑定 `mobile_coil_agg` 行进入实时聚合的红灯测试，断言产量、临时机列名和 cell 状态。
- [x] 后端实现：在 `backend/app/services/realtime_service.py` 查询并转换 `mobile_coil_agg` 行，合并到本地 runtime entries，并生成未绑定临时机列。
- [x] 前端契约：在 `frontend/tests/managementCommandCenter.test.js` 或相邻契约中断言 `local_shift_data` 显示为 `卷级直录`。
- [x] 前端实现：在 `frontend/src/utils/managementCommandCenter.js` 增加 `local_shift_data` 来源标签。
- [x] 验证、提交、部署并用生产库 `2026-05-06` 核对 Live aggregation 的 `factory_total.output=120460.0` 或至少不再为 0。

## Verification

```powershell
python -m pytest backend/tests/test_realtime_service.py -q
npm --prefix frontend test -- managementCommandCenter.test.js
python -m pytest backend/tests -m frontend_contract -q
npm --prefix frontend run build
git diff --check
```
