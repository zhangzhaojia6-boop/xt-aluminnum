# 鑫泰铝业 数据中枢 · 验收差距封闭 Spec

**日期**: 2026-05-07
**编制**: Claude Code（验收层）
**适用版本**: `main@e97f5ee` 之后
**目标读者**: Codex（执行者）+ 现场负责人（验收者）

---

## 0. 背景

当前系统已具备"独立填报端 + 管理审阅端 + Agent 自动校验 + MES MVC 同步"的闭环，`PLANS.md` 声称三 Phase 代码闭环均已验证。但把 `C:\Users\xt\Desktop\5.6` 的真实生产数据作为字段适配基线，比对代码与部署站实际输出后，发现如下落地阻塞——集中在**主数据缺失、单位语义不统一、车间别名收敛不全、管理端数据表达薄、门禁覆盖率口径错**五个点。

本 Spec 把这些点规整成可验证的交付项，作为 Codex 下一轮闭环的输入。**本 Spec 不是新功能，是对已完成 Phase 1/2/3 的实际现场可用性补齐。**

### 0.1 现场事实底（唯一真值）

`5.6` 调度员手记 + 看板 PNG：

| 口径 | 值 |
|---|---|
| 当日在制 | 1406.8 t |
| 铸锭 | 369 t / 8 炉 |
| 铸二 / 铸三 | 24 t / 39 t |
| 热轧 | 92 t / 9 块 |
| 1650 / 1850 / 2050 成品 | 220 t / 41 t / 59 t |
| 冷轧合计 | 532 t |
| 回收当日 / 月累 | 70 t / 435 t |
| 磨辊当日 / 累计 | 12 根 / 57 根 |
| 大修车间用电 | 508 度 |
| 办公小楼+质检 | 132 度 |

**验收红线**：任何字段映射跑出的数，必须能够与以上数值对上。pytest 全绿不构成验收通过。

---

## 1. 已确认的代码问题（Code Review 结论）

### 1.1 主数据缺 3 条关键车间（**阻塞**）

**文件**: `backend/app/services/real_master_data.py:35-48`

当前 `WORKSHOPS` 只有 12 条，**缺少 5.6 主战场**：

| 缺失车间 | 5.6 证据 | 影响 |
|---|---|---|
| `LZ1650` / 1650 冷轧车间 | 综合日报、合同报表、看板 PNG 均有 1650 成品口径；当日 220 t | MES 投影对不上、yield_matrix 走不通 |
| `LZ1850` / 1850 冷轧车间 | 当日 41 t 成品 + 23 t 中退 | 同上 |
| `HWB` / 花纹板车间 | docs/大推进.md 成本策略 `LOSS_DUAL_CALIBER` 明确列出花纹板 | 花纹板成本策略无法落地 |

文件内 `real_master_data.py:397` 自报：
> 冷轧1650和1850需要补入标准车间/机列后才能正式承接日报未解析行

`PLANS.md:58` 生产探针：`total_rows=16 / ready_rows=7 / unresolved_rows=9` — 这 9 条中大部分就是 1650/1850/拉矫/精整工序的未解析行。

### 1.2 `daily_production_mapping_service` 规则仅 7 条（**阻塞**）

**文件**: `backend/app/services/daily_production_mapping_service.py:75-83`

```python
DAILY_PRODUCTION_MAPPING_RULES = {
    ('铸锭', ''): MappingRule(workshop_code='ZD'),
    ('铸轧', '铸二'): MappingRule(workshop_code='ZR2', equipment_code='ZR2'),
    ('铸轧', '铸三'): MappingRule(workshop_code='ZR3', equipment_code='ZR3'),
    ('热轧', '铣床'): MappingRule(workshop_code='RZ', equipment_code='RZ-XC', equipment_required=True),
    ('热轧', '热轧'): MappingRule(workshop_code='RZ', equipment_code='RZ-ZJ', equipment_required=True),
    ('冷轧', '2050'): MappingRule(workshop_code='LZ2050', equipment_code='LZ2050-1', equipment_required=True),
    ('园区剪切', ''): MappingRule(workshop_code='JQ'),
}
```

