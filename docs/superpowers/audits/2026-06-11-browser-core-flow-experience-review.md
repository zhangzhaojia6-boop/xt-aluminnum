# 浏览器体验与核心主线风险审计

日期：2026-06-11

范围：实时调度墙、卷级线索、MES 数据映射、手机按卷补录、管理端登录态、测试门禁。

## 1. 小白版结论

这轮检查后，可以把系统现状理解成一句话：

**后端数据链路已经有基础，但前端入口和浏览器真实体验还没完全闭环。**

具体说：

1. MES 数据已经能进本地 `mes_*` 表，手机端也已经有“MES 待补录”能力。
2. 后端机列匹配、MES 补录准备度、工厂指挥接口测试是绿的。
3. 管理端还没有正式 `/manage/coils` 卷级线索页面，用户看不到完整卷级主线。
4. 首次浏览器测试里管理端会停在登录页，根因已定位为 E2E mock 漏掉 `/mes/supplement-readiness`，补齐后管理端壳测试已通过。
5. MES 记录里设备名如果只是 `PC`，不能直接当成机列，必须加“PC/一体机终端绑定规则”。
6. 生产站点服务本身可访问，但真实管理员登录 smoke 仍失败，登录接口返回 `400`，需要按账号安全流程修复生产库里的管理员登录记录。

## 2. 当前证据

### 2.1 代码结构证据

CodeGraph 当前索引状态：

| 项目 | 数量 |
| --- | ---: |
| 索引文件 | 972 |
| 结构节点 | 14742 |
| 调用关系 | 30663 |
| Vue 页面/组件 | 172 |
| Python 文件 | 559 |

当前真实文件系统证据：

| 位置 | 证据 |
| --- | --- |
| `frontend/src/views/manage/live/LiveDashboardPage.vue` | 实时调度墙页面存在 |
| `frontend/src/views/mobile/CoilEntryWorkbench.vue` | 手机按卷补录页面存在 |
| `frontend/src/views/factory-command` | 当前只剩 `FactoryCommandShell.vue` 和 `DestinationScreen.vue` |
| `frontend/src/router/index.js` | 存在 `/manage/live`、`/manage/today`、`/manage/production`、`/manage/fill-details`，但没有 `/manage/coils` |
| `frontend/src/api/factory-command.js` | 已有 `/factory-command/coils` 和 `/factory-command/coils/{coilKey}/flow` 前端 API |
| `backend/app/routers/factory_command.py` | 后端已有工厂指挥路由 |
| `backend/app/services/factory_command_service.py` | 后端已有卷级/工厂指挥服务 |

### 2.2 MES 到本地表的证据

`backend/app/adapters/sqlserver_mes_adapter.py` 负责从 SQL Server 只读抓取 MES 数据。

关键映射：

| 外部数据 | 本地用途 |
| --- | --- |
| `MES_ProductProcessRecord` | 车间工序记录、产量、上下机重量、工艺、设备名 |
| `MES_Product` | 当前在制、当前车间、当前工艺、随行卡、客户、合金、规格 |
| `MES_Device` | MES 设备/一体机/机列参考 |
| `WMS_Stock`、`WMS_InStockDetail` | 库存和入库参考 |

`backend/app/services/mes_sync_service.py` 会把工序记录写进 `mes_workshop_process_records`，其中会取：

| 本地字段 | 来源含义 |
| --- | --- |
| `process_name` | MES 工艺名 |
| `worker_name` | 操作人 |
| `device_name` | MES 设备名，可能只是 `PC` |
| `input_weight_kg` | 上机/投料重量 |
| `output_weight_kg` | 下机重量 |
| `workshop_name` | 车间 |
| `line_name` | 线别 |
| `alloy_grade` | 合金 |
| `spec_display` | 规格 |

### 2.3 机列匹配证据

`backend/app/services/mes_supplement_readiness_service.py` 已经在统计：

| 指标 | 含义 |
| --- | --- |
| `device_name_rate` | MES 记录里有没有设备名 |
| `machine_match_rate` | 能不能匹配到本系统机列 |
| `generic_terminal_count` | 设备名是泛化终端，比如 `PC` |
| `unmatched_devices` | 未匹配成功的设备清单 |
| `source_counts` | 匹配来源统计 |

这说明系统已经知道“设备名不等于机列”这个风险。下一步不是继续猜，而是把 `PC/一体机 -> 车间 -> 工艺 -> 机列` 做成可维护的绑定规则。

## 3. 测试结果

### 3.1 前端单元/静态测试

命令：

