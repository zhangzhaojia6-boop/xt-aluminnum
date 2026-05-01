# 在线退火车间新增 + 能耗按机器填报

日期：2026-05-01

## 一、在线退火车间 (ZXTF)

### 车间定义

| 属性 | 值 |
|------|-----|
| code | `ZXTF` |
| name | `在线退火车间` |
| workshop_type | `annealing` |
| 机列数 | 4（1#、2#、3#、4#）|

### 角色

| 角色 | 后缀 | 说明 |
|------|------|------|
| 主操 | OP | 每条机列一个 |
| 电工 | EN | 车间级 |
| 机修 | MT | 车间级 |

### QR 码

生成规则沿用现有模式，存入 Equipment 表（equipment_type = `virtual_role_qr` 或 `virtual_workshop_qr`）：

- 车间级：`XT-ZXTF-WS`
- 角色级：`XT-ZXTF-OP`、`XT-ZXTF-EN`、`XT-ZXTF-MT`
- 机列主操：`XT-ZXTF-1-OP`、`XT-ZXTF-2-OP`、`XT-ZXTF-3-OP`、`XT-ZXTF-4-OP`

### 车间模板

新增 `annealing` workshop_type，在 `workshop_templates.py` 的 `DEFAULT_WORKSHOP_TEMPLATES` 中注册。字段权限复用现有 `FIELD_OWNERSHIP` 体系。

`WORKSHOP_TYPE_BY_WORKSHOP_CODE` 新增映射：`ZXTF` → `annealing`。

## 二、能耗按机器填报（全车间）

### 现状

电工每班次在车间级填写 `electricity_daily`（电耗）和 `gas_daily`（气耗），存储在 `MobileShiftReport` 表。

### 改动

#### 新表：machine_energy_records

```
machine_energy_records
├── id (PK)
├── shift_report_id (FK → mobile_shift_reports.id)
├── machine_id (FK → equipment.id)
├── machine_code (冗余，方便查询)
├── machine_name (冗余，方便展示)
├── energy_kwh (Numeric, nullable)
├── gas_m3 (Numeric, nullable)
├── created_at
└── updated_at
```

#### 字段权限

- `energy_kwh` 和 `gas_m3`：`role_write: ['energy_stat']`，`role_read: ['energy_stat', 'admin', 'manager']`
- 与现有权限体系一致，责任人仍为电工

#### 车间级汇总

`MobileShiftReport` 的 `electricity_daily` 和 `gas_daily` 保留为只读汇总字段，值 = 该班次所有 `machine_energy_records` 的 `energy_kwh` / `gas_m3` 之和。保存/提交时自动计算，不破坏现有报表和统计。

#### 前端交互

电工扫码进入后，系统根据该车间的设备列表（Equipment 表中 workshop_id 匹配的实体设备），展示每台机器一行，每行两个输入框（电耗、气耗）。底部显示汇总合计。

#### 后端 API

- `POST /mobile/report/save` 和 `/mobile/report/submit` 的 payload 新增 `machine_energy_records` 数组字段
- `GET /mobile/current-shift` 返回时包含已保存的 machine_energy_records
- 新增 seed 脚本将 ZXTF 车间及其 QR 码写入数据库

## 三、影响范围

| 层 | 改动文件 |
|----|---------|
| 数据库 | 新增 `machine_energy_records` 表，Alembic migration |
| 后端模型 | `models/energy.py` 或新文件，新增 MachineEnergyRecord |
| 后端模板 | `workshop_templates.py` 新增 annealing 模板和 ZXTF 映射 |
| 后端 API | `routers/mobile.py`、`services/mobile_report_service.py` 处理 machine_energy_records |
| 后端 Schema | `schemas/mobile.py` 新增 MachineEnergyRecord schema |
| Seed 脚本 | 新增 `seed_annealing_workshop.py` 或扩展现有 seed 脚本 |
| 前端 | `MobileEntry.vue` 能耗区域改为按机器列表填报 |
| 前端 API | `api/mobile.js` 适配新字段 |

## 四、不做的事

- 不改动现有车间的模板结构
- 不改动现有报表的汇总逻辑（汇总字段自动兼容）
- 不新增角色类型，复用现有 energy_stat 角色
