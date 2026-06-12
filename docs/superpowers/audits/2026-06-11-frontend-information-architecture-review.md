# 前端信息架构与页面保留审计

日期：2026-06-11

范围：管理端路由、左侧导航、页面文件、API 入口、页面保留/合并/隐藏建议。

## 1. 小白版结论

现在前端不是“没有页面”，而是“页面太多、历史入口太多、核心任务不够集中”。用户真正每天要做的事情大概是：

1. 看今天或昨天全厂生产是否正常。
2. 查某卷料现在在哪、有没有异常。
3. 看哪些车间、机列、责任人缺填报。
4. 看能耗、产量、成品率这些核心指标。
5. 管理基础资料、账号、规则和终端绑定。

所以管理端应该继续收敛成“调度、日报、生产、卷级线索、填报明细、能耗、异常、设置”这条主线，而不是把库存、合同、考勤、报表、旧 review 页面都平铺在主导航里。

## 2. 本轮证据

### 2.1 路由和导航证据

| 证据 | 结果 |
| --- | --- |
| `frontend/src/router/index.js` 路由 path 数量 | 143 个 |
| `frontend/src/router/index.js` 命名路由数量 | 78 个 |
| `frontend/src/config/manage-navigation.js` 导航项数量 | 13 个 |
| `frontend/src/views` Vue 页面文件数量 | 84 个 |
| `frontend/src/api` API 模块数量 | 24 个 |

关键行号：

| 文件 | 行号 | 说明 |
| --- | ---: | --- |
| `frontend/src/router/index.js` | 111 | `/manage` 管理端主路由入口 |
| `frontend/src/router/index.js` | 116 | `/manage/live` 实时调度墙 |
| `frontend/src/router/index.js` | 119 | `/manage/today` 昨日报表 |
| `frontend/src/router/index.js` | 120 | `/manage/production` 生产分析 |
| `frontend/src/router/index.js` | 127 | `/manage/factory/destinations` 库存去向 |
| `frontend/src/router/index.js` | 141 | `/manage/inventory` 库存出入中心 |
| `frontend/src/router/index.js` | 142 | `/manage/contracts` 合同与订单中心 |
| `frontend/src/router/index.js` | 157 | `/review` 旧入口跳到 `/manage/today` |
| `frontend/src/router/index.js` | 210 | `/imports/files` 已停用并跳设置 |
| `frontend/src/router/index.js` | 214 | `/attendance/detail/:employeeId/:businessDate` 独立详情页 |
| `frontend/src/config/manage-navigation.js` | 11 | 车间主任专用导航组 |
| `frontend/src/config/manage-navigation.js` | 21 | 窄屏只保留 5 个核心入口 |
| `frontend/src/config/manage-navigation.js` | 23 | 普通管理端导航组 |
| `frontend/src/config/manage-navigation.js` | 53 | `考勤预留` 仍在导航 |
| `frontend/src/config/manage-navigation.js` | 63 | `系统设置` 已在导航 |

### 2.2 页面体量证据

当前最大的页面文件：

| 行数 | 页面 | 风险 |
| ---: | --- | --- |
| 4029 | `frontend/src/views/reports/LiveDashboard.vue` | 旧大屏页面体量很大，需确认是否还被真实入口依赖 |
| 1734 | `frontend/src/views/manage/today/TodayPage.vue` | 日报页很大，后续改口径要先保测试 |
| 1570 | `frontend/src/views/mobile/UnifiedEntryForm.vue` | 手机统一填报页复杂，不能贸然删字段 |
| 1446 | `frontend/src/views/mobile/CoilEntryWorkbench.vue` | 按卷补录页复杂，且直接调用 3 个接口 |
| 1176 | `frontend/src/views/manage/fill-details/FillDetailsPage.vue` | 填报明细页承担了较多对照信息 |
| 1044 | `frontend/src/views/energy/EnergyCenter.vue` | 能耗页已有完整 UI，但需要继续修数据来源状态 |

### 2.3 直接接口调用证据

这些页面绕过 `frontend/src/api` 模块，直接 `api.get/post`：

| 页面 | 直接调用 |
| --- | --- |
| `frontend/src/views/contracts/ContractsCenter.vue` | `/contracts/summary`、`/contracts/export` |
| `frontend/src/views/inventory/InventoryCenter.vue` | `/inventory/summary`、`/inventory/export` |
| `frontend/src/views/mobile/CoilEntryWorkbench.vue` | `/mobile/coil-flow-suggestion`、`/mobile/coil-list/...`、`/mobile/coil-entry` |