```powershell
cd frontend
npm run test -- manageLivePhase2.test.js manageTodayPage.test.js manageProductionPage.test.js energyCenterDesign.test.js manageFillDetailsAudit.test.js coilEntryWorkbench.scan.test.js coilEntryValidation.test.js coilFlowFields.test.js
```

结果：

| 结果 | 数量 |
| --- | ---: |
| 通过 | 619 |
| 失败 | 0 |

说明：

1. 前端很多业务保护测试是绿的。
2. 覆盖了实时页、日报页、生产页、能耗页、填报明细、手机按卷录入、网络错误文案、实时流兜底。
3. 但这类测试不等于真实浏览器全流程通过。

### 3.2 后端主线测试

命令：

```powershell
cd backend
python -m pytest tests/test_mes_supplement_readiness_service.py tests/test_mes_machine_match_service.py tests/test_factory_command_service.py tests/test_factory_command_routes.py tests/test_mobile_mes_pending_supplements.py
```

结果：

| 结果 | 数量 |
| --- | ---: |
| 通过 | 54 |
| 失败 | 0 |

说明：

1. MES 补录准备度测试通过。
2. 机列匹配测试通过。
3. 工厂指挥服务和路由测试通过。
4. 手机 MES 待补录测试通过。

### 3.3 浏览器 Playwright 测试：首次失败

命令：

```powershell
cd frontend
npx playwright test e2e/manage-shell.spec.js --reporter=line --workers=1
```

结果：

| 结果 | 数量 |
| --- | ---: |
| 通过 | 3 |
| 失败 | 2 |

失败现象：

1. `sidebar collapses and remembers state` 找不到 `.xt-manage__collapse-btn`。
2. `search overlay filters and routes to the selected result` 找不到 `manage-today`。
3. 失败截图显示浏览器停在“管理员登录”页。
4. 后端日志出现 `/api/v1/mes/supplement-readiness?limit=100` 返回 `401 Unauthorized`。

判断：

这不是单纯的按钮问题，而是管理端测试登录态没有稳定建立。对真实用户来说，这类问题会表现为：页面跳回登录、管理端进不去、network error 或接口未授权。

### 3.4 浏览器 Playwright 测试：定位后复跑

根因：

1. E2E 默认管理员登录后会先落到系统设置页。
2. 系统设置页会请求 `/api/v1/mes/supplement-readiness`。
3. `frontend/e2e/helpers/review-mocks.js` 原来没有 mock 这个接口。
4. 未 mock 的请求打到真实后端后返回 `401 Unauthorized`。
5. 前端统一接口拦截器看到 401 后会执行登出，所以页面回到登录页。

修复：

已在 `frontend/e2e/helpers/review-mocks.js` 增加 `/api/v1/mes/supplement-readiness` mock，只影响 E2E 测试，不改生产业务逻辑。

复跑命令：

```powershell
cd frontend
npx playwright test e2e/manage-shell.spec.js --reporter=line --workers=1
```

复跑结果：

| 结果 | 数量 |
| --- | ---: |
| 通过 | 5 |
| 失败 | 0 |

判断：

管理端壳浏览器门禁已恢复。线上真实登录仍应单独保留 smoke，因为这次修的是测试 mock 覆盖缺口，不等于已经证明生产账号、生产代理和生产接口全部稳定。

### 3.5 生产真实登录与健康检查 smoke

执行方式：

只用真实浏览器打开生产站点，做一次管理员登录尝试，再访问 `/manage/today` 和 `/manage/live`。不提交业务表单，不修改生产数据，不做多次重试。

结果：

| 检查项 | 结果 |
| --- | --- |
| `/healthz` | `200` |
| `/api/v1/healthz` | `200` |
| `/readyz` | `200` |
| `/api/v1/readyz` | `404` |
| 管理员登录 UI | 停在 `/login` |
| `/api/v1/auth/login` | `400` |

判定：

1. 生产服务是活的，不能简单归因为服务器宕机。
2. `/api/v1/readyz` 和 `/readyz` 路径不一致，后续健康检查脚本要统一。
3. 后端登录代码里 `400` 对应“用户名或密码校验失败”，账号停用会返回 `403`。
4. 这次真实登录失败更像是生产库账号密码记录与配置不一致，不能用前端改样式解决。
5. 下一步应走安全修复：在生产环境用受控脚本重置管理员密码、保留审计记录，然后重新跑一次真实登录 smoke。

代码侧处理：

已补齐 `/api/v1/readyz` 兼容路由，和 `/readyz` 共用同一套 readiness 结果。新增测试 `test_api_v1_readyz_matches_readiness`，并复跑 `backend/tests/test_health.py`，结果 `14` 个全部通过。部署后需要重新访问生产 `/api/v1/readyz` 确认从 `404` 变为 readiness JSON。