**5.6 `鑫泰每日产量5月.xls/综合报表` 实际 `(workshop_label, project_label)` 对**（未列入规则）：

- `('冷轧', '1650')` / `('冷轧', '1850')` / `('冷轧', '花纹板')`
- `('精整', '纵剪')` / `('精整', '剪子')` / `('精整', '剪切')` / `('精整', '横剪')` / `('精整', '包装')`
- `('拉矫', '拉矫')` / `('拉矫', '分切')` / `('拉矫', '洗拉')` / `('拉矫', '大分切')`
- `('退火炉', '拉矫')` / `('在线退火', '新厂北线')` / `('在线退火', '园区北线')` / `('在线退火', '南线')`
- `('园区淬火', *)` / `('园区精整', *)` / `('回收', '')` / `('大修', '')`

当前 `unresolved_rows=9` 的根因。

### 1.3 单位语义不统一（**数据正确性风险**）

**事实**:

- `WorkOrderEntry.input_weight / output_weight / scrap_weight`：**kg**（`realtime_service.py:601` 标注 `weight_unit: 'kg'`）
- `ShiftProductionData`：**混用** — `data_source='mobile_coil_agg'` 是 kg，其它（`import` / `mobile` / `mes_projection`）按 t 使用
- `reconciliation_service.py:34-38`、`aggregator.py:33-36` 只在 `data_source == 'mobile_coil_agg'` 时 `/1000`；其它 data_source 按 t 直出

**隐性坑**:

- `production_service.py:357` Excel 导入写 `data_source='import'`，如果上游表用 `kg` 表头（`耗材表.xls` 多列是 kg）没做换算，**静默乘 1000 进产量**
- `mobile_report/lifecycle.py:307-327` 写 `data_source='mobile'`，来源是 `mobile_shift_reports.input_weight`；当前入口 `/api/v1/mobile/report/save` 没有统一单位声明字段

**证据**:
- `daily_production_canonical_service.py:214` 把日报值固定写 `source_unit='t'`
- `daily_production_canonical_service.py:175-185` 只对 `>10000 t` 报 `suspicious_daily_output_tons` 警告——但 kg 误当 t 的值通常在 100-10000 t 之间，**大多数 kg→t 错配漏网**

### 1.4 `equipment_binding` readyz 门禁语义错（**假阳性**）

**文件**: `backend/app/services/config_readiness_service.py:182-211`

```python
bound_rows = [item for item in equipment_rows if item.bound_user_id is not None]
if not bound_rows:
    return {"status": "warning", ...}
# 任意一条机列已绑用户 → status=ok
return {"status": "ok", "detail": "bound_machine_users_available"}
```

**问题**: 只要**有一条**机列绑了用户，`readyz.equipment_binding=ok`。生产当前 `active_equipment_count=140 / active_mobile_user_count=348`，但**试点车间的机列覆盖率未纳入门禁**。

**现场后果**: 试点车间实际可能有 80% 主操未绑机列，`/readyz` 依然 ok，上线才发现数据进不去产量。

### 1.5 班次报表路径的 draft 悬空（**用户体验**）

**文件**: `backend/app/services/work_order/entry.py:640`

班次/work_order 填报默认 `entry_status='draft'`。当前生产 `work_order_entries draft=156`，这些 draft 永远不会被 `_aggregate_coil_to_shift`（summary.py:373 `entry_status.in_(('submitted', 'verified', 'approved'))`）消费。

**用户侧观感**: 工人反馈"我填了啊"，管理端"没数据"——两边都是真的，因为路径不同。

**不应做**：把 draft 改成 submitted。审阅闸门是核心使命的一部分，不能破。
**应做**：管理端要能看到 draft 堆积并给出"提升为 submitted"的一键动作（已有 `assistant_actions.py`，但未与 pending_assignment 联动）。

### 1.6 管理端动态图表缺失（**表达力**）

**文件**: `frontend/src/views/factory-command/*`、`frontend/package.json`

