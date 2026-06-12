# 鑫泰铝业 数据中枢：第一阶段 TDD 修复作业单

日期：2026-06-11

状态：可执行前置计划。下一轮如进入实现，应先按本清单写测试，再做小范围修复。

## 1. 第一阶段只解决什么

第一阶段目标不是重构全站，也不是先做更炫的实时大屏，而是先让核心数字可信、状态可懂、测试能防回退。

只做 6 类问题：

1. 实时大屏把“加载中/未同步”显示成 0 的风险。
2. 异常废料和异常成品率不能直接上主屏。
3. 能耗有明细但产量分母为 0 时，不能显示成真实 0 吨耗。
4. 库存去向的 `tons` 单位必须确认，不能把 kg 当吨。
5. 合同页履约率、延期、交付量口径不能互相矛盾。
6. MES 的 PC/WAN/一体机设备名不能强行归属到机列。

## 2. 不做清单

这一阶段先不做：

1. 不做大规模 UI 重构。
2. 不删除页面、接口、数据表。
3. 不让前端直接连 SQL Server 或物联网库。
4. 不把填报明细页改成卷级线索页。
5. 不把合同页、库存页直接放进主导航。
6. 不在没有绑定证据时自动把 PC/WAN 归到某台机。

## 3. 修复任务 1：实时大屏 0 值状态

### 现象

线上 `/manage/live` 短等待时曾显示：

- MES 包装产量 `0 吨`
- 内勤入库填报 `0 吨`
- 过站下机 `0 吨`
- 总电耗 `0 kWh`
- 机列 `0 台`

但同一业务日接口可返回 MES 包装产量 `177.61 吨`。

### 涉及代码

| 类型 | 文件 |
| --- | --- |
| 前端格式函数 | `frontend/src/utils/liveDashboardPhase2.js` |
| 前端聚合界面 | `frontend/src/views/manage/live/LiveDashboardPage.vue` |
| 前端测试 | `frontend/tests/manageLivePhase2.test.js` |
| 后端接口 | `backend/app/routers/realtime.py` |
| 后端服务 | `backend/app/services/realtime_service.py` |

### TDD 顺序

1. 先在 `frontend/tests/manageLivePhase2.test.js` 加测试：当字段缺失时，指标显示 `待同步` 或 `暂无可信数据`，不能显示 `0 吨`。
2. 再改 `formatTrustedMetric` 或新增状态格式函数，区分“真实 0”和“缺失值”。
3. 再给 `buildLiveTickerItems` 加测试：`packaging_output=0` 是真实 0，字段不存在是待同步。
4. 最后用浏览器打开 `/manage/live`，等待 `data-testid="manage-live"`，不使用 `networkidle` 作为完成标准。

### 验收

- 接口还没回来时，不显示全 0。
- 字段真实为 0 时，可以显示 0，但要保留来源。
- QA 不再因为 SSE 长连接误判页面超时。

## 4. 修复任务 2：异常废料和成品率隔离

### 现象

接口曾返回：

- `input=106490.53`
- `scrap=105145.3`
- `yield_rate=1.24`

这类值如果直接上实时大屏，会让管理层误判生产异常。

### 涉及代码

| 类型 | 文件 |
| --- | --- |
| 后端实时服务 | `backend/app/services/realtime_service.py` |
| 后端聚合契约测试 | `backend/tests/test_realtime_service.py` |
| 后端轻量契约测试 | `backend/tests/test_realtime_service_contract.py` |
| 前端实时大屏工具 | `frontend/src/utils/liveDashboardPhase2.js` |

### TDD 顺序

1. 先写后端测试：构造投料很大、废料接近投料、成品率极低的数据。
2. 断言异常值进入 `data_quality`，主屏 `factory_total` 不直接采用异常废料/成品率。
3. 再写前端测试：如果后端标记异常隔离，页面显示“异常隔离”而不是普通数值。
4. 最后浏览器验证 `/manage/live` 和 `/manage/today` 都能解释异常来源。

### 验收