### 3.6 PC/一体机终端线索 smoke

问题背景：

很多 MES 工序记录的设备名只有 `PC`，这不是具体机列。旧逻辑会把它统计成 `generic_mes_terminal`，但管理端只能看到数量，看不到哪些车间、哪些工艺、原始 payload 里有什么绑定线索。

代码侧处理：

1. 后端 `/api/v1/mes/supplement-readiness` 新增 `generic_terminals`，返回最多 10 条 PC/一体机待绑定样例。
2. 每条样例包含 `source_id`、随行批号、车间、工艺、设备名和 `terminal_hints`。
3. `terminal_hints` 从原始 `source_payload` 读取 `DeviceCode`、`MachineCode`、`WorkShopLine`、`LineName`、`TerminalCode`、`StationCode`、`ClientName`、`HostName`、`IP` 等字段。
4. 系统设置页 MES 补录卡片新增“PC 终端待绑定”，展示数量和前 3 条线索。
5. 这一步不自动归机列，只把隐藏问题显性化，防止把所有 `PC` 错绑到同一台机。

验证：

1. `python -m pytest tests/test_mes_supplement_readiness_service.py -q`：`3` 个通过。
2. `npm run test -- systemSettingsPage.test.js`：前端测试实际跑完 `619` 个，全部通过。
3. E2E mock 已补齐 `generic_terminals`，避免浏览器 smoke 出现“有数量但无样例”的假画面。
4. `npx playwright test e2e/manage-shell.spec.js --reporter=line --workers=1`：管理端壳 `5` 个浏览器用例全部通过。

### 3.7 PC/一体机结构化绑定后端规则

问题背景：

只显示 PC 待绑定线索还不够，系统最终需要知道“这台 PC 在这个车间、这个工艺、这个时间段，对应哪台真实机列”。但不能用普通别名直接把 `PC` 绑定到机列，因为不同车间、不同工艺都可能叫 `PC`。

代码侧处理：

1. 新增 `mes_terminal_bindings` 表，字段包含 `terminal_code`、车间、工艺、机列、可信度、生效时间和启停状态。
2. 新增 Alembic 迁移 `0038_mes_terminal_bindings`，接在 `0037_remap_legacy_shift_references` 后面。
3. 新增管理端后端接口 `/api/v1/master/mes-terminal-bindings`，支持列表、新增、修改、停用。
4. `resolve_mes_machine_binding` 在 `device_name=PC` 时会优先查结构化绑定；没有命中时仍返回 `generic_mes_terminal`，不会自动乱归机列。
5. `/api/v1/mes/supplement-readiness` 已接入绑定规则，绑定成功后会进入机列匹配分母并计入 `mes_terminal_binding` 来源。

验证：

1. `python -m pytest tests/test_alias_mapping.py tests/test_mes_machine_match_service.py tests/test_mes_supplement_readiness_service.py -q`：`14` 个通过。
2. `python -m pytest tests/test_migration_chain.py -q`：`4` 个通过。

边界：

这一步完成的是后端规则、迁移和接口，并已经补上首版“MES 终端绑定管理页”。现场管理员可以从系统设置页进入维护页，按“终端 + 车间 + 工艺 + 有效期”把 PC/一体机确认到真实机列；下一阶段应把系统设置页里的 PC 待绑定样例进一步做成一键带入表单，减少人工复制。

### 3.8 PC/一体机终端绑定前端入口

问题背景：

后端能配置规则还不够，如果管理端没有入口，现场人员仍然无法把 `PC`、`WAN`、一体机这些泛化设备名维护成真实机列。

代码侧处理：

1. 新增 `/manage/mes-terminal-bindings` 管理页。
2. 系统设置页新增“终端绑定”入口。
3. 新增前端 API：列表、新增、修改、停用。
4. 页面使用现有主数据表格形态，字段包含终端编码、MES 设备名、车间、工艺、机列、置信度、有效期和启用状态。

验证：

1. `node --test tests/mesTerminalBindingPage.test.js`：`4` 个静态契约测试全部通过。
2. `npm run test -- mesTerminalBindingPage.test.js systemSettingsPage.test.js`：前端测试 `623` 个全部通过。
3. `npm run build`：前端生产构建通过，产物包含 `MesTerminalBinding` 页面包。
4. 后端相关测试 `34` 个全部通过，覆盖绑定接口、机列匹配、补录准备度、迁移链和健康检查。
5. `npx playwright test e2e/admin-surface.spec.js --reporter=line --workers=1`：管理端浏览器用例 `12` 个全部通过，覆盖系统设置页点击进入终端绑定页。