- `package.json` **没有任何图表库依赖**（echarts / chart.js / d3 / vue-chartjs 均未引入）
- `FactoryOverview.vue` 只用 `formatLagLabel / sourceLabel` 做文本渲染；`MachineLineScreen / ExceptionMap / CostBenefitScreen` 全部是 KPI 数字 + 表格
- 后端已有丰富数据（`/aggregation/live` cell 二维、`pending_assignment.rows`、`reconciliation` `production_vs_mes` 等），前端未可视化

**现场后果**: 用户反馈"管理端前端页面可多些清晰的动态图表显示""科技感不足"。当前观感确实偏静态报表。

---

## 2. 交付项（按优先级）

### P0 · 字段数据贴合（5 点前必须落地）

#### D1. 补齐 3 条冷轧车间主数据

**文件**:
- 修改：`backend/app/services/real_master_data.py`
- 新增测试：`backend/tests/test_real_master_data_1650_1850_hwb.py`

**改动**:

1. `WORKSHOPS` 追加：
   ```python
   {'code': 'LZ1650', 'name': '1650冷轧车间', 'sort_order': 5},
   {'code': 'LZ1850', 'name': '1850冷轧车间', 'sort_order': 5},
   {'code': 'HWB',    'name': '花纹板车间',   'sort_order': 7},
   ```
   （`sort_order` 同 LZ2050 的 5，按字母序；也可改为 `5.1/5.2/5.3` 新 int，需评估前端依赖）

2. `EQUIPMENT_BY_WORKSHOP` 追加：
   ```python
   'LZ1650': [{'code': 'LZ1650-1', 'name': '1650轧机', 'machine_type': 'cold_mill', 'shift_mode': 'three', 'operational_status': 'running'}],
   'LZ1850': [{'code': 'LZ1850-1', 'name': '1850轧机', 'machine_type': 'cold_mill', 'shift_mode': 'three', 'operational_status': 'running'}],
   'HWB':    [{'code': 'HWB-1',    'name': '花纹板主轧', 'machine_type': 'cold_mill', 'shift_mode': 'three', 'operational_status': 'running'}],
   ```

3. `PROCESS_BUSINESS_UNITS.rolling_branch.workshop_codes` 增加 `LZ1650 / LZ1850 / HWB`。

4. `WORKSHOP_PROCESS_BUSINESS` 追加对应 process_business / tags（参照 LZ2050）。

5. `MACHINE_PROCESS_BUSINESS_BY_CODE` 追加 `LZ1650-1 / LZ1850-1 / HWB-1`。

6. `MES_WORKSHOP_ALIASES` 追加：
   ```python
   ('LZ1650', '1650车间'), ('LZ1650', '冷轧1650车间'), ('LZ1650', '1650冷轧'),
   ('LZ1850', '1850车间'), ('LZ1850', '冷轧1850车间'), ('LZ1850', '1850冷轧'),
   ('HWB',    '花纹板'),   ('HWB',    '花纹板车间'),
   ```

7. 同步更新 `yield_matrix_canonical_service.py:32-34` 的 `cold_roll_1650_2050` 别名组，拆成独立 `cold_roll_1650 / cold_roll_2050`。

8. 删除 `real_master_data.py:397` 的 open_items 第一条（已解决）。

**验收**:
- `python -m pytest backend/tests/test_real_master_data.py -q` 通过
- `curl .../api/v1/master/workshops` 返回 15 条（原 12 + 新 3）
- 别名查询 `MasterCodeAlias.filter(alias_code='1650车间').canonical_code == 'LZ1650'`

#### D2. 补齐 `daily_production_mapping_service` 映射规则

**文件**:
- 修改：`backend/app/services/daily_production_mapping_service.py:75-83`
- 修改测试：`backend/tests/test_daily_production_mapping_service.py`

**改动**: 追加以下映射（基于 5.6 `综合报表`/`分类报表` 实际 label）：

