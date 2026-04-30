# 多角色一线采集端重构 — 实施计划

**对应设计：** `docs/superpowers/specs/2026-04-29-multi-role-collection-redesign-design.md`
**目标：** 让各车间各项 owner 今天开始测试录入

---

## Phase 0：账号与种子数据（后端，阻塞所有后续）

### 0.1 新增角色常量与账号模型支持

文件：`backend/app/models/system.py`、`backend/app/core/field_permissions.py`

- User.role 枚举补齐：`energy_stat`、`maintenance_lead`、`hydraulic_lead`、`consumable_stat`、`qc`、`weigher`、`utility_manager`、`inventory_keeper`、`contracts`
- ROLE_ALIASES 补齐短码映射（EN/MT/HY/CS/QC/WG/UM/IK/CT）
- field_permissions.py FIELD_OWNERSHIP 补齐各角色 read/write 权限

验证：`pytest backend/tests/ -k "role" -q` 通过

### 0.2 批量创建账号种子脚本

文件：新建 `backend/scripts/seed_multi_role_accounts.py`

- 按 WORKSHOP_TYPE_BY_WORKSHOP_CODE 遍历所有车间
- 每车间创建：`{workshop}-EN`、`{workshop}-MT`、`{workshop}-HY`、`{workshop}-CS`、`{workshop}-QC`、`{workshop}-WG`
- 全厂级：`FACTORY-UM`、`FACTORY-IK`、`FACTORY-CT`
- 默认密码 `xt123456`，is_mobile_user=True
- 幂等：已存在则跳过

验证：脚本执行后 `SELECT count(*) FROM users WHERE role IN (...)` 返回预期数量

### 0.3 车间 QR 码生成

文件：`backend/app/models/master.py`、`backend/app/services/equipment_service.py`

- Equipment 表新增车间级虚拟设备记录，qr_code 格式 `XT-{workshop_code}-WS`
- 扫码后路由到移动端登录页并带入 workshop 参数

验证：数据库中每个车间有一条 `qr_code LIKE 'XT-%-WS'` 记录

---

## Phase 1：耗材统计员字段定义（后端）

### 1.1 新增 CONSUMABLE_OWNER_FIELDS

文件：`backend/app/core/workshop_templates.py`

按车间类型定义：

```python
CONSUMABLE_OWNER_FIELDS = {
    'casting': [
        {'key': 'liquefied_gas_per_ton', 'label': '液化气吨耗(kg)', 'type': 'number'},
        {'key': 'titanium_wire_per_ton', 'label': '钛丝吨耗(kg)', 'type': 'number'},
        {'key': 'steel_strip_per_ton', 'label': '钢带吨耗(kg)', 'type': 'number'},
        {'key': 'magnesium_per_ton', 'label': '镁锭吨耗(kg)', 'type': 'number'},
        {'key': 'manganese_per_ton', 'label': '锰剂吨耗(kg)', 'type': 'number'},
        {'key': 'iron_per_ton', 'label': '铁剂吨耗(kg)', 'type': 'number'},
        {'key': 'copper_per_ton', 'label': '铜剂吨耗(kg)', 'type': 'number'},
    ],
    'hot_roll': [
        {'key': 'hot_roll_emulsion_per_ton', 'label': '热轧乳液吨耗(kg)', 'type': 'number'},
    ],
    'cold_roll': [
        {'key': 'rolling_oil_per_ton', 'label': '轧制油吨耗(kg)', 'type': 'number'},
        {'key': 'filter_agent_per_ton', 'label': '飞滤剂吨耗(kg)', 'type': 'number'},
        {'key': 'diatomite_per_ton', 'label': '硅藻土吨耗(kg)', 'type': 'number'},
        {'key': 'white_earth_per_ton', 'label': '白土吨耗(kg)', 'type': 'number'},
        {'key': 'filter_cloth_daily', 'label': '滤布日用(米)', 'type': 'number'},
        {'key': 'high_temp_tape_daily', 'label': '高温胶带日用(卷)', 'type': 'number'},
        {'key': 'regen_oil_out', 'label': '再生油出(kg)', 'type': 'number'},
        {'key': 'regen_oil_in', 'label': '再生油回(kg)', 'type': 'number'},
    ],
    'finishing': [
        {'key': 'rolling_oil_per_ton', 'label': '轧制油吨耗(kg)', 'type': 'number'},
        {'key': 'd40_per_ton', 'label': 'D40吨耗(kg)', 'type': 'number'},
        {'key': 'steel_plate_per_ton', 'label': '钢板吨耗(kg)', 'type': 'number'},
        {'key': 'steel_strip_per_ton', 'label': '钢带吨耗(kg)', 'type': 'number'},
        {'key': 'steel_buckle_per_ton', 'label': '钢带扣吨耗(kg)', 'type': 'number'},
        {'key': 'high_temp_tape_daily', 'label': '高温胶带日用(卷)', 'type': 'number'},
    ],
}
```

验证：`python -c "from app.core.workshop_templates import CONSUMABLE_OWNER_FIELDS; print(len(CONSUMABLE_OWNER_FIELDS))"` 输出 4

---

## Phase 2：移动端路由与角色分流（前后端）

### 2.1 后端 bootstrap 接口按角色返回 entry_mode