影响：短期不一定出错，但长期会让接口契约测试、权限审计、错误提示、超时处理变散。

### 2.4 卷级线索证据

后端和 API 已经有卷级能力：

| 文件 | 行号 | 能力 |
| --- | ---: | --- |
| `frontend/src/api/factory-command.js` | 18 | `fetchFactoryCommandCoils()` |
| `frontend/src/api/factory-command.js` | 24 | `fetchFactoryCommandCoilFlow()` |
| `backend/app/routers/factory_command.py` | 57 | `GET /factory-command/coils` |
| `backend/app/routers/factory_command.py` | 79 | `GET /factory-command/coils/{coil_key}/flow` |

但当前真实文件系统里 `frontend/src/views/factory-command` 只剩：

1. `DestinationScreen.vue`
2. `FactoryCommandShell.vue`

说明：卷级线索页不是“修旧页面”，而是需要正式新增 `/manage/coils`。

## 3. 页面分类建议

### 3.1 核心保留并继续打磨

| 页面 | 建议 | 原因 |
| --- | --- | --- |
| `/manage/live` | 保留，升级为实时生产流转大屏 | 是全厂调度第一入口 |
| `/manage/today` | 保留，作为昨日报表和日报口径入口 | 管理层每天要看 |
| `/manage/production` | 保留，但和日报明确分工 | 更适合做生产分析，不要重复日报 |
| `/manage/fill-details` | 保留 | 专门看人工填报、责任人、时间、内容 |
| `/manage/energy` | 保留 | 后续接物联网能耗库也要落这里 |
| `/manage/workshop-dashboard` | 保留 | 车间主任和管理端都需要 |
| `/manage/alerts` | 保留 | 异常、缺报、差异核对需要统一入口 |
| `/manage/admin/settings` | 保留 | 系统健康、MES、终端绑定、配置入口 |
| `/manage/admin/users` | 保留 | 账号权限治理入口 |
| `/manage/master` | 保留 | 车间、机列、基础资料入口 |
| `/manage/alias` | 保留，但后续不要承载 PC 终端绑定 | 别名适合标准化名称，不适合复杂绑定 |

### 3.2 应新增为核心入口

| 新页面 | 建议路径 | 原因 |
| --- | --- | --- |
| 卷级线索 | `/manage/coils` | 用户最常要查“这卷料在哪、走过什么工序、有没有缺补录/异常” |
| 终端绑定清单 | 可放 `/manage/admin/settings` 内，也可后续独立 | PC/WAN/一体机到机列的绑定是 MES 主账可信的前提 |

### 3.3 可合并或降级

| 页面 | 建议 | 原因 |
| --- | --- | --- |
| `/manage/factory/destinations` | 合并到 `/manage/coils` 或 `/manage/live` | 它本质是卷和库存去向，不应单独散落 |
| `/manage/inventory` | 合并到卷级线索或库存卡片 | 当前如果数据不足，独立页面会像空壳 |
| `/manage/reports` | 合并到 `/manage/today` 的历史日报/导出区域 | 报表页和日报页职责重叠 |
| `/manage/attendance` | 降级到系统预留区 | 当前页面标题就是“考勤预留”，钉钉未接入前不应占主导航 |
| `/manage/contracts` | 暂时隐藏或移到二级入口 | 合同指标若不稳定，会干扰生产主线判断 |

### 3.4 详情页保留，但不放主导航

| 页面 | 建议 | 原因 |
| --- | --- | --- |
| `/attendance/detail/:employeeId/:businessDate` | 保留为详情页 | 只能从考勤/异常上下文进入 |
| `/shift/detail/:id` | 保留前先修空状态/404 提示 | 不能让用户看到像坏掉的页面 |
| `/manage/reconciliation/detail/:id` | 保留为异常差异详情 | 从异常处理页进入 |
| `/manage/quality/detail/:id` | 保留为质量详情 | 从异常处理页进入 |

### 3.5 已停用或历史兼容入口

| 入口 | 建议 |
| --- | --- |
| `/imports/files`、`/imports/history` | 保持跳转到设置页，不恢复导入功能 |
| `/review/*` | 保持兼容跳转，不作为新 UI 主入口 |
| `/admin/templates`、`/manage/admin/templates` | 保持跳设置页，模板中心不再作为产品功能 |
| `/mobile/*` 老路径 | 保持跳 `/entry/*`，保护旧二维码 |

## 4. 主要问题清单

### P1：缺少 `/manage/coils` 正式卷级线索页

