# 鑫泰铝业 数据中枢 · 现状审计报告

**Date:** 2026-05-16
**Phase:** A1 (Round 1)
**Author:** Claude (协调/验收)

---

## 1. Endpoint 清单（dashboard 相关）

| Router | Path | 职责 |
|--------|------|------|
| `dashboard.py` | `/factory-director` | 厂长驾驶舱 |
| `dashboard.py` | `/workshop-director` | 车间主任驾驶舱 |
| `executive.py` | (待确认) | 高管驾驶舱 |

**数据来源链路：** `routers/dashboard.py` → `services/report/__init__.py` → `services/report/dashboard_builder.py` → 直接 ORM 查询 + 各 service 调用

---

## 2. Service 职责分布

| 关键 Service | 职责 | 是否引用 domain/calculators |
|-------------|------|---------------------------|
| `report/dashboard_builder.py` | 聚合 dashboard 数据 | **否** — 直接写公式 |
| `daily_production_canonical_service.py` | Excel 解析 + 防护阈值 | **否** — 内联阈值逻辑 |
| `production_service.py` | 车间产量/出勤汇总 | **否** |
| `energy_service.py` | 能耗数据 | **否** |
| `quality_service.py` | 质量数据 | **否** |

**核心矛盾 #1：domain/calculators 存在但从未被调用链使用。**
所有口径公式在 service 层重复实现，与 calculator 模块脱节。

---

## 3. Domain Calculators 现状

### 已有模块（4 个）

| 文件 | 函数数 | 测试覆盖 |
|------|--------|---------|
| `production_calculators.py` | 5 | ✅ 15 条 parametrize |
| `energy_calculators.py` | 3 | ✅ 9 条 parametrize |
| `quality_calculators.py` | 3 | ✅ 9 条 parametrize |
| `attendance_calculators.py` | 3 | ✅ 6 条 parametrize |

### 测试质量

`test_calculators.py` 共 39 条断言，全部基于真实 Excel 5.5 抽样数据。
测试 ID 格式：`5.5-{车间}-{指标}`，可溯源到具体报表行。

**结论：** Calculator 模块本身质量优秀，但处于"孤岛"状态——有测试无调用。

---

## 4. 防护阈值（必须保留）

`daily_production_canonical_service.py:15-16`:
```python
SUSPICIOUS_DAILY_OUTPUT_TONS = 5_000.0   # 软警告
HARD_BLOCK_DAILY_OUTPUT_TONS = 50_000.0  # 硬阻断
```

用途：防止工人把 kg 当 t 填报。逻辑在 L176-197，对每行 `daily_output_tons` 做双层校验。

**A3 修复时必须保留此逻辑，不可删除或降级。**

---

## 5. 前端组件现状

### 已有 Xt 组件（14 个）

```
XtExport / XtFilter / XtGrid / XtNotification / XtSkeleton
XtAiActionCard / XtPageHeader / XtActionBar / XtSearch / XtEmpty
XtFactoryMap / XtModuleGlyph / XtWorkshopGlyph / XtFieldGroup
```

### 已有但不在 V2 B1 清单中

```
XtCard / XtTable / XtStatus / XtKpi / XtBatchAction
XtExecutionRail / XtLogo / XtAiThinking / XtModuleTile
```

### V2 B1 需新建（8 个核心组件）

| 组件 | 现状 |
|------|------|
| XtDashboardGrid | ❌ 不存在 |
| XtKpiRibbon | ❌ 不存在（有 XtKpi 但不同） |
| XtSectionCard | ❌ 不存在（有 XtCard 但不同） |
| XtDrawer | ❌ 不存在 |
| XtMetricCard | ❌ 不存在 |
| XtDataTable | ❌ 不存在（有 XtTable 但不同） |
| XtSourceTag | ❌ 不存在 |
| XtLineChart | ❌ 不存在 |

### 图表组件（已有 5 个）

```
ReconciliationWaterfall / PendingAssignmentHeatmap
WorkshopOutputRanking / WorkshopScrapRate / ShiftOutputTrend
```

### HUD 设计系统

`frontend/src/design/xt-hud.css` — 完整的暗色工业 HUD 主题变量。
`frontend/src/design/echarts-hud.js` — ECharts 配色适配。