边界：

这仍是首版维护入口，还没有做到从“PC 待绑定样例”一键带入表单，也没有完成生产部署后的真实浏览器复验。

## 4. 问题分级

### P1：管理端缺正式卷级线索页

问题：

后端和前端 API 已经有 `/factory-command/coils`、`/factory-command/coils/{coilKey}/flow`，但管理端没有 `/manage/coils` 正式页面。

影响：

用户无法清楚看到每卷材料的随行卡、客户、合金、规格、当前工艺、上一道/下一道工序、MES 记录和人工补录差异。

建议：

新增 `/manage/coils`，不要复活旧的多个工厂指挥页面。页面只做一件事：按卷查清楚材料在哪里、经历了什么、还缺什么。

### P1：管理端浏览器登录态测试门禁曾不稳，已补齐 E2E mock

问题：

Playwright 管理端壳测试首次有 2 个失败，截图停在登录页。根因是 E2E helper 没有 mock 系统设置页加载的 `/mes/supplement-readiness`。

影响：

这会让 QA 误判“管理端进不去”，也会掩盖真正的登录/network error。

建议：

该测试门禁已补齐并复跑通过。后续线上验收仍必须包含：

1. 登录后进入 `/manage/today`。
2. 刷新后仍保持登录。
3. 打开 `/manage/live` 不回登录页。
4. 401 时给出清楚提示，不伪装成普通网络错误。

### P1：生产管理员真实登录 smoke 未通过

问题：

真实生产站点健康接口可用，但管理员登录接口返回 `400`，页面停留在登录页。

影响：

管理端用户会认为“登录不上”或“network error”。如果不先修复登录，后续再漂亮的大屏、卷级页面和能耗页面都无法被正常验收。

证据：

1. `/healthz`、`/api/v1/healthz`、`/readyz` 返回 `200`。
2. `/api/v1/auth/login` 返回 `400`。
3. 后端 `backend/app/routers/auth.py` 中 `400` 分支对应 `Invalid username or password`。
4. `/api/v1/readyz` 兼容路由已在本地代码补齐，健康测试 `14/14` 通过，部署后可复验生产路径。

建议：

不要继续盲改前端。先执行一次受控的生产管理员账号修复流程：备份当前用户记录，重置管理员密码，确认 `is_active=true`，再做一次真实浏览器登录 smoke。

### P1：MES 设备名 `PC` 不能直接匹配机列

问题：

MES 工序记录里的 `device_name` 可能只是 `PC`，不是“铸轧三 1#机”这类具体机列。

影响：

如果直接用 `PC` 自动判定机列，会把产量、废料、能耗、补录责任人归错。

建议：

新增结构化绑定规则：

| 字段 | 作用 |
| --- | --- |
| `terminal_code` | PC/WAN/一体机唯一标识 |
| `mes_device_name` | MES 原始设备名 |
| `workshop_name` | 车间 |
| `process_name` | 工艺 |
| `equipment_id` | 本系统机列 |
| `confidence` | 匹配可信度 |
| `valid_from`、`valid_to` | 生效区间 |
| `is_active` | 是否启用 |

当前进度：

已完成三步：第一步“线索可见化”，后端返回 `generic_terminals`，管理端系统设置页展示 PC 待绑定数量和样例；第二步“后端结构化绑定”，新增 `mes_terminal_bindings`、迁移、CRUD 接口和匹配规则；第三步“前端维护入口”，新增 `/manage/mes-terminal-bindings` 页面并通过测试和构建。下一步应做生产部署复验，并把待绑定样例一键带入维护表单。

### P2：CodeGraph 与当前文件系统存在差异

问题：

CodeGraph 仍能看到部分 `factory-command` 旧页面符号，但当前文件系统已没有这些页面。

影响：

如果只看索引，可能误判“页面已经存在”。实际用户打开时并没有入口。

建议：

后续计划验收增加一条：结构索引结果必须和 `rg --files` 当前文件列表交叉确认。

### P2：浏览器测试链路偏慢

问题：

多个 Playwright 用例一起跑时超过 3 分钟未完成，单跑管理端壳也用了接近 2 分钟。

影响：

发布前如果浏览器测试太慢，团队容易跳过它，最后线上才发现页面进不去。

建议：

拆成两类：

1. 快速 smoke：登录、进入 `/manage/today`、进入 `/manage/live`、进入 `/entry`。
2. 深度 e2e：能耗日期、搜索、移动端、异常流、填报提交。