- 异常值不进入主指标。
- 用户能看到异常被隔离的原因。
- 原始数据仍可追溯，不删除。

## 5. 修复任务 3：能耗分母为 0

### 现象

线上 `/manage/energy` 有 6 条能耗记录，例如电耗、气耗都存在，但 `output_weight=0`，`energy_per_ton=null`。页面当前会显示“单吨峰值 0”，容易误读。

### 涉及代码

| 类型 | 文件 |
| --- | --- |
| 后端能耗服务 | `backend/app/services/energy_service.py` |
| 后端能耗路由测试 | `backend/tests/test_energy_summary.py` |
| 前端能源中心 | `frontend/src/views/energy/EnergyCenter.vue` |
| 前端 Stitch 映射 | `frontend/src/utils/stitchManageSurface.js` |

### TDD 顺序

1. 先在 `backend/tests/test_energy_summary.py` 加测试：有能耗、无产量时 `energy_per_ton` 必须为 `null`。
2. 再在前端测试中断言：`energy_per_ton=null` 显示为“无产量分母”或 `—`，不能显示 0。
3. 再改 `EnergyCenter.vue` 或 `buildEnergyStitchSurface` 的格式规则。
4. 最后浏览器验证 `/manage/energy`：总能耗有值，单吨能耗显示为分母缺失。

### 验收

- 有能耗不等于有吨耗。
- 无产量分母时，不出现“0 kgce/吨”这种误导。
- 未来接物联网库时仍复用同一规则。

## 6. 修复任务 4：库存去向单位

### 现象

线上 `/manage/factory/destinations` 显示：

- 在制 `330735.5`
- 1373 卷
- 已分配 `70436`
- 12 卷

页面标题容易让人理解为吨，但数值过大，必须确认 `tons` 是否真的是吨。

### 涉及代码

| 类型 | 文件 |
| --- | --- |
| 后端库存去向服务 | `backend/app/services/factory_command_service.py` |
| 关键函数 | `_weight`、`list_destinations` |
| 后端测试 | `backend/tests/test_factory_command_service.py` |
| 前端页面 | `frontend/src/views/factory-command/DestinationScreen.vue` |

### TDD 顺序

1. 先在 `backend/tests/test_factory_command_service.py` 加测试：`net_weight=1000` 如果来自 MES kg 字段，应输出 `1 吨`；如果字段已经是吨，应保持 `1000 吨`，两种来源必须有明确字段区分。
2. 检查 `MesCoilSnapshot` 模型字段到底是 `net_weight` 还是 `net_weight_tons`。
3. 如果当前字段语义不清，先给接口增加 `unit` 或 `weight_unit`，不要只改前端展示。
4. 前端显示时带单位来源，例如“MES 投影 · 单位已折吨”。

### 验收

- `tons` 名字和真实单位一致。
- 页面不再把疑似 kg 的大数直接显示为吨。
- 合并到实时大屏或卷级线索页前，单位已被测试锁住。

## 7. 修复任务 5：合同页指标矛盾

### 现象

线上 `/manage/contracts` 显示：

- 活跃合同 274
- 履约率 100%
- 延期预警 269
- 本月交付量 4444 吨

同时表格里大量合同合同量为 0、已交付为 0、状态延期。

### 涉及代码

| 类型 | 文件 |
| --- | --- |
| 后端合同路由 | `backend/app/routers/contracts.py` |
| 后端测试 | `backend/tests/test_inventory_contract_routes.py` |
| 合同投影服务 | `backend/app/services/contract_canonical_service.py` |
| 合同进度服务 | `backend/app/services/contract_progress_projection_service.py` |
| 前端页面 | `frontend/src/views/contracts/ContractsCenter.vue` |

### TDD 顺序

1. 先在 `backend/tests/test_inventory_contract_routes.py` 加测试：当合同总量全为 0 且延期很多时，履约率不能显示 100%。
2. 明确 `fulfillment_pct` 的分母：只统计合同量大于 0 的合同，或者返回 `null` 表示不可计算。
3. 如果合同量为 0，前端显示“缺合同吨数”，不要显示 0 吨合同仍延期。
4. 合同页在修好前保持隐藏/非核心入口。