**data-source 属性：** 前端目前无任何文件使用 `data-source` HTML attribute。B1 需从零建立溯源标签体系。

---

## 6. 页面状态

`frontend/src/views/` 下 63 个 Vue 文件，覆盖：
- dashboard / factory-command / executive（驾驶舱）
- quality / energy / inventory / cost / contracts（业务模块）
- mobile / entry（移动端）
- ops / admin / settings / ai（运维/管理）

---

## 7. 矛盾清单（≥15 条）

| # | 矛盾 | file:line | 严重度 |
|---|------|-----------|--------|
| 1 | calculators 存在但 service 层从未调用 | `services/report/dashboard_builder.py:1-40` | 🔴 高 |
| 2 | dashboard_builder 直接写聚合公式，绕过 domain 层 | `services/report/dashboard_builder.py:42+` | 🔴 高 |
| 3 | production_service 重复实现产量汇总逻辑 | `services/production_service.py` | 🟡 中 |
| 4 | SUSPICIOUS 阈值在 service 而非 domain | `services/daily_production_canonical_service.py:15-16` | 🟡 中 |
| 5 | router 直接 import report_service（跳过 domain） | `routers/dashboard.py:14` | 🟡 中 |
| 6 | XtKpi 组件存在但 B1 计划新建 XtKpiRibbon | 命名冲突风险 | 🟡 中 |
| 7 | XtTable 存在但 B1 计划新建 XtDataTable | 命名冲突风险 | 🟡 中 |
| 8 | XtCard 存在但 B1 计划新建 XtSectionCard | 命名冲突风险 | 🟡 中 |
| 9 | 前端无 data-source 属性使用 | 溯源体系从零开始 | 🟡 中 |
| 10 | 前端无 XtSourceTag 组件 | 溯源体系从零开始 | 🟡 中 |
| 11 | dashboard_builder 引用 scripts/ 模块 | `routers/dashboard.py:16` | 🟡 中 |
| 12 | 测试 39 条仅覆盖 calculators，service 层无单元测试 | `tests/test_calculators.py` | 🔴 高 |
| 13 | energy_service 被 dashboard_builder 调用但无 calculator 桥接 | `services/report/dashboard_builder.py:18` | 🟡 中 |
| 14 | quality_service 被 dashboard_builder 调用但无 calculator 桥接 | `services/report/dashboard_builder.py:20` | 🟡 中 |
| 15 | 无聚合 API（cumulative/comparison/timeseries）endpoint | 缺失 | 🔴 高 |
| 16 | 前端 charts/ 组件直接消费 raw data，无标准化数据层 | `components/charts/*.vue` | 🟡 中 |
| 17 | DESIGN.md 是 MiniMax 品牌稿，与 xt-hud.css 无关 | `DESIGN.md` vs `xt-hud.css` | 🟡 中 |

---

## 8. 测试覆盖总览

| 区域 | 测试文件数 | 状态 |
|------|-----------|------|
| backend/tests/ | 90+ | 存在但未验证全绿 |
| test_calculators.py | 1 (39 assertions) | ✅ 基于真实数据 |
| 前端测试 | 未发现 | ❌ 缺失 |
| e2e 测试 | 未发现 | ❌ 缺失 |

---

## 9. 保留清单（A2-A4 不可破坏）

1. `SUSPICIOUS_DAILY_OUTPUT_TONS` / `HARD_BLOCK_DAILY_OUTPUT_TONS` 阈值逻辑
2. `test_calculators.py` 全部 39 条断言（真实数据基线）
3. `daily_production_canonical_service.py` Excel 解析 + lineage_hash 溯源
4. `dashboard_builder.py` 现有 endpoint 契约（response schema 不可 break）
5. `xt-hud.css` 设计变量（前端唯一视觉真相）
6. 已有 14 个 Xt 组件的 API 接口

---

## 10. A2 执行建议

1. **不新建 calculator 文件** — 在现有 4 个文件中补齐缺失口径
2. **先扩展 test_calculators.py 到 ≥40 条** — 补充 dashboard_builder 中内联的公式
3. **产出 xintai-real-fields.md** — 从 daily_production_canonical_service.py 的 FIELD_ORDER + dashboard_builder 的 ORM 查询中提取完整字段目录
4. **不动 service 层** — A2 只沉淀口径，A3 才做 service→calculator 桥接