```python
# 冷轧
('冷轧', '1650'):  MappingRule(workshop_code='LZ1650', equipment_code='LZ1650-1', equipment_required=True),
('冷轧', '1850'):  MappingRule(workshop_code='LZ1850', equipment_code='LZ1850-1', equipment_required=True),
('冷轧', '花纹板'): MappingRule(workshop_code='HWB',    equipment_code='HWB-1',    equipment_required=True),

# 精整（JZ 已有 LWJ/HJ/ZJ/FT/FJ 机列）
('精整', '纵剪'): MappingRule(workshop_code='JZ', equipment_code='JZ-ZJ1', equipment_required=True),
('精整', '横剪'): MappingRule(workshop_code='JZ', equipment_code='JZ-HJ1', equipment_required=True),
('精整', '剪子'): MappingRule(workshop_code='JZ', equipment_code='JZ-HJ1', equipment_required=True),  # 同横剪
('精整', '剪切'): MappingRule(workshop_code='JZ', equipment_code='JZ-HJ1', equipment_required=True),
('精整', '包装'): MappingRule(workshop_code='JZ'),  # 包装无机列，只挂车间

# 拉矫
('拉矫', '拉矫'): MappingRule(workshop_code='JZ', equipment_code='JZ-LWJ1', equipment_required=True),
('拉矫', '洗拉'): MappingRule(workshop_code='JZ', equipment_code='JZ-LWJ1', equipment_required=True),
('拉矫', '分切'): MappingRule(workshop_code='JZ', equipment_code='JZ-FT1',  equipment_required=True),
('拉矫', '大分切'): MappingRule(workshop_code='JZ', equipment_code='JZ-FT1', equipment_required=True),
('退火炉', '拉矫'): MappingRule(workshop_code='JZ'),

# 在线退火（ZXTF-1/2/3/4 暂无南北线区分，先挂车间）
('在线退火', '新厂北线'): MappingRule(workshop_code='ZXTF', equipment_code='ZXTF-1', equipment_required=True),
('在线退火', '园区北线'): MappingRule(workshop_code='ZXTF', equipment_code='ZXTF-3', equipment_required=True),
('在线退火', '南线'):     MappingRule(workshop_code='ZXTF'),

# 园区
('园区淬火', ''): MappingRule(workshop_code='JQ'),
('园区精整', ''): MappingRule(workshop_code='JQ'),

# 辅助
('回收', ''): MappingRule(workshop_code='ZD'),  # 回收当日量并入铸锭前段
('大修', ''): MappingRule(workshop_code='RZ'),  # 大修暂挂热轧
```

**验收**:
- `python -m pytest backend/tests/test_daily_production_mapping_service.py -q` 通过（需补 1650/1850/花纹板/纵剪/拉矫 用例）
- 用 5.6 `鑫泰每日产量5月.xls` 跑 dry-run → `unresolved_rows ≤ 2`（只允许真正没见过的新车间）
- `needs_equipment_mapping_rows ≤ 2`

#### D3. 单位推断硬阻断

**文件**:
- 修改：`backend/app/services/daily_production_canonical_service.py:175-185`
- 新增：`backend/app/core/units.py`（可选，提取通用单位推断）
- 修改测试：`backend/tests/test_daily_production_canonical_service.py`

**改动**:

1. 扩展 `SUSPICIOUS_DAILY_OUTPUT_TONS` 阈值逻辑：
   ```python
   # 当前单行 > 10000 t 才警告；改为：
   # - 单行 > 5000 t  → suspicious_daily_output_tons（警告）
   # - 单行 > 50000 t → hard_block_kg_as_tons（硬阻断，拒收）
   # - 单个车间月累计 / 当日 > 31 × 5 = 155 → warning
   ```

2. 在 `ImportBatch` 预检阶段加"单位一致性探针"：
   - 同一 sheet 内 `daily_output_tons` 统计分布；如果中位数 > 1000 且最大值 > 20000，提示"疑似 kg 表"。
   - 探针结果写 `ImportBatch.metadata.unit_warnings`。

3. `daily_production_canonical_service.py:214` 的 `source_unit='t'` 改为从 sheet 表头解析（备选 `t/吨/千吨`），默认 `t` 但如果解析到 `kg/公斤` → 整批行自动 ×0.001。

**验收**:
- 构造 kg 样本 `daily_output_tons=12000 kg`（实际 12 t）→ canonical 输出 `daily_output_tons=12.0` 且 `source_unit='kg'`（转换后记录）
- 构造异常 `daily_output_tons=50000` → `status='blocked'` 且 `issues` 含 `hard_block_kg_as_tons`
- 5.6 `鑫泰每日产量5月.xls` 跑完不触发假阳性（实际最大单行在 200-500 t 区间）