问题：后端已有卷级接口，但管理端没有正式卷级线索入口。

影响：用户想查某卷料，只能在填报明细、实时页、库存去向之间来回找。

建议：新增 `/manage/coils`，先接现有 `factory-command` 卷接口，第一版只做搜索、列表、详情抽屉。

### P1：核心页面对“无数据、加载中、真实 0、异常隔离”的状态语言还需统一

问题：不同页面里 `0`、`—`、`暂无可信数据`、`同步中` 的含义不一致。

影响：用户会分不清是系统没同步、接口失败，还是当天真实为 0。

建议：建立统一状态字典，并把实时页、日报页、生产页、能耗页、填报明细页一起套进去。

### P2：导航里仍有预留或弱业务页面

问题：`考勤预留` 仍在主导航；库存、合同、报表等页面也容易分散用户注意力。

影响：现场用户会点进空页面或半成品页面，以为系统坏了。

建议：主导航只放高频核心任务；预留页放到设置/系统健康里。

### P2：旧页面和新页面边界不清

问题：旧 `reports/LiveDashboard.vue` 体量 4029 行，但当前主路由 `/manage/live` 用的是新页面。

影响：后续维护人员可能改错页面，造成“本地改了，线上没变化”的错觉。

建议：先做依赖追踪，确认无入口后再标记为 legacy 或删除。

### P2：部分页面直接调用接口

问题：合同、库存、按卷补录页直接 `api.get/post`，没有统一 API 模块封装。

影响：后续做接口契约测试、错误提示、权限边界时容易漏掉。

建议：逐步迁移到 `frontend/src/api/*.js`，不在本轮硬改。

## 5. 推荐信息架构

### 5.1 普通管理端主导航

建议收敛为 8 个主入口：

1. 实时调度：`/manage/live`
2. 昨日报表：`/manage/today`
3. 生产分析：`/manage/production`
4. 卷级线索：`/manage/coils`
5. 填报明细：`/manage/fill-details`
6. 能耗中心：`/manage/energy`
7. 异常处理：`/manage/alerts`
8. 系统设置：`/manage/admin/settings`

### 5.2 管理配置入口

建议放到系统设置或系统组：

1. 基础资料：`/manage/master`
2. 终端绑定：先放 `/manage/admin/settings`
3. 别名映射：`/manage/alias`
4. 账号权限：`/manage/admin/users`
5. 业务规则：`/manage/admin/rules`

### 5.3 暂不放主导航

1. 合同与订单：等指标口径稳定后再提升。
2. 库存出入：并入卷级线索。
3. 报表中心：并入昨日报表。
4. 考勤预留：等钉钉接入后再提升。

## 6. 执行顺序

### 第一步：只新增，不删除

1. 新增 `/manage/coils`。
2. 在导航增加“卷级线索”。
3. 使用已有卷列表/卷流向接口。
4. 不删除旧页面，避免误伤。

### 第二步：统一状态语言

1. 统一真实 0。
2. 统一未同步。
3. 统一加载中。
4. 统一异常隔离。
5. 统一无产量分母。

### 第三步：页面合并灰度

1. 库存去向并入卷级线索。
2. 报表中心并入昨日报表。
3. 考勤预留移出主导航。
4. 合同页先隐藏或移入二级入口。

### 第四步：删除前做依赖追踪

任何删除必须先确认：

1. 路由没有入口。
2. 导航没有入口。
3. 其他页面没有跳转。
4. 测试不依赖。
5. 线上用户路径不依赖。

## 7. 验收标准

1. 管理端主导航能覆盖所有高频任务。
2. `/manage/coils` 可以按随行卡、批号、客户、合金、规格搜索。
3. 用户能区分 MES 数据、人工填报数据、算法计算数据。
4. 预留页不再伪装成核心功能页。
5. 旧入口仍能跳转，不影响旧二维码和旧收藏链接。
6. 页面状态不再把“没同步”显示成真实 0。

## 8. 三视角评分

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.7 | 主线从“页面很多”收敛到“调度、日报、卷级、异常、能耗” |
| 工程 | 9.7 | 先新增卷级页、再灰度合并、最后删除，风险可控 |
| 设计 | 9.6 | 用户路径更清楚，但还需要后续配合真实浏览器截图继续打磨 |

综合：9.67/10。

## 9. 下一步

下一轮最推荐做两件事：

1. TDD 新增 `/manage/coils` 最小可用页。
2. 给实时页、日报页、生产页、能耗页统一状态语言。

这两件事做完后，再开始合并库存、报表、考勤这些弱业务页面。