### 验收

- `fulfillment_pct=100` 只在真的完成时出现。
- 合同量缺失时能显示“口径缺失”，不是假进度。
- 延期数量和履约率不会互相打架。

## 8. 修复任务 6：MES PC/WAN 机列匹配

### 现象

线上 `/api/v1/mes/supplement-readiness?limit=100` 显示：

- `machine_match_rate=83.33%`
- `generic_terminal_count=64`
- `unmatched_count=6`
- 未匹配集中在 `精整新19辊（WAN）`

### 涉及代码

| 类型 | 文件 |
| --- | --- |
| MES 补录就绪服务 | `backend/app/services/mes_supplement_readiness_service.py` |
| 后端测试 | `backend/tests/test_mes_supplement_readiness_service.py` |
| MES 同步服务 | `backend/app/services/mes_sync_service.py` |
| 系统设置页 | `frontend/src/views/manage/admin/SystemSettingsPage.vue` |

### TDD 顺序

1. 先补测试：`PC` 包装终端不阻断匹配，已有测试保留。
2. 新增测试：`精整新19辊（WAN）` 这类设备名如果没有绑定，必须进入 `unmatched_devices`，不能自动归属。
3. 设计终端绑定表之前，先输出“绑定候选线索”：设备名、工序、车间、操作员、IP 或 source payload。
4. 前端设置页显示“待绑定终端”列表，而不是只显示百分比。

### 验收

- 通用 PC 不误归属。
- WAN 未匹配能被管理端看到。
- 绑定前不影响人工填报。
- 绑定后可追溯匹配原因。

## 9. 浏览器 QA 标准

实时页因为 SSE 长连接，不能用“网络完全静止”判断页面加载完成。

统一 QA 等待规则：

| 页面 | 等待点 |
| --- | --- |
| `/manage/live` | `data-testid="manage-live"` 出现，并至少一个 KPI 卡完成渲染 |
| `/manage/today` | `data-testid="manage-today"` 和 `today-command-wall` 出现 |
| `/manage/energy` | `data-testid="energy-center-page"` 和 `energy-center-table` 出现 |
| `/manage/fill-details` | `data-testid="manage-fill-details"` 出现 |
| `/manage/workshop-dashboard` | `data-testid="workshop-dashboard"` 出现 |

验收时要记录：

1. 页面是否能打开。
2. 页面是否登录态稳定。
3. 页面是否出现接口失败提示。
4. 是否有请求被取消但不影响当前页面。
5. 核心数字是否和接口一致。

## 10. 三视角评分

### CEO 视角

评分：9.8/10。

原因：第一阶段抓住了最影响管理决策的 6 个问题，先解决“数字能不能信”，比先美化页面更有业务价值。

### 工程视角

评分：9.7/10。

原因：每个问题都有测试文件、代码文件、验收标准，且改动边界小。扣分点是库存单位还需要进一步确认模型字段语义。

### 设计视角

评分：9.7/10。

原因：先统一状态语言，再做页面重构，能减少用户误读。扣分点是还缺具体页面视觉稿。

### 安全视角

评分：9.8/10。

原因：不直连外部库、不删数据、不自动误归属机列，风险控制较好。

### 真实用户视角

评分：9.7/10。

原因：修完后用户会更清楚“现在是没数据、加载中、异常、还是确实为 0”。扣分点是还需要真实机台二维码复测。

综合：9.74/10。

## 11. 进入实现前的门禁

允许进入实现前，必须满足：

1. 先提交或保存当前审计文档，避免计划丢失。
2. 每个修复项先写失败测试。
3. 每次只改一个问题域，不把合同、能耗、实时大屏混在一个大改里。
4. 修完后至少跑对应后端测试、前端测试和浏览器页面抽查。
5. 如果测试显示现有业务口径和预期不一致，先回到计划确认，不直接硬改。