#### D4. 机列绑定覆盖率门禁

**文件**:
- 修改：`backend/app/services/config_readiness_service.py:175-211`
- 新增：`backend/app/routers/config.py` 增加 `/api/v1/configs/equipment-binding-coverage` 只读 endpoint
- 修改测试：`backend/tests/test_config_readiness_service.py`

**改动**:

1. `evaluate_equipment_binding` 重构为基于"试点车间清单"（从 `settings.PILOT_WORKSHOP_CODES` 读取，或回退为全部 active workshops）判断覆盖率：
   ```python
   # 试点车间内每条 active equipment 是否有 bound_user_id
   pilot_equipment = [e for e in equipment_rows if e.workshop.code in pilot_codes and e.is_active]
   bound_pilot = [e for e in pilot_equipment if e.bound_user_id]
   coverage = len(bound_pilot) / max(len(pilot_equipment), 1)

   if coverage < 0.8:
       return {"status": "warning", "action_required": "bind_pilot_machine_users",
               "detail": "pilot_binding_coverage_below_threshold",
               "coverage": round(coverage, 2),
               "unbound": [e.code for e in pilot_equipment if not e.bound_user_id][:20]}
   ```

2. `readyz` 响应里保留原字段，新增 `pilot_binding_coverage` float 和 `unbound_pilot_equipment` list。

3. 前端 `/admin/governance` 页面增加"未绑机列"卡片，`pilot_binding_coverage < 1.0` 时展示未绑机列清单。

**验收**:
- 新增测试：试点车间 5 条机列，3 条绑 → `status='warning'` / `coverage=0.6`
- 试点车间 5 条机列，全部绑 → `status='ok'` / `coverage=1.0`
- 其它车间绑定率不影响门禁

---

### P1 · 管理端表达力（应该做）

#### D5. 引入 echarts + 3 张核心图

**文件**:
- 修改：`frontend/package.json`（加 `echarts` 和 `vue-echarts` 依赖）
- 新增：`frontend/src/components/charts/ShiftOutputTrend.vue`（24h 产量折线）
- 新增：`frontend/src/components/charts/PendingAssignmentHeatmap.vue`（缺报 × 工位热力）
- 新增：`frontend/src/components/charts/ReconciliationWaterfall.vue`（MES vs 填报瀑布）
- 修改：`frontend/src/views/factory-command/FactoryOverview.vue`（塞入上述 3 个组件）

**数据源**（均已存在，不新增后端）：
- 折线：`/api/v1/aggregation/live` → 遍历 `workshop_items[].machine_items[].shift_items`，按 `shift_id` 汇总
- 热力：`/api/v1/aggregation/live/pending-assignment` → `rows[]` 直接喂
- 瀑布：`/api/v1/reconciliation/variance?business_date=...` → 用 `production_vs_mes` 和 `energy_vs_production` 已有数据

**视觉规范**（CLAUDE.md 规定）:
- 企业蓝白灰基调，克制，**不要 SaaS 模板风**
- tooltip/axis label 中文
- 禁用 echarts 默认彩虹色盘，用 `design/tokens.css` 的状态色
- 空态不是 echarts 默认空图，要用 `components/feedback/EmptyState.vue`（如无则新增）

**验收**:
- `npm --prefix frontend run build` 通过
- 浏览器访问 `http://8.140.218.13/admin` 打开管理端，3 张图可渲染
- 现场用户能一眼看出"今天哪个班次产量下滑"

#### D6. Draft 堆积联动

**文件**:
- 修改：`frontend/src/views/review/*`（审阅中心）
- 修改：`backend/app/routers/assistant_actions.py`（已存在）

**改动**:

- `pending_assignment` 卡片点击 → 跳转审阅中心的 draft 清单视图
- draft 清单每条可触发 `assistant_actions.promote_draft_entry`（需确认是否已有，否则按 role 权限新增）
- 提升后 `mobile_coil_agg` 自动聚合（现有 `_aggregate_coil_to_shift` 已自动触发）