文件：`backend/app/services/mobile_report_service.py`

- `get_mobile_bootstrap` 根据 user.role 返回不同 entry_mode：
  - `shift_leader` / `OP` → `coil_entry`（按卷录入）
  - `energy_stat` / `maintenance_lead` / `hydraulic_lead` / `consumable_stat` / `qc` / `weigher` → `auxiliary_shift_entry`
  - `utility_manager` / `inventory_keeper` / `contracts` → `owner_daily_entry`
- 返回 role_fields 列表，前端据此渲染表单

### 2.2 前端路由分流

文件：`frontend/src/views/mobile/MobileEntry.vue`

- 根据 bootstrap.entry_mode 路由：
  - `coil_entry` → 新建 `CoilEntryWorkbench.vue`
  - `auxiliary_shift_entry` → 复用 `DynamicEntryForm.vue` 的 owner-only 模式（按角色裁剪字段）
  - `owner_daily_entry` → 复用 `DynamicEntryForm.vue` 的 owner-only 模式（已有 parse3 分屏）

验证：不同角色账号登录后看到不同页面标题

---

## Phase 3：主操按卷录入页面（前端新建）

### 3.1 新建 CoilEntryWorkbench.vue

文件：`frontend/src/views/mobile/CoilEntryWorkbench.vue`

- 顶部状态栏：机台名称、当前班次、业务日期、操作人姓名输入
- 卷列表：本班次已录入卷，显示卷号/合金/规格/投入/产出
- 底部按钮："录入新卷" + "班次汇总预览"
- 单卷录入表单：坯料卷号、合金牌号、输入规格、输出规格、上机时间、下机时间、投入量、产出量、废料量（自动=投入-产出）、备注

### 3.2 后端按卷提交接口

文件：`backend/app/routers/mobile.py`

- `POST /mobile/coil-entry` 写入 WorkOrderEntry
- 自动关联 machine_id（从登录账号绑定设备获取）、shift_id（按时间判定）
- 返回本班次卷列表

### 3.3 班次汇总预览接口

文件：`backend/app/routers/mobile.py`

- `GET /mobile/shift-summary/{business_date}/{shift_id}` 返回本班次汇总：总投入、总产出、总废料、成品率、卷数

验证：主操账号登录 → 录入一卷 → 卷列表更新 → 汇总数据正确

---

## Phase 4：辅助角色表单适配（前端改造）

### 4.1 DynamicEntryForm 按角色裁剪字段

文件：`frontend/src/views/mobile/DynamicEntryForm.vue`

- 电工：只显示电耗(kWh)、气耗(m³)，铸轧车间额外显示按合金系分气耗
- 机修：只显示停机分钟、停机原因
- 液压：只显示液压油32#、液压油46#、齿轮油
- 耗材统计员：根据车间类型动态渲染 CONSUMABLE_OWNER_FIELDS 对应字段
- 质检：按卷录入质检结论、质检备注
- 称重员：按卷核实投入量、核实产出量

### 4.2 后端辅助角色提交写入

文件：`backend/app/services/mobile_report_service.py`

- 电工/机修/液压/耗材统计员 → 写入 MobileShiftReport 对应字段
- 耗材统计员动态字段 → 写入 MobileShiftReport.extra_payload
- 质检/称重员 → 写入 WorkOrderEntry 对应 qc_*/verified_* 字段

验证：各角色账号登录 → 只看到自己的字段 → 提交成功 → 数据落库正确

---

## Phase 5：全厂级 Owner 分屏落地

### 5.1 确认 parse3 分屏配置生效

文件：`backend/app/core/workshop_templates.py` 中已有 UTILITY_OWNER_FIELDS、INVENTORY_OWNER_FIELDS、CONTRACT_PROGRESS_FIELDS

- 确认 DynamicEntryForm 的 owner-only 模式正确按三段分屏渲染
- utility_manager：用电 → 天然气 → 用水
- inventory_keeper：今日入库 → 今日发货 → 结存与备料
- contracts：当日合同 → 月累计与余合同 → 投料与坯料

验证：三类全厂 owner 账号登录 → 看到正确分屏 → 提交成功

---

## Phase 6：QR 码登录流程改造

### 6.1 车间 QR 码扫码跳转

文件：`frontend/src/views/mobile/MobileEntry.vue`

- 解析 URL 参数 `?qr=XT-{workshop}-WS`
- 跳转登录页并自动填入车间参数
- 登录成功后根据角色路由到对应页面

验证：扫车间 QR 码 → 跳转登录 → 输入账号密码 → 进入对应角色页面

---

## 实施优先级

今天让 owner 开始测试的最短路径：

1. **Phase 0.1 + 0.2**：补角色、建账号（30min）
2. **Phase 2.1 + 2.2**：路由分流让不同角色看到不同页面（30min）
3. **Phase 5.1**：确认全厂 owner 分屏已生效（15min）
4. **Phase 4.1 + 4.2**：辅助角色字段裁剪（1h）
5. **Phase 1.1**：耗材统计员字段定义（30min）
6. **Phase 3**：主操按卷录入（2h，可后续迭代）
7. **Phase 0.3 + 6.1**：QR 码（1h，可后续迭代）

总计约 5-6 小时。Phase 0-2 + Phase 5 完成后，全厂级 owner 即可开始测试。
