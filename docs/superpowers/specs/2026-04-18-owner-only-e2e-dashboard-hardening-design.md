# Owner-Only E2E And Dashboard Hardening Design

## 背景

Phase 1 已经把 `contracts / inventory_keeper / utility_manager` 三类专项 owner 接入移动端高级填报，但后续要保证三件事同时成立：

1. 角色能真实提交，不是假闭环
2. dashboard API 有稳定契约，不靠聊天约定
3. 页面和 smoke 测试能跟着当前真实 UI 走，不被过时断言拖垮

## 设计

### 1. 数据入口

- owner-only 继续统一写入 `WorkOrderEntry.extra_payload`
- 不再为专项 owner 另建专属存储表
- 汇总层通过 source precedence 和 fallback 识别 owner-only 数据

### 2. API 契约

- `LeaderMetricsOut` 承认：
  - `shipment_weight`
  - `storage_inbound_area`
  - `active_contract_count`
  - `stalled_contract_count`
  - `active_coil_count`
  - `sync_lag_seconds`
- `WorkshopDashboardResponse` 先承认关键块：
  - `mobile_reporting_summary`
  - `reminder_summary`
  - `energy_summary`
  - `energy_lane`
  - `inventory_lane`
  - `exception_lane`

这是一层最小 typed contract，为后续 lane item typed 化预留接口。

### 3. UI 露出

- 厂长驾驶舱继续承担总览：
  - 今日发货
  - 入库面积
  - 合同量
- 车间主任看板补专项 owner 结果：
  - 顶部卡片：今日发货 / 入库面积 / 实际库存
  - 能耗泳道：来源 / 用水
  - 库存泳道：入库面积 / 实际库存

### 4. 测试策略

- Playwright 以真实账号、真实排班、真实响应跑 smoke
- 提交成功以 API 响应作为证据，不再依赖不稳定 toast
- 默认串行执行 Playwright，减少共享 DB 状态下的抖动

## 后续升级口

1. 把 `WorkshopDashboardResponse` 从关键块 typed 推进到 lane item typed
2. 继续补 `contracts / utility_manager` 的更细字段在车间主任看板的二级摘要卡
3. 在 owner-only 页面上补更稳的显式 data-testid，减少 E2E 对按钮顺序的依赖