**验收**:
- 造一条 draft work_order_entry，进审阅中心点"提升" → `entry_status='submitted'`，刷新管理端 `factory_output > 0`

---

### P2 · 导入鲁棒性（长期）

#### D7. 5.6 一次性回放脚本

**文件**: 新增 `backend/scripts/import_5_6_dry_run.py`

**内容**（概要）:

1. 扫 `C:/Users/xt/Desktop/5.6` 所有 Excel
2. 按文件路由到对应 `import_service`（综合日报 / 能耗 / 天然气 / 合同 / 剪切流水）的 dry-run 入口
3. 输出单个 markdown 报告：
   - 每个 sheet 的车间×工序解析统计
   - `unresolved / needs_equipment_mapping / ready` 比例
   - 单位警告列表
   - 与"事实底"表格的对账差额（必须列出：铸锭 369 t 等 10 个口径）

**验收红线**（见 §0.1）:
- 报告中的铸锭 = 369 ± 5 t
- 1650 / 1850 / 2050 成品三项 = 220 / 41 / 59 ± 5 t
- 冷轧合计 = 532 ± 10 t
- `unresolved_rows ≤ 2`

此脚本作为今后每轮验收的**回归门**。

---

## 3. 交付与验收清单

| ID | 标题 | 优先级 | 文件数 | 估时 | 验收口径 |
|---|---|---|---|---|---|
| D1 | 3 条冷轧车间主数据 | P0 | 2 | 1.5h | `/api/v1/master/workshops` 15 条 |
| D2 | 15 条 daily mapping 规则 | P0 | 2 | 1h | 5.6 dry-run `unresolved_rows ≤ 2` |
| D3 | 单位推断硬阻断 | P0 | 3 | 2h | kg→t 不再静默放过 |
| D4 | 机列绑定覆盖率门禁 | P0 | 3 | 1.5h | 新门禁语义通过 |
| D5 | 引入 echarts + 3 张图 | P1 | 4 | 3h | 浏览器渲染通过 |
| D6 | Draft 提升联动 | P1 | 2 | 1.5h | 端到端 draft→产量可见 |
| D7 | 5.6 dry-run 回放脚本 | P2 | 1 | 2h | 事实底对账通过 |

**总估时**: ~12 小时。P0 部分（D1-D4）约 6 小时，可在下午 5 点前完成落地。

---

## 4. 不做的事（YAGNI）

- **不做**：把 `work_order_entries.entry_status` 默认改成 submitted — 审阅闸门是核心使命的一部分。
- **不做**：新成本策略或 AI 大脑新功能 — 本轮是"字段贴合"不是"新能力"。
- **不做**：重构 `reference-command/*` 与 `views/*` 并存 — 按 PROJECT_STATE_RECOVERY 既定路线，此处暂时兼容即可。
- **不做**：echarts 堆砌一堆花哨图 — 只做 3 张有真实对用户有解释力的图。
- **不做**：为本 Spec 新增后端 endpoint，除 D4 `equipment-binding-coverage` 一个只读路由外，全部复用现有 API。

---

## 5. 风险与回滚

### 5.1 风险

1. **主数据新增车间触发级联**：`EQUIPMENT_BY_WORKSHOP` / `PROCESS_BUSINESS_UNITS` / `WORKSHOP_PROCESS_BUSINESS` / `MACHINE_PROCESS_BUSINESS_BY_CODE` / `MES_WORKSHOP_ALIASES` / `yield_matrix_canonical_service` 六处必须同步改。遗漏任一处会让 1650/1850 数据落在孤岛。
   - **缓解**：D1 验收里必须 `curl /api/v1/master/workshops` 和 `curl /admin/master/process-business-hierarchy`（如有）都能看到。

2. **单位硬阻断误伤历史数据**：5.6 之前已导入的历史批次可能包含 kg 误当 t 的脏数据，硬阻断会导致重导失败。
   - **缓解**：D3 的硬阻断**只对新导入批次生效**；历史 `ImportBatch` 不回滚。