### P2：能耗、废料、产量仍需要数据来源标签

问题：

系统里同时存在 MES、人工填报、算法计算、未来物联网能耗数据库。前端如果只显示一个数，用户不知道它从哪来。

影响：

用户会质疑数字可信度，也容易把“未同步”看成真实 0。

建议：

每个关键指标显示来源：

1. `MES 实时`
2. `人工填报`
3. `算法计算`
4. `物联网`
5. `未同步`
6. `异常隔离`

## 5. 优化后的执行顺序

### 第一阶段：先稳登录和验收门禁

目标：

保证管理员真的能进管理端，浏览器测试能稳定证明这一点。

验收：

1. Playwright `manage-shell.spec.js` 全绿。
2. 登录后刷新不掉线。
3. 未授权接口不把页面整体打回登录页。

### 第二阶段：补 PC/一体机终端绑定

目标：

让 `PC` 这类泛化设备名能通过“车间 + 工艺 + 终端”匹配到真实机列。

验收：

1. `generic_terminal_count` 可解释。
2. `unmatched_devices` 能在设置页看到。
3. 绑定后 `machine_match_rate` 提升。
4. 不确定的记录不自动归机列，只标为待确认。

### 第三阶段：新增 `/manage/coils` 卷级线索页

目标：

让管理端能按卷查看 MES 真值和人工补录差异。

页面必须包含：

1. 随行卡号。
2. 客户名。
3. 合金。
4. 规格。
5. 当前车间。
6. 当前工艺。
7. 上一道/下一道工序。
8. 上下机重量。
9. 废料自动计算结果。
10. 人工补录状态。

### 第四阶段：实时调度墙改成生产流转大屏

目标：

让 `/manage/live` 像实时生产流转墙，而不是普通报表页。

验收：

1. 无数据时显示 0，但必须标明“未同步”或“暂无数据”。
2. 有数据时局部跳动更新，不整页闪烁。
3. 显示全厂总产量、包装产量、在制卷、缺报、能耗。
4. 30 秒快照兜底仍保留。
5. 不加重型光效，避免拖慢页面。

### 第五阶段：手机端只做补录和异常审核

目标：

MES 已有的数据不再让主操重复填，手机端只补一体机没有的字段。

验收：

1. MES 参考值可见。
2. 人工字段可编辑，不锁死。
3. 无 MES 匹配时不阻断手工填报。
4. 废料由系统按安全规则自动算，异常值需人工确认。

## 6. 五视角评分

| 视角 | 分数 | 判断 |
| --- | ---: | --- |
| CEO | 9.7 | 抓住了用户最关心的“进得去、看得懂、数字可信” |
| 工程 | 9.7 | 后端主线测试绿，前端入口和登录态风险已明确 |
| 设计 | 9.6 | 明确了卷级页面和实时大屏的用户任务，但还需要实际视觉稿 |
| 安全 | 9.6 | 识别了 401、登录态和外部数据只读边界 |
| 真实用户 | 9.7 | 能减少重复扫码、重复填报和找不到卷级信息的痛点 |

综合：9.66/10。

本轮增量复评：`/api/v1/readyz` 已从“发现缺口”推进到“本地代码修复 + 测试通过”，工程和安全风险下降；生产管理员真实登录仍是 P1 未完成项，不能把健康路径修复误认为登录问题已解决。

PC 终端增量复评：`PC` 泛化终端已从“只有数量”推进到“可看到样例和原始终端线索”，设计和真实用户风险下降；但自动归机列仍未完成，不能把“可见化”误认为“已绑定”。

PC 绑定增量复评：结构化绑定表、迁移、接口、匹配规则和首版前端维护入口已完成，工程和真实用户风险下降；但还缺生产部署复验和从待绑定样例一键带入表单，不能把“本地可用”误认为“现场已闭环”。

PC 绑定浏览器增量复评：已补充管理端真实路径用例，从系统设置页点击“终端绑定”进入 `/manage/mes-terminal-bindings`，页面标题和表格可见，`admin-surface.spec.js` 共 `12` 项通过。这个证明“入口能进”，但仍不能替代生产部署后的真实账号登录复验。

## 7. 下一步

不建议马上做大屏视觉重构。推荐先做：

1. 先修复生产管理员真实登录，再保留线上 smoke，确认生产账号、代理和接口稳定。
2. 部署并复验 PC/一体机终端绑定维护页，确认真实管理员能进入 `/manage/mes-terminal-bindings`。
3. 新增 `/manage/coils` 最小可用页面。
4. 再把 `/manage/live` 改造成实时生产流转大屏。