3. **echarts bundle 体积**：echarts 完整包约 1MB+，前端构建产物可能超阈值。
   - **缓解**：按需引入（`echarts/core` + 按图表类型引 `LineChart` / `HeatmapChart` / `BarChart`），而不是 `import * from 'echarts'`。

4. **机列绑定覆盖率阈值可能过严**：首次部署试点车间可能覆盖率 < 80%，卡住 readyz。
   - **缓解**：阈值从 `settings.PILOT_BINDING_COVERAGE_THRESHOLD` 读取，默认 0.8，现场可降到 0.6 过渡。

### 5.2 回滚

每个 D 项独立 commit，独立 revert：

- `D1/D2` 回滚：`git revert <commit>` + 重跑 `seed_real_master_data`（幂等）
- `D3` 回滚：`source_unit` 回到硬编码 `t`
- `D4` 回滚：`evaluate_equipment_binding` 回到"任一绑定即 ok"
- `D5` 回滚：`FactoryOverview.vue` 移除 3 个组件引用即可；npm 依赖保留不伤
- `D6/D7` 回滚：直接删除新增文件

---

## 6. 验收流程

交付方（Codex）完成后，本验收层（Claude Code）按以下顺序核：

1. **D1 主数据**：
   ```bash
   curl -s http://8.140.218.13/api/v1/master/workshops | jq 'length'  # 期望 15
   curl -s http://8.140.218.13/api/v1/master/workshops | jq '[.[]|.code] | sort' | grep -E "LZ1650|LZ1850|HWB"
   ```

2. **D2 映射规则**：
   ```bash
   python backend/scripts/import_5_6_dry_run.py --workbook "C:/Users/xt/Desktop/5.6/鑫泰每日产量5月.xls"
   # 期望 unresolved_rows ≤ 2
   ```

3. **D3 单位阻断**：
   ```bash
   python -m pytest backend/tests/test_daily_production_canonical_service.py::test_hard_block_kg_as_tons -v
   ```

4. **D4 绑定覆盖率**：
   ```bash
   curl -s http://8.140.218.13/readyz | jq '.details.pipeline.checks.equipment_binding'
   # 期望看到 coverage 字段 + unbound_pilot_equipment（如有未绑）
   ```

5. **D5 图表**：
   - 浏览器访问 `http://8.140.218.13/admin`
   - 打开工厂指挥中心
   - 截图 3 张图 → 与 Claude Code 视觉规范对齐（企业蓝白灰、无彩虹色、有空态）

6. **D6 Draft 提升**：
   - 造一条 draft → 审阅中心点提升 → 工厂指挥 `factory_output > 0`

7. **D7 事实底对账**：
   ```bash
   python backend/scripts/import_5_6_dry_run.py --report out.md
   # 检查 out.md：铸锭 369±5 / 1650 220±5 / 1850 41±5 / 2050 59±5 / 冷轧合计 532±10
   ```

**通过标准**: 7 项全部通过方视为本 Spec 闭环；任何一项 fail 打回重做。

---

## 7. 执行建议

**Codex 按 D1 → D2 → D7 → D3 → D4 → D6 → D5 顺序执行**：
- D1/D2 是其它所有项的前置；
- D7 提前做是因为它就是 D1/D2 的验收工具；
- D5 放最后是因为前面跑通后再看图才有意义；
- 每一 D 项单独 commit，commit message 严格对应 D 编号（`feat(master): D1 add 1650/1850/HWB workshops`）。

**Claude Code（验收层）每 D 项交付后出具验收意见**，不合格当即打回。不积攒到最后整批验收。

---

## 8. 附：已写入 memory 的相关事实

- `memory/fields_5_6_audit.md` — 5.6 原始数据字段错配清单
- `memory/admin_data_path.md` — 工人填报到管理端实时态势的完整链路
- `memory/project_mission.md` — 核心使命"消灭人工统计中间层"（本 Spec 的所有决策不得违反）

---

**本 Spec 由 Claude Code 以验收层身份编制。Codex 执行前如有歧义，优先以本 Spec 为准；若本 Spec 与 `CLAUDE.md` / `memory/project_mission.md` 冲突，后者优先。**
