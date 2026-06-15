# 鑫泰铝业 数据中枢：系统理解总整合

日期：2026-06-14

这份文档把 `docs/system-understanding-*.md` 的分散理解记录整合到一起，作为后续接手、排查、继续 QA 和制定改造计划的总入口。

重要边界：这不是“全系统逐字符审计已经完成”的证明。它是当前已经验证过的系统地图、证据清单和剩余工作清单。

## 1. 当前完成度判断

按原目标拆开看，当前整体约完成 `98.1%` 左右。

如果只看“系统理解总文档是否足够交接”，当前覆盖度约 `99.97%`。剩下主要是真实提交类端到端填报 QA、机台电耗明细修复验证、每日一录历史统一修复、外部服务真实动作验证、AI 小时简报生产部署验证、understand 全量图谱刷新。

这个比例不是按文件数量机械计算，而是按“能不能拿出证据证明理解和 QA 已经覆盖”来估算。

| 目标项 | 当前状态 | 完成度估算 | 说明 |
|---|---|---:|---|
| 系统身份和产品边界 | 已清楚 | 90% | 系统叫 `鑫泰铝业 数据中枢`，不能叫 MES；MES 是外部数据源 |
| 后端结构和主要 API | 基本清楚 | 76% | 已确认 FastAPI 主入口、246 个路由量级、主要路由分组，也补充确认了 main lifespan 里额外注册的后台任务 |
| 前端路由和核心页面 | 基本清楚 | 89% | 已确认 `/manage/*`、`/entry/*`、旧入口重定向、主要页面、核心页面 API 映射，并完成一轮管理员登录态只读浏览器 QA；已定位生产页过站下机参考字段优先级风险，也确认调度大屏有 MES 同步稳定性可视化区域；已只读验证带用户上下文的工厂机列接口可返回数据 |
| 数据库表和业务分组 | 基本清楚 | 87% | 已确认 90 张模型表和主要业务分组；已用生产机只读脚本核验一个业务日核心字段、页面级服务返回形状、缺报导出工作簿结构、后台任务相关业务表数量、手机端三条真实写库线生产记录形状、逐卷无机列历史残留形状 |
| MES 数据链路 | 基本清楚 | 89% | 已确认 SQL Server 只读同步到本地 `mes_*` 投影，再供页面读取；生产机 `/readyz` 当前显示 `sqlserver/fresh/success`，`mes_sync_run_logs` 已有 4 万多条运行记录，最近多次同步成功 |
| 人工填报链路 | 基本清楚 | 86% | 主操、电工、内勤、补录表已梳理；已用真实角色登录态只读打开填报和历史页；已确认班次填报、逐卷填报、每日一录分别落到 `mobile_shift_reports`、`work_order_entries.mobile_coil`、`work_order_entries.owner_daily`；已用生产样本复现每日一录历史接口不返回的问题；仍需真实提交/保存类流程 QA |
| 能耗链路 | 部分清楚 | 79% | 已确认 2026-06-13 能耗汇总来自手机端填报，吨耗分母用 MES 包装产量；能耗页接口返回形状已核验，生产 `/readyz` 明确显示物联网能耗同步为 `unconfigured`，且 `iot_energy_sync_runs` 当前为 0 条；已确认 `machine_energy_records.energy_kwh` 为 0 的核心原因是机列级电耗未被真实拆分入明细，班次总电耗仍在 `mobile_shift_reports.electricity_daily` |
| 权限和角色边界 | 部分清楚且已修一处风险 | 80% | 管理员、车间主任、手机角色边界清楚；已验证车间主任被限制到本车间看板，手机角色能进填报端；主数据写接口权限已补测试 |
| 外部链接和部署健康 | 基本清楚 | 98% | 已确认 `/healthz`、`/api/v1/healthz`、`/readyz`、`/api/v1/readyz`、Nginx 转发、部署脚本门禁、定时任务注册、MES 同步运行历史、非 MES 后台任务业务落库状态、外部同步健康语义、生产服务状态；已本地修复 AI 小时简报空机列编码兜底，并补强 AI 简报真实链路测试，待提交部署后生产验证；外部通讯治理链路线上尚未配置真实通道 |
| 浏览器 QA 和全角色体验 | 部分完成 | 76% | 已完成管理员管理端和主操、电工、内勤、车间主任真实角色只读浏览器 QA；已用已提交样本核验历史接口；已只读核验缺报导出接口能生成 Excel；还没做真实提交/保存/导出下载人工验收/外发类操作 |
| understand 图谱 | 未完全完成 | 50% | CodeGraph 当前可用；已确认 understand 图谱停在 2026-06-05 旧提交，距当前 HEAD 有 400 个文件变动；全量重建前仍需确认 `.understandignore` |
| 记忆保存 | 持续完成中 | 94% | 多条记忆 note 已保存，总文档已补到真实角色、历史回看、缺报导出、外部通讯、健康检查、MES 同步运行记录、非 MES 后台任务、AI 简报阻塞、understand 图谱边界、手机端真实写库链路、每日一录历史缺口复现、逐卷机列匹配现状、机列级能耗明细断点、AI 主动汇报与钉钉外发闸门、AI 小时简报本地修复和测试补强层面，但最终总记忆仍需在全量 QA 后再沉淀 |

一句话：系统地图已经比较完整，但真正离“完成目标”还差最大的部分是 `全角色真实提交 QA`、`机台电耗明细修复验证`、`每日一录历史统一`、`AI 小时简报生产部署验证`、`外部服务真实动作验证`、`understand 全量图谱刷新`。

## 2. 当前最可靠的系统一句话

`鑫泰铝业 数据中枢` 是一个把外部 MES、人工填报、能耗、日报、异常、权限、AI 助手和钉钉汇报整合起来的生产数据中枢。

它不是 MES 本身。它通过后端同步外部 MES 数据到本地 `mes_*` 投影表，再把这些数据和人工补录、算法指标一起展示到管理端、车间端和手机填报端。

## 3. 系统大链路

```text
用户浏览器
  -> Vue 前端
  -> /api/v1 后端接口
  -> FastAPI 服务层
  -> 本地业务数据库
  -> 本地 mes_* 投影表
  -> 外部 MES SQL Server 只读同步
  -> 管理端看板、手机填报、日报、AI、钉钉
```

前端不直接连接外部 MES 数据库。

后端也不应该把外部 MES 当作唯一现场事实直接暴露给页面，而是先同步、清洗、映射到本地投影表，再和业务规则合并。

## 4. 当前代码底座

CodeGraph 当前索引状态：

| 项 | 数量 |
|---|---:|
| 索引文件 | 1032 |
| 总节点 | 15551 |
| 总边 | 31986 |
| Python 文件 | 593 |
| Vue 文件 | 176 |
| JavaScript 文件 | 254 |
| TypeScript 文件 | 9 |

主要入口：

| 层 | 入口 |
|---|---|
| 后端主入口 | `backend/app/main.py` |
| 后端配置 | `backend/app/config.py` |
| 前端路由 | `frontend/src/router/index.js` |
| 前端 API 客户端 | `frontend/src/api/index.js` |
| 前端管理导航 | `frontend/src/config/manage-navigation.js` |
| 活跃车间口径 | `backend/app/core/active_workshops.py` |
| 业务时间 | `backend/app/core/business_time.py` |
| 权限范围 | `backend/app/core/scope.py`、`backend/app/core/permissions.py` |
| 部署脚本 | `scripts/deploy_systemd_host.sh` |
| Nginx 配置 | `nginx/nginx.conf` |

## 5. 页面入口总图

### 管理端

| 页面 | 作用 | 当前理解状态 |
|---|---|---|
| `/manage/live` | 生产实时大屏、实时流、缺报、MES 状态 | 已梳理数据流，仍需持续浏览器 QA |
| `/manage/today` | 昨日日报工作台 | 已梳理日报和包装产量口径 |
| `/manage/production` | 生产分析、产量、成品率、在制、能耗 | 已梳理核心字段，仍需逐字段核对 |
| `/manage/coils` | 卷级线索、随行卡、客户、合金、规格、当前工艺 | 已梳理方向，仍需真实数据查询 QA |
| `/manage/fill-details` | 人工填报明细 | 已确认不应混入 MES 自动投影 |
| `/manage/energy` | 能耗中心 | 已梳理电工填报和物联网待接入边界 |
| `/manage/alerts` | 异常、缺报、质量、核对差异 | 已修一处日期参数问题，仍需页面 QA |
| `/manage/workshop-dashboard` | 车间主任看板 | 已确认车间主任范围边界 |
| `/manage/admin/settings` | 设置入口集合 | 已确认入口和导航 |
| `/manage/admin/users` | 用户管理 | 已确认后端写操作要求管理员 |
| `/manage/master` | 车间主数据 | 已补主数据写接口管理员兜底 |
| `/manage/alias` | 别名映射 | 已补写接口管理员兜底 |
| `/manage/mes-terminal-bindings` | PC / MES 终端到机列映射 | 已确认配置入口存在 |
| `/manage/ai-assistant` | AI 助手工作台 | 已梳理 AI 调用和治理边界 |
| `/manage/admin/agents` | 智能体治理 | 已梳理外部通讯和审批边界 |

### 手机端

| 页面 | 作用 | 当前理解状态 |
|---|---|---|
| `/entry` | 手机填报入口 | 已梳理角色重定向 |
| `/entry/fill` | 统一填报 | 已梳理主操、电工、内勤入口方向 |
| `/entry/coil` | 按卷补录 | 已梳理 MES 辅助和字段可编辑原则 |
| `/entry/history` | 历史记录 | 已确认应按整日业务口径查看 |
| `/entry/consumables` | 辅材和内勤专项 | 已梳理但仍需真实内勤账号 QA |
| `/entry/attendance` | 考勤异常补录 | 已梳理移动端边界 |
| `/entry/drafts` | 草稿箱 | 已纳入手机端地图 |

## 6. 数据来源分层

系统前端展示数据不能混成一锅，当前应按三层理解：

| 数据层 | 含义 | 典型表 |
|---|---|---|
| MES 投影数据 | 外部 MES 抓取后落到本地，作为生产主数据 | `mes_coil_snapshots`、`mes_workshop_process_records`、`mes_stock_records`、`mes_material_records` |
| 人工填报数据 | 手机端或专项角色补录、纠偏、异常说明 | `mobile_shift_reports`、`machine_energy_records`、`work_order_entries`、`daily_consumable_logs` |
| 算法计算数据 | 由后端根据 MES 和填报计算出的指标 | 日报、成品率、吨耗、异常、对账差异 |

核心原则：

- 生产、卷材、工艺、在制、包装产量优先看 MES 投影。
- 人工填报用于补录、对照、异常审核，不应覆盖 MES 主事实。
- `fill-details` 只显示人工填报和补录，不混入 MES 自动抓取数据。
- 能耗吨耗可以用 MES 产量做分母，但能耗本身仍来自电工填报或未来物联网数采。

## 7. 车间口径

当前活跃生产车间是 13 个：

| 序号 | 车间 |
|---:|---|
| 1 | 铸锭 |
| 2 | 铸二 |
| 3 | 铸三 |
| 4 | 热轧 |
| 5 | 淬火车间 |
| 6 | 精整 |
| 7 | 拉矫 |
| 8 | 园区剪切 |
| 9 | 新厂在线 |
| 10 | 园区在线 |
| 11 | 冷轧1650 |
| 12 | 冷轧1850 |
| 13 | 冷轧2050 |

注意：数据库和管理配置里可能出现 15 个更宽口径，包括 `回收车间`、`成品库`。这个 15 不是活跃生产车间口径。

## 8. 业务时间口径

| 口径 | 开始时间 | 说明 |
|---|---|---|
| 生产业务日 | 07:30 | 主操、电工、生产看板、日报核心口径 |
| 内勤/一日汇总补录 | 09:30 | 一日汇总类角色可在早上补前一日数据 |
| 迟报参考节点 | 10:00 | 用于判断补录和缺报提醒 |

如果当前时间早于开始时间，系统会把业务日算到前一天。

还需要继续核对：所有日报、今日、生产分析、调度大屏、MES 在制和缺报是否都严格用同一套时间口径。

## 9. 权限和角色边界

| 角色 | 入口 | 关键边界 |
|---|---|---|
| 管理员 | `/manage/*` | 全局管理、账号、主数据、设置 |
| 车间主任 | `/manage/workshop-dashboard` | 只能看自己车间 |
| 主操 | `/entry/*` | 手机填报、按卷补录、历史 |
| 电工 | `/entry/*` | 能耗填报、历史 |
| 内勤/专项 | `/entry/*` | 每日一录、辅材、包装/入库对照 |
| AI/治理管理员 | `/manage/ai-assistant`、`/manage/admin/agents` | AI 问答、简报、审批、外部通讯治理 |

已修复的权限风险：

- 车间、班组、员工、班次、别名映射的主数据写接口已补管理员兜底。
- 新增测试 `backend/tests/test_master_write_permissions.py` 证明非管理员直接调这些写接口会返回 `403`。

## 10. 外部系统边界

| 外部项 | 当前理解 |
|---|---|
| 外部 MES SQL Server | 只读同步源，线上 `/readyz` 显示 SQL Server 同步为主链路 |
| 物联网能耗库 | 尚未接入，`iot_energy_sync=unconfigured` 是预期状态 |
| 钉钉 | 配置和代码链路已梳理，真实发送/审批仍需指定人员实测 |
| LLM / AI | AI 助手、简报、关注项和治理入口已梳理，实际模型质量和权限动作仍需继续 QA |
| 域名 | `https://xtmijd.com` 正常，`https://www.xtmijd.com` 当前不可作为登录入口 |

## 11. 健康检查和部署边界

| 路径 | 含义 |
|---|---|
| `/healthz` | 程序是否活着 |
| `/api/v1/healthz` | 同上，兼容 API 前缀 |
| `/readyz` | 主业务链路是否准备好 |
| `/api/v1/readyz` | 同上，兼容 API 前缀 |

当前只读探测：

- `https://xtmijd.com/api/v1/healthz`：HTTP 200。
- `https://xtmijd.com/api/v1/readyz`：HTTP 200，`status=ready`。
- `https://xtmijd.com/healthz`：HTTP 200。
- `https://xtmijd.com/readyz`：HTTP 200，`status=ready`。
- `https://www.xtmijd.com/api/v1/healthz`：连接失败。

登录 network error 的优先排查顺序：

1. 是否用了 `www.xtmijd.com`。
2. 是否开了代理。
3. 浏览器是否有旧缓存、旧 Token、旧 Service Worker。
4. 是否能访问 `/api/v1/healthz`。
5. 页面是否显示“账号或密码不正确”。如果是，说明请求已到后端；如果还是“连接服务器失败”，说明浏览器到服务器没通。

## 12. 已运行过的验证

近期可确认的测试证据：

| 验证项 | 结果 |
|---|---|
| 主数据写权限测试 | `1 passed` |
| 用户/主数据/规则相关后端回归 | `34 passed` |
| 健康检查和 Nginx 配置测试 | `17 passed` |
| 告警/能耗/考勤/导出相关后端回归 | `48 passed` |
| 前端测试集 | 当前多次实际触发为 `666 passed` |

边界：后端全量 `python -m pytest -q` 没有在本轮被完整证明通过，所以不能写成“后端全量测试已完成”。

## 13. 已整合的原始理解记录

| 文件 | 主题 |
|---|---|
| `system-understanding-2026-06-14.md` | 总体快照 |
| `system-understanding-runtime-map-2026-06-14.md` | 运行链路、数据库、外部状态 |
| `system-understanding-database-api-route-map-2026-06-14.md` | 页面、API、数据库表映射 |
| `system-understanding-dashboard-live-dataflow-2026-06-14.md` | 实时大屏数据流 |
| `system-understanding-today-production-dataflow-2026-06-14.md` | 日报和生产数据流 |
| `system-understanding-mes-production-dashboard-dataflow-2026-06-14.md` | MES 到生产看板链路 |
| `system-understanding-mobile-entry-dataflow-2026-06-14.md` | 手机填报链路 |
| `system-understanding-role-permission-route-flow-2026-06-14.md` | 角色、权限、路由 |
| `system-understanding-role-qa-2026-06-14.md` | 角色 QA 记录 |
| `system-understanding-manage-core-qa-2026-06-14.md` | 管理端核心页面 QA |
| `system-understanding-master-data-permission-audit-2026-06-14.md` | 主数据权限审计 |
| `system-understanding-manage-admin-permission-map-2026-06-14.md` | 管理端登录、权限、主数据 |
| `system-understanding-users-permissions-master-mobile-2026-06-14.md` | 用户、权限、主数据和手机入口 |
| `system-understanding-alert-energy-attendance-export-2026-06-14.md` | 异常、能耗、考勤、导出 |
| `system-understanding-ai-dingtalk-communication-2026-06-14.md` | AI、钉钉、外部通讯 |
| `system-understanding-admin-login-auth-2026-06-14.md` | 管理员登录链路 |

## 14. 剩余工作清单

如果要真正完成原目标，还需要至少做完这些：

| 优先级 | 剩余项 | 为什么还差 |
|---|---|---|
| 高 | 全角色真实账号浏览器 QA | 需要主操、电工、内勤、车间主任、管理员逐流程点完 |
| 高 | 每个核心页面字段到接口到表的逐字段复核 | 现在是主链路清楚，字段级还未全部逐项验完 |
| 高 | MES 主数据替代内勤统计岗的最终口径确认 | 这是用户核心业务目标，还要和实际日报/现场流程对齐 |
| 高 | 能耗数采库接入后重新核对能耗链路 | 当前物联网能耗未配置 |
| 中 | 钉钉主动汇报和指定人员审批真实测试 | 配置和代码链路清楚，但真实动作还没全测 |
| 中 | AI 助手问答、简报、关注项、操作审批全链路 QA | 需要确认不会越权、不会误触发写操作 |
| 中 | understand 全量图谱刷新 | 需要先确认 `.understandignore`，再跑完整 `/understand` 流程 |
| 中 | 旧路由、旧入口、旧页面依赖追踪 | 不能误删历史二维码、收藏入口、兼容跳转 |
| 中 | 后端全量测试稳定跑完 | 当前只有多组定向测试，不能替代全量 |
| 低 | 将分散文档继续精简成长期维护版 | 现在总整合已完成，后续可再压缩成 README 式手册 |

## 15. 估算还差多少

如果按“只看系统理解文档能不能交接给下一位工程师”看，现在大概完成 `94%`。

如果按用户原话“每一行代码、每一个字符、所有功能、所有角色、数据库、外部链接都深刻理解并 QA”看，现在大概完成 `82%`。

两者差距这么大，是因为文档地图已经比较完整，但真实系统验收还差几块重活：

- 用真实账号逐角色操作。
- 把每个页面每个字段追到真实接口和真实表字段。
- 把外部服务动作真正跑通。
- 刷新 understand 全量图谱。

这四项做完后，原始超大目标才可能接近 `90%` 以上；最后 10% 是长期维护中持续更新，因为系统还在变化。

## 16. 下一步推荐顺序

1. 确认 `.understandignore`，刷新全量 understand 图谱。
2. 把已建立的“页面字段 -> 前端 API -> 后端接口 -> 服务函数 -> 数据表字段”矩阵拿线上某个业务日做真实数字对账。
3. 用真实角色账号做浏览器 QA，逐页记录截图、接口状态和失败点。
4. 对 MES 替代内勤统计岗做专项口径验收。
5. 对能耗数采库、钉钉、AI 外部动作做真实联调。
6. 把最终版本写入记忆，并把旧的阶段性理解文档降级为历史证据。

## 17. 追加理解：核心管理页字段链路第一轮矩阵

本节是 2026-06-14 晚间继续梳理后的新增底账。它解决一个最容易误判的问题：前端页面上看到的数字，不一定来自同一种数据。当前系统至少有三类来源：

- 外部 MES 同步到本地的 `mes_*` 投影表。
- 手机端或内勤端人工填报进入本地业务表。
- 后端服务把前两类数据再做算法汇总后返回给前端。

| 页面 | 前端入口 | 主要前端 API | 后端入口 | 主要服务 | 主要数据表 | 当前理解 |
|---|---|---|---|---|---|---|
| `/manage/live` 实时大屏 | `frontend/src/views/manage/live/LiveDashboardPage.vue` | `/aggregation/live`、`/realtime/stream`、`/aggregation/live/fill-details`、`/aggregation/live/detail` | `backend/app/routers/realtime.py` | `backend/app/services/realtime_service.py` | `work_order_entries`、`mobile_shift_reports`、`machine_energy_records`、`mes_coil_snapshots`、`mes_workshop_process_records`、`mes_stock_records`、`realtime_events` | 大屏不是单表直出。它把人工填报、MES 投影、机台能耗、实时事件揉成一个看板。全厂包装产量注入逻辑优先读 MES 包装产量。 |
| `/manage/today` 昨日日报 | `frontend/src/views/manage/today/TodayPage.vue` | `/dashboard/factory-director`、`/dashboard/daily-production`、`/factory-command/overview` | `backend/app/routers/dashboard.py`、`backend/app/routers/factory_command.py` | `daily_overview_builder.py`、`factory_command_service.py` | `mes_stock_records`、`mes_workshop_process_records`、`work_order_entries`、`machine_energy_records`、`energy_import_records`、`iot_energy_snapshots` | 日报页通过 `useDashboardSnapshot.js` 组合多个接口。包装产量和全厂入库产量必须分开看，前者是 MES 包装主口径，后者是成品库内勤入库口径。 |
| `/manage/production` 生产分析 | `frontend/src/views/manage/production/ProductionPage.vue` | 同 `/manage/today`，共用 `useDashboardSnapshot.js` | 同 `/manage/today` | 同 `/manage/today` | 同 `/manage/today` | 生产分析页和昨日日报同源，但展示重点不同。它更偏车间排名、成品率、吨耗、合同缺口、生产趋势。 |
| `/manage/coils` 卷级线索 | `frontend/src/views/manage/coils/CoilTracePage.vue` | `/factory-command/coils`、`/factory-command/coils/{coil_key}/flow` | `backend/app/routers/factory_command.py` | `backend/app/services/factory_command_service.py` | `mes_coil_snapshots`、`mes_workshop_process_records`、`mes_machine_line_snapshots`、`coil_flow_events` | 这是最接近“按卷追踪”的页面。主数据来自 MES 投影，能看到随行卡、客户、合金、规格、当前工艺、当前车间、机列、自动废料估算。 |
| `/manage/fill-details` 填报明细 | `frontend/src/views/manage/fill-details/FillDetailsPage.vue` | `/aggregation/live/fill-details`、`/aggregation/live/mes-fill-gaps`、`/aggregation/live/missing-report-export`、`/dashboard/daily-production` | `backend/app/routers/realtime.py`、`backend/app/routers/dashboard.py` | `realtime_service.py`、`daily_overview_builder.py` | `work_order_entries`、`mobile_shift_reports`、`machine_energy_records`、`mes_workshop_process_records` | 这个页面的主职责是人工填报和补录明细。后端明确排除了 `entry_type='mes_projection'`，MES 只作为缺口和对照，不应混进人工填报流水。 |
| `/manage/energy` 能耗中心 | `frontend/src/views/energy/EnergyCenter.vue` | `/energy/summary` | `backend/app/routers/energy.py` | `backend/app/services/energy_service.py` | `machine_energy_records`、`mobile_shift_reports`、`work_order_entries`、`energy_import_records`、`iot_energy_snapshots`、`mes_stock_records`、`mes_workshop_process_records` | 能耗不是只看一张表。优先会合并机台能耗、电工班次汇总、内勤专项、老导入和物联网影子数据。没有班次产量时，可用 MES 包装产量做吨耗分母兜底。 |
| `/manage/alerts` 异常页 | `frontend/src/views/manage/alerts/AlertsPage.vue` | `/quality/issues`、`/reconciliation/items`、`/aggregation/live/mes-fill-gaps` | `quality.py`、`reconciliation.py`、`realtime.py` | `quality_service.py`、`reconciliation_service.py`、`realtime_service.py` | `data_quality_issues`、`data_reconciliation_items`、`mes_workshop_process_records`、`work_order_entries` | 异常页不是只显示缺报。它把质量问题、对账差异、MES 与本地填报缺口合并成事件流。 |

### 17.1 当前最重要的数据边界

| 名称 | 应该怎么理解 |
|---|---|
| 包装产量 | 优先来自 `mes_stock_records`，缺失时回退到 `mes_workshop_process_records` 的包装工序记录。它代表 MES 投影里的包装口径。 |
| 全厂入库产量 | 来自成品库内勤每日一录，也就是 `work_order_entries(entry_type='owner_daily')` 里成品库相关字段。它不是 MES 包装产量。 |
| 填报明细 | 人工填报和补录流水，不是 MES 自动同步流水。 |
| 卷级线索 | 以 MES 投影为主，用来帮助现场少填随行卡、合金、规格、工艺等重复信息。 |
| 能耗总览 | 需要同时看机台能耗明细、班次电工填报、内勤专项和未来物联网能耗。现在物联网能耗库仍属于未完全接入边界。 |
| 业务日 | 主操、电工等生产角色按早上 07:30 起算；内勤/专项每日一录按早上 09:30 起算。日报、生产分析、调度大屏默认看已完成生产业务日。 |

### 17.2 这一轮新确认的风险点

- `/manage/today` 和 `/manage/production` 共用 `useDashboardSnapshot.js`，好处是口径集中，风险是这个组合层一旦字段兜底写错，两个页面会一起错。
- `/manage/live` 会用实时事件和 30 秒快照兜底两套机制，测试和排错时不能只看一次接口返回。
- `/manage/energy` 的 `output_weight` 可能来自班次产量，也可能在全厂总览下由 MES 包装产量兜底，所以页面文案要持续保留来源感，不能写成“唯一真值”。
- `/manage/fill-details` 当前边界是正确的：人工填报为主，MES 缺口另列。如果以后把 MES 主数据当主口径，也不能把 MES 自动记录塞进填报明细表格里，否则现场会分不清“人填的”和“系统同步的”。
- `/manage/coils` 依赖 `mes_coil_snapshots` 和机列别名/绑定，若 MES 设备名只给 `PC` 而没有真实机列，仍需要 `mes_terminal_bindings` 或同等绑定规则补齐。

## 18. 本轮新增验证记录

本轮没有改业务代码，只做理解、交叉阅读和测试验证。

| 验证类型 | 命令 | 结果 | 说明 |
|---|---|---|---|
| 后端定向测试 | `python -m pytest -q backend/tests/test_business_time_contract.py backend/tests/test_daily_overview_mes_packaging.py backend/tests/test_energy_mes_packaging_output_basis.py backend/tests/test_realtime_service.py::test_build_fill_detail_ledger_excludes_mes_projection_rows backend/tests/test_realtime_service.py::test_build_fill_detail_ledger_excludes_mes_projection_work_order_entries backend/tests/test_realtime_service.py::test_inject_factory_packaging_output_uses_mes_as_live_main_metric` | `11 passed` | 覆盖业务时间、MES 包装产量、能耗 MES 分母兜底、填报明细排除 MES 自动投影。 |
| 前端测试集 | `npm run test -- --run frontend/tests/manageDashboardSnapshot.test.js frontend/tests/manageDailyReportSurface.test.js frontend/tests/manageFillDetailsAudit.test.js frontend/tests/manageAlertsTimeline.test.js frontend/tests/businessDateDefaults.test.js frontend/tests/workshopEnergyLiveRegression.test.js` | `666 passed` | 当前 `npm run test` 实际会跑 `frontend/tests/*.test.js` 全部前端测试。它证明前端契约和静态行为通过，不等同于浏览器全流程 QA 已完成。 |
| CodeGraph 索引状态 | `codegraph_status` | `1032` 文件、`15551` 节点、`31986` 边 | 可作为当前结构检索底座。全量 understand 图谱仍需先确认 `.understandignore` 后再刷新。 |

边界说明：这轮仍然没有完成“真实账号逐角色浏览器全流程 QA”，也没有完成“后端全量 pytest 稳定跑完”。所以目前只能说核心数据口径的第一轮矩阵和定向测试已补齐，不能说整个系统已经完整验收。

## 19. 追加理解：手机填报端和车间主任看板链路

本节继续把“现场手机怎么填、数据写到哪里、管理端怎么看”说清楚。这里要先记住一个边界：管理员账号不是手机填报账号。管理员进不了 `/entry` 或调用手机填报接口返回 `403`，不是系统坏了，而是权限隔离生效。

### 19.1 手机端主要入口

| 入口 | 页面 | 用途 | 当前结论 |
|---|---|---|---|
| `/entry` | `MobileEntry.vue` | 手机填报首页 | 负责把现场人员带到填报、历史、异常等入口。 |
| `/entry/fill` | `UnifiedEntryForm.vue` | 当前主填报页 | 真实提交会按角色分流到主操逐卷、电工班次、内勤每日一录三条链路。 |
| `/entry/coil/:businessDate/:shiftId` | `CoilEntryWorkbench.vue` | 旧的按卷录入工作台 | 仍保留兼容，主流程已经更多走统一填报页。 |
| `/entry/history` | `ShiftReportHistory.vue` | 历史记录 | 前端按整日查询，但后端目前主要返回班次填报和主操逐卷；每日一录尚未完全并入统一历史。 |
| `/entry/consumables` | `ConsumableEntry.vue` | 辅材填报 | 仍有独立入口，需要和统一填报长期保持边界清楚。 |

### 19.2 不同角色分别写到哪里

| 角色类型 | 前端模式 | 后端接口 | 主要写入表 | 小白解释 |
|---|---|---|---|---|
| 主操 `machine_operator` | `per_coil` | `POST /api/v1/mobile/coil-entry` | `work_order_entries(entry_type='mobile_coil')`，必要时创建 `work_orders` | 每扫一卷或录一卷，就生成一条“卷级补录”。废料可由上机量、下机量、套筒/切边/托盘自动算出。 |
| 电工 `energy_stat` | `per_shift` | `POST /api/v1/mobile/report/save` + `POST /api/v1/mobile/report/submit` | `mobile_shift_reports`，机台明细另写 `machine_energy_records` | 电工不是逐卷填，而是按班次填电耗、气耗；如果填了每台机列明细，后端会汇总到班次总电气。 |
| 普通班次补录角色 | `per_shift` | 同电工班次接口 | `mobile_shift_reports` | 用于还保留的班次汇总类字段，不走每日一录。 |
| 内勤/专项每日一录 | `owner_daily` | `GET/POST /api/v1/mobile/owner-daily` | `work_order_entries(entry_type='owner_daily')`，字段在 `extra_payload` | 每天一条，不绑定班次、不绑定机列，适合成品库、总电工、回收、大修等专项数据。 |

### 19.3 业务时间口径

| 人群 | 时间口径 | 代码表现 | 业务含义 |
|---|---|---|---|
| 主操、电工等生产角色 | 早上 `07:30` 起算 | 后端 `get_current_shift()` 使用生产业务日和班次推断 | 07:30 到次日 07:30 算同一个生产业务日。 |
| 内勤/专项每日一录 | 早上 `09:30` 起算 | 后端 `save_owner_daily_entry()` 使用 owner daily 业务日纠偏 | 方便内勤早上补完前一天完整数据，不被自然日卡住。 |

### 19.4 历史记录的当前边界

`/entry/history` 前端会用 `all_day=true` 查询整日记录。后端 `list_report_history()` 当前会返回两类：

- `mobile_shift_reports`：班次汇总、电工等记录。
- `work_order_entries(entry_type='mobile_coil')`：只在主操整日查询时补入逐卷记录。

当前风险：`owner_daily` 每日一录虽然前端有“专项每日”的样式，但后端历史接口尚未把 `work_order_entries(entry_type='owner_daily')` 统一并入历史列表。所以以后如果现场说“内勤昨天填了，但历史里看不到”，优先查这个接口边界，不要先判断数据丢了。

### 19.5 车间主任看板链路

| 层级 | 位置 | 当前作用 |
|---|---|---|
| 前端路由 | `/manage/workshop-dashboard` | 车间主任、管理员、全局管理人员共用这个页面。 |
| 前端权限 | `auth.js`、`guardRules.js` | `workshop_director` 被视为可看管理端，但会被导向本车间看板，不能随意看全厂页面。 |
| 后端权限 | `assert_manager_dashboard_access()` | 车间主任必须有 `workshop_id`，并且请求别的车间会被拒绝。 |
| 后端接口 | `/api/v1/dashboard/workshop-director` | 根据当前用户或请求参数确定车间，再构建车间看板。 |
| 后端聚合 | `build_workshop_dashboard()` | 合并产量、能耗、异常、缺报、库存、历史摘要、MES 同步状态等数据。 |
| 前端聚合 | `WorkshopDashboardPage.vue` | 同时请求车间看板、实时汇总、填报明细、待分配、MES 缺口、MES 工序、MES 在制料。 |

小白版理解：车间主任看板不是“一张表直接显示”，而是一个聚合页面。它像一个小调度室，把本车间产量、能耗、缺报、MES 缺口、在制料、异常都放在一个屏幕里。安全边界也不是只靠菜单隐藏，后端接口也会检查车间主任只能看自己的车间。

### 19.6 后续建议补强点

| 优先级 | 建议 | 原因 |
|---|---|---|
| 高 | 把 `owner_daily` 纳入 `/entry/history` 统一历史接口 | 现场每日一录人员需要能在历史页看到自己整日提交记录。 |
| 高 | 给车间主任看板补一组真实账号浏览器 QA | 现在已有自动测试保护权限，但还没用真实车间主任账号逐页点完。 |
| 中 | 明确 `/entry/consumables` 和 `/entry/fill` 的长期边界 | 避免现场不知道应该进哪个入口。 |
| 中 | 继续补 PC 到真实机列/工艺绑定 | MES 设备名如果只有 `PC`，车间看板里的机列匹配仍会不稳。 |

## 20. 本轮新增验证记录：手机填报与车间看板

本轮仍然没有改业务代码，主要是读代码、跑定向测试、把理解合并进本文档。

| 验证类型 | 命令 | 结果 | 能证明什么 |
|---|---|---|---|
| CodeGraph 索引 | `codegraph_status` | `1032` 文件、`15551` 节点、`31986` 边 | 当前结构索引可用，可以继续用作理解底座。 |
| 后端手机/权限定向测试 | `python -m pytest -q backend/tests/test_mobile_routes.py backend/tests/test_mobile_report_service.py backend/tests/test_mobile_report_write_guards.py backend/tests/test_mobile_scope_isolation.py backend/tests/test_mobile_shift_report_machine_binding.py backend/tests/test_workshop_director_scope.py` | `31 passed` | 手机路由、手机填报权限、电工能耗字段、主操机列绑定、车间主任范围控制通过现有自动测试。 |
| 前端测试集 | `npm run test -- --run frontend/tests/entryShellNavigation.test.js frontend/tests/mobileTransition.test.js frontend/tests/coilEntryWorkbench.scan.test.js frontend/tests/manageRouteRedirects.test.js frontend/tests/manageNavigationSkeleton.test.js frontend/tests/manageFillDetailsAudit.test.js` | `666 passed` | 当前前端测试脚本实际跑了全部 `frontend/tests/*.test.js`，覆盖入口、路由、视觉壳层、字段静态契约等。 |

边界说明：这些测试不是浏览器真实账号全流程 QA，也没有向生产环境提交数据。它们能证明代码层面的入口、权限和字段契约没有明显断裂，但不能替代现场扫码填报和车间主任真实账号验收。

## 21. 追加理解：AI、钉钉、主动汇报和外部通讯治理链路

本节把“AI 助手、钉钉、主动汇报、多智能体治理”拆开说清楚。最关键的一句话是：当前系统不是让 AI 直接随意发群消息，而是把 AI 事件、待发送消息、通讯通道、审核记录分层管理。只有配置了真实通道、关闭演练模式，并执行发送动作后，才会真正外发。

### 21.1 页面、接口和用途

| 入口 | 前端位置 | 后端接口 | 用途 | 副作用边界 |
|---|---|---|---|---|
| `/manage/ai-assistant` | `AiWorkstation.vue`、`ai-assistant.js` | `/api/v1/ai/*` | AI 工作台，会话、消息、日报简报、关注项 | 创建会话、发送消息、生成简报、关注项增删改都会写数据库。 |
| 常驻 AI 抽屉 | `AiAssistantDrawer.vue` | `/api/v1/ai/*` | 在管理端页面内快速唤起 AI 助手 | 只打开抽屉一般不写数据，发送消息会写入 AI 会话记录。 |
| `/manage/admin/agents` | `AgentManagementPage.vue`、`agent-management.js` | `/api/v1/agent-management/overview` | 多智能体外部通讯治理台 | `GET overview` 是只读；知识问答、发件箱派发等 POST 类能力需要按写操作看待。 |
| 钉钉登录 | 钉钉 H5/网页登录流程 | `/api/v1/dingtalk/login`、`/api/v1/dingtalk/h5-login` | 把钉钉身份换成系统登录态 | 会更新用户绑定、最后登录时间和审计日志，不能当只读探针。 |
| 智能体动作 | AI 助手动作按钮或后台调用 | `/api/v1/assistant/actions` | 调用校验、对账、提醒、聚合、草稿转正等动作 | 这是高风险写操作，可能改业务状态，只允许管理员或指定管理角色调用。 |

### 21.2 主要数据表职责

| 类型 | 表 | 作用 |
|---|---|---|
| AI 会话 | `ai_conversations`、`ai_messages` | 保存用户和 AI 的对话记录。 |
| AI 上下文 | `ai_context_packs` | 保存 AI 回答时用到的业务上下文快照。 |
| AI 简报 | `ai_briefing_events` | 保存 AI 生成的主动日报、提醒、跟进事件。 |
| AI 关注项 | `ai_watchlist_items` | 保存用户关注的指标或异常。 |
| 智能体档案 | `agent_profiles` | 定义有哪些智能体。 |
| 通讯通道 | `communication_channels` | 定义钉钉群等外部通道，包含 `dry_run` 演练开关。 |
| 绑定关系 | `agent_channel_bindings` | 定义哪个智能体可以用哪个通道。 |
| 事件记录 | `agent_events` | 记录智能体产生的事件。 |
| 发件箱 | `agent_outbox_messages` | 待发送、演练、已发送、失败的消息队列。 |
| 外发日志 | `external_message_logs` | 记录每一次外部通讯尝试的结果。 |
| 多模态证据 | `multimodal_evidence` | 保存图片、文件、文本等证据引用。 |
| 审核治理 | `agent_operation_approvals`、`agent_rate_limits` | 负责人工审核、限流、治理边界。 |

### 21.3 外部通讯真实链路

小白版可以理解成 5 个步骤：

1. 智能体先生成一个事件，比如“某车间缺报”。
2. 系统把要发的话放进 `agent_outbox_messages` 发件箱。
3. 系统检查这个智能体是否绑定了可用通道。
4. 如果通道是 `dry_run=true`，只把消息标记为“演练”，并写入日志，不会真的发到钉钉。
5. 只有通道启用、不是演练模式、类型是 `dingtalk_group`，并执行发送派发时，才会真正调用钉钉发送。

这条链路的价值是可控：以后要主动汇报时，不应该让 AI 绕过治理台直接发消息，而应该继续走“事件 -> 发件箱 -> 通道 -> 日志”的路径。

### 21.4 权限和安全边界

| 模块 | 当前边界 | 说明 |
|---|---|---|
| AI 工作台 | 管理员、管理人员、审核类角色可访问 | 普通手机填报人员不应该直接看到全厂 AI 工作台。 |
| 外部通讯治理台 | 管理员可访问 | 这里能看通道、发件箱、审核和证据，权限要比普通管理页更严。 |
| 智能体动作 | 管理员或指定管理角色，且有范围校验 | 车间范围管理人员不能越权执行全厂动作。 |
| 钉钉登录 | 需要钉钉配置和用户绑定 | 登录过程会写用户绑定和审计日志。 |
| AI 上下文 | 发给 LLM 前会清理敏感字段 | `password`、`secret`、`token`、`credential`、`api_key` 等字段会被过滤。 |

当前理解：AI 可以辅助总结、问答、生成简报，但涉及“改业务数据”“外发群消息”“补产量发布日报”这类动作，必须继续放在权限、审核、日志、回滚边界内，不应做成一键无审计自动执行。

### 21.5 生产 QA 注意事项

| 操作类型 | 是否适合直接线上点 | 原因 |
|---|---|---|
| `GET /api/v1/agent-management/overview` | 可以只读查看 | 主要读取治理台概览。 |
| `GET /api/v1/ai/runtime` | 可以只读查看 | 只看 AI 运行模式和配置状态。 |
| `POST /api/v1/ai/assistant/conversations` | 不建议当探针 | 会创建会话记录。 |
| `POST /api/v1/ai/assistant/messages` | 不建议当探针 | 会写用户消息和 AI 回复。 |
| `POST /api/v1/ai/briefings/generate-now` | 不建议当探针 | 会生成简报事件。 |
| `POST /api/v1/assistant/actions` | 高风险，必须确认 | 可能触发校验、对账、提醒、聚合或草稿转正。 |
| `POST /api/v1/dingtalk/h5-login` | 不能当只读探针 | 会更新登录状态和绑定信息。 |

## 22. 本轮新增验证记录：AI 与外部通讯治理

本轮没有修改业务代码，只做结构追踪、无副作用定向测试和文档合并。

| 验证类型 | 命令 | 结果 | 能证明什么 |
|---|---|---|---|
| 后端 AI/钉钉/外部通讯测试 | `python -m pytest -q backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_overview_service.py backend/tests/test_agent_operation_approval_service.py backend/tests/test_assistant_action_service.py backend/tests/test_ai_assistant_routes.py backend/tests/test_dingtalk_h5_login.py backend/tests/test_dingtalk_service.py` | `44 passed, 2 warnings` | 外部通讯 dry-run、治理台概览、审核服务、智能体动作权限、AI 路由、钉钉 H5 登录服务的现有自动测试通过。两个 warning 是测试代码里的 `datetime.utcnow()` 弃用提醒，不是本轮阻塞。 |
| 前端 AI/治理台测试 | `npm run test -- --run frontend/tests/agentManagementPage.test.js frontend/tests/aiAssistantContracts.test.js frontend/tests/aiAssistantUiContract.test.js frontend/tests/aiWorkstationActions.test.js frontend/tests/dingtalkAutoLogin.test.js frontend/tests/assistantFallbackTruthfulness.test.js` | `666 passed` | 当前前端测试脚本实际跑了全部 `frontend/tests/*.test.js`，覆盖治理台、AI 合约、AI 工作台动作、钉钉自动登录等静态契约。 |
| 结构追踪 | CodeGraph 上下文和源码追踪 | 已确认主要页面、接口、表、服务边界 | 能说明 AI、钉钉和外部通讯不是一条混在一起的链路，而是分成 AI 内部记录、治理台发件箱、通道外发和外部日志。 |

边界说明：这些测试没有真正往钉钉群发消息，也没有用生产真实通道做外发验收。它们证明“代码层面的边界和 dry-run 保护还在”，不能证明“钉钉真实群消息已经发送成功”。真实外发验收必须单独准备测试通道、指定接收群、确认 dry-run 关闭，并保留日志回查。

## 23. 追加理解：异常、能耗、考勤和缺报导出链路

本节补的是管理端里最容易误点、误读和误删的一组页面：异常、能耗、考勤、缺报导出。它们不像普通列表页那样“一张表直接显示”，而是多来源拼起来的业务视图。

### 23.1 异常页不是单表页面

`/manage/alerts` 的前端入口是 `AlertsPage.vue`，核心逻辑在 `useAlertsTimeline.js`。它一次聚合 5 个来源：

| 来源 | 前端调用 | 日期参数 | 业务含义 |
|---|---|---|---|
| 厂长看板异常 | `fetchFactoryDashboard()` | `target_date` | 生产和填报提醒类异常。 |
| 质量问题 | `fetchQualityIssues()` | `business_date` | `data_quality_issues` 中的质量/数据质量问题。 |
| 对账差异 | `fetchReconciliationItems()` | `business_date` + `status=open` | `data_reconciliation_items` 中尚未闭环的差异。 |
| 外部 MES 与本地填报缺口 | `fetchMesFillGaps()` | `business_date` | 外部 MES 投影和本地补录之间的匹配缺口。 |
| 实时聚合 | `fetchLiveAggregation()` | `business_date` | 缺报、未匹配、填报但没产量等实时聚合状态。 |

小白版理解：异常页像一个“报警汇总台”，不是一个“异常表”。它把多个地方的异常拉到一起排时间线。所以以后如果异常页某一类数据没出来，要先看是哪一路接口失败，不要直接判断整个异常系统坏了。

### 23.2 异常相关的写操作

| 模块 | 只读接口 | 写入接口 | 风险说明 |
|---|---|---|---|
| 质量问题 | `GET /api/v1/quality/issues` | `POST /api/v1/quality/run-checks`、`POST /api/v1/quality/issues/{id}/resolve`、`POST /api/v1/quality/issues/{id}/ignore` | 运行检查会生成问题；处理/忽略会改状态并写处理人、处理时间。 |
| 对账差异 | `GET /api/v1/reconciliation/items` | `POST /api/v1/reconciliation/generate`、`POST /api/v1/reconciliation/items/{id}/confirm|ignore|correct` | 生成会重建差异项；确认、忽略、纠正会改变闭环状态。 |
| 实时缺口 | `GET /api/v1/aggregation/live/mes-fill-gaps` | 另有缺失产量修正类 POST/PATCH | 只看缺口是安全的，补产量/修正才是写操作。 |

### 23.3 能耗页的数据来源

`/manage/energy` 前端主要读 `fetchEnergySummary()`，对应后端 `GET /api/v1/energy/summary`。旧的 `POST /api/v1/energy/import` 路由还在，但会返回 `410`，提示“能耗导入功能已停用，请使用电工/内勤每日填报。”

能耗汇总不是只从一张表来，而是按来源合并：

| 来源标签 | 主要表/逻辑 | 含义 |
|---|---|---|
| `mobile_shift_report` | `mobile_shift_reports` + `machine_energy_records` | 电工/班次填报；如果机台明细有值且班次总值为空，优先用机台明细补总值。 |
| `owner_only` | `work_order_entries(entry_type='owner_daily')` | 总电工、专项每日一录等内勤/专项口径。 |
| `energy_import` | `energy_import_records` | 历史导入表，导入接口当前已停用，但历史数据仍可能被读。 |
| `iot_shadow` | `iot_energy_snapshots` | 物联网能耗影子表；独立数采库接入后会走这里。 |
| `mes_packaging_output_basis` | 外部 MES 包装产量口径 | 当能耗有值但本地没有产量分母时，用外部 MES 包装产量作为吨耗分母参考。 |

关键点：能耗页的“用电、用气、用水”和“吨耗分母”不是同一类数据。能耗值来自电工/内勤/物联网/历史导入，产量分母可能来自外部 MES 包装产量。以后排查“吨耗不对”时，要同时看能耗来源和产量分母来源。

### 23.4 考勤页当前是预留和核查，不是导入中心

考勤相关页面包括 `AttendanceOverview.vue`、`AttendanceDetail.vue`、`ExceptionList.vue`。当前前端文案已经说明：考勤后续接入钉钉打卡后启用，现在主要保留结果核查入口。

| 能力 | 接口 | 状态 |
|---|---|---|
| 排班导入 | `POST /api/v1/attendance/schedules/import` | 已停用，返回 `410`。 |
| 打卡导入 | `POST /api/v1/attendance/clocks/import` | 已停用，返回 `410`。 |
| 查询考勤结果 | `GET /api/v1/attendance/results` | 只读。 |
| 查询员工考勤详情 | `GET /api/v1/attendance/results/{employee_id}/{business_date}` | 只读。 |
| 自动处理考勤 | `POST /api/v1/attendance/process` | 写操作，会生成结果和异常。 |
| 修正考勤结果 | `POST /api/v1/attendance/results/{id}/override` | 写操作，需要修正原因。 |
| 处理考勤异常 | `POST /api/v1/attendance/exceptions/{id}/resolve` | 写操作，会改异常状态。 |
| 确认考勤 | `POST /api/v1/attendance/confirm` | 写操作，用于考勤确认链路。 |
| 审核考勤异常明细 | `PATCH /api/v1/attendance/anomalies/{detail_id}/review` | 写操作。 |

小白版理解：考勤页现在更像“未来钉钉考勤接入后的核查台”。不要把它当成现在主要生产填报链路，也不要恢复旧 Excel 导入作为主流程。

### 23.5 缺报导出链路

车间主任看板和部分管理端页面会调用：

`GET /api/v1/aggregation/live/missing-report-export`

前端包装函数是 `exportMissingReportExcel()`。它不是通用导出中心，而是实时聚合模块下的专用导出。测试确认导出的 Excel 至少包含：

| 工作表 | 内容 |
|---|---|
| `缺报明细` | 哪个车间、机列、班次、角色缺报。 |
| `待归属明细` | 已有填报但机列/班次/归属不完整的记录。 |
| `车间汇总` | 按车间汇总缺报和待处理数量。 |
| `MES异常明细` | 有外部 MES 匹配缺口时追加，显示重量不一致、MES 机列、本地机列等信息。 |

如果现场反馈“导出的 Excel 没信息”，优先检查这四点：业务日期是否选对、实时聚合是否有缺报、待归属接口是否有数据、外部 MES 缺口接口是否有数据。不要只看导出按钮本身。

### 23.6 这一组页面的安全边界

| 操作 | 可否线上只读 QA | 说明 |
|---|---|---|
| 打开 `/manage/alerts` | 可以 | 主要是 GET 聚合，但会触发多路接口。 |
| 打开 `/manage/energy` | 可以 | 主要读 `energy/summary`，权限会按角色范围过滤。 |
| 打开考勤结果页 | 可以 | 查询结果安全。 |
| 导出缺报 Excel | 一般可以，但要注意文件下载 | GET 下载，不改数据。 |
| 运行质量检查、生成对账、自动处理考勤 | 不建议随便点 | 会新增或更新业务记录。 |
| 处理/忽略/纠正异常 | 不建议当测试按钮 | 会改闭环状态。 |

## 24. 本轮新增验证记录：异常、能耗、考勤和缺报导出

本轮没有修改业务代码，只做结构追踪、定向测试和文档合并。

| 验证类型 | 命令 | 结果 | 能证明什么 |
|---|---|---|---|
| 后端定向测试 | `python -m pytest -q backend/tests/test_energy_summary.py backend/tests/test_missing_report_export_service.py backend/tests/test_attendance_process.py backend/tests/test_attendance_confirmation_routes.py backend/tests/test_quality_checks.py backend/tests/test_reconciliation_flow.py` | `30 passed` | 能耗汇总权限和来源、缺报导出工作表、考勤处理/导入停用、质量问题、对账闭环的现有自动测试通过。 |
| 前端测试集 | `npm run test -- --run frontend/tests/manageAlertsTimeline.test.js frontend/tests/manageAlertsPage.test.js frontend/tests/energyCenterDesign.test.js frontend/tests/attendanceOverviewDesign.test.js` | `666 passed` | 当前前端测试脚本实际跑了全部 `frontend/tests/*.test.js`，覆盖异常页时间参数、能耗页真实接口路径、考勤页真实接口路径和视觉契约。 |
| 结构追踪 | CodeGraph + 关键路由/API 文件阅读 | 已确认 | 能说明这些页面哪些是只读、哪些是写入，避免把“页面能打开”误解成“可以安全点所有按钮”。 |

边界说明：这不是浏览器真实账号全流程 QA，也没有在生产环境点写操作。它能证明当前代码层面契约稳定，但不能替代现场真实账号、真实日期、真实数据的页面验收。

## 25. 追加理解：主数据、账号、别名和 PC 终端映射

本节补“配置到底配置了什么”。这里不能只把 `/manage/admin/settings` 理解成一个普通设置页。它更像一个入口中转台，把主数据、账号权限、别名归一、二维码机列、PC 工艺映射、规则配置、AI 助手等关键入口放到一起。

### 25.1 设置页和设置抽屉分别做什么

| 入口 | 前端位置 | 作用 |
|---|---|---|
| `/manage/admin/settings` | `SystemSettingsPage.vue` | 管理员设置总览页，展示十三车间、别名映射、机列台账、PC 工艺映射、规则配置、用户管理、权限治理、QR 打印、AI 助手等入口。 |
| 设置抽屉 | `SettingsDrawer.vue` + `manage-settings-drawer.js` | 管理端右侧设置抽屉，会按当前账号权限显示或隐藏入口。 |
| `/manage/master` | `Workshop.vue` 等主数据页面 | 维护车间、班组、员工、机列、班次等基础资料。 |
| `/manage/alias` | `AliasMapping.vue` | 维护外部 MES、历史名称、内部标准名称之间的别名映射。 |
| `/manage/mes-terminal-bindings` | `MesTerminalBinding.vue` | 维护 MES 里显示为 `PC` 或泛化终端时，应该对应哪台机列和哪个工艺。 |
| `/manage/admin/users` | `UserManagement.vue` | 维护账号、角色、车间范围、手机端权限、管理权限、机列绑定、钉钉同步。 |

小白版理解：设置页不是“可有可无的后台菜单”。它决定了现场扫哪个二维码、哪个账号属于哪个车间、外部 MES 名字如何翻译成系统车间、PC 一体机如何匹配到真实机列。

### 25.2 主数据表和它们影响什么

| 表/模型 | 主要字段 | 影响范围 |
|---|---|---|
| `workshops` | `code`、`name`、`workshop_type`、`is_active` | 管理端车间筛选、日报车间列表、车间主任范围、填报端所属车间。 |
| `teams` | `workshop_id`、`code`、`name` | 手机填报账号班组归属、考勤和班次类统计。 |
| `employees` | `employee_no`、`name`、`workshop_id`、`team_id` | 考勤、人员基础资料。 |
| `equipment` | `workshop_id`、`qr_code`、`bound_user_id`、`assigned_shift_ids`、`operational_status` | 机列二维码、主操账号绑定、机列产量聚合、手机扫码入口。 |
| `shift_configs` | `code`、`name`、`start_time`、`end_time`、`business_day_offset` | 班次显示顺序、业务时间口径、日报/实时看板班次聚合。 |
| `users` | `role`、`workshop_id`、`team_id`、`is_mobile_user`、`is_reviewer`、`is_manager`、`data_scope_type` | 谁能登录管理端、谁能进手机填报、谁是车间主任、谁能看全厂或本车间数据。 |
| `master_code_aliases` | `entity_type`、`canonical_code`、`alias_code`、`alias_name`、`source_type` | 把历史车间名、外部 MES 名称、内部标准名对齐。 |
| `mes_terminal_bindings` | `terminal_code`、`mes_device_name`、`workshop_name`、`process_name`、`equipment_id`、`confidence` | 解决外部 MES 记录设备名是 `PC` 时，系统如何推断真实机列。 |
| `audit_logs` | `action`、`module`、`table_name`、`record_id`、`old_value`、`new_value` | 主数据和账号修改留痕。 |

### 25.3 当前生产车间口径

当前代码和测试锁定的“活跃生产车间”是 13 个：

`铸锭`、`铸二`、`铸三`、`热轧`、`淬火车间`、`精整`、`拉矫`、`园区剪切`、`新厂在线`、`园区在线`、`冷轧1650`、`冷轧1850`、`冷轧2050`。

注意两个边界：

- `成品库`、回收、大修等专项/管理口径不能直接混进“13 个活跃生产车间”过滤里。
- 历史名称会被归一，比如 `铸轧二` -> `铸二`，`1650冷轧车间` -> `冷轧1650`，`园区淬火` -> `淬火车间`。

当前无一体机/非 MES 主终端车间策略也有代码约束：`铸锭`、`铸二`、`铸三`、`热轧`、`淬火车间` 属于不能简单依赖现场一体机终端的车间。热轧、铸二、铸三更偏坯料卷人工补录；铸锭偏每日汇总；后工序如精整更适合作为外部 MES 主数据优先的车间。

### 25.4 账号字段怎么影响权限

`users` 不是只保存用户名密码，它还决定入口和数据范围：

| 字段 | 含义 |
|---|---|
| `role` | 角色类型，比如管理员、主操、电工、内勤、车间主任等。 |
| `is_mobile_user` | 是否能进入手机填报端。管理员不是手机填报用户。 |
| `is_manager` | 是否能进入管理端管理视图。车间主任会被设置为管理人员，但范围受限。 |
| `is_reviewer` | 是否能进入审核/复核类视图。 |
| `workshop_id` | 账号绑定车间，车间主任必须有这个字段。 |
| `team_id` | 账号绑定班组。 |
| `data_scope_type` | 数据范围，比如全厂、本车间、指定班次等。 |
| `assigned_shift_ids` | 指定班次范围。 |
| `equipment.bound_user_id` | 哪台机列绑定哪个用户，影响扫码填报和机列聚合。 |

小白版理解：一个账号能看哪里、能填哪里，不是只看角色名，还要同时看 `is_mobile_user`、`is_manager`、`workshop_id`、`team_id`、`data_scope_type` 和机列绑定。

### 25.5 写接口权限边界

| 模块 | 只读 | 写操作 | 当前权限结论 |
|---|---|---|---|
| 车间/班组/员工/班次 | `GET /api/v1/master/*` | `POST/PUT/DELETE /api/v1/master/workshops|teams|employees|shift-configs` | 写操作需要管理员。 |
| 机列台账 | `GET /api/v1/master/equipment` | 更新机列、创建机列账号、重置 PIN、切换状态 | 写操作需要管理员。 |
| 别名映射 | `GET /api/v1/master/aliases` | 新增、更新、删除 | 写操作需要管理员；删除是软停用，不是物理删除。 |
| PC 终端映射 | `GET /api/v1/master/mes-terminal-bindings` | 新增、更新、删除 | 写操作需要管理员；删除是软停用。 |
| 用户管理 | `GET /api/v1/users/` | 新增、更新、停用、重置密码、钉钉同步 | 用户管理路由需要管理员。 |

这里最重要的安全结论：不能只看前端有没有入口。前端隐藏不是安全边界，后端 `_require_admin()` 和对应测试才是安全边界。

### 25.6 对业务链路的影响

| 配置错了 | 会出现什么业务问题 |
|---|---|
| 车间名没归一 | 日报、实时看板、填报明细会把同一个车间拆成多个名字。 |
| 机列没绑定用户 | 主操扫码填报可能不能正确归到机列，或者车间主任看板缺机列明细。 |
| PC 终端没绑定机列 | 外部 MES 记录里设备名是 `PC` 时，系统无法稳定判断真实机列。 |
| 用户车间范围错 | 车间主任可能看不到本车间，或者错误看到其他车间。 |
| 班次配置错 | 业务日、日报、缺报、实时看板的班次口径会对不上。 |
| 别名映射错 | 外部 MES、历史报表、前端展示会出现同一对象多个名字。 |

### 25.7 后续仍要谨慎的点

| 优先级 | 建议 |
|---|---|
| 高 | 不要硬删旧车间、旧账号、旧别名。先确认是否还有历史数据、二维码、报表或审计链路依赖。 |
| 高 | PC 终端到机列/工艺映射要继续补齐，这是外部 MES 数据自动替代人工填报的关键前置条件。 |
| 中 | 用户管理页看到重复角色时，要先看是否有真实提交记录和二维码绑定，再决定停用。 |
| 中 | 主数据改动后至少跑主数据权限、用户管理、活跃车间、别名、PC 终端绑定这几组测试。 |

## 26. 本轮新增验证记录：主数据、账号、别名和终端映射

本轮没有修改业务代码，只做结构追踪、定向测试和文档合并。

| 验证类型 | 命令 | 结果 | 能证明什么 |
|---|---|---|---|
| 后端定向测试 | `python -m pytest -q backend/tests/test_master_write_permissions.py backend/tests/test_users_routes.py backend/tests/test_alias_mapping.py backend/tests/test_active_workshops.py backend/tests/test_config_readiness_service.py` | `31 passed` | 主数据写权限、用户管理、别名 CRUD、PC 终端绑定、13 个生产车间和配置就绪检查通过现有自动测试。 |
| 前端测试集 | `npm run test -- --run frontend/tests/activeWorkshopCanonical.test.js frontend/tests/mesTerminalBindingPage.test.js frontend/tests/aliasMappingDesign.test.js frontend/tests/userManagementDesign.test.js frontend/tests/workshopMasterDesign.test.js frontend/tests/manageSettingsDrawer.test.js frontend/tests/frontendSecondPassPlan.test.js` | `666 passed` | 当前前端测试脚本实际跑了全部 `frontend/tests/*.test.js`，覆盖活跃车间、设置入口、用户管理、别名映射、车间主数据、PC 终端映射等前端契约。 |
| 结构追踪 | CodeGraph + 关键路由/API/模型文件阅读 | 已确认 | 能说明主数据、用户、机列、别名和 PC 终端映射之间的影响关系。 |

边界说明：这不是生产环境真实账号浏览器全流程 QA，也没有对线上主数据做任何修改。它能证明当前代码层面边界清楚，但不能替代生产配置审计和真实账号逐项核对。

## 27. 追加理解：AI 助手、钉钉和外部通讯治理

本节补“AI 和外部通讯到底会不会真的发消息、会不会自动改数据”。结论先说清楚：当前设计不是让 AI 直接向钉钉群乱发消息，而是经过事件、发件箱、通道、演练/真实发送、外部日志这一整套闸门。

### 27.1 前端入口

| 入口 | 前端位置 | 作用 |
|---|---|---|
| `/manage/ai-assistant` | `AiWorkstation.vue` | AI 工作台，包含对话、主动汇报、关注列表。 |
| 管理端常驻抽屉 | `AiAssistantDrawer.vue` | 管理端右侧 AI 助手抽屉，可根据当前页面上下文提问。 |
| `/manage/admin/agents` | `AgentManagementPage.vue` | 通讯治理台，只给管理员看，用来看智能体、通道、事件、多模态证据、审核操作、发件箱、知识口径。 |
| `/entry` 钉钉环境 | `MobileEntry.vue` + `dingtalk-jsapi-loader.js` | 手机端在钉钉内尝试 H5 免登，失败时回退到账号登录。 |

小白版理解：`AI 助手`是给人问问题、看汇报；`通讯治理台`是看“系统准备发什么、有没有真的发、是否还在演练”。

### 27.2 后端入口

| 后端路径 | 主要作用 | 是否有副作用 |
|---|---|---|
| `/api/v1/ai/runtime` | 查看 AI 当前是 LLM 还是规则兜底 | 只读 |
| `/api/v1/ai/assistant/conversations*` | AI 对话列表、创建对话、消息读写 | 会写对话和消息 |
| `/api/v1/ai/assistant/ask` | 基于当前系统数据回答问题 | 会构造上下文包，可能记录使用量 |
| `/api/v1/ai/briefings` | 查看主动汇报 | 只读 |
| `/api/v1/ai/briefings/generate-now` | 立即生成一条主动汇报 | 会写 `ai_briefing_events` |
| `/api/v1/ai/watchlist` | 关注对象列表和增删改 | 增删改会写关注项 |
| `/api/v1/assistant/actions` | AI 建议后的处置动作，比如校验、催报、核对、提升草稿 | 有业务副作用，不能当只读测试按钮 |
| `/api/v1/agent-management/overview` | 通讯治理总览 | 只读，管理员可用 |
| `/api/v1/agent-management/knowledge` | 查看治理知识口径 | 只读，管理员可用 |
| `/api/v1/agent-management/knowledge/answer` | 对治理知识提问 | 计算回答，不改业务指标 |
| `/api/v1/dingtalk/h5-login` | 钉钉 H5 免登 | 会更新钉钉绑定和最近登录时间 |

### 27.3 数据表怎么分工

| 表/模型 | 保存什么 | 业务含义 |
|---|---|---|
| `ai_conversations` | AI 会话 | 谁创建了哪些对话。 |
| `ai_messages` | AI 消息 | 人和 AI 的问答内容。 |
| `ai_context_packs` | AI 回答前整理出的上下文包 | AI 回答所依据的“证据包”。 |
| `ai_briefing_events` | AI 主动汇报事件 | 开班、巡检、异常快报、管理层简报等。 |
| `ai_watchlist_items` | 关注列表 | 管理者想长期关注的车间、机列、卷材、工艺或指标。 |
| `agent_profiles` | 智能体身份 | 比如全厂调度 Agent、车间汇报 Agent。 |
| `communication_channels` | 外部通道 | 钉钉群等通道，关键字段是 `dry_run`。 |
| `agent_channel_bindings` | 智能体和通道绑定 | 哪个智能体允许往哪个通道发消息。 |
| `agent_events` | 智能体事件 | 主动汇报、异常检测、现场证据等事件。 |
| `agent_outbox_messages` | 发件箱 | 等待发送、演练、已发送、失败的消息。 |
| `external_message_logs` | 外部发送日志 | 每次演练或真实外发的结果留痕。 |
| `multimodal_evidence` | 图片、语音、附件、文本证据 | 现场人员通过钉钉等方式补充的证据。 |
| `agent_operation_approvals` | 高风险操作审核 | 补产量、发布日报这类动作先预览、确认、再执行。 |
| `agent_rate_limits` | 限流记录 | 防止同类主动汇报短时间刷屏。 |

### 27.4 外部消息真实链路

当前外部通讯链路是：

`智能体事件` -> `发件箱消息` -> `通道配置` -> `dry-run 演练或真实发送` -> `外部发送日志`

这里有几个保护点：

| 保护点 | 作用 |
|---|---|
| `communication_channels.dry_run=true` | 只记录演练，不调用真实钉钉发送。 |
| 通道必须是激活状态 | 通道停用或不存在时，消息会失败并留日志。 |
| 智能体必须绑定通道 | 未绑定时不能入队，避免任意智能体乱发。 |
| 真实外发只支持指定通道类型 | 当前真实群消息走 `dingtalk_group`。 |
| `agent_rate_limits` | 同一时间窗口内重复汇报会被抑制，但事件仍会留档。 |
| `external_message_logs` | 每次 dry-run、sent、failed 都有记录。 |

小白版理解：系统先把“准备说的话”放进发件箱；如果通道是演练模式，就只记账不发群；只有通道允许真实发送时，才会调用钉钉。

### 27.5 AI 回答和 LLM 边界

AI 助手不是随便编答案。当前后端会先从系统里取事实，再生成回答：

1. 读取工厂总览、机列、卷材、同步新鲜度等事实。
2. 按当前用户权限过滤数据范围。
3. 清理敏感字段，比如 `password`、`secret`、`token`、`credential`、`api_key`。
4. 先生成一个规则兜底答案。
5. 如果 LLM 配置完整、没有超过每日额度，再让 LLM 把规则答案整理成更好读的中文。
6. 如果 LLM 失败或没配置，就直接返回规则答案。

这意味着：AI 可以辅助解释和汇总，但不能脱离数据中枢已有事实自由编指标。

### 27.6 主动汇报怎么生成

主动汇报主要有两类：

| 类型 | 服务 | 说明 |
|---|---|---|
| AI 页面内简报 | `ai_briefing_service.py` | 写入 `ai_briefing_events`，用于 AI 助手里的“主动汇报”列表。 |
| 外部通讯主动汇报 | `agent_active_reporting_service.py` | 写入 `agent_events` 和 `agent_outbox_messages`，用于后续钉钉群或其他通道。 |

两者不要混为一谈。页面里出现一条 AI 汇报，不等于钉钉群已经收到消息；发件箱里有消息，也不等于已经真实外发，要看通道是不是 `dry_run`、消息状态是不是 `sent`。

### 27.7 多模态证据和审核治理

多模态证据支持图片、语音、附件、文本，也能把钉钉消息转成证据记录。当前设计非常谨慎：

| 机制 | 当前结论 |
|---|---|
| 证据默认状态 | `machine_only`，也就是机器识别或系统记录阶段。 |
| 是否允许直接改指标 | 默认 `metric_write_allowed=false`。 |
| 人工确认后 | 状态可变为 `human_confirmed`，但仍不自动开放指标写入。 |
| 高风险操作 | `supplement_production`、`publish_daily_report` 必须进入预览和确认流程。 |
| 默认执行模式 | `execute_confirmed_operation(..., dry_run=True)` 时只演练，不真实写业务数据。 |

小白版理解：图片、语音可以作为“证据”，但不能自动变成产量、能耗、日报数据；真正改数据必须走审核确认。

### 27.8 钉钉能力边界

钉钉目前承担三类能力：

| 能力 | 当前代码路径 | 注意事项 |
|---|---|---|
| H5 免登 | `/api/v1/dingtalk/h5-login` | 会根据钉钉 userid/unionid 找系统账号，并更新最近登录时间。 |
| 工作通知 | `send_work_notification()` | 发给具体钉钉用户；可被 `DINGTALK_NOTIFY_DRY_RUN` 保护。 |
| 群消息 | `send_group_message()` | 发给钉钉群 chatid；外部通讯发件箱真实发送时会走这里。 |
| 考勤同步 | `sync_recent_clock_records()` 定时任务 | 每 30 分钟拉取最近考勤记录，依赖钉钉配置和人员绑定。 |
| 通讯录同步 | `/api/v1/users/sync-dingtalk` | 管理员操作，会把钉钉身份绑定到系统用户，不能当只读测试。 |

### 27.9 权限和安全边界

| 模块 | 权限结论 |
|---|---|
| AI 助手 | 管理员、管理者、复核者可访问工厂 AI 上下文。 |
| 通讯治理台 | 只有管理员可访问。 |
| AI 处置动作 | 需要管理员或管理者，并且还会按数据范围校验。 |
| 全厂处置 | 普通本车间管理者不能执行全厂类动作。 |
| 车间范围处置 | 要匹配本车间、本班次或授权范围。 |
| 通道密钥展示 | 前端治理台只显示 `channel_key_masked`，不展示完整通道 key 或 `secret_ref`。 |

### 27.10 后续要谨慎的点

| 优先级 | 建议 |
|---|---|
| 高 | 生产 QA 不要随便点 POST 类 AI、钉钉、assistant action、用户同步接口，它们可能写记录或触发业务动作。 |
| 高 | 启用真实钉钉群外发前，必须确认通道不在 `dry_run`、目标群正确、agent 绑定正确、限流窗口正确。 |
| 高 | 补产量、发布日报必须保留“指定人员 + 预览 + 确认 + 留档”四道门。 |
| 中 | 治理台事件类型中文映射要继续覆盖真实后端事件，比如 `factory_overview_report`、`workshop_status_report`。 |
| 中 | 钉钉通讯录同步前要先确认开放平台权限和绑定策略，避免把人员绑定错账号。 |
| 中 | AI 回答可以辅助判断，但日报最终发布仍要看明确数据来源和审核状态。 |

## 28. 本轮新增验证记录：AI、钉钉和外部通讯治理

本轮没有修改业务代码，只做结构追踪、定向测试和文档合并。

| 验证类型 | 命令 | 结果 | 能证明什么 |
|---|---|---|---|
| 后端定向测试 | `python -m pytest -q backend/tests/test_agent_communication_service.py backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_operation_approval_service.py backend/tests/test_agent_multimodal_evidence_service.py backend/tests/test_agent_management_router.py backend/tests/test_agent_management_overview_service.py backend/tests/test_ai_context_service.py backend/tests/test_ai_briefing_service.py backend/tests/test_ai_assistant_routes.py backend/tests/test_dingtalk_h5_login.py backend/tests/test_dingtalk_service.py backend/tests/test_users_dingtalk_sync.py` | `73 passed` | 外部通讯发件箱、dry-run、真实发送分支、主动汇报、限流、操作审批、多模态证据、治理台权限、AI 上下文、AI 简报、钉钉 H5 登录和钉钉用户同步的现有自动测试通过。 |
| 前端测试集 | `npm run test -- --run frontend/tests/agentManagementPage.test.js frontend/tests/aiAssistantUiContract.test.js frontend/tests/aiWorkstationActions.test.js frontend/tests/dingtalkAutoLogin.test.js frontend/tests/assistantFallbackTruthfulness.test.js` | `666 passed` | 当前前端测试脚本实际跑了全部 `frontend/tests/*.test.js`，覆盖通讯治理台入口、AI 助手抽屉、AI 工作台、建议动作、钉钉 H5 登录入口和“规则兜底不冒充在线 AI”等前端契约。 |
| 结构追踪 | CodeGraph + 关键路由/API/模型/服务文件阅读 | 已确认 | 能说明 AI、主动汇报、外部发件箱、钉钉、审批和多模态证据之间的真实边界。 |

边界说明：这不是生产环境真实钉钉群外发测试，也没有调用真实发送或真实业务处置按钮。它能证明当前代码层面的安全闸门和契约稳定，但不能替代真实通道配置、真实群、真实人员绑定和浏览器端到端验收。

## 29. 追加理解：运行健康、部署门禁、定时任务和外部同步

本节补“系统是否真的跑得稳、部署时靠什么拦住坏版本、外部数据同步怎么判断健康”。结论先说清楚：`/healthz` 只能证明应用活着，`/readyz` 才看主业务准备状态，但即使 `/readyz` 返回 200，也要继续看 `details` 里的外部同步细节，不能一句话说“所有外部系统都完全正常”。

### 29.1 健康检查不是一个意思

| 路径 | 小白版含义 | 代码依据 | 注意事项 |
|---|---|---|---|
| `/healthz` | 应用进程活着 | `health_service.build_liveness_payload()` | 只返回 `app=ok`，不代表数据库、MES、能耗、钉钉都正常。 |
| `/api/v1/healthz` | 同上，带 API 前缀 | `main.py` 兼容路由 | 方便不同探针都能访问。 |
| `/readyz` | 主业务准备情况 | `health_service.build_readiness_payload()` | 会检查数据库、上传目录、pipeline、MES 同步、物联网能耗同步等信息。 |
| `/api/v1/readyz` | 同上，带 API 前缀 | `main.py` 兼容路由 | 部署脚本也会用 readiness 判断是否可以继续。 |

最关键的区别：

| 项目 | 判断方式 |
|---|---|
| 应用是否活着 | 看 `/healthz`。 |
| 核心业务是否可用 | 看 `/readyz` 的 HTTP 状态和 `status`。 |
| 外部 MES 是否同步新鲜 | 看 `/readyz.details.mes_sync`，尤其是 `status`、`last_run_status`、`lag_seconds`、`sync_freshness_seconds`。 |
| 物联网能耗库是否接入 | 看 `/readyz.details.iot_energy_sync`。当前没配置时是 `unconfigured`，这不等于后端挂了。 |
| 自动日报 pipeline 是否能跑 | 看 `/readyz.details.pipeline.hard_gate_passed` 和相关 checks。 |

小白版理解：`healthz` 像“机器插电了没”，`readyz` 像“机器能不能开工”。但外部数据是否新鲜，还要看机器面板里的细项。

### 29.2 `/readyz` 里哪些会挡部署

`/readyz` 会明确检查：

| 检查项 | 出问题时影响 |
|---|---|
| 数据库连接 | 直接 `not_ready`，因为系统不能读写核心数据。 |
| 上传目录可写 | 直接 `not_ready`，因为二维码、附件、证据等可能无法保存。 |
| 自动 pipeline 硬门禁 | 如果 `AUTO_PIPELINE_REQUIRE_READY=true` 且硬门禁不过，会 `not_ready`。 |
| MES 同步状态 | 会写入 `checks.mes_sync` 和 `details.mes_sync`，用于判断外部数据是否新鲜或失败。 |
| 物联网能耗同步 | 会写入 `checks.iot_energy_sync` 和 `details.iot_energy_sync`，当前未配置是预期边界。 |

需要特别谨慎的一点：外部同步异常会在 readiness 里暴露出来，但不能只看 HTTP 200/503 就下结论。排查线上“数据没同步”时，要看 `details`，不能只看 `status=ready`。

### 29.3 Nginx 对外入口

Nginx 当前做了几件事：

| 入口 | 转发方式 | 作用 |
|---|---|---|
| `/healthz` | 转到后端 `/healthz` | 给外部探针看应用存活。 |
| `/readyz` | 转到后端 `/readyz` | 给部署和运维看业务 readiness。 |
| `/api/` | 转到后端 API | 前端所有业务接口走这里。 |
| `/api/v1/realtime/stream` | 特殊 SSE 转发，关闭缓冲 | 实时大屏事件流，避免被 Nginx 缓冲卡住。 |
| `/uploads/` | 转到后端上传资源 | 二维码、附件、证据等资源。 |
| 其他前端路径 | `try_files ... /index.html` | 管理端和手机端前端路由刷新不 404。 |

小白版理解：Nginx 是门卫，普通页面、API、实时流、上传文件、健康检查走的门不一样。实时流这扇门专门关掉了缓冲，防止“前端一直连接但看不到新数据”。

### 29.4 部署脚本的安全门

`scripts/deploy_systemd_host.sh` 是当前生产机 systemd 部署脚本。它不是简单复制文件，而是按顺序做防护：

| 步骤 | 作用 |
|---|---|
| 预检 `.env` | 要求生产环境配置存在。 |
| 检查 `APP_ENV=production` | 防止拿错环境。 |
| 检查 `SECRET_KEY` 和初始管理员密码强度 | 防止弱密钥上线。 |
| 检查 `DATABASE_URL` | 没有数据库不继续。 |
| 默认不自动 `git pull` | 除非显式加 `--pull`，避免误拉未知代码。 |
| 数据库备份 | 迁移前先备份，降低回滚成本。 |
| 后端依赖和迁移 | 安装依赖、执行 Alembic 数据库迁移。 |
| 初始化主数据 | 确保基础车间、机列、角色等底账存在。 |
| 创建管理员 | 只在显式给 `ADMIN_LOGIN_PASSWORD` 时才重置密码，避免部署悄悄改登录密码。 |
| 前端构建 | 构建管理端/手机端页面。 |
| 重启服务 | 重启后端 systemd 和 Nginx。 |
| 轮询 `/readyz` | 要求 HTTP 200 且 `hard_gate_passed=true`。 |
| 可选外部 readiness | 加 `--require-external` 后，再跑统计模块外部 readiness 自检。 |

这解释了一个重要问题：管理端密码不应该因为普通部署自动变化；只有部署时显式传入重置密码变量，才会触发重置。

### 29.5 定时任务总表

当前后端启动时会根据配置注册定时任务，并用 PostgreSQL advisory lock 避免多进程重复跑任务。

| 任务 | 频率 | 作用 |
|---|---|---|
| `default_schedule_seed` | 每天 00:05 | 补默认排班/计划。 |
| `daily_report` | 每天 08:00 | 生成上一业务日生产日报。 |
| `deterministic_pipeline` | 每小时 | 在 readiness 通过后，跑聚合和汇报流程。 |
| `reminder_sweep` | 每 30 分钟 | 扫描提醒状态。 |
| `fill_reminder` | 每天 08:00、14:00、20:00 | 推送填报提醒。 |
| `ai_hourly_briefing` | 每小时 | 生成 AI 巡检简报。 |
| `aluminum_price_daily` | 工作日 10:30 | 同步铝价信息。 |
| `executive_daily_snapshot` | 每天 08:20 | 生成管理层快照。 |
| `mes_sync_core` | 按 `MES_SYNC_POLL_SECONDS` | 同步外部 MES 核心卷材快照。 |
| `mes_sync_realtime` | 按 `MES_REALTIME_SYNC_POLL_SECONDS` | 同步实时投影。 |
| `mes_sync_business` | 按 `MES_BUSINESS_SYNC_POLL_MINUTES` | 同步业务投影，比如在制、包装、产量。 |
| `mes_sync_reference` | 按 `MES_REFERENCE_SYNC_POLL_MINUTES` | 同步工艺、设备、机列等基础参考。 |
| `iot_energy_sync` | 按 `IOT_ENERGY_SYNC_POLL_SECONDS` | 同步物联网能耗影子数据，当前依赖后续数据库配置。 |
| 钉钉考勤同步 | 每 30 分钟 | 拉取最近钉钉考勤记录。 |
| `realtime-events-cleanup` | 每小时 | 清理 48 小时前的实时事件。 |
| `data_archive` | 每周日 02:00 | 做历史数据归档。 |

小白版理解：系统不只是用户打开页面才算一次数据，它后台自己也会按时间跑同步、日报、提醒、AI 简报、归档。

### 29.6 外部 MES 同步链路

外部 MES 同步的真实链路是：

`外部 MES 适配器` -> `同步任务` -> `本地 mes_* 投影表` -> `同步日志/游标` -> `实时事件` -> `管理端页面`

当前分成几组：

| 同步组 | 主要内容 | 用途 |
|---|---|---|
| 核心卷材快照 | 卷材、随行卡、客户、规格、状态等 | 卷级线索、在制料、机列追踪。 |
| 实时投影 | 跟单、派工等较实时信息 | 调度大屏、实时状态。 |
| 业务投影 | 在制总量、库存、车间工序、包装、投料、成品率等 | 日报、生产分析、包装产量口径。 |
| 参考投影 | 工艺、设备、基础项、MES 机列 | 名称映射、PC 终端到机列匹配。 |

同步健康里要重点看：

| 字段 | 含义 |
|---|---|
| `configured` | 外部数据源是否已经配置。 |
| `migration_ready` | 本地投影表/迁移是否准备好。 |
| `status` | 当前同步状态，如 `fresh`、`stale`、`failed`、`unconfigured`。 |
| `last_run_status` | 最近一次同步任务成功还是失败。 |
| `fetched_count` | 从外部抓到多少条。 |
| `upserted_count` | 写入或更新本地多少条。 |
| `replayed_count` | 回放或补偿处理多少条。 |
| `lag_seconds` | 数据延迟多久。 |
| `sync_freshness_seconds` | 距离最近成功同步过去多久。 |
| `action_required` | 系统建议下一步，比如检查供应商、检查同步延迟、配置 MES。 |

小白版理解：不是“能连上数据库就等于数据对了”。还要看抓到了几条、写进了几条、最近一次成功是什么时候、延迟多久。

### 29.7 物联网能耗同步边界

物联网能耗库当前还没正式接入。代码已经有 `iot_energy_sync_service` 和 `iot_energy_snapshots` 影子表链路，但 readiness 中 `iot_energy_sync=unconfigured` 目前应理解为“外部能耗数采数据库尚未提供/配置”，不是后端代码故障。

等后续拿到能耗数采数据库时，应该按这条链路接：

`物联网能耗数据库只读账号` -> `iot_energy_sync_service` -> `iot_energy_snapshots` -> `能耗中心/吨耗算法`

不要让前端直接连外部能耗数据库，仍然必须由后端同步、清洗、统一口径后再给页面。

### 29.8 外部 readiness 和部署 readiness 的区别

系统里还有一个更偏“正式试用前自检”的能力：`check_statistics_module_ready.py` 和 `/api/v1/dashboard/external-readiness`。

它检查的不只是应用能不能跑，还包括：

| 检查方向 | 例子 |
|---|---|
| 外部 MES 配置 | `MES_ADAPTER`、SQL Server/MVC/REST 相关字段是否齐。 |
| 自动日报 workflow | `WORKFLOW_ENABLED`、自动发布、自动推送是否开启。 |
| LLM/AI 配置 | 模型地址、密钥、模型名或 endpoint 是否齐。 |
| 钉钉配置 | 企业、应用、agent、通讯录权限和人员绑定是否齐。 |
| 应用连接外发 | 外发 API 地址、密钥、是否 dry-run。 |

所以它更像“上线前体检清单”，而 `/readyz` 更像“当前服务能不能对外提供主功能”。

### 29.9 后续排查建议

| 场景 | 第一反应不应该是 | 应该先看 |
|---|---|---|
| 页面能打开但数据旧 | “前端坏了” | `/readyz.details.mes_sync` 的 `lag_seconds` 和 `last_run_status`。 |
| 实时大屏一直连接 | “后端挂了” | SSE 是否中断、前端是否回落轮询、Nginx 是否关闭缓冲。 |
| 能耗中心没有物联网数据 | “能耗算法错了” | `iot_energy_sync` 是否配置、`iot_energy_snapshots` 是否有数据。 |
| 部署后登录密码变了 | “系统自动改密码” | 部署时是否显式设置了 `ADMIN_LOGIN_PASSWORD`。 |
| readiness 是 200 但外部数据不新鲜 | “readyz 没用” | 继续看 `details`，HTTP 200 不等于所有外部系统都满血。 |

## 30. 本轮新增验证记录：运行健康、部署门禁和外部同步

本轮没有修改业务代码，只做结构追踪、定向测试和文档合并。

| 验证类型 | 命令 | 结果 | 能证明什么 |
|---|---|---|---|
| 后端运行态定向测试 | `python -m pytest -q backend/tests/test_health.py backend/tests/test_scheduler.py backend/tests/test_statistics_module_ready_script.py backend/tests/test_iot_energy_sync_service.py backend/tests/test_dashboard_routes.py::test_external_readiness_dashboard_route_exposes_hard_issues backend/tests/test_dashboard_routes.py::test_external_readiness_dashboard_route_exposes_missing_inputs_without_secret_values backend/tests/test_dashboard_routes.py::test_external_readiness_dashboard_route_rejects_mobile_user` | `54 passed` | 健康检查、readiness、定时任务注册、统计模块自检、物联网能耗同步、外部 readiness 权限边界目前有自动测试兜底。 |
| 前端运行态定向测试 | `node --test tests/managementCommandCenter.test.js tests/useRealtimeStream.test.js` | `32 passed` | 管理端状态中枢、实时大屏业务日选择、实时流授权头、SSE 解析、卡住连接后的轮询兜底等前端契约通过。 |
| 云端只读健康探针 | 访问 `https://xtmijd.com/healthz`、`https://xtmijd.com/readyz`、`https://xtmijd.com/api/v1/healthz`、`https://xtmijd.com/api/v1/readyz` | 4 个入口均 HTTP 200；`readyz.status=ready`；`database=ok`、`uploads=ok`、`pipeline=ok`、`mes_sync=ok`、`iot_energy_sync=unconfigured`；`mes_status=fresh`；`iot_action=configure_iot_energy` | 云端生产入口当前可达，外部 MES 同步健康，物联网能耗库仍是未配置边界。 |
| 结构追踪 | CodeGraph + `main.py`、`health.py`、`scheduler.py`、`event_bus.py`、`mes_sync.py`、`iot_energy_sync.py`、`deploy_systemd_host.sh`、`nginx.conf` 阅读 | 已确认 | 能说明服务启动、健康检查、部署门禁、后台任务、外部 MES/能耗同步、实时事件流之间怎么连接。 |

边界说明：这不是生产环境真实部署演练，也没有去触发真实 MES 同步、真实物联网能耗同步或真实钉钉外发。它能证明代码层面的运行骨架和测试契约稳定，但不能替代生产机只读 health 检查、外部数据源真实延迟检查和上线后日志观察。

## 31. 追加理解：业务日、班次、日报默认日期和页面参数口径

本节补“为什么同一天页面看起来有时像昨天、有时像今天”。结论先说清楚：系统不是按自然日 00:00 切一天，而是按业务规则切日。生产角色、电工、MES 生产数据按 `07:30` 切；内勤/专项每日一录按 `09:30` 切；日报、能耗、填报明细这类历史账默认看“上一个已经完整结束的生产业务日”。

### 31.1 两套切日规则

| 口径 | 切点 | 24 小时窗口 | 主要适用对象 | 代码来源 |
|---|---:|---|---|---|
| 生产业务日 | 07:30 | 当天 07:30 到次日 07:30 | 主操、电工、MES 生产投影、实时看板、车间看板、生产分析 | `resolve_production_business_date()`、`production_business_window()`、`inferBusinessDate()` |
| 内勤每日一录业务日 | 09:30 | 当天 09:30 到次日 09:30 | 成品库、内勤、辅材、专项每日一录 | `resolve_owner_daily_business_date()`、`inferOwnerDailyBusinessDate()` |

小白版理解：生产一线从早上 `07:30` 开始算新的一天，因为大夜班到 `07:30` 才结束；内勤从 `09:30` 开始算新的一天，因为他们早上补录前一天完整数据。

### 31.2 班次顺序和时间

当前前端 `shiftClock.js` 锁定的班次是：

| 班次 | 代码 | 时间 |
|---|---|---|
| 长白班 | `A` | 07:30 到 15:30 |
| 小夜班 | `B` | 15:30 到 23:30 |
| 大夜班 | `C` | 23:30 到次日 07:30 |

所以凌晨 `02:30` 虽然自然日已经变了，但业务日仍然归到前一天的生产业务日。

### 31.3 页面默认日期怎么选

| 页面/模块 | 默认日期 | 为什么 |
|---|---|---|
| `/manage/live` 实时大屏 | 当前生产业务日 | 看正在发生的调度和填报状态。 |
| `/manage/workshop-dashboard` 车间看板 | 当前生产业务日 | 车间主任要看本业务日实时情况。 |
| 老报表实时页、考勤总览、异常列表 | 当前生产业务日 | 看当前窗口内正在产生的问题。 |
| `/manage/today` 昨日日报 | 上一个完成的生产业务日 | 日报要等大夜班结束后才完整。 |
| `/manage/production` 生产分析 | 上一个完成的生产业务日 | 分析页要避免拿未结束的一天当最终值。 |
| `/manage/fill-details` 填报明细 | 上一个完成的生产业务日 | 方便查完整一天的补录和缺报。 |
| `/manage/energy` 能耗中心 | 上一个完成的生产业务日 | 吨耗和总能耗要等整日结束后才可信。 |
| `/entry`、`/entry/fill` 主操/电工 | 后端当前班次上下文 | 以后端返回的 `business_date` 和 `shift_id` 为准。 |
| 内勤/专项手机入口 | 内勤每日一录业务日 | 09:30 前填的算前一天。 |
| `/entry/history` 历史填报 | 当前生产业务日作为默认筛选 | 查的是整日记录，不只是当前班次。 |

这解释了一个常见疑问：早上 `08:00` 打开实时看板和日报页，它们可能默认不是同一天。实时看板在看 `07:30` 之后的新业务日，日报页在看已经完整结束的上一业务日。

### 31.4 `target_date` 和 `business_date` 不能混用

前端和后端目前有两类日期参数：

| 参数 | 主要给谁用 | 说明 |
|---|---|---|
| `target_date` | 工厂日报、厂长看板、日报快照、趋势接口 | 更像“我要看哪天的日报/快照”。 |
| `business_date` | 质量问题、对账问题、MES 缺口、实时聚合、能耗、填报明细 | 更像“我要查哪个业务日窗口里的明细”。 |

已验证的关键页面参数规则：

| 页面/功能 | 参数规则 |
|---|---|
| 异常时间线 | 工厂看板接口传 `target_date`；质量、对账、MES 缺口、实时聚合传 `business_date`。 |
| 车间看板 | 车间概览传 `target_date`；实时聚合、填报明细、待归属、MES 缺口、MES 工序、MES 在制传 `business_date`。 |
| 填报明细 | 人工填报明细、实时聚合、MES 缺口用 `business_date`；日报对照用 `target_date`。 |
| 能耗中心 | 查询能耗汇总用 `business_date`，默认上一个完成业务日。 |
| 今日/生产分析 | 日报快照走 `target_date`，实时聚合补充走 `business_date`。 |

如果把这两个参数搞混，就会出现“页面显示了旧日期异常”“日报和异常对不上”“缺报导出没数据”等问题。

### 31.5 后端怎么把 MES 时间归到业务日

外部 MES 投影不是简单用自然日。同步服务会把外部记录里的时间字段转成生产业务日：

| MES 投影 | 归属逻辑 |
|---|---|
| `mes_workshop_process_records` | 优先按工序结束时间 `end_time` 归属生产业务日。 |
| `mes_stock_records` | 优先按入库时间 `in_stock_date` 归属生产业务日。 |
| `mes_material_records` | 优先按生产时间 `production_date` 归属生产业务日。 |
| `mes_yield_records` | 优先按报表时间 `report_time` 归属生产业务日。 |
| `mes_wip_total_snapshots` | 没有业务日字段时，用 `production_business_window(business_date)` 过滤 `snapshot_at`。 |

小白版理解：MES 里一条记录发生在凌晨 `02:00`，系统不会把它算成自然日今天，而会按 `07:30` 口径算到上一生产业务日。

### 31.6 指标字典里的时间口径

核心指标字典 `CORE_METRIC_CONTRACTS` 已经把口径写明：

| 指标 | 时间口径 |
|---|---|
| 全厂总产量 | 生产业务日，主数据优先 MES 包装/成品库存口径。 |
| 机台用电 | 生产业务日，机台能耗明细优先。 |
| 正式成品率 | 生产业务日，优先正式成品率矩阵。 |
| 外部在制卷 | 生产业务日，按外部 MES 在制卷/工序状态过滤。 |
| 内勤业务日 | 09:30 起算，24 小时窗口。 |

这份字典是后续防止“口径写散”的关键锚点。

### 31.7 13 个活跃生产车间和成品库边界

本轮测试再次确认：活跃生产车间是 `13` 个，`成品库` 是内勤/管理口径，不应混进生产车间筛选。

测试锁定的例子：

| 输入名 | 标准名 |
|---|---|
| `铸轧二` | `铸二` |
| `园区淬火` | `淬火车间` |
| `成品库` | 不进入活跃生产车间列表 |
| `铸轧五` | 不进入活跃生产车间列表 |
| `冷轧三车间` | 不进入活跃生产车间列表 |

这和前面“13 个活跃生产车间 + 成品库/回收/大修保留为专项或历史口径”的结论一致。

### 31.8 当前仍要小心的点

| 风险 | 为什么要小心 | 建议 |
|---|---|---|
| 自然日和业务日混用 | 早上 07:30/09:30 前后最容易看错日期 | 页面文案要明确“业务日”，不要只写“今日”。 |
| `target_date` 和 `business_date` 混用 | 不同接口参数名不同，错传会查不到或查错日期 | 新增页面时先看接口定义，不要复制别的页面参数。 |
| 日报默认日期和实时看板默认日期不同 | 一个看完整历史日，一个看实时当前日 | 页面标题要继续用“昨日日报”“实时调度”区分。 |
| 内勤 09:30 口径和生产 07:30 口径不同 | 这不是 bug，是业务设计 | 做对账时要明确是人工补录还是生产主数据。 |
| 外部 MES 在制快照 | 快照类数据可能没有业务日字段 | 必须按 `production_business_window` 过滤时间窗口。 |

## 32. 本轮新增验证记录：业务日、班次和日期参数口径

本轮没有修改业务代码，只做结构追踪、定向测试和文档合并。

| 验证类型 | 命令 | 结果 | 能证明什么 |
|---|---|---|---|
| 后端时间口径测试 | `python -m pytest -q backend/tests/test_business_time_contract.py backend/tests/test_mobile_bootstrap.py backend/tests/test_core_metric_contracts.py` | `37 passed` | 生产业务日 07:30、内勤业务日 09:30、24 小时窗口、手机端业务日、核心指标口径字典目前有自动测试兜底。 |
| 前端时间口径测试 | `node --test tests/shiftClock.test.js tests/businessDateDefaults.test.js tests/manageAlertsTimeline.test.js tests/workshopEnergyLiveRegression.test.js tests/mobileHistoryAllDay.test.js` | `38 passed` | 班次切换、页面默认日期、异常页参数、填报历史整日查询、能耗/填报明细默认上一个完成业务日、13 个活跃生产车间过滤均通过。 |
| 结构追踪 | CodeGraph + `business_time.py`、`shiftClock.js`、`shift_context.py`、`mes_extended_service.py`、`metric_contracts.py`、`useAlertsTimeline.js` 阅读 | 已确认 | 能说明后端、前端、MES 投影、手机端、异常页和指标字典如何共同使用业务日。 |

边界说明：这不是生产真实数据逐字段对账，也没有用真实角色在浏览器里跨 07:30/09:30 做现场测试。它能证明代码和自动测试层面的时间口径一致；真正上线验收还需要在关键时间点做只读页面核对和真实角色流程 QA。

## 33. 追加理解：核心页面字段到 API、服务和数据表的映射矩阵

本节补“页面上的数字到底从哪里来”。结论先说清楚：前端核心页面不直接连数据库，更不会直接连外部 MES SQL Server。页面读取的是前端 API 模块；前端 API 调后端 `/api/v1/*`；后端路由再调用服务函数；服务函数最后读本地业务表和 `mes_*` 投影表。

### 33.1 核心页面总矩阵

| 页面 | 前端主文件 | 前端 API | 后端路由 | 后端服务 | 主要表 |
|---|---|---|---|---|---|
| `/manage/live` 实时大屏 | `LiveDashboardPage.vue` | `realtime.js` | `realtime.py` | `realtime_service.py` | `work_order_entries`、`mobile_shift_reports`、`machine_energy_records`、`mes_coil_snapshots`、`mes_workshop_process_records`、`mes_stock_records`、`realtime_events` |
| `/manage/today` 昨日日报 | `TodayPage.vue` + `useDashboardSnapshot.js` | `dashboard.js`、`factory-command.js`、`realtime.js` | `dashboard.py`、`factory_command.py`、`realtime.py` | `report_service`、`daily_overview_builder.py`、`factory_command_service.py`、`realtime_service.py` | `mes_stock_records`、`mes_workshop_process_records`、`work_order_entries`、`machine_energy_records`、`data_quality_issues`、`data_reconciliation_items` |
| `/manage/production` 生产分析 | `ProductionPage.vue` + `useDashboardSnapshot.js` | 同 `/manage/today` | 同 `/manage/today` | 同 `/manage/today` | 同 `/manage/today` |
| `/manage/coils` 卷级线索 | `CoilTracePage.vue` | `factory-command.js` | `factory_command.py` | `factory_command_service.py` | `mes_coil_snapshots`、`mes_workshop_process_records`、`mes_machine_line_snapshots`、`coil_flow_events` |
| `/manage/fill-details` 填报明细 | `FillDetailsPage.vue` | `realtime.js`、`dashboard.js` | `realtime.py`、`dashboard.py` | `realtime_service.py`、`daily_overview_builder.py` | `work_order_entries`、`mobile_shift_reports`、`machine_energy_records`、`mes_workshop_process_records` |
| `/manage/energy` 能耗中心 | `EnergyCenter.vue` | `energy.js` | `energy.py` | `energy_service.py` | `machine_energy_records`、`mobile_shift_reports`、`work_order_entries`、`energy_import_records`、`iot_energy_snapshots`、`mes_stock_records`、`mes_workshop_process_records` |
| `/manage/alerts` 异常中心 | `AlertsPage.vue` + `useAlertsTimeline.js` | `dashboard.js`、`quality.js`、`reconciliation.js`、`realtime.js` | `dashboard.py`、`quality.py`、`reconciliation.py`、`realtime.py` | `report_service`、`quality_service.py`、`reconciliation_service.py`、`realtime_service.py` | `data_quality_issues`、`data_reconciliation_items`、`work_order_entries`、`mes_workshop_process_records` |
| `/manage/workshop-dashboard` 车间看板 | `WorkshopDashboardPage.vue` | `dashboard.js`、`realtime.js`、`mes.js` | `dashboard.py`、`realtime.py`、`mes.py` | `report_service`、`realtime_service.py`、`mes_extended_service.py` | 上述车间范围内的数据表 |

小白版理解：页面不是自己算一切，而是像“点菜”。前端点菜，后端厨房做菜，数据库是食材仓库。

### 33.2 关键指标字段来源

| 页面字段 | 页面显示含义 | 主来源 | 后备/对照来源 | 后端字段或函数 |
|---|---|---|---|---|
| `包装产量` | 生产主口径产量 | `mes_stock_records.net_weight_tons` | 没有成品库存投影时回退 `mes_workshop_process_records.output_weight_tons` | `_query_mes_packaging_output_with_source_by_date()` |
| `全厂入库产量` | 成品库内勤入库对照 | `work_order_entries.extra_payload` 里的成品库每日一录 | 旧专项字段或组件合计 | `_query_finished_inbound_totals_by_date()` |
| `车间下机/过站产量` | 车间工序经过量 | `mes_workshop_process_records.output_weight_tons` | 本地手机填报 `work_order_entries.output_weight` | `_build_workshop_output()`、实时聚合输入 |
| `在制料/在制卷` | 当前仍在流程中的卷材或重量 | `mes_coil_snapshots`、`mes_wip_total_snapshots`、`mes_material_records` | 无 | `factory_command_service`、`mes_extended_service` |
| `成品率` | 正式成品率或矩阵成品率 | `quality_yield_daily`、`MesYieldRecord` 或成品率矩阵 | 运行态投入/产出比仅做兼容参考 | `_build_yield_rates()`、`build_yield_matrix_projection()` |
| `能耗值` | 用电、用气、用水 | `machine_energy_records`、`mobile_shift_reports`、`work_order_entries` | `energy_import_records`、`iot_energy_snapshots` | `get_energy_summary()`、`summarize_energy_for_date()` |
| `吨耗分母` | 每吨能耗用哪个产量除 | 优先 MES 包装产量 | 无 MES 时看人工包装入库或能耗行产量 | `_mes_packaging_output_tons()`、`_factory_final_output_tons()` |
| `合同量` | 合同剩余或新增吨数 | 合同/日报聚合服务 | 无 | `report_service` 和日报快照 |
| `填报明细` | 人工填报、补录、能耗填报流水 | `work_order_entries`、`machine_energy_records`、`mobile_shift_reports` | MES 只做缺口对照，不混进人工流水 | `build_fill_detail_ledger()` |
| `MES 填报差异` | 外部 MES 有记录但本地缺补录、重量不一致等 | `mes_workshop_process_records` + 本地填报对照 | 无 | `build_mes_fill_gaps()` |
| `卷级线索` | 单卷从哪里来、现在在哪、下一步去哪 | `mes_coil_snapshots` | 本地 `coil_flow_events`、本地班次数据补充 | `list_coils()`、`build_coil_flow()` |
| `异常列表` | 质量、对账、缺报、MES 缺口等 | 多接口聚合 | 无 | `quality_service.list_issues()`、`reconciliation_service.list_items()`、`realtime_service` |

这里最容易搞混的是前三个：`包装产量`、`全厂入库产量`、`车间过站产量`不是一个数字。包装产量是生产主口径，全厂入库产量是成品库人工对照，车间过站产量是工序经过量。

### 33.3 `/manage/today` 和 `/manage/production` 共用的数据快照

这两个页面都依赖 `useDashboardSnapshot.js`，它同时请求三个接口：

| 接口 | 参数 | 作用 |
|---|---|---|
| `/dashboard/factory-director` | `target_date` | 厂长日报快照、风险、异常、管理层总览。 |
| `/dashboard/daily-production` | `target_date` | 每日生产经营总览，含包装产量、全厂入库产量、在制料、成品率、能耗、合同。 |
| `/factory-command/overview` | `target_date` | 调度视角的工厂流转、MES 扩展概览、卷级/工序状态补充。 |

注意：`factory-director` 调 `report_service.build_factory_dashboard()`；`daily-production` 调 `daily_overview_builder.build_daily_production_overview()`。它们是两套服务结果，前端再合并展示。

### 33.4 `/manage/live` 实时大屏字段链路

实时大屏主要读：

| 接口 | 来源 | 用途 |
|---|---|---|
| `/aggregation/live` | `realtime_service.build_live_aggregation()` | 大屏主体：车间、机列、班次、填报、MES、能耗、异常。 |
| `/realtime/stream` | `realtime_events` 事件流 | 有新填报、新同步、新异常时让页面局部更新。 |
| `/aggregation/live/fill-details` | `build_fill_detail_ledger()` | 明细抽屉/填报流水。 |
| `/aggregation/live/detail` | 实时单元格详情 | 点某个车间/机列/班次看细节。 |

实时大屏会注入两个全厂字段：

| 字段 | 来源 |
|---|---|
| `factory_total.packaging_output`、`daily_output`、`factory_total_output` | MES 包装产量。 |
| `factory_total.finished_inbound_output`、`owner_storage_finished_weight` | 成品库内勤入库对照。 |

### 33.5 `/manage/fill-details` 不是 MES 原始数据页

填报明细页的后端 `build_fill_detail_ledger()` 明确排除了 `entry_type='mes_projection'` 的本地记录，所以它主职责是人工填报和补录，不是外部 MES 原始明细。

它会显示：

| 来源类型 | 表 | 页面含义 |
|---|---|---|
| `machine_energy` | `machine_energy_records` + `mobile_shift_reports` | 电工/机台能耗明细。 |
| `work_order_entry` | `work_order_entries` + `work_orders` | 主操扫码卷明细。 |
| `owner_daily` | `work_order_entries.extra_payload` | 内勤/专项每日一录。 |
| `mobile_shift_report` | `mobile_shift_reports` | 班次汇总。 |

MES 只通过 `mes-fill-gaps`、日报对照、卷级线索做辅助，不应混进人工流水。

### 33.6 `/manage/energy` 能耗中心字段链路

能耗中心读 `/energy/summary`，后端 `get_energy_summary()` 会合并多种来源：

| 来源 | 表 | 说明 |
|---|---|---|
| 手机/电工填报 | `machine_energy_records`、`mobile_shift_reports` | 当前更接近真实现场填报。 |
| 内勤每日一录 | `work_order_entries.extra_payload` | 专项或全厂口径补充。 |
| 旧能耗导入 | `energy_import_records` | 历史兼容，老导入功能已弱化。 |
| 物联网影子数据 | `iot_energy_snapshots` | 等外部能耗数采库接入后使用。 |
| MES 包装产量分母 | `mes_stock_records`、`mes_workshop_process_records` | 用于吨耗分母，不是能耗值本身。 |

吨耗逻辑要分两步看：先看能耗值从哪里来，再看产量分母从哪里来。不要把“能耗值为空”和“产量分母为空”混成一个问题。

### 33.7 `/manage/coils` 卷级线索字段链路

卷级线索页读 `/factory-command/coils` 和 `/factory-command/coils/{coil_key}/flow`。

| 字段 | 主来源 | 说明 |
|---|---|---|
| 随行卡/批号 | `mes_coil_snapshots.tracking_card_no`、`batch_no` | 查卷最关键字段。 |
| 客户、合金、规格 | `mes_coil_snapshots` | 用于减少手机端重复输入。 |
| 当前车间/当前工艺/下一工艺 | `mes_coil_snapshots.current_workshop`、`current_process`、`next_process` | 生产流转判断。 |
| 设备/机列 | `machine_code` + 机列别名/终端映射 | MES 里设备可能是 `PC`，要靠终端映射补稳。 |
| 自动废料 | 最新 `mes_workshop_process_records` 的投入和产出差 | 自动计算，异常时给审核线索。 |
| 流转事件 | `coil_flow_events` | 本地补充的卷级流转证据。 |

如果 `mes_coil_snapshots` 没有数据，`factory_command_service` 有本地班次数据回退能力，但那只是兜底，不应当替代 MES 主线。

### 33.8 `/manage/alerts` 异常中心字段链路

异常中心聚合多类来源：

| 异常来源 | 接口 | 表/服务 | 说明 |
|---|---|---|---|
| 生产/上报异常 | `/dashboard/factory-director` | `report_service` | 工厂日报快照里的异常 lane。 |
| 质量问题 | `/quality/issues` | `data_quality_issues` | 质量检查生成或人工处理。 |
| 对账差异 | `/reconciliation/items` | `data_reconciliation_items` | 产量、MES、能耗、考勤之间的差异。 |
| MES 填报缺口 | `/aggregation/live/mes-fill-gaps` | `mes_workshop_process_records` + 本地填报 | 外部有记录、本地缺补录或重量不一致。 |
| 实时缺报 | `/aggregation/live` | 实时聚合 | 班次、角色、机列未填或不适用状态。 |

这页如果没显示具体异常，不一定是“异常表没数据”，也可能是某个来源接口失败或日期参数传错。

### 33.9 仍要继续逐字段实测的风险

| 风险 | 当前理解 | 下一步 |
|---|---|---|
| 字段名看起来相近 | `packaging_output`、`daily_output`、`finished_inbound_output` 很容易被误认为一个字段 | 用真实某日数据逐字段截图对账。 |
| MES 投影和人工填报同屏 | 页面必须显示来源标签，否则用户会误解哪个是真值 | 浏览器 QA 时重点看来源文案。 |
| 能耗吨耗分子分母不同源 | 能耗值可能来自填报，分母可能来自 MES 包装产量 | 用实际能耗日核对一轮。 |
| 旧导入表仍被读 | `energy_import_records`、`MesImportRecord` 等还在兼容链路里 | 清理前必须先证明没有页面/算法依赖。 |
| 车间主任权限 | 同一接口会按 scope 限制车间 | 需要真实车间主任账号浏览器验证。 |

## 34. 本轮新增验证记录：页面字段映射和核心数据链路

本轮没有修改业务代码，只做结构追踪、定向测试和文档合并。

| 验证类型 | 命令 | 结果 | 能证明什么 |
|---|---|---|---|
| 后端字段链路测试 | `python -m pytest -q backend/tests/test_daily_overview_chain.py backend/tests/test_daily_overview_mes_packaging.py backend/tests/test_energy_mes_packaging_output_basis.py backend/tests/test_energy_summary.py backend/tests/test_factory_command_service.py backend/tests/test_factory_command_routes.py backend/tests/test_realtime_service_contract.py backend/tests/test_realtime_routes.py` | `97 passed` | 日报包装产量、全厂入库对照、能耗吨耗分母、实时聚合、卷级线索和相关后端路由契约通过。 |
| 前端页面契约测试 | `node --test tests/manageDashboardSnapshot.test.js tests/manageProductionPage.test.js tests/manageFillDetailsAudit.test.js tests/manageCoilsPage.test.js tests/manageAlertsTimeline.test.js tests/energyCenterDesign.test.js tests/factoryCommandScreens.test.js tests/coilFlowFields.test.js tests/workshopEnergyLiveRegression.test.js` | `88 passed` | 日报/生产分析快照、包装产量和入库产量分离、填报明细来源、电工能耗字段、卷级线索、异常时间线、能耗页和实时看板字段契约通过。 |
| 结构追踪 | CodeGraph + 前端 API 模块 + 后端路由/服务文件阅读 | 已确认 | 能说明核心管理页面的主要字段如何从页面一路追到后端服务和数据库表。 |

边界说明：这不是生产真实数据逐字段对账，也不是全角色浏览器 QA。它证明代码层面的字段链路和自动测试契约是清楚的；下一步还要拿线上某个业务日，把页面数字和数据库查询结果一项项对账。

## 35. 追加理解：线上只读健康与真实业务日对账边界

本轮继续补“真实运行环境到底能确认到哪里”。结论先说清楚：

- 不带 `www` 的正式域名当前可用，`healthz` 和 `readyz` 都正常。
- 线上业务数据库在生产环境是可用的，因为 `/readyz` 返回 `database=ok`。
- 外部 MES 同步在生产环境显示为 `fresh / success / sqlserver`，说明线上当前是 SQL Server 同步链路在跑，不是只靠旧 MVC 抓取。
- 物联网能耗同步仍是 `unconfigured`，这是“还没接入外部能耗库”的状态，不等于系统故障。
- 未登录时访问日报、调度、能耗、实时大屏业务接口都会返回 `401`，这是正确权限边界。

### 35.1 本轮匿名只读可确认的信息

本轮直接访问线上健康接口，得到以下可公开读取的运行状态：

| 项 | 当前结果 |
|---|---|
| 生产状态 | `ready` |
| 环境 | `production` |
| 健康时间戳 | `2026-06-14T10:05:40+00:00` |
| 数据库 | `ok` |
| 外部 MES 同步 | `ok` |
| 外部 MES 详细状态 | `fresh` |
| 外部 MES 最近任务 | `success` |
| 外部 MES 适配器 | `sqlserver` |
| 外部 MES 延迟 | `0.0` 秒 |
| 生产管道目标日期 | `2026-06-14` |
| 管道硬门禁 | `true` |
| 活跃生产车间 | `13` |
| 更宽数据库管理口径 | `15` |
| 活跃手机填报用户 | `86` |
| 活跃设备 | `106` |
| 物联网能耗 | `unconfigured` |

这里的 `13` 和 `15` 不是冲突：`13` 是当前活跃生产车间口径，`15` 是数据库里保留的更宽管理口径。以后汇报数量时要继续先说清“是哪一种口径”。

### 35.2 本轮匿名不能直接确认的信息

未登录状态下，本轮访问这些核心业务接口都返回 `401`：

| 接口 | 本轮结果 | 说明 |
|---|---:|---|
| `/api/v1/dashboard/daily-production?target_date=2026-06-13` | `401` | 日报业务数据需要登录态。 |
| `/api/v1/factory-command/overview?target_date=2026-06-13` | `401` | 调度业务数据需要登录态。 |
| `/api/v1/energy/summary?business_date=2026-06-13` | `401` | 能耗业务数据需要登录态。 |
| `/api/v1/aggregation/live?target_date=2026-06-13` | `401` | 实时大屏业务数据需要登录态。 |

这不是坏事。它说明业务数据没有被匿名开放。后续要做“页面数字和数据库数字逐项对账”，必须使用管理员登录态、车间主任登录态，或者在生产机上执行只读查询脚本。

### 35.3 本地服务层对账为什么没跑通

本轮尝试用本地后端配置跑只读服务层对账，目标是读取上一完整生产业务日的数据。代码没有写库，只是调用后端汇总服务和表计数。

实际结果：

```text
连接 localhost:5432 失败，本机 PostgreSQL 没启动。
```

这只能说明“本机数据库没开”，不能说明线上数据库异常。因为线上 `/readyz` 同时已经证明生产数据库是 `ok`。

### 35.4 已有登录态只读对账证据

仓库里今天已有一份已登录只读验证记录，验证日期是 `2026-06-13`。这份记录能作为当前可靠证据引用：

| 位置 | 已验证结果 |
|---|---|
| `/dashboard/factory-director` | `today_total_output=241.91`，`total_output_basis=mes_packaging_output` |
| `/dashboard/daily-production` | `plant_output.daily_output=241.91`，来源 `mes_stock_records` |
| `/dashboard/daily-production` | `plant_output.finished_inbound_output=246.38`，来源 `storage_owner_daily_entry` |
| `/factory-command/overview` | `today_output_tons=1618.55`，来源 `live_aggregation` |
| `/aggregation/live` | `factory_total.packaging_output=241.91`，`factory_total.finished_inbound_output=246.38` |
| `/aggregation/live` | `workshops=13`，外部 MES 同步 `adapter=sqlserver`、`last_run_status=success` |
| `/factory-command/coils` | 已返回随行卡号、批号、规格、MES 上下机、自动废料线索等卷级字段 |

这一组数字说明：

- `包装产量=241.91 吨` 是外部 MES 投影主口径。
- `全厂入库产量=246.38 吨` 是成品库内勤入库对照口径。
- `调度总输出=1618.55 吨` 是实时流转观察口径。
- 三个数字不是同一个业务概念，不能互相覆盖。

### 35.5 下一步最该补的对账动作

为了把总目标从 `70%` 继续往上推，下一轮最有价值的是：

1. 用登录态打开 `/manage/today`、`/manage/production`、`/manage/live`，把页面显示的 `241.91`、`246.38`、`1618.55` 是否同屏来源清楚确认一遍。
2. 在生产机执行只读脚本，直接查 `mes_stock_records`、`storage_owner_daily_entry`、`machine_energy_records`、`mobile_shift_reports`、`data_quality_issues`、`data_reconciliation_items`。
3. 对一个业务日出一张“页面字段 -> 后端接口 -> 服务函数 -> 数据表 -> 真实数值”的核对表。
4. 用车间主任和手机填报角色各跑一次真实浏览器流程，不能继续只用管理员代替。
5. 等能耗数采库配置给出后，再补能耗值来源和吨耗分母的真实对账。

## 36. 本轮新增验证记录：线上健康、权限边界和对账限制

本轮没有修改业务代码，也没有写生产数据，只改了这份总理解文档。

| 验证类型 | 动作 | 结果 | 能证明什么 |
|---|---|---|---|
| 线上健康检查 | 访问 `https://xtmijd.com/readyz`、`https://xtmijd.com/api/v1/readyz`、`https://xtmijd.com/healthz`、`https://xtmijd.com/api/v1/healthz` | 全部 HTTP 200 | 正式无 `www` 域名、后端应用、生产数据库和主要门禁当前可用。 |
| 线上健康细项 | 解析 `/api/v1/readyz` | `database=ok`、`mes_sync=ok`、`mes_adapter=sqlserver`、`mes_status=fresh`、`active_workshop_count=13` | 线上外部 MES SQL Server 投影链路是新主线，且当前同步新鲜。 |
| 业务接口匿名访问 | 访问日报、调度、能耗、实时大屏 API | 均返回 `401` | 业务数据接口需要登录态，匿名不能直接读生产数据。 |
| 本地后端只读脚本 | 调用日报总览和能耗汇总服务 | 连接 `localhost:5432` 失败 | 本机数据库未启动，不能当作线上故障；后续要用生产机只读查询或登录态 API。 |
| 部署入口探测 | 检查本机 SSH 配置 | 未发现 SSH config | 当前会话不能直接登录生产机做只读数据库查询。 |
| 既有对账证据合并 | 阅读今天已有登录态只读验证文档 | 已纳入第 35 节 | `2026-06-13` 的包装产量、全厂入库产量、调度总输出已经有来源标签证据。 |

当前完成度更新：

| 维度 | 本轮前 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `68%` | `70%` |
| 系统理解总文档可交接度 | `91%` | `92%` |

剩余最大的缺口仍然是：真实登录态逐页浏览器 QA、生产机数据库只读逐字段对账、全角色流程验证、外部钉钉/LLM/能耗数采真实动作验证。

## 37. 追加理解：AI、钉钉和外部通讯的当前完成边界

本轮继续把 AI、钉钉、主动汇报和外部通讯治理往“可交接”方向补齐。这里要反复强调一个边界：

`自动测试通过`、`dry-run 演练保护存在`、`治理台接口有权限`，不等于“真实钉钉群已经成功收到消息”。

### 37.1 当前链路拆解

| 链路 | 当前代码位置 | 数据落点 | 是否可能写数据 | 当前理解 |
|---|---|---|---|---|
| AI 工作台 | `/api/v1/ai/*`、`/manage/ai-assistant` | `ai_conversations`、`ai_messages`、`ai_context_packs`、`ai_briefing_events`、`ai_watchlist_items` | 是 | 创建会话、发送消息、生成简报、关注项增删改都会写记录。 |
| 旧 assistant 能力入口 | `/api/v1/assistant/*` | `assistant_usage` 等 | 是 | `GET capabilities/live-probe` 是读状态；`POST query/generate-image` 会消耗模型能力或写用量。 |
| 智能体动作 | `/api/v1/assistant/actions` | `agent_events`、业务动作结果、审计日志 | 是 | 属于高风险操作入口，不能当只读探针。 |
| 外部通讯治理台 | `/api/v1/agent-management/overview`、`/manage/admin/agents` | `agent_profiles`、`communication_channels`、`agent_outbox_messages`、`external_message_logs` 等 | `GET overview` 只读，部分 POST 写 | 这里是“系统准备发什么、有没有发、是否演练”的治理台。 |
| 钉钉 H5 免登 | `/api/v1/dingtalk/login`、`/api/v1/dingtalk/h5-login` | `users`、审计日志、最后登录时间 | 是 | 登录会更新绑定、登录时间和审计记录，不能随便拿生产真实 code 当探针。 |
| 外部消息派发 | `dispatch_outbox_message()` | `agent_outbox_messages`、`external_message_logs` | 是 | 通道未启用会失败；`dry_run=true` 只记录演练；只有非演练钉钉群通道才会真实外发。 |

### 37.2 外发闸门

当前真正外发必须同时满足这些条件：

1. 已有启用的 `CommunicationChannel`。
2. 通道类型是 `dingtalk_group` 或后续支持的真实外部通道。
3. 通道 `dry_run=false`。
4. 已有待发送 `AgentOutboxMessage`。
5. 执行 `dispatch_outbox_message()`。
6. 发送结果写回 `agent_outbox_messages.status` 和 `external_message_logs`。

如果通道 `dry_run=true`，代码会把消息状态标记为 `dry_run`，并写一条“dry-run only, message not sent”的外部日志，不会真的发到钉钉。

小白版理解：系统不是“AI 想说什么就直接发群”。它像一个有出门登记的办公室：先写申请单，再放到发件箱，再看通道是不是演练，最后才可能真的发送，并且每一步都要留日志。

### 37.3 线上匿名权限边界

本轮从未登录状态访问以下线上接口，全部返回 `401`：

| 接口 | 结果 | 说明 |
|---|---:|---|
| `/api/v1/ai/runtime` | `401` | 未登录不能查看 AI 运行状态。 |
| `/api/v1/ai/briefings` | `401` | 未登录不能查看主动汇报。 |
| `/api/v1/agent-management/overview` | `401` | 未登录不能进入治理台概览。 |
| `/api/v1/agent-management/knowledge` | `401` | 未登录不能读取治理知识库。 |
| `/api/v1/assistant/capabilities` | `401` | 未登录不能查看 assistant 能力。 |
| `/api/v1/assistant/live-probe` | `401` | 未登录不能探测 assistant 实时状态。 |

这证明“匿名访问”这层边界是关着的。它不证明管理员登录后所有按钮都安全，也不证明真实外发已经配置好。

### 37.4 本轮自动测试刷新

本轮重新跑了 AI、钉钉、外部通讯相关测试：

| 测试类型 | 命令 | 结果 | 证明范围 |
|---|---|---|---|
| 后端治理链路测试 | `python -m pytest -q backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_overview_service.py backend/tests/test_agent_management_router.py backend/tests/test_assistant_action_service.py backend/tests/test_assistant_actions_router.py backend/tests/test_ai_assistant_routes.py backend/tests/test_ai_context_service.py backend/tests/test_dingtalk_h5_login.py backend/tests/test_dingtalk_service.py` | `52 passed, 2 warnings` | dry-run 外发保护、治理台权限、assistant action、AI 上下文、钉钉 H5 服务等代码契约通过。 |
| 前端治理/AI 测试 | `node --test tests/agentManagementPage.test.js tests/aiAssistantContracts.test.js tests/aiAssistantUiContract.test.js tests/aiWorkstationActions.test.js tests/dingtalkAutoLogin.test.js tests/assistantFallbackTruthfulness.test.js` | `23 passed` | 治理台入口、AI 工作台、钉钉自动登录前端契约、兜底文案真实性通过。 |

后端测试里的 `2 warnings` 是 `datetime.utcnow()` 弃用提醒，不是本轮业务阻塞。但后续可以单独清理，避免 Python 未来版本升级时变成噪声。

### 37.5 还不能宣称完成的部分

以下内容目前仍不能说“完成”：

| 项 | 为什么还不能宣称完成 | 需要什么证据 |
|---|---|---|
| 真实钉钉群主动汇报 | 本轮没有关闭 dry-run，也没有往真实群发消息。 | 指定测试群、指定人员、关闭演练通道后发送一条测试消息，并在 `external_message_logs` 查到成功记录。 |
| LLM 真实回答质量 | 自动测试只证明接口契约和兜底逻辑，不证明模型回答真的可靠。 | 登录后用真实问题测试 AI 工作台，并保存输入、输出、来源引用和权限过滤证据。 |
| 指定人员补产量发布日报 | 这属于写操作，可能影响业务日报。 | 指定角色、测试业务日、审批记录、回滚方案、审计日志。 |
| 钉钉 H5 真实免登 | 本轮没有真实钉钉 code。 | 在钉钉客户端内用绑定用户访问手机端，确认登录、角色跳转和审计日志。 |
| 外部通讯治理台真实配置 | 匿名 401 只证明未登录进不去，不证明登录后配置完整。 | 管理员登录后读取 `/agent-management/overview`，确认 agent/channel/outbox/log 的真实数量和状态。 |

## 38. 本轮新增验证记录：AI、钉钉、外部通讯治理

本轮没有触发任何真实外部发送，没有写生产数据，只做代码追踪、自动测试和匿名 GET 权限探测。

| 验证类型 | 结果 | 结论 |
|---|---|---|
| CodeGraph 追踪 | 已定位 `AgentManagementPage.vue`、`agent_management_overview_service.py`、`agent_management.py`、`assistant_actions.py`、`agent_communication_service.py`、`dingtalk.py`、`ai.py`、`assistant.py` | AI、钉钉、外部通讯治理是多层链路，不是一条“AI 直接发群”的直通线。 |
| 后端测试 | `52 passed, 2 warnings` | 外发演练保护、治理台、assistant action、AI 上下文、钉钉服务当前自动测试通过。 |
| 前端测试 | `23 passed` | 管理端治理台、AI 工作台、钉钉自动登录前端契约当前通过。 |
| 线上匿名探测 | 6 个 AI/治理/assistant GET 接口全部 `401` | 未登录不能读 AI/治理信息，匿名边界成立。 |
| 文档合并 | 已合并到第 37 节 | 后续接手时能分清“测试通过、dry-run、真实外发、写操作”的差别。 |

当前完成度更新：

| 维度 | 本轮前 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `70%` | `72%` |
| 系统理解总文档可交接度 | `92%` | `93%` |

下一轮如果继续推进，最优先的不是再读 AI 代码，而是用登录态或生产机只读脚本补“真实数据逐字段对账”，因为那是当前离完成目标差距最大的证据缺口。

## 39. 追加理解：目标完成审计总表

本节把“继续完成目标”拆成一张验收表。它的作用是防止后续把“读过代码”“跑过定向测试”“看过健康接口”误写成“目标已经完成”。

当前结论：目标还没有完成，但已经从“系统地图”推进到“可以按证据逐项收口”的阶段。

### 39.1 总体完成审计

| 要求 | 当前状态 | 已有证据 | 缺口 | 下一步验收方式 |
|---|---|---|---|---|
| 系统身份和外部系统边界清楚 | 基本完成 | 总文档第 2、3、10 节；产品名统一为 `鑫泰铝业 数据中枢` | 后续文档和 UI 仍要持续避免把本系统叫成 MES | 新增文档/页面时检查文案。 |
| 后端入口、主要路由和服务链路清楚 | 基本完成 | 已定位 `backend/app/main.py`、主要路由分组、246 条路由量级 | 未逐函数审完所有文件 | 后续只在改动相关模块时用 CodeGraph 精确追踪。 |
| 前端核心页面入口清楚 | 基本完成 | 第 5、17、33 节记录 `/manage/*`、`/entry/*` 页面链路 | 仍缺全角色浏览器逐按钮 QA | 用真实账号逐页截图和记录接口状态。 |
| 数据库表和业务字段清楚 | 部分完成 | 已确认 90 张模型表量级和核心表分组 | 字段级真实数据仍没逐项对账 | 生产机只读查询或登录态 API 对账。 |
| 外部 MES 同步链路清楚 | 基本完成 | `/readyz` 显示 `mes_adapter=sqlserver`、`fresh/success`；第 35 节记录 | 仍缺生产数据库层面的逐字段 SELECT 对账 | 查 `mes_stock_records`、`mes_workshop_process_records`、`mes_coil_snapshots`。 |
| MES 主数据和人工填报边界清楚 | 基本完成 | 第 6、17、33、35 节已区分 MES 投影、人工填报、算法数据 | 还缺真实页面上来源标签逐项确认 | 登录态打开日报、生产分析、实时大屏逐 KPI 对照。 |
| 手机端主操/电工/内勤流程清楚 | 部分完成 | 第 20、25 节记录写库路径；记忆中确认主操、电工、内勤表落点 | 没用真实手机角色完整走一遍 | 用真实 `machine_operator`、`energy_stat`、`consumable_stat` 账号 QA。 |
| 车间主任权限边界清楚 | 部分完成 | 已记录车间主任只能看本车间，管理员不是手机填报角色 | 仍需真实车间主任账号浏览器验权 | 用至少一个车间主任账号验证越权访问返回。 |
| 能耗链路清楚 | 部分完成 | 第 23、33、35 节说明能耗值和吨耗分母分开；物联网未配置 | 外部能耗数采库尚未接入；真实电工填报对账不足 | 接入能耗库后重做能耗值、吨耗、页面映射对账。 |
| 异常、缺报、导出链路清楚 | 部分完成 | 第 24、33、34 节记录异常页、缺报导出、日期参数边界 | 仍需真实导出文件内容和页面异常逐项核查 | 登录态导出 Excel，只读检查工作表和异常明细。 |
| AI、钉钉、外部通讯治理清楚 | 基本完成 | 第 21、27、37、38 节；后端 52 个相关测试、前端 23 个相关测试通过 | 真实钉钉群外发、LLM 真实质量、H5 免登仍未实测 | 指定测试群、指定人员、真实登录态和日志回查。 |
| 健康检查和部署边界清楚 | 基本完成 | 第 11、13、35 节；线上 `healthz/readyz` 正常 | 不能把 `readyz=200` 误当所有外部动作完成 | 每次上线继续看 `checks/details` 细项。 |
| understand 图谱刷新 | 未完成 | CodeGraph 当前可用；已有图谱边界记录 | 官方 understand 全量图谱未重建 | 先确认 `.understandignore`，再跑完整 `/understand --full --language zh`。 |
| 全量测试和全站 QA | 未完成 | 多组定向测试通过；前端测试多次通过 | 没有本轮后端全量 pytest，没有全站真实浏览器 QA | 分阶段跑后端全量、前端构建、浏览器逐页 QA。 |

### 39.2 为什么当前不是 100%

如果只看“系统理解文档能不能接手”，当前约 `94%`。原因是：

- 主要页面、主要表、主要接口、主要权限边界都已经有文字底图。
- 最容易混淆的口径已经拆清：包装产量、全厂入库产量、调度总输出、填报明细、MES 投影不是一回事。
- AI/钉钉/外部通讯已经拆清楚：测试通过和真实外发不是一回事。

但如果按用户最初的超大目标衡量，当前约 `82%`，原因是：

- 没有用所有真实角色逐个登录和逐按钮操作。
- 没有在生产机上把每个页面字段逐项查表对账。
- 没有真实发送钉钉消息、真实钉钉 H5 免登、真实 LLM 质量验收。
- 没有在本轮跑完完整后端全量测试和全站浏览器 QA。
- understand 官方全量图谱没有在确认忽略规则后重建。

### 39.3 剩余工作按“最能推进完成度”的顺序

| 顺序 | 工作 | 做完预计推进 | 原因 |
|---:|---|---:|---|
| 1 | 登录态核心页面逐字段对账 | `+6%` 到 `+8%` | 这是最大不确定性，直接决定数据可信度。 |
| 2 | 真实角色浏览器 QA | `+5%` 到 `+7%` | 能验证主操、电工、内勤、车间主任是否真能用。 |
| 3 | 生产机只读数据库对账 | `+4%` 到 `+6%` | 能把页面数字和真实表字段闭环。 |
| 4 | 外部钉钉/LLM/能耗动作专项测试 | `+4%` 到 `+6%` | 能把“代码链路存在”变成“真实业务可用”。 |
| 5 | understand 全量图谱刷新 | `+2%` 到 `+4%` | 能把结构地图从 CodeGraph/文档理解推进到官方图谱产物。 |
| 6 | 后端全量测试、前端构建、全站烟测 | `+3%` 到 `+5%` | 能做最终收口，但必须在前面数据/角色问题之后才有意义。 |

### 39.4 下一步执行建议

下一步不要继续泛泛“读全仓”。更高价值的做法是拿一个固定业务日做样板：

```text
业务日：2026-06-13
页面：/manage/today、/manage/production、/manage/live、/manage/energy、/manage/fill-details
目标：页面每个关键数字都能追到接口字段、服务函数、数据表字段、真实数值。
```

建议核对字段：

| 字段 | 页面 | 应查接口 | 应查表 |
|---|---|---|---|
| 包装产量 | 日报、生产分析、实时大屏 | `/dashboard/daily-production`、`/aggregation/live` | `mes_stock_records`，必要时回退 `mes_workshop_process_records` |
| 全厂入库产量 | 日报、实时大屏 | `/dashboard/daily-production`、`/aggregation/live` | `work_order_entries(entry_type='owner_daily')` 的成品库入库字段 |
| 调度总输出 | 实时大屏、调度概览 | `/factory-command/overview`、`/aggregation/live` | `mes_workshop_process_records`、实时聚合结果 |
| 能耗总览 | 能耗页、生产分析 | `/energy/summary` | `machine_energy_records`、`mobile_shift_reports`、`work_order_entries`、`energy_import_records`、`iot_energy_snapshots` |
| 填报明细 | 填报明细页 | `/aggregation/live/fill-details` | `work_order_entries`、`mobile_shift_reports`、`machine_energy_records`，排除 `mes_projection` |
| 异常明细 | 异常页 | `/quality/issues`、`/reconciliation/items`、`/aggregation/live/mes-fill-gaps` | `data_quality_issues`、`data_reconciliation_items`、`mes_workshop_process_records` |

这一步完成后，整体完成度才有资格从 `82%` 继续往 `85%` 附近推进。

## 40. 本轮新增验证记录：完成审计和进度口径统一

本轮没有修改业务代码，也没有写生产数据，只做了三件事：

1. 重新读取 understand 规则，确认不在未确认 `.understandignore` 的情况下重建全量图谱。
2. 复核当前总文档，发现并修正第 15 节旧进度数字。
3. 新增第 39 节，把剩余目标拆成“要求、已有证据、缺口、下一步验收方式”。

当前完成度更新：

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `72%` | `74%` |
| 系统理解总文档可交接度 | `93%` | `94%` |

本轮为什么只提升 `2% / 1%`：

- 因为这轮主要是把“完成标准”写清楚，不是完成真实角色 QA 或生产数据库逐字段对账。
- 它让后续工作更不容易跑偏，但不能替代真实验证。

如果下一轮能完成 `2026-06-13` 业务日的登录态页面 + 数据库逐字段对账，整体目标进度会有更明显提升。

## 41. 追加理解：生产机只读业务日对账样板

本节补上之前最大的证据缺口之一：不是只看本地代码，而是在生产机上用只读方式核对一个已经沉淀完成的业务日。

本轮核对日期选择 `2026-06-13`。原因是：今天是 `2026-06-14`，昨日业务日的数据更接近日报沉淀状态，比当天实时数据更适合做样板对账。

### 41.1 生产运行边界

| 项 | 结果 | 说明 |
|---|---|---|
| 生产代码目录 | `/srv/aluminum-bypass` | 当前生产主目录，不是旧目录 `/opt/aluminum-bypass` |
| 生产提交号 | `dfd68681` | 这是本轮只读检查时线上代码版本 |
| 后端服务 | `active` | `aluminum-bypass` 服务正在运行 |
| Nginx | `active` | 反向代理正在运行 |
| `/api/v1/readyz` | `ready` | 主业务链路健康检查通过 |
| MES 同步 | `sqlserver / fresh / success` | 线上已经是 SQL Server 直连投影链路，不是只停留在本地代码 |
| MES 最近同步 | `2026-06-14 18:20:30 +08:00` | 健康接口显示同步新鲜度正常 |
| 物联网能耗 | `unconfigured` | 这是尚未接入能耗数采库，不等于系统宕机 |

本轮没有重启服务，没有跑迁移，没有导入数据，没有写生产库，只做查询和服务层只读计算。

### 41.2 2026-06-13 核心日报口径对账

| 页面指标 | 线上服务返回 | 数据来源 | 业务含义 |
|---|---:|---|---|
| 包装产量 | `241.91 吨` | `mes_stock_records` | 外部 MES 入库/包装投影表里的包装产量，是日报包装产量主口径 |
| 全厂入库产量 | `246.38 吨` | `storage_owner_daily_entry` | 成品库内勤每日一录的入库口径，和 MES 包装产量并列显示，不应混成一个数 |
| 日成品率 | `94.57%` | 后端算法 | 由日报服务层计算后返回 |
| 当天接合同 | `227.00 吨` | 后端日报接口 | 页面显示单位已是吨 |
| 总余合同量 | `2626.00 吨` | 后端日报接口 | 页面显示单位已是吨 |
| 综合能耗成本 | `299 元/吨` | 后端日报接口 | 由能耗和产量口径计算 |

最重要结论：`包装产量` 和 `全厂入库产量` 线上已经不是同一个字段。前者是 MES 包装/入库投影，后者是成品库内勤填报入库。前端应该继续同时显示二者，并明确来源。

### 41.3 2026-06-13 生产表真实数量

| 表或链路 | 只读统计结果 | 说明 |
|---|---:|---|
| `mes_stock_records` | `79` 条 | 该业务日有 MES 入库/包装类投影记录 |
| `mes_workshop_process_records` | `195` 条 | 该业务日有 MES 工序过站记录 |
| `mes_coil_snapshots` | `6` 条 | 该业务日有卷级快照，但数量偏少，说明卷级页面仍要允许空状态和人工补录 |
| `mes_material_records` | `0` 条 | 该业务日没有在制料明细投影，不能把页面空值直接误判为前端坏了 |
| `mobile_shift_reports` | `6` 条 | 该业务日有手机端班次填报 |
| `work_order_entries(owner_daily)` | `7` 条 | 该业务日有每日一录/内勤类记录 |
| `machine_energy_records` | `4` 条 | 有机台能耗明细记录，但电量字段合计为 0 |
| `energy_import_records` | `0` 条 | 该业务日没有旧导入能耗数据 |
| `iot_energy_snapshots` | `0` 条 | 物联网能耗库尚未接入，符合健康接口的 `unconfigured` |
| `data_quality_issues` | `0` 条 | 当天质量异常表无记录 |
| `data_reconciliation_items` | `0` 条 | 当天对账项表无记录 |

原始求和校验：

| 校验项 | 数值 | 解释 |
|---|---:|---|
| MES 入库/包装净重合计 | `241.906 吨` | 四舍五入后等于日报包装产量 `241.91 吨` |
| MES 工序下机量合计 | `1216.385 吨` | 这是所有过站/下机工序合计，不等于最终包装产量 |
| 已识别内勤入库字段合计 | `194.764 吨` | 这是按当前已知 payload 字段直接扫出来的求和，不完全等同服务层 `246.38`，后续需要继续拆 payload 字段 |
| 机台能耗明细电量合计 | `0 度` | 说明 `machine_energy_records.energy_kwh` 当天仍没有形成有效电量明细 |
| 机台能耗明细气量合计 | `3541 m³` | 气量明细存在 |

### 41.4 能耗链路的当前真实边界

2026-06-13 能耗服务层返回：

| 项 | 数值 | 来源说明 |
|---|---:|---|
| 总电量 | `6512 度` | 来自 `mobile_shift_reports.electricity_daily` 汇总 |
| 总气量 | `18913 m³` | 来自 `mobile_shift_reports.gas_daily` 汇总 |
| 总能耗值 | `25425` | 当前服务层把电量和气量按现有口径合计 |
| 吨耗分母 | `241.906 吨` | 使用 MES 包装产量 |
| 吨耗口径 | `mes_packaging_output` | 能耗分母不是手机填报产量 |
| 主能耗来源 | `mobile_shift_report` | 物联网库未接入前，仍以手机端填报为主 |
| 系统导入能耗 | `0` | 当天没有旧导入记录 |
| 内勤能耗 | `0` | 当天没有 owner-only 能耗记录 |

这一点很容易误会：能耗总览不是“完全没数据”，而是 `machine_energy_records.energy_kwh` 这张机台明细表当天电量为 0；服务层能耗总览有值，来自 `mobile_shift_reports`。因此后续前端应该把“能耗汇总来源”和“机台明细来源”分开标识，避免用户看到机台明细 0 就误以为整套能耗链路全是 0。

### 41.5 线上业务接口匿名边界

本轮还从生产机本地请求了几个 GET 接口，只看状态码，不带登录态，不提交任何数据。

| 接口 | 匿名状态 | 说明 |
|---|---:|---|
| `/api/v1/readyz` | `200` | 健康检查可以匿名读取，这是部署和监控需要。 |
| `/api/v1/dashboard/daily-production?target_date=2026-06-13` | `401` | 日报业务数据需要登录。 |
| `/api/v1/energy/summary?business_date=2026-06-13` | `401` | 能耗业务数据需要登录。 |
| `/api/v1/aggregation/live?target_date=2026-06-13` | `401` | 实时聚合业务数据需要登录。 |

结论：业务数据接口不是匿名裸露的。后续如果要做“页面字段逐项对账”，必须带真实管理员登录态或在生产机用服务层只读脚本核对，不能用匿名请求替代。

### 41.6 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `74%` | `79%` |
| 系统理解总文档可交接度 | `94%` | `96%` |

为什么这轮提升比较明显：

- 已经在生产机上确认线上是 SQL Server MES 同步链路，且健康状态为新鲜成功。
- 已经用真实业务日确认 `包装产量=mes_stock_records`，`全厂入库产量=storage_owner_daily_entry`。
- 已经确认能耗总览的值来自手机端汇总，吨耗分母使用 MES 包装产量。
- 已经确认机台能耗明细电量为 0 是一个独立风险点，不能再笼统说“能耗链路完全没数据”。

仍不能标记 100% 的原因：

- 没有用真实管理端登录态逐页核对页面展示。
- 没有用主操、电工、内勤、车间主任等真实角色完整走浏览器流程。
- 没有真实触发钉钉、LLM、外部通讯发送动作。
- 没有确认 `.understandignore` 后重建官方 understand 全量图谱。
- 没有把 2026-06-13 的所有页面字段逐一扩成完整对账表。

## 42. 追加理解：核心页面服务级映射核验

本节继续补“页面字段到底接哪里”的证据。上一节已经证明生产数据库里核心数字能查到；本节进一步把前端页面、前端请求、后端路由、服务函数和线上服务返回形状连起来。

本轮仍然没有写生产库，没有重启服务，没有触发外部发送，只做本地代码结构读取和生产机只读服务调用。

### 42.1 核心页面到接口的映射

| 页面 | 前端入口 | 前端请求 | 后端路由 | 后端服务 |
|---|---|---|---|---|
| `/manage/today` | `TodayPage.vue` | `useDashboardSnapshot()` | `/dashboard/daily-production`、`/factory-command/overview` | `build_daily_production_overview()`、`factory_command_service.build_overview()` |
| `/manage/production` | `ProductionPage.vue` | `useDashboardSnapshot()` | `/dashboard/daily-production`、`/factory-command/overview` | 同上 |
| `/manage/live` | `LiveDashboardPage.vue` | `fetchLiveAggregation()`、实时流 | `/aggregation/live`、`/realtime/stream` | `realtime_service.build_live_aggregation()` |
| `/manage/fill-details` | `FillDetailsPage.vue` | `fetchLiveFillDetails()`、`fetchMesFillGaps()`、导出缺报 Excel | `/aggregation/live/fill-details`、`/aggregation/live/mes-fill-gaps`、`/aggregation/live/missing-report-export` | `build_fill_detail_ledger()`、`build_mes_fill_gaps()` |
| `/manage/energy` | 能耗页 API | `fetchEnergySummary()` | `/energy/summary` | `energy_service.get_energy_summary()` |
| `/manage/coils` | `CoilTracePage.vue` | `fetchFactoryCommandCoils()`、`fetchFactoryCommandCoilFlow()` | `/factory-command/coils`、`/factory-command/coils/{coil_key}/flow` | `factory_command_service.list_coils()`、`get_coil_flow()` |

简单说：日报和生产分析是一套“日报快照”；实时大屏是一套“实时聚合”；填报明细是一套“人工填报/补录台账”；卷级线索是一套“MES 投影后的卷级线索”；能耗页是一套“能耗汇总行”。

### 42.2 2026-06-13 页面服务级返回形状

本轮用生产机服务层按管理员全局数据范围只读调用，得到以下结果：

| 页面级服务 | 关键结果 | 说明 |
|---|---|---|
| 日报快照 | `header_kpi_count=7`，`workshop_output_count=10` | 日报快照有 7 个顶部指标、10 条车间产量行。 |
| 日报包装产量 | `241.91 吨`，来源 `mes_stock_records` | 这是最终包装产量主口径。 |
| 日报全厂入库产量 | `246.38 吨`，来源 `storage_owner_daily_entry` | 这是成品库内勤入库口径，和包装产量并列。 |
| 能耗页 | `row_count=7`，来源 `mobile_shift_report` + `mes_packaging_output_basis` | 能耗值来自手机端填报，吨耗分母补了一行 MES 包装产量。 |
| 实时大屏 | `workshop_count=13`，`data_source=mixed` | 实时大屏覆盖 13 个活跃生产车间。 |
| 实时大屏工序总输出 | `factory_total.output=1618.55 吨` | 这是工序/过站/填报汇总口径，不等于最终包装产量。 |
| 实时大屏包装产量 | `factory_total.packaging_output=241.91 吨` | 和日报 MES 包装产量一致。 |
| 实时大屏全厂入库 | `factory_total.finished_inbound_output=246.38 吨` | 和日报全厂入库产量一致。 |
| 填报明细 | `item_count=196` | 明细页能看到人工填报和补录明细。 |
| 填报明细来源 | `owner_daily=7`、`work_order_entry=179`、`mobile_shift_report=6`、`machine_energy=4` | 没有把 MES 自动投影记录直接混进填报明细。 |
| MES 填报缺口 | `item_count=195` | 这是 MES 记录与本地填报对照出来的缺口，不是填报明细本体。 |
| 缺口状态 | `mes_batch_unmapped=85`、`matched=46`、`missing_local_entry=28`、`weight_mismatch=36` | 后续优化机列/随行卡匹配时要优先看这四类。 |
| 调度总览 | `source=mixed`，`today_output_tons=1618.55`，`wip_tons=171.57`，`yield_rate=90.42%` | 调度总览更适合看生产流转和在制状态，不应当替代日报最终包装产量。 |
| 卷级线索 | 首屏 `20` 卷，样本均有随行卡和批号，但 `machine_code` 多为空 | 卷级线索能说明“卷在哪个车间/工艺”，但当前仍不能稳定自动知道具体机台。 |

### 42.3 本轮新增的关键业务判断

这轮最重要的新增理解有三点：

1. `/manage/today` 和 `/manage/production` 不是两套完全独立口径，它们共用 `useDashboardSnapshot()`，因此这两个页面如果同一指标不一致，优先查前端展示转换，而不是先怀疑后端算了两套。
2. `/manage/live` 同时放了“工序总输出”和“包装产量”。`1618.55 吨` 是工序/过站汇总，`241.91 吨` 才是最终包装主口径，页面必须清楚标注，否则用户会误以为产量对不上。
3. `/manage/fill-details` 仍然应该定义为人工填报/补录台账。MES 相关内容应该通过“MES 填报缺口”或“卷级线索”做对照，不应直接混进填报明细列表。

### 42.4 当前仍暴露出的风险点

| 风险点 | 当前证据 | 后续处理建议 |
|---|---|---|
| 车间产量行只有 10 条，但活跃生产车间是 13 个 | 日报快照 `workshop_output_count=10`，实时大屏 `workshop_count=13` | 要确认缺的 3 个车间是当天无产量、无一体机、还是映射未覆盖。 |
| 卷级线索多数没有具体机台号 | 首屏样本 `machine_code=null` | 需要继续补 PC/设备/工艺路线到机列的映射表，不能直接要求 MES 自动知道机台。 |
| 实时大屏缺报数较高 | `submitted_cells=33/144`，缺报 `111` | 要结合“哪些角色必须填、哪些车间无一体机”重算缺报规则，避免把不适用也当缺报。 |
| 机台能耗明细电量仍为 0 | 第 41 节已确认 `machine_energy_records.energy_kwh=0` | 继续查电工填报端是只进了班次汇总，还是明细字段没有落库。 |
| `mes_fill_gaps` 中未匹配较多 | `mes_batch_unmapped=85`、`missing_local_entry=28`、`weight_mismatch=36` | 优先建立随行卡、批号、机列、工艺名的稳定匹配规则。 |

### 42.5 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `79%` | `82%` |
| 系统理解总文档可交接度 | `96%` | `97%` |

为什么这轮只加 `3% / 1%`：

- 这轮把页面级服务映射打通了，已经比只看表更接近真实页面。
- 但还没有真的用浏览器登录打开页面看视觉和交互，也没有用真实角色完成填报流程。
- 因此它能提高“理解可信度”，但还不能替代“真实使用 QA”。

## 43. 追加理解：管理员登录态核心页面只读浏览器 QA

本节补上上一节缺的“真实打开页面”证据。本轮用临时管理员登录态做只读浏览器 QA，只打开页面和读取 GET 接口，不提交表单、不点击会写库的按钮、不触发钉钉或 AI 外发。

安全边界：

- 没有把管理员明文密码写入文档。
- 没有把临时登录令牌写入文档或文件。
- 浏览器测试时拦截了非只读请求，本轮拦截到的写入请求数量为 `0`。
- 管理员只能代表管理端体验，不能代表主操、电工、内勤、车间主任的真实手机端流程。

### 43.1 页面打开结果

测试时间：2026-06-14 晚间。

| 页面 | 结果 | 关键证据 |
|---|---|---|
| `/manage/live` | 可打开 | 标题为“全厂实时调度墙”，实时连接正常；当前业务日显示 MES 包装产量、内勤入库、过站下机等指标。 |
| `/manage/today` | 可打开 | 等待加载完成后显示 2026-06-13 的 `包装产量 241.91 吨`、`全厂入库产量 246.38 吨`、`合同吨数 227 吨`、`算法能耗 6512 度`、`日成品率 94.57%`。 |
| `/manage/production` | 可打开 | 显示 `包装产量 241.91 吨`、`10 个车间`排行、`在制 171.57 吨`、`成品率 94.57%`。 |
| `/manage/workshop-dashboard` | 可打开 | 显示车间看板、机列填报明细、电工填报明细、外部 MES 明细。 |
| `/manage/fill-details` | 可打开 | 显示 `196 条`填报明细、`21 台`机列、`29 人`责任人、`产量 1618.56 吨`、`用电 6512 kWh`、`天然气 18913 m³`。 |
| `/manage/energy` | 可打开 | 显示 `电耗 6512 kWh`、`气耗 18913 m³`、`产量 241.91 吨`、`单吨峰值约 105.1`。 |
| `/manage/coils` | 可打开 | 显示卷级线索，当前筛选约 `100 / 100` 卷；仍能看到“待绑定机列”问题。 |
| `/manage/alerts` | 可打开 | 异常总览当前显示全部异常 `0`，异常处理队列为空。 |
| `/manage/admin/settings` | 可打开 | 系统设置入口可用，页面内能看到十三车间、主数据标准、别名映射、机列台账、二维码与账号、PC 工艺映射等配置入口。 |
| `/entry`、`/entry/history` | 管理员被导回管理端 | 管理员访问手机端入口会回到管理端默认页面；这符合“管理员不是手机填报角色”的权限边界，但不能替代手机端角色 QA。 |

本轮打开这些页面时，没有发现业务接口 `4xx/5xx`，也没有发现控制台红错。

### 43.2 页面加载速度风险

第一次只等 `4-6 秒` 时，`/manage/today`、`/manage/production`、`/manage/fill-details` 会出现“暂无可信数据”或空值，容易误判成没数据。

继续等待到约 `12 秒` 后，页面数据才完整出现。说明：

- 后端接口有数据，不是“数据库没数据”。
- 但页面首屏加载慢，用户很可能在数据出现前就认为系统坏了。
- 后续优化优先级应该包括：首屏骨架、加载状态、接口并发节流、慢接口定位、关键指标优先返回。

### 43.3 只读接口核验

本轮用同一临时登录态直接读取只读接口，确认接口返回和页面展示能对上：

| 接口 | 状态 | 关键返回 |
|---|---:|---|
| `/api/v1/dashboard/daily-production?target_date=2026-06-13` | `200` | `daily_output=241.91`，来源 `mes_stock_records`；`finished_inbound_output=246.38`，来源 `storage_owner_daily_entry`；能耗 `6512/18913`；合同 `227 吨`。 |
| `/api/v1/aggregation/live?business_date=2026-06-13` | `200` | `factory_total.output=1618.55`，`packaging_output=241.91`，`finished_inbound_output=246.38`，`submitted_cells=33/144`。 |
| `/api/v1/aggregation/live/fill-details?business_date=2026-06-13&limit=800` | `200` | `entry_count=196`，`machine_count=21`，`owner_count=29`，`output=1618.557`，`energy_kwh=6512`。 |
| `/api/v1/aggregation/live/mes-fill-gaps?business_date=2026-06-13` | `200` | `total=195`，其中 `mes_batch_unmapped=85`、`missing_local_entry=28`、`weight_mismatch=36`。 |
| `/api/v1/factory-command/overview?target_date=2026-06-13` | `200` | `today_output_tons=1618.55`，`process_output_tons=1618.55`，`workshop_summary_count=10`。 |

注意：实时聚合接口的日期参数名是 `business_date`，不是 `target_date` 或 `date`。如果前端或测试脚本传错参数，会返回 `422`。这个不是业务数据错误，是接口参数名不统一带来的易错点。

### 43.4 本轮发现的新问题

| 问题 | 证据 | 建议 |
|---|---|---|
| 生产页有一个“过站下机参考”小卡显示 `0 吨` | 后端 `/factory-command/overview` 返回 `process_output_tons=1618.55`，但旧工厂总览 `/dashboard/factory-director` 返回 `process_total_output=0.0`；`ProductionPage.vue` 里 `productionSourceOverview` 先取 `snapshot.data.value.process_total_output`，把后面正确的 `factoryCommandOverview.process_output_tons` 挡住了 | 这是前端字段优先级问题，不是后端完全没过站数据。修复时应让 `process_output_tons` 优先使用调度总览接口的工序产量，旧字段为 `0/null` 时不能覆盖正确来源。 |
| 页面加载慢，短等待容易误判为空 | 4-6 秒看到“暂无可信数据”，12 秒后真实数据出现 | 增加清楚的加载态，把关键指标优先渲染；慢接口单独计时。 |
| 日报快照车间产量为 10 行，但实时大屏是 13 个活跃生产车间 | 页面和接口都能复现这个差异 | 需要明确：缺的车间是无产量、不适用、还是映射未覆盖；前端不要把“不适用”显示成缺报。 |
| 车间看板选择里同时有 13 个活跃生产车间和更宽的管理口径 | 页面出现回收车间、成品库等 | 文案要区分“13 个活跃生产车间”和“含回收、成品库的更宽管理口径”，不要混成一个数字。 |
| 卷级线索仍有大量待绑定机列 | `/manage/coils` 显示待绑定机列，`mes_fill_gaps` 也有 `mes_batch_unmapped=85` | 继续补 PC/设备/工艺到机列的稳定映射。 |

### 43.5 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `82%` | `85%` |
| 系统理解总文档可交接度 | `97%` | `98%` |

为什么这轮能提升：

- 已经用管理员登录态实际打开核心管理页面，不再只是服务层和数据库只读核验。
- 已经确认核心页面没有登录回跳、没有业务接口 `4xx/5xx`、没有控制台红错。
- 已经确认日报、生产、填报明细页面最终能显示真实业务日数据。
- 也发现并定位了一个具体前端映射风险：生产页“过站下机参考”小卡显示 `0 吨`，根因是旧工厂总览字段 `process_total_output=0.0` 被前端优先采用，挡住了调度总览接口的正确值 `1618.55 吨`。

仍不能标记 100% 的原因：

- 还没有用真实主操、电工、内勤、车间主任账号逐流程操作。
- 还没有做手机端扫码填报、历史查询、缺报导出、车间主任看板的真实端到端 QA。
- 还没有触发钉钉、LLM、外部通讯真实动作，只做了权限边界和只读理解。
- 还没有确认 `.understandignore` 后重建官方 understand 全量图谱。

## 44. 追加理解：真实角色只读入口 QA

本节继续补“真实用户能不能进该进的页面”的证据。上一节管理员 QA 只能证明管理端可用，不能代表现场扫码角色。本轮从生产库只读抽样真实角色，用临时登录态打开页面，不提交表单、不保存草稿、不导出文件、不触发外部发送。

安全边界：

- 没有记录任何明文密码。
- 没有把临时登录令牌写入文档或文件。
- 浏览器测试拦截了非只读请求，本轮每个角色的写入请求数量都是 `0`。
- 这轮证明“入口、权限、首屏字段、历史读取”可用；还不能证明“真实点击提交后落库完全正确”。

### 44.1 抽样角色

| 角色 | 抽样账号 | 车间 | 是否带机台上下文 | 说明 |
|---|---|---|---|---|
| 主操 | `LZ2050-1` | 2050冷轧 | 是 | 绑定 2050# 机台，适合验证逐卷填报和历史记录。 |
| 电工 | `LZ2050-EN` | 2050冷轧 | 是 | 车间电工角色，适合验证能耗填报入口。 |
| 内勤 | `JZ-CS` | 精整车间 | 是 | 生产内勤角色，适合验证每日一录和包装入库字段。 |
| 车间主任 | `RZ-DIR` | 热轧 | 是 | 车间主任看板角色，适合验证只能看本车间。 |

### 44.2 手机端填报入口

浏览器使用手机宽度 `390px` 打开 `/entry/fill` 和 `/entry/history`。

| 角色 | 页面 | 结果 | 关键证据 |
|---|---|---|---|
| 主操 | `/entry/fill` | 可打开 | 页面显示“现场填报 / 2050# / 主操 / 2050冷轧 / 小夜班 / 2026-06-14”，字段包含随行卡号、工序、道次、上机规格、合金成分、上机重量、下机规格、下机重量、填报问题等。 |
| 主操 | `/entry/history` | 可打开 | 请求 `/mobile/report/history?business_date=2026-06-14&all_day=true&limit=30` 返回 `200`，页面显示整日历史记录 `13` 条，说明“历史只看当前班次”的问题至少在该样本上已不是现状。 |
| 电工 | `/entry/fill` | 可打开 | 页面显示“车间电工 / 2050冷轧 / 小夜班”，字段包含电耗、气耗、能耗备注、机列能耗明细、合计电耗、合计气耗。 |
| 电工 | `/entry/history` | 可打开 | 页面显示整日历史记录入口，请求返回 `200`，当天样本记录为 `0` 条。 |
| 内勤 | `/entry/fill` | 可打开 | 页面显示“生产内勤 / 精整车间 / 每日一录”，字段包含 D40吨耗、钢板吨耗、钢带吨耗、钢带扣吨耗、高温胶带日用、液压油日用、包装入库产量。 |
| 内勤 | `/entry/history` | 可打开 | 页面显示整日历史记录入口，请求返回 `200`，当天样本记录为 `0` 条。 |

本轮手机宽度下没有发现横向溢出，没有发现登录回跳，没有发现接口 `4xx/5xx`，没有发现控制台红错。

### 44.3 车间主任看板入口

浏览器使用桌面宽度打开热轧车间主任账号：

| 页面 | 结果 | 关键证据 |
|---|---|---|
| `/manage/workshop-dashboard` | 可打开 | 请求带 `workshop_id=4`，页面显示热轧车间数据、机列填报明细、电工填报明细、外部 MES 明细、在制料明细、异常事务等模块。 |
| `/manage/live` | 被导回本车间看板 | 最终地址为 `/manage/workshop-dashboard`，说明车间主任不能直接进入全厂实时调度墙，符合“只看本车间”的权限边界。 |

车间主任看板在 `8 秒`时仍能看到“加载中”字样，但等待到约 `16 秒` 后加载完成，显示热轧今日下机量 `443.49 吨`、成品口径产量 `443.49 吨`、机列填报明细 `12 条`。这不是权限或接口失败，而是页面慢加载体验问题。

### 44.4 本轮新增判断

1. 主操历史页已经按 `all_day=true` 读取整日记录，本轮样本能看到 `13` 条，不再只是当前班次。
2. 电工和内勤历史页入口能打开，但当天样本记录为 `0`。这可能是当天未填，也可能仍存在 owner_daily / energy 记录未完整进统一历史的问题，后续需要拿“已确认当天已提交”的真实样本再验证。
3. 车间主任权限边界是对的：能看本车间，看全厂大屏会被带回本车间看板。
4. 车间主任看板和手机填报端首屏都偏慢，虽然功能可用，但现场用户会感觉“等得久”。后续体验优化应该把“加载中”和“正在取数”做得更清楚。

### 44.5 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `85%` | `88%` |
| 系统理解总文档可交接度 | `98%` | `98.5%` |

为什么这轮提升：

- 已经不再只用管理员账号判断手机端和车间主任端。
- 已经用真实主操、电工、内勤、车间主任角色打开关键页面，并确认权限边界和只读接口状态。
- 已经确认手机端 `390px` 宽度下没有明显横向溢出。

仍不能标记 100% 的原因：

- 还没有进行真实提交、保存草稿、继续录入、导出缺报等会写库或下载文件的动作。
- 还没有用“当天确实已提交”的电工和内勤样本反查历史页是否完整覆盖。
- 还没有触发钉钉/LLM/外部通讯真实动作。
- 还没有确认 `.understandignore` 后重建官方 understand 全量图谱。

## 45. 追加理解：已提交电工/内勤历史回看核验与 understand 图谱状态

本节补上上一节留下的一个关键疑问：电工和内勤历史页显示 `0`，到底是当天没填，还是历史查询链路没把数据查出来。

本轮仍然只做只读核验：

- 没有提交新填报。
- 没有保存草稿。
- 没有修改生产数据。
- 没有记录任何临时登录令牌或明文密码。

### 45.1 真实已提交样本

生产库只读抽样确认，确实存在已经提交过的电工和内勤数据：

| 类型 | 样本账号 | 业务日期 | 数据位置 | 关键证据 |
|---|---|---|---|---|
| 电工填报 | `ZR3-EN` | `2026-06-14` | `mobile_shift_reports` | 有已提交记录，包含 `electricity_daily=1572.0`、`gas_daily=2176.0`，提交时间 `2026-06-14 17:35:18 +08:00`。 |
| 内勤每日填报 | `LJ-CS` | `2026-06-13` | `work_order_entries`，`entry_type=owner_daily` | 有已提交记录，包含 `packaging_inbound_output_tons` 等内勤每日字段，提交时间 `2026-06-14 07:40:34 +08:00`。 |

这说明内勤不是“没有填”，而是要继续看历史接口有没有查这类记录。

### 45.2 历史接口只读核验

使用真实角色临时登录态，只读调用：

```text
GET /api/v1/mobile/report/history?business_date=...&all_day=true&limit=30
```

结果如下：

| 角色 | 账号 | 业务日期 | 接口状态 | 返回条数 | 结论 |
|---|---|---|---:|---:|---|
| 电工 | `ZR3-EN` | `2026-06-14` | `200` | `2` | 可以查到电工已提交历史。 |
| 内勤 | `LJ-CS` | `2026-06-13` | `200` | `0` | 查不到内勤已提交的 `owner_daily` 历史。 |

通俗说：电工历史页这条线是通的；内勤每日填报已经进库，但手机端历史查询没有把它捞出来。

### 45.3 根因定位

代码位置：

```text
backend/app/services/mobile_report/lifecycle.py:925
```

`list_report_history()` 的逻辑目前主要查两类数据：

1. 先查 `MobileShiftReport`，也就是主操、电工这类班次填报记录。
2. 如果是主操并且查整日历史，再额外查 `WorkOrderEntry.entry_type == 'mobile_coil'` 的逐卷补录记录。

但它没有为内勤角色额外查：

```text
WorkOrderEntry.entry_type == 'owner_daily'
```

所以内勤每日填报虽然能保存到 `work_order_entries`，也能被管理端报表、缺报、能耗或内勤专项逻辑使用，但手机端 `/entry/history` 暂时看不到这类记录。

这不是数据库没写入，也不是账号没权限，而是历史查询接口漏了一个数据来源。

### 45.4 对业务的影响

| 影响点 | 说明 | 严重程度 |
|---|---|---|
| 内勤看不到自己的历史每日填报 | 用户会以为“我填过的数据没保存” | 高 |
| 管理端不一定受影响 | 管理端很多地方直接查 `owner_daily` 或汇总服务，不完全依赖手机历史接口 | 中 |
| QA 容易误判 | 只看 `/entry/history` 会误以为内勤没填，实际库里有记录 | 高 |
| 后续去内勤化时需要注意 | 如果以后内勤只是补录/审核，这个历史链路也要能回看补录和审核痕迹 | 中 |

建议后续修复方式：

- 在 `list_report_history()` 里为 `consumable_stat` 等内勤每日角色追加 `owner_daily` 查询。
- 返回字段沿用现有历史列表结构，增加 `source_type='owner_daily'`，前端已有“专项每日”标签方向，可以少改页面。
- 加一个后端测试：给某内勤用户造一条 `owner_daily`，调用历史接口必须返回。
- 加一个前端测试：历史页能显示“专项每日”记录，不和主操逐卷记录混在一起。

### 45.5 official understand 图谱状态

当前仓库里已经有 official understand 产物，但它不是今天最新全量图：

| 文件 | 状态 |
|---|---|
| `.understand-anything/knowledge-graph.json` | 存在，约 `1449` 个节点、`216` 条边、`10` 个层、`5` 个导览步骤。 |
| `.understand-anything/meta.json` | 存在，记录分析时间为 `2026-06-05`，提交为 `f4e95c8c...`。 |
| 当前仓库提交 | `dfd68681...`，与 understand 元信息不一致。 |
| `.understand-anything/.understandignore` | 已存在。 |

按 understand skill 的规则，既然 `.understandignore` 已存在， full rebuild 之前需要先让用户确认忽略规则。也就是说：现在不能把 official understand 图谱说成“今天已全量刷新”。更准确的说法是：

```text
CodeGraph 当前可用于结构查询；official understand 图谱存在但偏旧。
如果要全量刷新，需要先确认 .understandignore，再执行 understand 重建。
```

### 45.6 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `88%` | `90%` |
| 系统理解总文档可交接度 | `98.5%` | `99%` |

为什么这轮继续提升：

- 已经用真实“已提交”的电工样本证明电工历史回看链路可用。
- 已经用真实“已提交”的内勤样本证明内勤每日历史回看链路存在缺口。
- 已经把缺口定位到具体服务函数，而不是笼统说“前端没显示”。
- 已经确认 official understand 图谱状态，避免把旧图谱误报成最新图谱。

还不能标记 100% 的原因：

- 内勤 `owner_daily` 历史回看还没有修复并回归。
- 还没有进行真实提交、保存草稿、导出缺报、外发钉钉、AI 真实动作等带副作用流程。
- official understand 全量刷新还需要先确认 `.understandignore`。
- 页面慢加载、生产页过站下机参考字段优先级、卷级线索待绑定机列等问题仍是后续修复项。

## 46. 追加理解：缺报导出、异常日期参数和生产页过站下机字段优先级

本节继续补两个容易误判的问题：

1. 缺报导出到底有没有内容，还是只是页面上看起来空。
2. 生产页“过站下机参考”为什么可能显示 `0 吨`，是不是数据库真的没有工序下机量。

本轮仍然只做只读核验：

- 只调用 `GET` 接口。
- 没有提交表单。
- 没有改生产库。
- 没有触发钉钉、AI 外发或考勤自动处理。

核验业务日期：`2026-06-13`。

### 46.1 异常页日期参数口径

前端异常时间线代码位置：

```text
frontend/src/composables/useAlertsTimeline.js
```

当前调用口径是：

| 来源 | 参数名 | 说明 |
|---|---|---|
| 工厂总览异常 | `target_date` | 走旧工厂总览口径。 |
| 质量问题 | `business_date` | 质量问题接口按业务日查。 |
| 对账问题 | `business_date` + `status=open` | 对账接口按业务日查未关闭事项。 |
| MES 填报差异 | `business_date` | 查 MES 和本地填报差异。 |
| 实时缺报 | `business_date` | 查实时聚合里的缺报。 |

这说明之前“质量/对账旧日期混进异常页”的风险已经有明确修复方向：质量和对账不能再误传 `target_date`，现在代码里传的是 `business_date`。

只读接口核验结果：

| 接口 | 参数 | 状态 | 结果 |
|---|---|---:|---|
| `/api/v1/quality/issues` | `business_date=2026-06-13` | `200` | `0` 条。 |
| `/api/v1/reconciliation/items` | `business_date=2026-06-13&status=open` | `200` | `0` 条。 |
| `/api/v1/aggregation/live/mes-fill-gaps` | `business_date=2026-06-13` | `200` | `195` 条差异。 |

通俗说：异常页不是只看一张“异常表”，它是把多个来源拼到一起。当天质量和对账为空，不代表系统没有异常；MES 填报差异还有 `195` 条。

### 46.2 缺报 Excel 导出链路

后端路由位置：

```text
backend/app/routers/realtime.py:312
GET /api/v1/aggregation/live/missing-report-export
```

这个接口的真实链路是：

```text
请求 business_date
  -> build_live_aggregation()
  -> build_pending_assignment_detail()
  -> build_mes_fill_gaps()
  -> build_missing_report_workbook()
  -> 返回 xlsx 文件
```

只读核验结果：

| 项 | 结果 |
|---|---|
| HTTP 状态 | `200` |
| 文件类型 | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| 文件名 | `missing-report-2026-06-13.xlsx` |
| 文件大小 | `24856` 字节 |
| 工作表 | `缺报明细`、`待归属明细`、`车间汇总`、`MES异常明细` |

工作表行数如下：

| 工作表 | 行数 | 说明 |
|---|---:|---|
| 缺报明细 | `128` | 包含标题、说明、表头和缺报数据行。 |
| 待归属明细 | `5` | 包含标题、说明、表头和待归属数据行。 |
| 车间汇总 | `16` | 包含标题、表头和车间汇总行。 |
| MES异常明细 | `198` | 包含标题、表头和 MES 差异数据行。 |

注意：这里的行数不是纯数据条数，因为 Excel 里还有标题行、说明行、表头行。更准确的结论是：缺报导出接口能生成有结构、有内容的 Excel，不是空文件。

后续如果用户说“导出缺报 Excel 信息不全”，排查重点不应该先怀疑接口完全没数据，而应该看：

- 哪个工作表缺字段。
- 表头是否符合现场需要。
- 数据行是否把责任人、车间、机列、班次、原因、来源写清楚。
- 前端下载按钮是否传对 `business_date` 和 `workshop_id`。

### 46.3 生产页过站下机参考为什么会显示 0

生产页代码位置：

```text
frontend/src/views/manage/production/ProductionPage.vue:224
```

关键逻辑是：

```text
process_output_tons =
  snapshot.data.value.process_total_output
  ?? factoryCommandOverview.process_output_tons
  ?? factoryCommandOverview.total_output_tons
```

这段代码的问题在于：`??` 只会跳过 `null` 和 `undefined`，不会跳过 `0`。

本轮生产只读接口核验：

| 接口 | 字段 | 返回 |
|---|---|---:|
| `/api/v1/dashboard/factory-director?target_date=2026-06-13` | `process_total_output` | `0.0` |
| `/api/v1/factory-command/overview?target_date=2026-06-13` | `process_output_tons` | `1618.55` |
| `/api/v1/factory-command/overview?target_date=2026-06-13` | `total_output_tons` | `1618.55` |

所以前端如果先拿旧字段 `process_total_output=0.0`，就会把 `0` 当成有效值，后面的 `1618.55` 不会再被使用。

通俗说：不是后端完全没有过站下机量，而是前端先看到一个旧接口给的 `0`，就停止继续往后找正确值。

建议后续修复方式：

- 生产页的“过站下机参考”优先使用 `factoryCommandOverview.process_output_tons`。
- 如果旧字段 `process_total_output` 是 `0`，不能直接覆盖后面更可信的调度总览字段。
- 前端文案要保留“参考”二字，因为它不是“包装产量”，也不是“全厂入库产量”。

### 46.4 日报接口当前结构

本轮还确认了一个容易写错的接口结构：

```text
GET /api/v1/dashboard/daily-production?target_date=2026-06-13
```

它的产量字段在根级 `plant_output` 里，不在 `daily_overview.plant_output` 里。

关键返回：

| 字段 | 数值 | 来源 |
|---|---:|---|
| `plant_output.daily_output` | `241.91` | `mes_stock_records` |
| `plant_output.packaging_output` | `241.91` | 包装产量口径 |
| `plant_output.finished_inbound_output` | `246.38` | `storage_owner_daily_entry` |
| `energy.total_electricity` | `6512.0` | `mobile_shift_report` |
| `energy.total_gas` | `18913.0` | `mobile_shift_report` |
| `contracts.daily_new` | `227.0` | 吨 |

这进一步确认：同一天同时存在多个合法数字。

- `241.91 吨` 是 MES 包装产量。
- `246.38 吨` 是全厂入库产量，来自成品库/内勤入库口径。
- `1618.55 吨` 是调度观察用的工序过站下机参考。

这三个数不能互相替换，也不能简单合成一个“总产量”。

### 46.5 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `90%` | `91%` |
| 系统理解总文档可交接度 | `99%` | `99.2%` |

为什么这轮继续提升：

- 已经确认缺报导出不是空文件，而是 4 个工作表都有结构和内容。
- 已经确认异常页日期参数当前口径，避免再次把 `target_date` 和 `business_date` 混用。
- 已经确认生产页 `0 吨` 风险是前端字段优先级问题，不是调度总输出不存在。
- 已经确认日报接口产量字段当前在根级 `plant_output`，不是旧理解里的 `daily_overview.plant_output`。

还不能标记 100% 的原因：

- 还没有修复生产页字段优先级并做浏览器回归。
- 还没有实际点击前端导出按钮下载 Excel 后做人工验收，只核验了接口生成的工作簿。
- 还没有真实提交/保存类 QA，也没有触发外部通讯真实动作。
- official understand 全量图谱仍未重建。

## 47. 追加理解：AI、钉钉和外部通讯真实边界

本节补“主动汇报、钉钉、AI 智能体”这块最容易说混的地方。

本轮仍然只做只读核验：

- 没有调用任何 `POST` 外发接口。
- 没有生成新的 AI 对话。
- 没有触发日报推送。
- 没有触发钉钉免登。
- 没有修改通道、发件箱、用户或日报。
- 没有读取或记录任何密钥明文。

### 47.1 三条链路不要混在一起

系统里至少有三类看起来都和“AI / 钉钉 / 汇报”有关的链路，但它们不是一回事：

| 链路 | 主要用途 | 关键位置 | 是否等于真实外发 |
|---|---|---|---|
| AI 工作台和 briefing | 管理端 AI 对话、日报摘要、智能分析记录 | `ai_conversations`、`ai_messages`、`ai_briefing_events` | 不是。它主要是系统内记录和页面展示。 |
| 外部通讯治理台 | 多智能体、通道、证据、审批、发件箱、外部日志 | `agent_profiles`、`communication_channels`、`agent_outbox_messages`、`external_message_logs` | 只有配置通道并派发 outbox 后才可能外发。 |
| 钉钉免登/日报推送/提醒 | 钉钉登录、工作通知、日报推送、提醒 | `/api/v1/dingtalk/*`、`reports/{id}/push-dingtalk`、`dingtalk_service.py` | 某些 POST 或定时任务会外发，不能当只读探针。 |

通俗说：

```text
AI 有记录 ≠ 已经发钉钉群
治理台有页面 ≠ 已经配置外发通道
钉钉配置存在 ≠ 当前每条消息都会真实发送
```

### 47.2 外部通讯治理台当前生产状态

管理端接口：

```text
GET /api/v1/agent-management/overview
```

代码边界：

- `backend/app/routers/agent_management.py:25` 是只读总览接口。
- `_ensure_agent_management_access()` 要求管理员权限，非管理员会 `403`。
- 页面读取 `frontend/src/api/agent-management.js` 的 `fetchAgentManagementOverview()`。

生产只读核验结果：

| 项 | 当前结果 |
|---|---:|
| `safe_mode` | `true` |
| `agent_total` | `0` |
| `channel_total` | `0` |
| `active_channel_total` | `0` |
| `pending_event_total` | `0` |
| `outbox_pending_total` | `0` |
| `knowledge_entry_total` | `11` |
| 返回的 agents/channels/events/evidence/approvals/outbox | 都是 `0` 条 |

数据库只读核验也一致：

| 表 | 当前数量 |
|---|---:|
| `agent_profiles` | `0` |
| `communication_channels` | `0` |
| `agent_channel_bindings` | `0` |
| `agent_events` | `0` |
| `agent_outbox_messages` | `0` |
| `external_message_logs` | `0` |
| `multimodal_evidence` | `0` |
| `agent_operation_approvals` | `0` |
| `agent_rate_limits` | `0` |

这说明：新“多智能体外部通讯治理台”的能力已经有页面、接口和表，但生产当前还没有配置真实 agent、通道、发件箱和外部日志。

### 47.3 outbox 派发的真正闸门

代码位置：

```text
backend/app/services/agent_communication_service.py:202
```

`dispatch_outbox_message()` 的关键逻辑是：

1. 先找 `agent_outbox_messages` 里的待发送消息。
2. 再找对应的 `communication_channels`。
3. 如果通道不存在或未启用，标记失败。
4. 如果通道 `dry_run=true`，只把消息标为 `dry_run`，写 `external_message_logs`，不真正发送。
5. 只有通道不是 dry-run，才会调用 `send_group_message()` 发钉钉群消息。

所以判断一条消息会不会真实发出，不能只看“有 AI 事件”或“有 outbox”，还要看：

- 有没有 `communication_channels`。
- 通道是否 `is_active=true`。
- 通道是否 `dry_run=false`。
- 是否真的执行了 `dispatch_outbox_message()`。

当前生产环境 `communication_channels=0`、`agent_outbox_messages=0`，所以新治理台链路没有真实群消息在发。

### 47.4 钉钉配置和直接通知路径

生产配置只读核验：

| 项 | 当前结果 |
|---|---|
| `DINGTALK_ENABLED` | `true` |
| `LLM_ENABLED` | `true` |
| `DINGTALK_APP_KEY` | 已配置，但本轮不读取值 |
| `DINGTALK_APP_SECRET` | 已配置，但本轮不读取值 |
| `DINGTALK_AGENT_ID` | 已配置，但本轮不读取值 |
| `DINGTALK_NOTIFY_DRY_RUN` | `false` |

这个结果要谨慎理解：

- `DINGTALK_NOTIFY_DRY_RUN=false` 说明：如果某条直接通知路径被触发，并且接收人/群配置完整，就可能真实调用钉钉。
- 但当前生产库里活跃用户绑定 `dingtalk_user_id` 的数量是 `0`，其中管理员或经理绑定数也是 `0`。
- 所以很多“发给某个用户”的工作通知路径当前没有实际收件人。

直接通知相关代码：

| 路径 | 位置 | 风险边界 |
|---|---|---|
| 钉钉免登 | `/api/v1/dingtalk/login`、`/api/v1/dingtalk/h5-login` | POST，会换取身份并可能更新用户钉钉绑定，不能当只读探针。 |
| 日报推送 | `POST /api/v1/reports/{report_id}/push-dingtalk` | 会调用 `push_daily_report_to_dingtalk()`，可能发工作通知并写审计。 |
| reporter/reminder | `backend/app/agents/reporter.py`、`backend/app/agents/reminder.py` | 如果启用且用户有钉钉身份，可能调用 `send_work_notification()`。 |
| 钉钉考勤同步 | `dingtalk-clock-sync` 定时任务 | 每 30 分钟同步考勤记录，属于外部数据拉取/写本地考勤，不是消息群发。 |

### 47.5 日报推送当前只读状态

日报推送服务：

```text
backend/app/services/dingtalk_daily_report.py
```

核心规则：

- `quality_gate_status == 'blocked'` 时拒绝推送。
- `final_text_summary` 为空时拒绝推送。
- 默认收件人是有 `dingtalk_user_id` 的 `admin` 或 `manager`。
- 调用后会写审计记录。

生产只读核验：

| 项 | 当前结果 |
|---|---:|
| `daily_reports` 总数 | `1` |
| 有 `final_text_summary` 的日报 | `1` |
| 质量闸门为 blocked 的日报 | `0` |
| 活跃且绑定钉钉 user_id 的用户 | `0` |
| 活跃且绑定钉钉 user_id 的 admin/manager | `0` |

最近日报样本：

| 日报 ID | 日期 | 状态 | 质量闸门 | 是否有最终正文 |
|---:|---|---|---|---|
| `1` | `2026-05-26` | `published` | `pending` | 是 |

这说明日报推送功能链路存在，但当前默认收件人为空。后续如果给管理员/经理绑定钉钉身份，再点击推送，就可能真的发。

### 47.6 AI 数据当前生产状态

生产库只读统计：

| 表 | 当前数量 | 说明 |
|---|---:|---|
| `ai_conversations` | `6` | AI 对话记录。 |
| `ai_messages` | `26` | AI 消息记录。 |
| `ai_briefing_events` | `1271` | AI briefing / 事件摘要记录较多。 |
| `ai_watchlist_items` | `0` | 当前无关注项。 |
| `assistant_usage` | `4` | LLM 用量记录。 |

这个结果说明：系统内 AI 记录确实在产生或曾经产生过，但这不代表钉钉群里已经真实外发。外发还要看上面的通道、发件箱、直接通知路径。

### 47.7 后续 QA 建议

外部通讯类 QA 要分层做：

1. 只读层：继续使用 `GET /api/v1/agent-management/overview`、数据库只读统计、日志只读查看。
2. dry-run 层：如果要测试 outbox 派发，先创建测试通道并强制 `dry_run=true`，确认只写 dry-run 日志。
3. 小范围真实层：只有你明确指定收件人、测试群、测试日报，才允许关闭 dry-run 并触发真实发送。
4. 回滚层：测试后恢复 dry-run 或停用测试通道，保留审计记录。

最重要的操作规则：

```text
生产环境里，所有 AI、钉钉、日报推送、assistant actions 的 POST，都先当成有副作用。
没有明确授权，不要点，不要跑，不要用它们做“探测”。
```

### 47.8 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `91%` | `92%` |
| 系统理解总文档可交接度 | `99.2%` | `99.4%` |

为什么这轮继续提升：

- 已经把 AI 记录、外部通讯治理台、钉钉免登、钉钉真实推送区分开。
- 已经只读确认生产治理台当前没有 agent、channel、outbox、external log。
- 已经只读确认钉钉配置存在且 notify dry-run 关闭，因此后续真实推送测试必须非常谨慎。
- 已经只读确认当前没有活跃用户绑定钉钉 user_id，默认日报工作通知没有实际收件人。

还不能标记 100% 的原因：

- 没有做真实钉钉发送测试。
- 没有做 dry-run outbox 派发测试。
- 没有做 AI 生成 briefing 的真实 POST 测试。
- 没有做钉钉免登真实扫码闭环。

## 48. 追加理解：生产健康检查、定时任务和外部同步状态

本节只记录只读核验结果。本轮没有触发手机填报提交、日报推送、AI 生成、钉钉发送、MES 手动同步等写入型动作。

### 48.1 健康检查接口分两类

代码位置：

```text
backend/app/main.py:294
backend/app/core/health.py:86
```

当前后端同时提供四个健康检查入口：

| 接口 | 含义 | 当前生产结果 |
|---|---|---|
| `/healthz` | 服务活着没有，主要看应用进程是否能响应 | `200`，`status=ok` |
| `/api/v1/healthz` | 同上，只是带 API 前缀 | `200`，`status=ok` |
| `/readyz` | 服务是否准备好承载核心业务，会检查数据库、上传目录、排班、MES 同步等 | `200`，`status=ready` |
| `/api/v1/readyz` | 同上，只是带 API 前缀 | `200`，`status=ready` |

通俗理解：

```text
healthz = 服务有没有活着
readyz  = 服务能不能比较安全地接业务流量
```

所以不能只看 `/healthz=200` 就说全系统都正常。更重要的是看 `/readyz` 里面的 `checks` 和 `details`。

### 48.2 生产 readyz 当前细项

生产只读核验结果：

| 检查项 | 当前结果 | 解释 |
|---|---|---|
| `database` | `ok` | 本地业务数据库可连接。 |
| `uploads` | `ok` | 上传目录可用。 |
| `equipment_binding` | `ok` | 机台绑定覆盖率达到当前门槛。 |
| `schedule` | `ok` | 当前业务日排班口径可用。 |
| `pipeline` | `ok` | 当前生产日报硬门禁通过。 |
| `mes_sync` | `ok` | 外部 MES 投影同步当前被判定为新鲜可用。 |
| `iot_energy_sync` | `unconfigured` | 物联网能耗同步还没有配置，不等于程序故障。 |

几个关键数字：

| 字段 | 当前值 | 说明 |
|---|---:|---|
| 活跃生产车间 | `13` | 这里是生产车间口径。 |
| 活跃数据库车间 | `15` | 更宽口径，包含非生产或管理类口径，不要和 13 混用。 |
| 活跃班次 | `3` | 当前三班次口径。 |
| 活跃手机填报用户 | `86` | 当前还可用于手机端的角色账号量级。 |
| 活跃机台 | `106` | 当前被系统识别的机台量级。 |
| 排班行数 | `261` | 当前排班数据量级。 |
| 机台绑定覆盖率 | `0.95` | 约 95%，不是 100%。 |

### 48.3 MES 同步当前是 SQL Server 投影链路

生产 `/readyz` 的 `details.mes_sync` 当前显示：

| 字段 | 当前值 |
|---|---|
| `adapter` | `sqlserver` |
| `source` | `mes_projection` |
| `configured` | `true` |
| `migration_ready` | `true` |
| `status` | `fresh` |
| `last_run_status` | `success` |
| `fetched_count` | `50` |
| `upserted_count` | `50` |
| `replayed_count` | `0` |
| `error_message` | 空 |
| `action_required` | `none` |

这说明当前生产健康检查认可的是：

```text
外部 MES SQL Server
  -> 后端只读同步
  -> 本地 mes_* 投影表
  -> 页面和算法读取本地投影
```

注意两个时间字段不要误读：

| 字段 | 怎么理解 |
|---|---|
| `sync_freshness_seconds` | 同步任务距离现在多久跑过一次。当前约几十秒量级，所以 readyz 判断同步是新鲜的。 |
| `lag_seconds` | 外部 MES 最近事件时间距离现在多久。它可能比同步任务间隔大，说明外部源数据本身可能一段时间没新事件，不一定是同步任务没跑。 |

所以当前结论是：

```text
同步任务最近跑成功了。
但如果业务上要求“现场秒级变化”，还要继续看外部 MES 本身有没有新事件，以及页面是否做了实时刷新。
```

### 48.4 MES 同步状态接口路径容易写错

代码位置：

```text
backend/app/routers/mes.py:58
```

真实路由是：

```text
/api/v1/mes/sync-status
```

不是：

```text
/api/v1/mes/sync/status
```

本轮只读探测时，错误路径返回 `404`，这不是 MES 同步故障，而是路径写错。

后续排查时要优先用正确路径，避免把“接口地址错了”误判成“同步挂了”。

### 48.5 定时任务注册逻辑

代码位置：

```text
backend/app/main.py:35
backend/app/core/scheduler.py:83
backend/app/services/dingtalk_service.py:698
backend/app/core/event_bus.py:228
```

服务启动时会做几件事：

1. 校验配置。
2. 创建上传目录。
3. 尝试获取数据库里的 leader lock。
4. 只有拿到 leader lock 的进程会注册后台定时任务。
5. 注册钉钉考勤同步任务。
6. 注册实时事件清理任务。
7. 注册编排流水线。

为什么要有 leader lock：

```text
线上可能有多个 worker。
如果每个 worker 都跑同一批定时任务，就会重复同步、重复生成日报、重复提醒。
leader lock 的作用是让同一时间只有一个 worker 负责后台任务。
```

### 48.6 当前会注册的主要后台任务

| 任务 | 触发规则 | 作用 |
|---|---|---|
| `daily_report` | 每天 `08:00` | 自动处理日报相关流程。 |
| `mes_sync_core` | 按 `MES_SYNC_POLL_SECONDS` 周期 | 同步核心 MES 数据。 |
| `mes_sync_realtime` | 按 `MES_REALTIME_SYNC_POLL_SECONDS` 周期 | 同步更实时的 MES 数据。 |
| `mes_sync_business` | 按 `MES_BUSINESS_SYNC_POLL_MINUTES` 周期 | 同步业务分析需要的数据。 |
| `mes_sync_reference` | 按 `MES_REFERENCE_SYNC_POLL_MINUTES` 周期 | 同步参考类数据。 |
| `iot_energy_sync` | 仅物联网能耗适配器配置后注册 | 同步物联网能耗数据。当前生产为未配置。 |
| `fill_reminder` | 每天 `08:00`、`14:00`、`20:00` | 填报提醒。 |
| `data_archive` | 每周日 `02:00` | 数据归档。 |
| `dingtalk-clock-sync` | 每 30 分钟 | 同步钉钉考勤打卡。 |
| `realtime-events-cleanup` | 每小时 | 清理实时事件旧数据。 |

这里要注意：

```text
代码里“注册了任务”不等于“每个任务最近都成功跑完”。
```

本轮已经确认生产服务在运行、readyz 认可 MES 同步最近成功，但还没有逐个核验所有定时任务的最近执行日志和失败重试记录。

### 48.7 生产服务当前运行状态

生产机只读查看服务状态：

| 项 | 当前结果 |
|---|---|
| 服务名 | `aluminum-bypass.service` |
| 状态 | `active` |
| 主进程 | `uvicorn` |
| worker 数 | `2` |
| 内存量级 | 约 `1.2G` |
| 启动时间 | 2026-06-14 早上约 `07:46` |

日志里能看到：

- 本轮只读访问了健康检查和少量管理接口。
- 日志里也能看到现场用户真实访问手机端接口。
- 有一条现场用户的 `POST /api/v1/mobile/coil-entry` 成功记录，但这不是本轮操作触发的，只能说明生产现场有人正在使用这条手机端写入路径。
- 日志里出现过外部扫描 `/.git/config` 的 404，这类扫描很常见，但仍提醒：生产不要暴露源码目录或敏感配置。

### 48.8 这一轮新增的判断边界

本轮可以更确定的事：

1. 生产健康检查路径已经统一到 `/healthz`、`/api/v1/healthz`、`/readyz`、`/api/v1/readyz` 四个入口。
2. `/readyz` 当前返回 `ready`，不是 503。
3. 外部 MES 当前在线上走的是 SQL Server 直连同步到本地投影，不是单纯 MVC 页面抓取。
4. MES 同步最近一次任务成功，并且写入了 50 条。
5. 物联网能耗当前是 `unconfigured`，所以能耗仍主要依赖现有填报/本地链路，不能说物联网能耗已经接通。
6. 定时任务有 leader lock，避免多 worker 重复跑任务。
7. 钉钉考勤同步和实时事件清理是独立注册的后台任务，不要和钉钉消息外发混为一谈。

本轮还不能确定的事：

1. 每一个定时任务最近一次是否都执行成功。
2. MES 同步的每类数据是否都和前端所有指标完全对齐。
3. 物联网能耗库接入后的机台级电量是否能自动替代人工电工填报。
4. 手机端真实提交后，每个字段是否都百分百进入正确业务表。
5. 钉钉真实推送、AI 真实生成、日报真实外发是否在生产目标群里按预期工作。

### 48.9 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `92%` | `93%` |
| 系统理解总文档可交接度 | `99.4%` | `99.5%` |

为什么只加 1%：

- 健康检查、readyz、MES 同步和服务状态都更清楚了。
- 但没有做写入类真实 QA，也没有逐个触发或核验所有定时任务执行结果。
- 所以这轮是“运行边界更清楚”，不是“全部业务闭环已经完成”。

下一步最有价值的 3 件事：

1. 做一轮只读到半写入的分层 QA：先 GET 查，再用测试账号和测试数据做手机端提交。
2. 核对 MES 投影表到前端核心指标的字段映射，尤其是包装产量、全厂入库产量、在制卷、机列匹配。
3. 给定时任务补一张“最近执行状态表”，让日报、MES 同步、考勤同步、事件清理、归档这些任务不用靠翻日志判断。

## 49. 追加理解：MES 同步运行历史和调度大屏可观测性

本节继续只读核验，重点是回答一个实际运维问题：

```text
同步是不是只靠日志看？
用户在页面上能不能看到同步稳定性？
线上数据库里到底有没有同步运行记录？
```

结论先说：

```text
外部 MES 同步已经有落库的运行历史表，也有管理端大屏可视化。
物联网能耗同步虽然有模型和服务设计，但当前生产还没有接入运行记录。
```

### 49.1 MES 同步运行记录表

代码位置：

```text
backend/app/models/mes.py:307
backend/app/services/mes_sync_service.py:1382
backend/app/routers/mes.py:88
backend/app/schemas/mes_sync.py:48
```

MES 同步运行记录落在：

```text
mes_sync_run_logs
```

核心字段：

| 字段 | 含义 |
|---|---|
| `cursor_key` | 同步游标类型，当前主要是 `coil_snapshots`。 |
| `started_at` | 本次同步开始时间。 |
| `finished_at` | 本次同步结束时间。 |
| `status` | `running`、`success`、`failed` 等运行状态。 |
| `fetched_count` | 从外部 MES 读到多少条。 |
| `upserted_count` | 写入或更新到本地投影多少条。 |
| `replayed_count` | 回放处理条数。 |
| `lag_seconds` | 外部事件时间与当前时间的差距。 |
| `error_message` | 失败原因，接口返回前会做敏感信息脱敏。 |

后端服务 `recent_sync_runs()` 会按最新开始时间倒序取最近记录，并统计：

- 总次数。
- 成功次数。
- 失败次数。
- 运行中次数。
- 最新状态。

所以这里不是纯日志，是真正有表、有接口、有摘要统计。

### 49.2 页面和接口链路

后端接口：

```text
GET /api/v1/mes/sync-runs
```

前端 API：

```text
frontend/src/api/mes.js
fetchMesSyncRuns(params)
```

调度大屏页面：

```text
frontend/src/views/reports/LiveDashboard.vue
```

页面会请求：

```text
fetchMesSyncStatus()
fetchMesSyncRuns({ limit: 12 })
```

并展示一个“MES 同步稳定性”区域，包含：

| 页面字段 | 含义 |
|---|---|
| 最近 12 次同步条形状态 | 用小柱状图看最近同步是否连续成功。 |
| 成功率 | 最近记录里成功次数占比。 |
| 最近拉取 | 最近一次 `fetched_count`。 |
| 最近入库 | 最近一次 `upserted_count`。 |
| 耗时 | 最近一次从开始到结束的秒数。 |

这个页面设计的价值是：

```text
管理者不用懂日志，也能看到“数据是不是还在同步、最近是不是成功、有没有入库”。
```

### 49.3 生产库只读核验结果

本轮使用生产机同一套后端环境只读查询，未输出数据库连接串，未写入数据。

截至本轮核验时：

| 项 | 结果 |
|---|---:|
| `mes_sync_run_logs` 总数 | `42843` |
| 成功记录数 | `42807` |
| 失败记录数 | `36` |
| 运行中记录数 | `0` |
| 最近 5 次状态 | 全部 `success` |
| 最近 5 次每次拉取 | `50` |
| 最近 5 次每次入库 | `50` |

最近 5 次同步时间大致集中在：

```text
2026-06-14 20:45:00 到 20:47:00
```

最近几次耗时大致是：

```text
1.1 秒到 6.2 秒之间
```

通俗理解：

```text
同步任务不是偶尔跑一下。
它在持续按周期跑，而且最近多次都成功把 50 条数据写入本地投影。
```

### 49.4 失败记录如何看

生产库里有 `36` 条失败记录，这不一定代表当前故障。

更合理的判断方式是：

1. 先看最近一次状态。
2. 再看最近 12 次或最近 1 小时成功率。
3. 再看失败是否连续。
4. 最后才看单条 `error_message`。

当前最新多次是成功，所以不能因为历史上有 36 条失败，就说“MES 同步现在坏了”。

但这也说明：

```text
后续管理端最好显示“最近失败时间”和“连续失败次数”，比只显示总失败数更有用。
```

### 49.5 物联网能耗同步当前只有设计，没有生产运行记录

代码位置：

```text
backend/app/models/energy.py:68
backend/app/services/iot_energy_sync_service.py
```

物联网能耗同步运行表是：

```text
iot_energy_sync_runs
```

字段包括：

| 字段 | 含义 |
|---|---|
| `source_system` | 来源系统，默认 `iot_meter`。 |
| `status` | 同步状态。 |
| `started_at` | 开始时间。 |
| `finished_at` | 结束时间。 |
| `records_read` | 读取记录数。 |
| `records_written` | 写入记录数。 |
| `error_message` | 失败原因。 |

但生产只读核验结果是：

```text
iot_energy_sync_runs = 0
```

这和 `/readyz` 里的结果一致：

```text
iot_energy_sync = unconfigured
```

所以当前能耗不能按“物联网已自动接入”来理解。更准确的说法是：

```text
系统已经预留了物联网能耗同步模型和服务，
但生产当前还没有真实物联网能耗同步运行记录。
```

### 49.6 当前可观测性缺口

MES 同步可观测性已经比较好：

- 有运行表。
- 有最近运行接口。
- 调度大屏已显示同步稳定性。
- `/readyz` 会把同步新鲜度纳入上线健康。

但其他后台任务还不够清楚：

| 任务 | 当前情况 | 缺口 |
|---|---|---|
| 日报自动任务 | 代码里有注册 | 还缺最近执行状态表。 |
| 填报提醒 | 代码里有注册 | 还缺最近发送/跳过/失败记录视图。 |
| 数据归档 | 代码里有注册 | 还缺归档结果状态。 |
| 钉钉考勤同步 | 代码里有注册 | 还缺页面化的最近同步结果。 |
| 实时事件清理 | 代码里有注册 | 还缺清理数量和最近执行时间展示。 |

最短补齐路径：

```text
新增一张通用 job_run_logs 表，
或者在现有任务各自表的基础上做一个统一“后台任务健康”接口。
```

字段建议很简单：

| 字段 | 作用 |
|---|---|
| `job_key` | 任务名，比如 `daily_report`、`fill_reminder`。 |
| `started_at` | 开始时间。 |
| `finished_at` | 结束时间。 |
| `status` | 成功、失败、跳过、运行中。 |
| `read_count` | 读取多少。 |
| `write_count` | 写入多少。 |
| `skip_reason` | 为什么跳过。 |
| `error_message` | 失败原因，必须脱敏。 |

### 49.7 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `93%` | `94%` |
| 系统理解总文档可交接度 | `99.5%` | `99.6%` |

为什么这轮能继续提升：

- 已经证明 MES 同步不只是 readyz 状态，而是有真实落库运行记录。
- 已经确认调度大屏会展示最近 12 次同步稳定性。
- 已经确认物联网能耗同步当前生产没有运行记录，不能误说已经接通。
- 已经把“哪些后台任务还缺统一可观测性”列成清单。

还不能到 100% 的原因：

- 非 MES 后台任务还缺逐项运行结果核验。
- 物联网能耗数据源还没提供，无法核验真实同步。
- 真实手机端提交和真实钉钉/AI 外发仍未授权触发。

## 50. 追加理解：非 MES 后台任务可观测性和 AI 小时简报阻塞

本节继续只读核验，重点补齐第 49 节留下的问题：

```text
除了 MES 同步以外，其他后台任务有没有运行记录？
如果没有统一 job_run_logs，要从哪些业务表判断？
AI 小时简报现在到底有没有在正常生成？
```

结论先说：

```text
系统没有统一的 job_run_logs 表。
MES 同步有专门运行表。
催报、日报、钉钉考勤、实时事件清理分别靠各自业务表或日志判断。
AI 小时简报当前在线上每小时失败，根因是 MES 卷材投影没有 machine_code，代码又没有过滤空机列。
```

### 50.1 后台任务分两处注册

后台任务不是只在 `backend/app/core/scheduler.py` 一处注册。

第一处：

```text
backend/app/core/scheduler.py
```

这里注册：

| 任务 ID | 作用 |
|---|---|
| `daily_report` | 每天 08:00 生成日报。 |
| `mes_sync_core` | 周期同步核心 MES 投影。 |
| `mes_sync_realtime` | 周期同步实时 MES 投影。 |
| `mes_sync_business` | 周期同步业务分析 MES 投影。 |
| `mes_sync_reference` | 周期同步参考数据。 |
| `iot_energy_sync` | 物联网能耗同步，当前生产未配置。 |
| `fill_reminder` | 每天 08:00、14:00、20:00 催报。 |
| `data_archive` | 每周日 02:00 数据归档。 |

第二处：

```text
backend/app/main.py
```

在 `lifespan` 启动时还会注册：

| 任务 ID | 作用 |
|---|---|
| `default_schedule_seed` | 每天 00:05 补默认排班种子。 |
| `deterministic_pipeline` | 每小时跑确定性汇总和发布主链路。 |
| `reminder_sweep` | 每 30 分钟检查未提交班次。 |
| `ai_hourly_briefing` | 每小时生成 AI 巡检简报。 |
| `aluminum_price_daily` | 工作日 10:30 抓铝价。 |
| `executive_daily_snapshot` | 每天 08:20 汇总成本和利润快照。 |

另外两类任务由服务各自注册：

| 任务 ID | 注册位置 | 作用 |
|---|---|---|
| `dingtalk-clock-sync` | `backend/app/services/dingtalk_service.py` | 每 30 分钟同步钉钉考勤打卡。 |
| `realtime-events-cleanup` | `backend/app/core/event_bus.py` | 每小时清理 48 小时前的实时事件。 |

### 50.2 当前没有统一 job_run_logs

生产库里和“运行记录、日志、提醒、事件、报表”相关的表包括：

```text
agent_events
ai_briefing_events
attendance_clock_records
attendance_process_logs
audit_logs
clock_records
coil_flow_events
daily_consumable_logs
daily_reports
external_message_logs
iot_energy_sync_runs
mes_sync_run_logs
mobile_reminder_records
mobile_shift_reports
quality_issue_log
realtime_events
```

这里面没有一个统一的：

```text
job_run_logs
```

所以排查后台任务时不能只问“任务有没有跑”，而要按任务类型分别看：

| 任务 | 主要证据表 |
|---|---|
| MES 同步 | `mes_sync_run_logs` |
| 物联网能耗同步 | `iot_energy_sync_runs` |
| 催报 | `mobile_reminder_records`、`audit_logs` |
| 日报生成 | `daily_reports`、`audit_logs` |
| 钉钉考勤同步 | `attendance_clock_records` |
| 人工考勤处理 | `attendance_process_logs` |
| 实时事件清理 | `realtime_events` 的最早时间和 48 小时前剩余数量 |
| AI 简报 | `ai_briefing_events` 和服务日志 |

### 50.3 生产只读数据：日报、催报、实时事件、考勤

本轮只读查询生产库，只取数量、状态和最新时间，不输出人员明细。

| 表 | 当前结果 | 怎么理解 |
|---|---:|---|
| `daily_reports` | `1` 条 | 当前只有 1 份已发布日报，最新更新时间是 2026-05-26；不能证明近期日报自动任务正常产出。 |
| `mobile_reminder_records` | `4452` 条 | 催报链路确实在落库。 |
| `mobile_reminder_records.last_reminded_at` | 2026-06-14 20:47 左右 | 最近仍在更新催报记录。 |
| `mobile_reminder_records.reminder_status` | 全部 `sent` | 当前记录都处于已发送/已记录状态。 |
| `mobile_reminder_records.reminder_channel` | 全部 `system` | 当前催报主要是系统记录，不是实际钉钉用户通知。 |
| `realtime_events` | `11822` 条 | 实时事件流在落库。 |
| `realtime_events` 最早时间 | 2026-06-12 20:47 左右 | 与 48 小时清理规则基本接近。 |
| `realtime_events` 最新时间 | 2026-06-14 20:55 左右 | 实时事件还在持续产生。 |
| `realtime_events` 超过 48 小时数量 | `35` 条 | 不是很大，但说明清理任务状态最好单独可视化。 |
| `attendance_process_logs` | `1` 条 | 只有一次人工/手动考勤处理记录。 |
| `attendance_clock_records` | `0` 条 | 钉钉考勤自动同步没有实际打卡记录入库。 |
| `clock_records` | `0` 条 | 另一套打卡表当前也没有记录。 |
| `audit_logs` | `4095` 条 | 审计日志在记录登录、扫码、填报等操作。 |

实时事件类型分布里，最多的是：

```text
mes_sync_completed = 11784
entry_saved = 15
entry_submitted = 15
energy_changed = 8
```

这说明调度大屏实时事件目前主要由 MES 同步驱动，人工填报和能耗变化事件占比很小。

### 50.4 钉钉考勤同步当前边界

代码位置：

```text
backend/app/services/dingtalk_service.py
```

`dingtalk-clock-sync` 每 30 分钟调用：

```text
sync_recent_clock_records()
  -> sync_clock_records()
  -> service.fetch_clock_records()
  -> 写 attendance_clock_records
```

但 `fetch_clock_records()` 有两个前置条件：

1. 钉钉服务启用。
2. 系统里有绑定了 `dingtalk_user_id` 的用户。

如果没有绑定用户，会直接返回空列表，不会去拉外部打卡记录。

生产现状：

```text
attendance_clock_records = 0
clock_records = 0
```

所以当前不能说“钉钉考勤已经接通并正常同步”。更准确说法是：

```text
钉钉考勤同步任务已经注册，
但生产当前没有实际考勤打卡同步入库结果。
```

### 50.5 数据归档任务当前是占位行为

代码位置：

```text
backend/app/tasks/data_archive.py
```

当前 `archive_old_data()` 只计算 cutoff，然后返回：

```text
status = skipped
```

它没有真实迁移、压缩、删除或归档数据。

这意味着：

```text
data_archive 现在更像一个预留任务，不是已经生效的数据生命周期治理。
```

### 50.6 AI 小时简报当前阻塞

日志只读核验发现，`ai_hourly_briefing` 在 2026-06-14 当天多次失败，错误核心是：

```text
TypeError: '<' not supported between instances of 'NoneType' and 'str'
```

触发位置：

```text
backend/app/services/ai_briefing_service.py:175
backend/app/services/factory_command_service.py:1555
```

调用链是：

```text
ai_hourly_briefing 定时任务
  -> ai_briefing_service.generate_briefing()
  -> factory_command_service.list_machine_lines()
  -> sorted(all_line_codes)
  -> all_line_codes 里混入 None
  -> 排序失败
```

代码里造成 `None` 的关键逻辑：

```text
_line_code_for_coil()
  如果卷材 machine_code 为空，就返回 None
```

随后：

```text
coil_groups[line_code].append(coil)
all_line_codes = set(line_map) | set(coil_groups)
sorted(all_line_codes)
```

当 `all_line_codes` 同时有字符串和 `None`，Python 无法排序，就报错。

### 50.7 根因数据：MES 卷材投影缺机列编码

生产只读核验：

| 项 | 数量 |
|---|---:|
| `mes_coil_snapshots` 总卷材数 | `1399` |
| `machine_code` 为空的卷材数 | `1399` |
| `current_workshop` 为空的卷材数 | `134` |
| `current_process` 为空的卷材数 | `134` |
| `machine_code` 为空但仍有当前工艺的卷材数 | `1265` |

也就是说：

```text
当前所有 MES 卷材投影都没有 machine_code。
但大部分卷材仍有 current_workshop 和 current_process。
```

样本显示这些无机列编码的卷材仍然有车间和工序，例如：

```text
拉矫车间 / 洗拉
园区在线车间 / 在线退火
新厂在线车间 / 北线退火
精整 / 剪切
2050车间 / 冷轧
```

所以问题不是“完全没有 MES 卷材数据”，而是：

```text
MES 卷材数据有车间和工艺，但缺少能直接映射机列的 machine_code。
```

### 50.8 为什么管理端页面未必同样报错

管理端接口：

```text
GET /api/v1/factory-command/machine-lines
```

调用时会传：

```text
current_user
```

`factory_command_service.list_machine_lines()` 在有 `current_user` 时，会先尝试走实时填报聚合：

```text
_live_aggregation_for_factory_command()
```

而 AI 小时简报后台任务没有用户上下文，所以它更容易走到 MES 卷材分组逻辑并暴露空 `machine_code` 的问题。

因此当前判断要精确：

```text
AI 小时简报后台任务确定失败。
不能仅凭这个日志直接推断 /manage/live 页面同样失败。
但这说明机列映射数据链路仍有真实缺口。
```

### 50.9 最短修复建议

这里先记录建议，不在本轮直接改代码。

第一优先级：让代码不因空机列崩溃。

```text
_line_code_for_coil() 返回 None 时，不要把 None 放进 sorted。
可以归入“未匹配机列”桶，例如 unmatched:<workshop>:<process>。
```

第二优先级：补 MES 到机列的映射。

```text
如果 MES 源里设备名常是 PC，就建立 PC -> 车间 -> 工艺 -> 机列 的映射表。
没有 machine_code 时，用 current_workshop + current_process + source_payload 推断。
```

第三优先级：给后台任务补统一运行表。

```text
新增 job_run_logs 或后台任务健康接口。
把 ai_hourly_briefing、daily_report、reminder_sweep、dingtalk-clock-sync 等任务的成功/失败/跳过都记录下来。
```

第四优先级：把 AI 简报状态展示到管理端。

```text
显示最近生成时间、最近失败时间、失败原因摘要。
不要让 AI 简报默默失败一天后才从 journal 发现。
```

### 50.10 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `94%` | `95%` |
| 系统理解总文档可交接度 | `99.6%` | `99.7%` |

为什么这轮能提升：

- 已经把非 MES 后台任务的注册位置、业务表和缺口补齐。
- 已经只读确认催报、实时事件、日报、考勤、AI briefing 的生产数据状态。
- 已经发现 AI 小时简报当前真实阻塞，并定位到代码和数据根因。

还不能到 100% 的原因：

- 本轮只记录问题，没有执行修复。
- 手机端真实提交字段闭环仍需专门 QA。
- 钉钉真实外发和钉钉考勤真实同步仍未授权触发。
- understand 全量图谱仍需你确认 `.understandignore` 后才能重建。

## 51. 追加理解：understand 图谱可信边界和 AI 简报影响面

本节补两个容易误判的问题：

```text
1. understand 图谱还能不能当当前架构图使用？
2. AI 小时简报失败，是不是代表管理端工厂机列页面也坏了？
```

结论先说：

```text
当前应以 CodeGraph 和只读线上证据为准。
understand 图谱已经明显过期，只能看历史结构，不能当当前状态。
AI 小时简报后台路径确定失败，但带用户上下文的管理端机列接口当前可返回数据。
```

### 51.1 CodeGraph 当前状态

当前 CodeGraph 结构索引状态：

| 项 | 数量 |
|---|---:|
| 索引文件 | `1032` |
| 总节点 | `15551` |
| 总边 | `31986` |
| 数据库大小 | 约 `29.78 MB` |
| Python 文件 | `593` |
| Vue 文件 | `176` |
| JavaScript 文件 | `254` |
| TypeScript 文件 | `9` |

通俗理解：

```text
当前做代码结构排查，CodeGraph 比旧 understand 图谱更可信。
```

### 51.2 understand 图谱当前是旧快照

本地 `.understand-anything/meta.json` 显示：

| 项 | 当前值 |
|---|---|
| `lastAnalyzedAt` | `2026-06-05T07:07:25.631714+00:00` |
| `gitCommitHash` | `f4e95c8c863a60e0a7718fca77a5d0c1db2a711a` |
| `version` | `1.0.0-deterministic-fallback` |
| `analyzedFiles` | `1267` |
| `officialUnderstandCoreAvailable` | `true` |

当前仓库 HEAD 是：

```text
dfd68681dc6617d4e744dd58d665e51bd747c4da
```

从旧图谱提交到当前 HEAD，变动文件数量是：

| 范围 | 文件数 |
|---|---:|
| 后端 | `153` |
| 前端 | `170` |
| 文档 | `61` |
| 脚本 | `3` |
| 其他 | `13` |
| 合计 | `400` |

这意味着：

```text
understand 图谱不是不能看，
而是只能用来理解 2026-06-05 左右的历史结构。
它不能证明现在的页面、接口、表、权限、定时任务还是一样。
```

### 51.3 旧 understand 图谱本身的内容

旧图谱仍有一些参考价值：

| 项 | 值 |
|---|---:|
| 节点 | `1449` |
| 边 | `216` |
| 层 | `10` |
| 导览步骤 | `5` |

图谱描述的项目名是：

```text
鑫泰铝业 数据中枢
```

框架识别包括：

```text
FastAPI
SQLAlchemy
Alembic
Vue 3
Vite
Element Plus
PostgreSQL
Nginx
```

但图谱生成器是：

```text
deterministic fallback graph
```

这说明它不是完整 LLM 语义图谱。现在最多作为历史目录和层级参考，不适合拿来做“当前系统已经全量理解完成”的证据。

### 51.4 为什么不能直接重建 understand

本地已有：

```text
.understand-anything/.understandignore
```

当前忽略规则会排除：

- `node_modules/`
- `.git/`
- `dist/`
- `build/`
- `coverage/`
- Python 缓存。
- 本地 `.env`、后端 `.env`。
- 本地数据库。
- 上传目录。
- 备份目录。
- 日志。
- 图片、PDF、压缩包等重资源。

这个规则总体是安全合理的，尤其是排除了 `.env` 和运行时上传文件。

但 understand 技能规则要求：

```text
如果 .understandignore 已存在，重建前要让用户确认。
```

所以当前不能静默全量重建。正确流程是：

1. 先把 `.understandignore` 给你确认。
2. 你确认后再跑全量 understand。
3. 重建后再把新图谱和 CodeGraph / 线上证据交叉校验。

### 51.5 AI 小时简报和管理端机列接口不是同一路径

上一节发现：

```text
AI 小时简报后台任务失败。
原因是无用户上下文时，factory_command_service.list_machine_lines() 会走 MES 卷材机列分组。
所有 mes_coil_snapshots.machine_code 为空，导致 line_code 里混入 None，排序失败。
```

本轮进一步只读验证：

| 调用方式 | 结果 |
|---|---|
| 带管理员用户上下文调用 `list_machine_lines()` | 成功，返回 `17` 条 |
| 不带用户上下文调用 `list_machine_lines()` | 失败，报 `NoneType` 和字符串无法排序 |

这说明：

```text
管理端用户打开工厂机列页面时，有 current_user，上游可走实时聚合兜底。
AI 小时简报是后台任务，没有 current_user，更容易走到 MES 卷材空 machine_code 的问题。
```

所以判断要精确：

```text
AI 简报后台链路是坏的。
管理端带用户上下文的机列接口当前不是同一个失败面。
但底层 MES -> 机列映射确实存在缺口。
```

### 51.6 这个差异对业务的影响

对用户页面：

```text
调度大屏和工厂机列页面可能仍能打开，
因为它们有用户身份，可以走实时填报聚合路径。
```

对后台 AI：

```text
每小时 AI 巡检简报会失败，
导致 AI 无法主动产出“优先机列、异常规则、在制状态”的小时摘要。
```

对后续规划：

```text
如果以后想让 AI 主动汇报到钉钉群，
这个问题必须先修。
否则外部通讯链路即使接好，也可能没有稳定内容源。
```

### 51.7 最短下一步

如果下一轮进入修复，建议顺序是：

1. 先给 `factory_command_service.list_machine_lines()` 加测试，复现“空 machine_code 不应崩溃”。
2. 最小修复：`_line_code_for_coil()` 返回空时归入“未匹配机列”分组，不进入 `None` 排序。
3. 再补业务修复：建立 MES PC / 设备 / 工艺 到机列的映射。
4. 最后验证：AI 小时简报能生成新 `ai_briefing_events`，同时管理端机列接口仍返回数据。

### 51.8 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `95%` | `96%` |
| 系统理解总文档可交接度 | `99.7%` | `99.8%` |

为什么这轮能提升：

- 已确认 understand 图谱不是当前状态，避免后续误用旧图谱。
- 已确认 CodeGraph 当前结构索引规模和可信边界。
- 已把 AI 简报失败和管理端页面接口区分开，避免误判“整个页面坏了”。
- 已明确下一步修复的最短路径。

还不能到 100% 的原因：

- AI 小时简报还没修复和验证。
- 真实手机端写入 QA 还没做。
- 钉钉真实外发和考勤真实同步还没授权触发。
- understand 全量重建还需要你确认 `.understandignore`。

## 52. 追加理解：手机端真实填报写库链路和生产记录形状

本轮目标：

```text
继续把“手机端填报到底写到哪里”合并进总理解文档。
只读核验，不做任何线上新提交。
```

本轮没有执行任何生产写入。验证方式是：

1. 用 CodeGraph 定位手机端前端、后端路由和服务层。
2. 阅读手机端提交代码、字段清洗代码、数据库模型。
3. 只读查询生产库已有记录数量、状态和字段覆盖情况。
4. 不打印账号密码、不打印连接串、不打印人员明细。

### 52.1 手机端现在有三条主要写库线

从用户角度看，手机端像一个入口；但从系统角度看，它实际分三条线写库：

| 用户类型 | 前端入口 | 后端接口 | 主要落表 | 说明 |
|---|---|---|---|---|
| 主操 / 逐卷录入 | `/entry/fill`，模式为 `coil_entry` | `/api/v1/mobile/coil-entry` | `work_order_entries`，`entry_type='mobile_coil'` | 每扫/录一卷，写一条逐卷记录；随行卡基础对象会放在 `work_orders` |
| 电工 / 班次填报 | `/entry/fill`，模式为 `shift_report` | `/api/v1/mobile/report/save` 和 `/api/v1/mobile/report/submit` | `mobile_shift_reports`，可附带 `machine_energy_records` | 先保存，再提交；日电耗/日气耗在班次表，机列明细在机台能耗表 |
| 内勤 / 专项每日一录 | `/entry/fill`，模式为 `owner_daily` | `/api/v1/mobile/owner-daily` | `work_order_entries`，`entry_type='owner_daily'` | 每人每天一条，具体字段放在 `extra_payload` |

这说明：

```text
不要只查一张表。
主操、电工、内勤的数据不是全部进入同一张表。
```

### 52.2 前端字段怎么进入后端

手机端主页面是：

```text
frontend/src/views/mobile/UnifiedEntryForm.vue
```

它会先读取：

```text
/api/v1/mobile/current-shift
/api/v1/mobile/entry-fields
```

然后根据后端返回的 `submit_target` 决定提交到哪里：

| submit_target | 前端构造函数 | 后端写入 |
|---|---|---|
| `coil_entry` | `buildCoilEntryPayload()` | `/mobile/coil-entry` |
| `owner_daily` | `buildOwnerDailyPayload()` | `/mobile/owner-daily` |
| 其他班次填报 | `buildMobileReportPayload()` | `/mobile/report/save` 和 `/mobile/report/submit` |

几个关键字段映射：

| 前端字段 | 后端字段 / 表字段 | 说明 |
|---|---|---|
| `tracking_card_no` | `work_orders.tracking_card_no` | 随行卡号 |
| `alloy_grade` | `work_orders.alloy_grade` | 合金牌号 |
| `input_weight` | `work_order_entries.input_weight` 或 `mobile_shift_reports.input_weight` | 上机量 / 投料量，取决于提交模式 |
| `output_weight` / `unit_output` | `work_order_entries.output_weight` 或 `mobile_shift_reports.output_weight` | 下机量 |
| `scrap_weight` | `work_order_entries.scrap_weight` 或 `mobile_shift_reports.scrap_weight` | 废料，逐卷场景可由输入、输出、卷芯、边料、托盘反推 |
| `energy_kwh` / `electricity_daily` | `mobile_shift_reports.electricity_daily` | 日电耗 |
| `gas_m3` / `gas_daily` | `mobile_shift_reports.gas_daily` | 日气耗 |
| `machine_energy_records[].energy_kwh` | `machine_energy_records.energy_kwh` | 机列电耗明细 |
| `machine_energy_records[].gas_m3` | `machine_energy_records.gas_m3` | 机列气耗明细 |
| 每日一录动态字段 | `work_order_entries.extra_payload` | 内勤、成品库、总电工、回收、大修等专项字段 |

通俗说：

```text
普通字段不是随便塞进一个大 JSON。
逐卷核心字段有固定列。
每日一录的专项字段才主要放 extra_payload。
```

### 52.3 生产库只读证据

生产库已有真实记录：

| 表 / 类型 | 数量 | 最近记录时间 | 说明 |
|---|---:|---|---|
| `mobile_shift_reports` | 193 | 2026-06-14 17:35 | 班次填报表，含电工能耗和部分班次汇总 |
| `work_order_entries.mobile_coil` | 2757 | 2026-06-14 21:14 | 主操逐卷填报记录 |
| `work_order_entries.owner_daily` | 107 | 2026-06-14 17:49 | 内勤 / 专项每日一录记录 |
| `machine_energy_records` | 27 | 2026-06-14 08:15 | 机列能耗明细，目前只看到气耗明细 |
| `shift_production_data.data_source='mobile'` | 91 | 2026-05-30 17:44 | 旧手机填报聚合记录，目前不应再当作逐卷主链路 |

`mobile_shift_reports` 状态分布：

| 状态 | 数量 |
|---|---:|
| `submitted` | 135 |
| `returned` | 49 |
| `draft` | 9 |

最近 7 个业务日班次填报数量：

| 业务日 | 数量 |
|---|---:|
| 2026-06-14 | 6 |
| 2026-06-13 | 6 |
| 2026-06-12 | 9 |
| 2026-06-11 | 9 |
| 2026-06-10 | 10 |
| 2026-06-09 | 9 |
| 2026-06-08 | 10 |

最近 7 个业务日逐卷和每日一录数量：

| 业务日 | 逐卷 `mobile_coil` | 每日一录 `owner_daily` |
|---|---:|---:|
| 2026-06-14 | 105 | 1 |
| 2026-06-13 | 179 | 7 |
| 2026-06-12 | 229 | 6 |
| 2026-06-11 | 267 | 7 |
| 2026-06-10 | 261 | 6 |
| 2026-06-09 | 83 | 6 |
| 2026-06-08 | 69 | 8 |

这能证明：

```text
手机端不是“填了但完全没进库”。
三类核心人工记录都已经真实进入生产库。
```

但这不能证明：

```text
每个角色、每个字段、每个当前页面按钮都 100% 正确。
要证明这个，仍需用真实角色做一轮受控提交 QA。
```

### 52.4 主操逐卷记录字段覆盖情况

`work_order_entries.mobile_coil` 当前字段覆盖：

| 字段 | 有值数量 | 总数 | 说明 |
|---|---:|---:|---|
| `input_weight` | 2757 | 2757 | 上机量 / 投料量都有值 |
| `output_weight` | 2540 | 2757 | 下机量大部分有值 |
| `scrap_weight` | 2679 | 2757 | 废料大部分有值；代码允许自动计算 |
| `input_spec` | 2474 | 2757 | 上机规格大部分有值 |
| `output_spec` | 705 | 2757 | 下机规格覆盖较低 |
| `machine_id` | 2601 | 2757 | 大部分能匹配到机列 |

这里的业务含义：

```text
逐卷填报链路是活的。
但仍有 156 条逐卷记录没有 machine_id。
这类记录会影响“每台机列产量”和“责任人追溯”的准确性。
```

下一步要重点查：

```text
没有 machine_id 的记录，是因为用户账号没绑机台？
还是 MES / PC / 工艺到机列的映射没补齐？
还是历史旧数据？
```

### 52.5 能耗明细的真实缺口

能耗要分两层看：

| 层级 | 表 | 当前情况 |
|---|---|---|
| 日电耗 / 日气耗 | `mobile_shift_reports.electricity_daily`、`mobile_shift_reports.gas_daily` | 有真实数据 |
| 机列电耗 / 机列气耗明细 | `machine_energy_records.energy_kwh`、`machine_energy_records.gas_m3` | 只有气耗明细，电耗明细为 0 |

生产库只读结果：

| 指标 | 数量 |
|---|---:|
| 有日电耗或日气耗的班次记录 | 135 |
| `mobile_shift_reports.electricity_daily` 有值 | 121 |
| `mobile_shift_reports.gas_daily` 有值 | 125 |
| `machine_energy_records` 总行数 | 27 |
| `machine_energy_records.energy_kwh` 有值 | 0 |
| `machine_energy_records.gas_m3` 有值 | 27 |
| 关联到的班次记录数 | 13 |

这说明：

```text
总日电耗不是 0。
但是“机列级电耗明细”确实没有进 machine_energy_records.energy_kwh。
```

从代码看，前端和后端都支持机列电耗字段：

```text
前端：form.machine_energy_records[].energy_kwh
后端：_save_machine_energy_records(... energy_kwh=rec.get('energy_kwh'))
```

所以当前更像是：

```text
用户实际填了日总电耗，但没有填机列级电耗；
或者机列明细 UI / 机列列表没有按预期让用户填电耗；
或者现有真实场景只录了气耗机列明细。
```

这里不能直接下结论“字段写错表”。更严谨的结论是：

```text
代码映射支持电耗明细入表。
生产已有记录证明气耗明细能入表。
生产已有记录也证明电耗明细目前没有真实值。
需要用真实电工账号做一次受控提交，才能判断是用户流程问题、页面展示问题，还是字段传输问题。
```

### 52.6 历史记录页覆盖边界

`/entry/history` 对普通班次记录和主操逐卷记录的覆盖逻辑如下：

```text
先查 mobile_shift_reports。
如果是主操并且 all_day=true，再合并 work_order_entries.entry_type='mobile_coil'。
```

但当前历史合并逻辑没有把：

```text
work_order_entries.entry_type='owner_daily'
```

统一并入 `/entry/history`。

这意味着：

```text
内勤 / 专项每日一录在填报页可以查当前业务日已有记录，
但统一历史页还不能说已经完整覆盖每日一录。
```

这和之前发现的“内勤历史暂查不到”是一致的。

如果以后要裁掉内勤统计岗，但仍保留补录和追溯能力，这里必须补齐：

```text
/entry/history 应按业务日显示 owner_daily。
管理端 fill-details 也应明确显示 owner_daily 来源。
```

### 52.7 逐卷记录不会自动变成旧的 mobile 聚合产量

代码中 `_aggregate_coil_to_shift()` 已被明确停用：

```text
Disabled 2026-05-27: mobile_coil_agg duplicate filing path retired.
Mobile filing now flows only through data_source='mobile' via lifecycle.py.
```

生产库里还有：

```text
shift_production_data.data_source='mobile'：91 条，最近更新时间 2026-05-30。
```

这说明：

```text
旧的手机聚合产量路径还留有历史数据。
现在逐卷填报不应再靠这个旧聚合表当主口径。
```

结合当前系统方向，正确理解应该是：

```text
MES / mes_* 投影作为生产主数据。
手机逐卷和每日一录作为补录、对照、异常和追溯。
不要把手机逐卷补录再偷偷聚合成另一套生产主口径。
```

### 52.8 本轮发现的待修复点

| 优先级 | 问题 | 为什么重要 | 建议下一步 |
|---|---|---|---|
| 高 | `machine_energy_records.energy_kwh` 当前生产记录为 0 | 会影响机列级电耗明细、机列吨耗、能耗责任追溯 | 用真实电工账号做受控提交；如果页面没有稳定出现机列电耗输入，修前端；如果传了但没入库，修后端 |
| 高 | `/entry/history` 尚未统一合并 `owner_daily` | 内勤 / 专项每日一录追溯不完整 | 给历史接口和历史页补 owner_daily 项 |
| 中 | 156 条逐卷记录没有 `machine_id` | 会影响按机列汇总和责任机列追溯 | 查账号绑机台、二维码机台、MES PC/工艺到机列映射 |
| 中 | 旧 `shift_production_data.data_source='mobile'` 仍有历史记录 | 容易被误当作当前主口径 | 页面和报表必须优先标明数据来源，必要时仅做历史兼容 |
| 中 | 每日一录字段都在 `extra_payload` | 字段灵活但不利于强校验和搜索 | 对核心字段建立口径字典和查询索引，不急着迁表 |

### 52.9 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `96%` | `97%` |
| 系统理解总文档可交接度 | `99.8%` | `99.85%` |

为什么这轮能提升：

- 已把手机端三条写库线讲清楚。
- 已用生产库只读证据证明三类人工记录真实存在。
- 已定位“机列电耗明细为 0”的真实层级，不再把它和总日电耗混成一个问题。
- 已确认 `/entry/history` 的每日一录覆盖边界。
- 已确认逐卷记录和旧 `shift_production_data.mobile` 聚合路径不能混用。

还不能到 100% 的原因：

- 还没有用真实主操、电工、内勤账号做受控提交 QA。
- 机列电耗明细缺口还没有修复。
- 每日一录历史统一还没有实现。
- 逐卷未匹配机列还要继续追根因。
- understand 全量图谱仍需确认 `.understandignore` 后再刷新。

## 53. 追加理解：每日一录历史缺口复现和逐卷机列匹配现状

本轮继续沿着两个剩余缺口做只读核验：

```text
1. 内勤 / 专项每日一录为什么历史页看不到。
2. 逐卷记录里没有 machine_id 的 156 条到底像不像当前链路问题。
```

本轮仍然没有执行任何生产写入。

### 53.1 每日一录历史缺口已经用生产样本复现

代码层面：

```text
backend/app/services/mobile_report/lifecycle.py
list_report_history()
```

当前历史接口主要做两件事：

1. 查询 `mobile_shift_reports`。
2. 当 `all_day=true` 且当前用户是 `machine_operator` 时，额外合并 `work_order_entries.entry_type='mobile_coil'`。

它没有第三步：

```text
当当前用户是内勤 / 专项每日一录角色时，
合并 work_order_entries.entry_type='owner_daily'。
```

生产只读复现结果：

| 项 | 结果 |
|---|---|
| 样本角色 | `planning_owner` |
| 样本车间 | `CPK` |
| 样本业务日 | `2026-06-14` |
| 该用户当天 `owner_daily` 记录 | `1` 条 |
| 同用户调用历史服务返回 | `0` 条 |
| 历史返回来源类型 | 空 |

这能证明：

```text
每日一录不是没写进库。
是 /entry/history 背后的历史服务没有把 owner_daily 合并进去。
```

业务影响：

```text
内勤、成品库、计划、质检、回收、大修等每日一录人员，
可能在填报页能看到当天记录，
但去统一历史页时看不到整日记录。
```

这会带来两个后果：

1. 现场人员误以为“刚才填的数据丢了”。
2. 管理端或后续追溯如果只看移动历史接口，会漏掉每日一录。

### 53.2 每日一录生产记录涉及的角色和车间

生产库 `owner_daily` 当前不是孤立一两条，而是多个角色都在用：

| 角色 | 车间代码 | 记录数 | 最近业务日 |
|---|---|---:|---|
| `consumable_stat` | `LZ1650` | 15 | 2026-06-13 |
| `quality_owner` | `CPK` | 15 | 2026-06-13 |
| `storage_owner` | `CPK` | 15 | 2026-06-13 |
| `recovery_owner` | `HS` | 14 | 2026-06-13 |
| `planning_owner` | `CPK` | 13 | 2026-06-14 |
| `consumable_stat` | `LJ` | 12 | 2026-06-13 |
| `consumable_stat` | `ZXTF-N` | 10 | 2026-06-13 |
| `consumable_stat` | `ZR2` | 6 | 2026-06-04 |
| `consumable_stat` | `ZR3` | 4 | 2026-06-03 |
| `consumable_stat` | `ZXTF` | 2 | 2026-06-01 |
| `consumable_stat` | `JZ` | 1 | 2026-06-08 |

注意：

```text
这里的 CPK 是成品库 / 全厂专项类口径，不是生产车间数量口径。
不要把它和 13 个活跃生产车间混成一个数。
```

### 53.3 每日一录历史页最短修复路线

建议修复方式：

1. 给 `list_report_history()` 增加 `owner_daily` 分支。
2. 条件是：当前用户角色属于 `OWNER_DAILY_ROLES`，并且传入 `business_date`。
3. 查询：

```text
work_order_entries.business_date == business_date
work_order_entries.entry_type == 'owner_daily'
work_order_entries.created_by_user_id == current_user.id
```

4. 返回字段复用现有历史结构，增加：

```text
source_type='owner_daily'
role_bucket=当前用户角色
report_status=entry.entry_status
last_saved_at=entry.updated_at 或 entry.submitted_at
```

5. 前端 `ShiftReportHistory.vue` 已经把 `planning_owner`、`storage_owner`、`recovery_owner`、`overhaul_owner` 等列入高级历史角色，理论上可以少改页面。

6. 必补测试：

```text
造一条 owner_daily。
用同一个用户调用 list_report_history(all_day=true, business_date=当天)。
断言返回 1 条，并且 source_type='owner_daily'。
```

### 53.4 逐卷未匹配机列更像历史残留，不像当前链路阻塞

上一轮看到：

```text
work_order_entries.entry_type='mobile_coil'
总数 2757 条。
其中 2601 条有 machine_id。
156 条没有 machine_id。
```

本轮继续拆开看：

| 车间代码 | 无机列记录数 | 最早业务日 | 最晚业务日 | 创建用户数量 |
|---|---:|---|---|---:|
| `LZ2050` | 101 | 2026-05-01 | 2026-05-06 | 0 |
| `ZR3` | 32 | 2026-05-01 | 2026-05-06 | 0 |
| `JZ` | 20 | 2026-05-03 | 2026-05-06 | 0 |
| `RZ` | 3 | 2026-05-04 | 2026-05-04 | 0 |

进一步确认：

| 指标 | 结果 |
|---|---:|
| 无机列记录总数 | 156 |
| 其中没有 `created_by_user_id` 且没有 `created_by` | 156 |
| 其中有 `work_order_id` | 156 |
| 涉及随行卡 / 工单对象数 | 139 |
| 最近 30 天无机列逐卷记录 | 0 |
| 最近 30 天逐卷记录总数 | 2428 |
| 最近 30 天有 `machine_id` 的逐卷记录 | 2428 |
| 最近 30 天机列匹配缺失 | 0 |

这说明：

```text
当前扫码填报链路的机列匹配看起来是通的。
那 156 条无 machine_id 更像 5 月初旧数据、导入数据或早期过渡数据。
```

不能再笼统说：

```text
现在逐卷填报经常匹配不到机列。
```

更准确的说法是：

```text
历史库里存在一批 5 月初无机列逐卷记录；
最近 30 天逐卷记录全部带 machine_id。
当前若现场还反馈未匹配，应拿当天样本单独查，而不是用这批历史数据推断当前链路坏。
```

### 53.5 当前机台账号绑定和 MES 终端绑定状态

生产只读结果：

| 项 | 数量 |
|---|---:|
| 启用中设备 | 106 |
| 已绑定用户的设备 | 101 |
| 未绑定用户的设备 | 5 |
| `mes_terminal_bindings` 总数 | 0 |
| 启用中的 `mes_terminal_bindings` | 0 |

这里要分清两种绑定：

| 绑定类型 | 当前作用 | 当前状态 |
|---|---|---|
| 设备绑定用户 | 扫机台二维码后知道是哪个机列账号 | 大部分已绑定，当前逐卷填报最近 30 天机列匹配正常 |
| MES 终端绑定 | 外部 MES 里 `PC`、终端、工艺和本系统机列的映射 | 目前为空 |

所以：

```text
手机扫码填报的机列绑定，当前主要靠 equipment.bound_user_id。
外部 MES 的 PC/终端到机列映射，仍缺 mes_terminal_bindings。
```

这解释了之前两个看似矛盾的现象：

```text
手机端逐卷填报最近能匹配机列。
但 MES 数据里很多设备名是 PC，仍不能稳定自动映射到具体机列。
```

### 53.6 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `97%` | `97.3%` |
| 系统理解总文档可交接度 | `99.85%` | `99.9%` |

为什么这轮能提升：

- 已用生产样本复现 `owner_daily` 历史接口漏读。
- 已确认 `owner_daily` 涉及多个真实角色，不是边缘功能。
- 已把逐卷无机列问题从“当前链路疑似问题”缩小为“5 月初历史残留为主”。
- 已区分“手机二维码机台账号绑定”和“MES 终端 PC 到机列绑定”这两类不同问题。

还不能到 100% 的原因：

- `owner_daily` 历史接口还没有修。
- `machine_energy_records.energy_kwh` 机列电耗明细还没有修复。
- AI 小时简报空机列编码问题还没有修。
- 真实提交类 QA 还没有做。
- understand 全量图谱仍需确认 `.understandignore` 后再刷新。

## 54. 追加理解：机列级电耗明细为 0 的真实断点

本轮继续追一个长期容易误判的问题：

```text
为什么 machine_energy_records.energy_kwh 一直是 0？
这是不是说明电工能耗完全没保存？
```

结论先说：

```text
不是电工能耗完全没保存。
班次总电耗在 mobile_shift_reports.electricity_daily 里有真实数据。
真正缺的是“按机列拆分的电耗明细”没有进入 machine_energy_records.energy_kwh。
```

本轮依旧只读，不做任何生产提交。

### 54.1 代码链路本身支持机列电耗

前端：

```text
frontend/src/views/mobile/UnifiedEntryForm.vue
```

当满足下面条件时，会显示“机列能耗明细”：

```text
auth.role === 'energy_stat'
mode === 'per_shift'
form.machine_energy_records 有数据
```

每一行机列明细都有两个输入：

| 前端字段 | 含义 |
|---|---|
| `rec.energy_kwh` | 机列电耗 |
| `rec.gas_m3` | 机列气耗 |

提交时前端会把它们放到：

```text
machine_energy_records: [
  { machine_id, machine_code, machine_name, energy_kwh, gas_m3 }
]
```

后端：

```text
backend/app/services/mobile_report/lifecycle.py
_save_machine_energy_records()
```

后端会把它写到：

```text
machine_energy_records.energy_kwh
machine_energy_records.gas_m3
```

所以从代码能力看：

```text
系统不是没有设计机列电耗字段。
也不是后端完全不会保存 energy_kwh。
```

### 54.2 线上电工账号实际拿到的字段

本轮用生产库和后端只读函数检查了启用中的 `energy_stat` 用户。

总体结果：

| 项 | 结果 |
|---|---:|
| 启用中的电工账号覆盖车间 | 15 个车间/部门代码 |
| 大多数生产车间电工表单模式 | `per_shift` |
| 提交目标 | `shift_report` |
| 普通能耗字段 | `energy_kwh`、`gas_m3`、`energy_note` |
| 机列明细来源 | 当前车间的 `workshop_machines` |

典型生产车间的电工账号能拿到机列列表，例如：

| 车间代码 | 当前拿到的机列数 |
|---|---:|
| `ZR3` | 9 |
| `RZ` | 9 |
| `JZ` | 17 |
| `JQ` | 5 |
| `LZ1850` | 5 |
| `LJ` | 4 |
| `ZXTF-N` | 2 |
| `ZXTF-P` | 2 |

这说明：

```text
多数生产车间不是因为没有机列列表而无法填机列能耗。
```

但也发现两个特殊边界：

| 车间/部门代码 | 情况 |
|---|---|
| `CPK` 成品库 | 电工账号启用，但当前模板没有能耗字段，机列列表为空 |
| `HS` 回收 | 电工账号启用，但当前模板没有能耗字段，机列列表为空 |

原因来自模板：

```text
inventory 成品库模板 extra_fields 只有合同进度字段。
recycling 回收模板 extra_fields 为空。
```

所以：

```text
CPK/HS 的 energy_stat 账号目前不适合作为标准电工填报账号。
如果业务确实需要它们填能耗，要补模板。
如果业务不需要，应把这些账号从电工填报口径中排除，避免缺报误判。
```

### 54.3 生产库最近能耗数据分布

近 14 天班次总能耗有真实数据：

| 车间代码 | 有能耗总值的班次记录 | 有总电耗 | 有总气耗 | 最近业务日 |
|---|---:|---:|---:|---|
| `ZR3` | 40 | 33 | 40 | 2026-06-14 |
| `ZD` | 38 | 38 | 38 | 2026-06-14 |
| `ZR2` | 38 | 31 | 38 | 2026-06-14 |
| `JQ` | 6 | 6 | 6 | 2026-06-12 |
| `LJ` | 6 | 6 | 0 | 2026-06-08 |
| `ZXTF-N` | 2 | 2 | 0 | 2026-06-06 |
| `LZ1650` | 1 | 1 | 0 | 2026-05-31 |
| `LZ1850` | 1 | 1 | 0 | 2026-05-31 |

这证明：

```text
电工总电耗不是 0。
能耗数据确实通过 mobile_shift_reports 保存过。
```

### 54.4 机列明细只在铸二、铸三形成，而且只有气耗

近 14 天 `machine_energy_records` 分布：

| 车间代码 | 机列明细行数 | 有机列电耗 | 有机列气耗 | 最近业务日 |
|---|---:|---:|---:|---|
| `ZR3` | 15 | 0 | 15 | 2026-06-14 |
| `ZR2` | 12 | 0 | 12 | 2026-06-14 |

再看每张带机列明细的班次报告：

| 业务日 | 车间 | 班次总电耗 | 班次总气耗 | 机列行数 | 机列电耗合计 | 机列气耗合计 |
|---|---|---:|---:|---:|---:|---:|
| 2026-06-14 | `ZR2` | 空 | 1340 | 2 | 0 | 1340 |
| 2026-06-14 | `ZR3` | 空 | 3083 | 3 | 0 | 3083 |
| 2026-06-13 | `ZR2` | 空 | 1697 | 2 | 0 | 1697 |
| 2026-06-13 | `ZR3` | 空 | 1844 | 2 | 0 | 1844 |
| 2026-06-12 | `ZR2` | 空 | 1992 | 2 | 0 | 1992 |
| 2026-06-12 | `ZR3` | 空 | 1328 | 2 | 0 | 1328 |

这说明：

```text
铸二、铸三的机列明细链路能保存。
但现场实际只按机列填了气耗，没有按机列填电耗。
```

而其他车间：

```text
有的填了班次总电耗，但没有形成 machine_energy_records 明细行。
```

### 54.5 目前最准确的问题定义

不要再说：

```text
能耗保存失败。
```

更准确应该说：

```text
能耗总值保存链路是通的。
机列级气耗明细保存链路也是通的。
机列级电耗明细没有真实数据。
```

目前最可能的原因排序：

| 可能原因 | 证据 | 下一步 |
|---|---|---|
| 现场实际只按机列填气耗，没有填机列电耗 | `machine_energy_records.gas_m3` 有值，`energy_kwh` 全空 | 用电工账号做一次受控提交，看页面是否明显提示要填机列电耗 |
| 电耗主要按车间总表填，不按机列拆 | 多车间 `mobile_shift_reports.electricity_daily` 有值，但没有机列行 | 业务上确认是否要求电耗必须按机列拆 |
| 部分车间电工账号配置不该参与填报 | `CPK`、`HS` 电工账号无字段、无机列 | 决定补模板还是停用/排除这些账号 |
| 未来物联网能耗库尚未接入 | `iot_energy_sync` 是 `unconfigured`，`iot_energy_sync_runs=0` | 等能耗数采库信息后接入，不要用当前人工明细假装物联网已通 |

### 54.6 如果要修，最短修复路线

建议按低风险顺序做：

1. 先不动生产数据，用测试写一个电工提交用例：

```text
提交 machine_energy_records=[{energy_kwh: 123, gas_m3: 45}]
断言 machine_energy_records.energy_kwh=123
断言 mobile_shift_reports.electricity_daily=123
```

2. 用真实电工账号做一次受控浏览器 QA：

```text
打开 /entry/fill
确认机列能耗明细是否展开
确认每个机列是否都有“电耗”和“气耗”
不提交，先截图确认
```

3. 如果业务要求“电耗必须按机列拆”，前端要加强提示：

```text
机列电耗为空时，用醒目的中文提示。
如果只填总电耗，也要标明“未拆分到机列”。
```

4. 管理端能耗页面要分两列显示：

```text
班次总电耗：来自 mobile_shift_reports。
机列电耗明细：来自 machine_energy_records。
```

这样用户不会再把“机列明细为 0”误解为“能耗总览为 0”。

5. `CPK` 和 `HS` 的电工账号要做口径决策：

```text
如果需要填，就补模板。
如果不需要填，就从电工缺报口径中排除或停用。
```

### 54.7 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `97.3%` | `97.6%` |
| 系统理解总文档可交接度 | `99.9%` | `99.93%` |

为什么这轮能提升：

- 已把“能耗总值”和“机列明细”分开确认。
- 已确认代码支持机列电耗保存，问题不在“系统没有字段”。
- 已确认生产现状是“机列气耗有明细、机列电耗无明细”。
- 已发现 `CPK`、`HS` 电工账号启用但模板不给字段，可能导致缺报/不可填误判。
- 已给出低风险修复路线，不需要先动生产数据。

还不能到 100% 的原因：

- 还没有做真实电工账号受控提交 QA。
- 还没有修复机列电耗明细提示或必填策略。
- 还没有决定 `CPK`、`HS` 电工账号到底保留还是排除。
- 物联网能耗库还没接入。

## 55. 追加理解：AI 主动汇报与钉钉外发闸门

本节只做生产只读核验，没有触发任何钉钉发送，也没有调用会写入业务数据的 POST 接口。

### 55.1 先把三件事分清

这里最容易混淆的是“系统里有 AI 简报”和“真的发到了钉钉群”。

当前代码里至少有三层：

| 层级 | 作用 | 是否等于真实发钉钉 |
|---|---|---|
| AI 小时简报 | 后台定时生成 `ai_briefing_events`，给管理端 AI 区域看 | 不是 |
| agent 外部通讯治理 | `agent_events -> agent_outbox_messages -> communication_channels -> external_message_logs` | 只有通道启用且非 dry-run 才可能真实发 |
| 旧日报推送 Agent | `ReporterAgent` 可以按配置给绑定用户发工作通知 | 这是另一条旧推送链路，不等于新治理台群发链路 |

简单说：

```text
AI 简报存在
  不等于
钉钉群已经收到主动汇报
```

### 55.2 代码层面确认

代码链路如下：

| 模块 | 关键文件 | 当前理解 |
|---|---|---|
| AI 小时简报 | `backend/app/main.py`、`backend/app/services/ai_briefing_service.py` | 定时任务会调用 `generate_briefing(... briefing_type='hourly_inspection')` |
| 简报依赖的数据 | `backend/app/services/factory_command_service.py` | 简报会先取工厂总览和机列列表 |
| 外发治理服务 | `backend/app/services/agent_communication_service.py` | 如果通道是 dry-run，只写发件箱和外发日志，不真正发送 |
| 外发通道表 | `backend/app/models/agent_communication.py` | `communication_channels.dry_run` 默认为 true |
| 钉钉服务 | `backend/app/services/dingtalk_service.py` | 真实群发入口是 `send_group_message`，工作通知入口是 `send_work_notification` |

### 55.3 生产环境开关现状

生产只读读取到的安全开关：

| 配置项 | 生产值 | 解释 |
|---|---|---|
| `MES_ADAPTER` | `sqlserver` | 外部 MES 当前走 SQL Server 只读同步 |
| `DINGTALK_ENABLED` | `true` | 钉钉基础能力打开 |
| `DINGTALK_NOTIFY_DRY_RUN` | `false` | 旧通知链路不是 dry-run |
| `AUTO_PUSH_ENABLED` | `true` | 旧自动推送开关打开 |
| `LLM_ENABLED` | `true` | LLM 能力打开 |
| `APP_CONNECTION_ENABLED` | `false` | 应用连接外部推送未启用 |
| `APP_CONNECTION_PUSH_MODE` | `disabled` | 外部应用推送模式关闭 |
| `IOT_ENERGY_ADAPTER` | `null` | 物联网能耗库尚未接入 |

这个结果要小心解读：

```text
钉钉基础开关打开
  不代表
agent 治理台已经配置了群通道并开始真实发送
```

### 55.4 生产表状态

生产只读表数量：

| 表 | 当前数量 | 说明 |
|---|---:|---|
| `agent_profiles` | 0 | 还没有配置主动汇报 agent |
| `communication_channels` | 0 | 还没有配置外发通道 |
| `agent_channel_bindings` | 0 | 没有 agent 和通道绑定 |
| `agent_events` | 0 | 新治理链路没有事件 |
| `agent_outbox_messages` | 0 | 新治理链路没有待发/已发消息 |
| `external_message_logs` | 0 | 新治理链路没有外发日志 |
| `multimodal_evidence` | 0 | 多模态证据留档还没有数据 |
| `agent_operation_approvals` | 0 | 审核流还没有数据 |
| `agent_rate_limits` | 0 | 限流表还没有数据 |
| `ai_briefing_events` | 1271 | AI 小时简报曾经持续生成 |
| `ai_conversations` | 6 | 管理端 AI 对话有少量记录 |
| `ai_messages` | 26 | AI 对话消息有少量记录 |
| `ai_watchlist_items` | 0 | 关注对象还没有配置 |

最重要结论：

```text
新 agent 外部通讯治理链路在线上有表结构，但还没有真实配置和真实发送记录。
```

### 55.5 AI 小时简报当前阻塞

生产 `ai_briefing_events` 的情况：

| 类型 | 严重级别 | 数量 | 最新记录 |
|---|---|---:|---|
| `hourly_inspection` | `warning` | 1270 | 2026-06-13 14:19:26 |
| `hourly_inspection` | `critical` | 1 | 2026-06-06 19:35:27 |

生产服务器当前时间为：

```text
2026-06-14 21:49:20 +0800
```

也就是说，AI 小时简报记录没有持续更新到 2026-06-14 晚上。

服务日志显示定时任务仍在运行，但每小时失败，错误是：

```text
TypeError: '<' not supported between instances of 'NoneType' and 'str'
```

触发位置：

```text
backend/app/services/factory_command_service.py
list_machine_lines()
for line_code in sorted(all_line_codes)
```

通俗解释：

```text
系统想把“所有机列编号”排序。
但里面混进了一个空值。
Python 不能把“空值”和“文字编号”放在一起排序。
所以整个 AI 小时简报失败。
```

### 55.6 为什么会混进空机列

生产只读核验 `mes_coil_snapshots`：

| 项 | 数量 |
|---|---:|
| 卷材快照总数 | 1399 |
| `machine_code` 为空 | 1399 |
| `current_workshop` 为空 | 134 |

按车间看，缺 `machine_code` 的卷材主要集中在：

| 车间 | 数量 |
|---|---:|
| 2050车间 | 402 |
| 新厂在线车间 | 248 |
| 园区在线车间 | 225 |
| 拉矫车间 | 145 |
| 空车间 | 134 |
| 精整 | 109 |
| 园区淬火车间 | 47 |
| 园区精整 | 46 |
| 1850车间 | 36 |
| 热轧 | 7 |

这说明：

```text
外部 MES 当前能告诉我们“卷在哪个车间/工艺”，
但 `mes_coil_snapshots` 这张投影表里不能直接告诉“是哪台机列”。
```

这和前面业务判断一致：

```text
如果 MES 里设备名经常只是 PC，
就必须补一层 “PC / 终端 / 工艺 -> 真实机列” 的映射。
否则不能完全靠 MES 自动识别机列。
```

### 55.7 对业务的影响

影响分成两类。

第一类是 AI 汇报：

```text
后台小时巡检当前会失败。
管理端能看到旧简报，但不会稳定产生新的小时简报。
```

第二类是生产流转/卷级线索：

```text
如果页面需要展示“每台机列有多少卷”，
当前不能只靠 mes_coil_snapshots.machine_code。
必须用额外映射或从其他 MES 工序记录中推导。
```

这不是“MES 数据没用”，而是：

```text
MES 主数据适合做车间、工艺、卷材、包装产量、在制料主口径。
机列级归属还需要终端/PC/工艺映射补强。
```

### 55.8 最短修复路线

建议按低风险顺序做：

1. 先修 AI 小时简报兜底：

```text
list_machine_lines 里不要把空 line_code 放进排序集合。
如果卷材没有机列，就归到“未匹配机列”。
```

2. 增加测试锁住：

```text
给 list_machine_lines 加一个测试：
当 MES 卷材 machine_code 为空时，接口不报错，并返回“未匹配机列”分组。
```

3. 增加 PC/终端映射表或配置：

```text
PC 名称 / 终端编号 / 工艺名称 / 车间
  -> 真实机列
```

4. 调度大屏显示要诚实：

```text
能匹配机列的卷：显示到具体机列。
不能匹配机列的卷：显示在“未匹配机列”。
不要假装已经精确到机列。
```

5. agent 外发链路先 dry-run：

```text
先建 agent、通道、绑定，但通道 dry_run=true。
确认 outbox 和 external_message_logs 都正常后，
再让指定人员确认是否打开真实钉钉群发送。
```

### 55.9 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `97.6%` | `97.8%` |
| 系统理解总文档可交接度 | `99.93%` | `99.95%` |

为什么这轮能提升：

- 已把“AI 简报”和“钉钉真实外发”拆开确认。
- 已确认生产新 agent 治理链路表存在，但没有真实 agent、通道、发件箱和外发日志。
- 已确认钉钉基础开关打开，但不能据此判断已经群发。
- 已确认 AI 小时简报当前仍由空机列编码阻塞。
- 已确认外部 MES 卷材快照当前没有机列编码，机列级看板必须补映射或兜底。

还不能到 100% 的原因：

- 还没有修复 `list_machine_lines` 空机列兜底。
- 还没有做 agent 外发 dry-run 全链路测试。
- 还没有经指定人员确认真实钉钉群发送。
- 还没有补 PC/终端到真实机列的映射。

## 56. 追加理解：AI 小时简报空机列阻塞的本地修复

本节记录本地代码修复结果。注意：

```text
本地已修复并通过测试
  不等于
生产环境已经恢复
```

生产恢复仍需要后续提交、部署、观察下一次小时简报是否正常落库。

### 56.1 修复前的真实问题

生产日志确认：

```text
AI briefing generation failed
TypeError: '<' not supported between instances of 'NoneType' and 'str'
```

触发点：

```text
backend/app/services/factory_command_service.py
list_machine_lines()
for line_code in sorted(all_line_codes)
```

通俗解释：

```text
有些外部 MES 卷材没有机列编码。
系统把“空机列”和“正常机列编码”放在一起排序。
排序失败后，AI 小时简报整条链路失败。
```

### 56.2 为什么不能粗暴把所有空机列都改掉

本地测试发现一个重要边界：

```text
卷材明细 list_coils 原本用 line_code=None 表示“还没匹配机列”。
```

如果直接把 `_line_code_for_coil()` 全局改成“未匹配机列”，会破坏卷材明细页面和旧前端判断。

所以最终采用更小的修复：

| 位置 | 处理方式 |
|---|---|
| 机列汇总 `list_machine_lines()` | 空机列归入 `未匹配机列:标准车间名` |
| 卷材明细 `list_coils()` | 继续保留 `line_code=None` |

这样既避免 AI 简报报错，又不改变卷材明细旧语义。

### 56.3 本地代码改动

改动文件：

```text
backend/app/services/factory_command_service.py
backend/tests/test_factory_command_service.py
```

新增行为：

```text
当 MES 卷材没有 machine_code，
并且要进入机列汇总时，
系统把它归到 “未匹配机列:冷轧2050” 这类分组。
```

示例：

| MES 原始车间 | 标准化后 | 机列汇总显示 |
|---|---|---|
| `2050车间` | `冷轧2050` | `未匹配机列:冷轧2050` |

### 56.4 测试结果

先写了一个失败测试，复现生产问题：

```text
空机列卷材 + 正常机列卷材同时存在时，
list_machine_lines 不应该因为排序报错。
```

红灯结果：

```text
TypeError: '<' not supported between instances of 'str' and 'NoneType'
```

修复后运行：

```text
python -m pytest backend/tests/test_factory_command_service.py::test_machine_lines_group_missing_mes_machine_code_as_unmatched -q
```

结果：

```text
1 passed
```

继续运行相关回归：

```text
python -m pytest backend/tests/test_factory_command_service.py backend/tests/test_ai_briefing_service.py -q
```

结果：

```text
39 passed
```

### 56.5 当前还没完成的生产验证

这次本地修复还没有提交、部署到云端，所以生产上仍可能继续出现小时简报失败。

上线后需要验证：

1. 部署后观察服务日志：

```text
不再出现 AI briefing generation failed 的空机列排序错误。
```

2. 观察 `ai_briefing_events`：

```text
最新 hourly_inspection 记录应恢复到部署后的小时。
```

3. 打开管理端 AI 简报区域：

```text
能看到新的小时巡检记录。
```

4. 打开生产流转大屏：

```text
没有机列编码的卷显示在“未匹配机列”，而不是让页面或后台报错。
```

### 56.6 本轮推进后的完成度

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `97.8%` | `98.0%` |
| 系统理解总文档可交接度 | `99.95%` | `99.96%` |

为什么这轮能提升：

- 已把 AI 小时简报阻塞从“只定位”推进到“本地修复 + 自动测试”。
- 已避免破坏卷材明细原有空机列语义。
- 已用相关回归测试确认工厂调度服务和 AI 简报服务没有被改坏。

还不能继续大幅提升的原因：

- 修复尚未提交并部署到生产。
- 还没有观察下一次生产小时简报是否恢复。
- 还没有补 PC/终端到真实机列的映射，所以“未匹配机列”只是兜底，不是最终业务闭环。

## 57. 追加理解：AI 简报真实链路测试已补强

上一节的测试已经覆盖了 `list_machine_lines()` 本身，但还不够贴近生产故障。

生产真实故障链路是：

```text
定时任务
  -> ai_briefing_service.generate_briefing()
  -> factory_command_service.list_machine_lines()
  -> 外部 MES 卷材没有 machine_code
  -> 空值参与排序
  -> 小时简报失败
```

所以本轮又补了一个更贴近真实链路的测试。

### 57.1 新增测试覆盖了什么

新增测试：

```text
backend/tests/test_ai_briefing_service.py::test_hourly_inspection_handles_unmatched_mes_machine_codes
```

这个测试不再把 `list_machine_lines()` 假装成正常返回，而是让 AI 简报真实调用工厂机列汇总。

测试数据里同时放了两类卷：

| 卷材 | 机列编码 | 期望 |
|---|---|---|
| `MES:1` | 空 | 进入 `未匹配机列:冷轧2050` |
| `MES:2` | `冷轧:01` | 正常进入 `冷轧:01` |

这样能证明：

```text
AI 小时简报遇到 MES 空机列时，不会再整体失败。
```

### 57.2 最新测试结果

单测：

```text
python -m pytest backend/tests/test_ai_briefing_service.py::test_hourly_inspection_handles_unmatched_mes_machine_codes -q
```

结果：

```text
1 passed
```

相关回归：

```text
python -m pytest backend/tests/test_factory_command_service.py backend/tests/test_ai_briefing_service.py -q
```

结果：

```text
40 passed
```

比上一轮多出的价值：

- 不只是测“机列列表不会报错”。
- 还测了“AI 小时简报真实调用机列列表也不会报错”。
- 同时确认正常机列和未匹配机列可以并存。

### 57.3 同类风险检查

本轮还扫了 `factory_command_service.py` 里同类 `line_code` 排序点。

结论：

| 位置 | 风险判断 |
|---|---|
| 实时聚合机列列表 | 生成的 `line_code` 是字符串 |
| 本地填报机列列表 | 生成的 `line_code` 是字符串 |
| MES 卷材机列列表 | 已给空机列补 `未匹配机列:车间名` |
| 卷材明细列表 | 继续保留 `line_code=None`，不参与机列汇总排序 |

这说明当前修复是“只修会导致报错的汇总路径”，没有把卷材明细的空值语义改掉。

### 57.4 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `98.0%` | `98.1%` |
| 系统理解总文档可交接度 | `99.96%` | `99.97%` |

还不能继续提高太多的原因：

- 生产环境还没部署这次修复。
- 还没看到部署后的新 `hourly_inspection` 记录。
- 还没在管理端实际打开 AI 简报区域验证新记录展示。

## 58. 输出skill 对齐底座与管理端入口

本轮开始落实 `D:\输出skill` 对齐第一阶段，不再停留在方案层。

### 58.1 新增能力

新增后端只读对齐底座：

| 文件 | 作用 |
|---|---|
| `backend/app/services/mapping_reconciliation_service.py` | 内存级字段对齐、单位换算、别名归一、差异原因、dry-run 规则建议 |
| `backend/app/routers/mapping_reconciliation.py` | `/api/v1/mapping-reconciliation/sources`、`/api/v1/mapping-reconciliation/run` |
| `backend/tests/fixtures/output_skill_mapping_sample.json` | 脱敏输出skill 对齐样例 |
| `docs/audits/output-skill-data-mapping-baseline.md` | 第一阶段只读基线审计 |

新增前端入口：

| 文件 | 作用 |
|---|---|
| `frontend/src/api/mapping-reconciliation.js` | 前端调用新对齐接口 |
| `frontend/src/views/manage/mapping-reconciliation/MappingReconciliationPage.vue` | 管理端输出skill 对齐页面 |
| `frontend/src/router/index.js` | 新增 `/manage/mapping-reconciliation` |
| `frontend/src/config/manage-navigation.js` | 管理端系统导航新增“输出skill对齐” |

### 58.2 当前只读证据

本地 `D:\输出skill` 只读扫描结果：

| 类型 | 数量 |
|---|---:|
| `.xls` | 208 |
| `.xlsx` | 86 |
| `.png` | 235 |
| `.txt` | 77 |
| `.json` | 114 |

参考目录里存在 `.exe/.cmd/.ps1` 等文件，所以后续 RAG/解析必须按白名单读取，不能把可执行文件纳入知识库或测试样本。

云端只读查询确认关键表存在：

| 表 | 行数 |
|---|---:|
| `mes_stock_records` | 1547 |
| `mes_workshop_process_records` | 2180 |
| `shift_production_data` | 91 |
| `work_order_entries` | 2876 |
| `daily_consumable_logs` | 1 |
| `machine_energy_records` | 27 |
| `data_quality_issues` | 6 |
| `data_reconciliation_items` | 0 |
| `daily_reports` | 1 |

云端活跃管理口径仍是 `13 个活跃生产车间 + 回收车间 + 成品库` 的 15 项口径，不能混成一个数字讲。

### 58.3 已固化的最小规则

已用测试固定：

| 规则 | 例子 |
|---|---|
| kg/吨统一 | `12500 kg = 12.5 吨` |
| 车间别名 | `精整车间 -> 精整` |
| 班次别名 | `白班 -> 长白班` |
| 差异原因 | `value_diff`、`missing_system_row`、`extra_system_row`、`missing_field_value` |
| 安全边界 | 对齐接口需要管理员，且规则建议只返回 dry-run |

### 58.4 测试结果

后端：

```text
python -m pytest backend/tests/test_mapping_reconciliation_service.py backend/tests/test_mapping_reconciliation_route.py backend/tests/test_imports_daily_production_mapping_preview_route.py -q
8 passed
```

前端：

```text
npm run test
668 passed
```

构建：

```text
npm run build
passed
```

### 58.5 仍未完成

当前不能宣称输出skill 真实全量匹配率已经达到 95%。

原因：

- 还没有把 `D:\输出skill` 中 `.txt/.xls/.xlsx` 内容解析成结构化行。
- 还没有把云端系统数据按同一日期、车间、班次、机列、工序拉平成对齐行。
- `/api/v1/mapping-reconciliation/run` 当前支持传入脱敏/内存行 dry-run，还不是选择文件后自动跑真实对齐。
- `/manage/mapping-reconciliation` 已能进入和调用接口，但还没做真实日期批量匹配。

### 58.6 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `98.1%` | `98.4%` |
| 系统理解总文档可交接度 | `99.97%` | `99.98%` |

下一步最应该做：

1. 写输出skill `.txt/.xls/.xlsx` 只读解析器。
2. 写系统侧只读拉平函数。
3. 让 `/api/v1/mapping-reconciliation/run` 支持按日期和文件范围真实试算。

## 59. 输出skill 真实文件解析与业务日 dry-run 接入

本轮继续推进第一阶段 `D:\输出skill` 对齐，从“内存样例 dry-run”推进到“文件解析 + 系统表只读拉平 + 接口自动试算”。

### 59.1 新增能力

| 文件 | 新增内容 |
|---|---|
| `backend/app/services/mapping_reconciliation_service.py` | 新增 `parse_output_skill_reference_file`、`resolve_reference_file`、`build_system_mapping_rows` |
| `backend/app/routers/mapping_reconciliation.py` | `/api/v1/mapping-reconciliation/run` 支持 `reference_file + business_date` |
| `backend/tests/test_mapping_reconciliation_service.py` | 覆盖 `.txt/.xlsx/.xls` 解析和 MES 工序行拉平 |
| `backend/tests/test_mapping_reconciliation_route.py` | 覆盖接口按文件和业务日自动 dry-run |
| `backend/requirements.txt` | 补 `xlrd==2.0.1`，用于读取老 `.xls` |
| `docs/audits/output-skill-data-mapping-baseline.md` | 更新第一阶段审计证据 |

### 59.2 当前实现边界

已支持的参考文件：

| 类型 | 当前处理 |
|---|---|
| `.txt/.md/.log` | 按 UTF-8/GBK 只读解析，识别日期、车间、班次、产量、能耗、废料 |
| `.xlsx` | 用 `openpyxl` 只读解析常见列：日期、车间、班次、产量、能耗、废料 |
| `.xls` | 用 `xlrd` 只读解析常见列：日期、车间、班次、产量、能耗、废料 |

系统侧本轮只拉平 `mes_workshop_process_records`：

| 输出字段 | 来源 |
|---|---|
| `business_date` | `mes_workshop_process_records.business_date` |
| `workshop` | `workshop_name` |
| `process` | `process_name` |
| `machine` | `device_name` |
| `coil_no` | `batch_no` |
| `input_tons` | 优先 `input_weight_tons`，否则 `input_weight_kg / 1000` |
| `output_tons` | 优先 `output_weight_tons`，否则 `output_weight_kg / 1000` |
| `yield_rate` | `yield_rate` |

为了避免任意读磁盘，接口中的 `reference_file` 会被限制在 `OUTPUT_SKILL_REFERENCE_ROOT` 或默认输出skill参考根目录下。

### 59.3 测试证据

已执行：

```text
python -m pytest backend/tests/test_imports_daily_production_mapping_preview_route.py backend/tests/test_mapping_reconciliation_service.py backend/tests/test_mapping_reconciliation_route.py -q
13 passed
```

已执行：

```text
git diff --check
passed
```

### 59.4 仍未完成

还不能宣称输出skill 真实全量匹配率达到 95%。

原因：

- 还没用真实 `D:\输出skill` 批量跑某个业务日的匹配率。
- 系统侧还只拉了 MES 工序表，没把 `mes_stock_records` 包装/入库、`machine_energy_records` 能耗、`daily_consumable_logs` 辅材一起拉平。
- 前端 `/manage/mapping-reconciliation` 还没从静态样例升级到选择文件和业务日发起真实 dry-run。
- `.txt` 解析当前是日报正文常见句式的确定性解析，不代表能覆盖所有历史自然语言格式。

### 59.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `98.4%` | `98.7%` |
| 系统理解总文档可交接度 | `99.98%` | `99.99%` |

下一步最应该做：

1. 加系统侧 `mes_stock_records`、`machine_energy_records`、`daily_consumable_logs` 拉平。
2. 改 `/manage/mapping-reconciliation`，让页面真正选择文件和业务日跑 dry-run。
3. 用真实输出skill文件做只读匹配率样本，但不提交原始数据。

## 60. 输出skill 系统侧多表拉平补齐

本轮继续第一阶段，不改生产数据，只把系统侧“可拿来和输出skill对账的数据行”补齐。

### 60.1 本轮解决了什么

上一轮 `build_system_mapping_rows` 只会读 `mes_workshop_process_records`，也就是“每个卷过某道工序”的 MES 工序记录。这会导致三个重要口径缺失：

| 缺口 | 为什么重要 |
|---|---|
| 成品库入库/包装参考 | 全厂入库产量不能只看车间工序下机量 |
| 能耗明细 | 输出skill 和日报常会看电、气等消耗 |
| 内勤辅材填报 | 在 MES 还没完全覆盖前，它仍是包装入库、辅材、专项字段的对照来源 |

本轮把系统侧拉平扩展为四类来源：

| 来源表 | 拉平后的含义 |
|---|---|
| `mes_workshop_process_records` | MES 工序产量、上机量、下机量、机台、工序、卷号 |
| `mes_stock_records` | 成品库入库/包装参考，统一放到 `成品库 + 入库` 口径 |
| `machine_energy_records` | 通过 `mobile_shift_reports` 找到业务日、车间、班次，再输出机台电量和气量 |
| `daily_consumable_logs` | 内勤日填报的包装入库、能耗、气耗和辅材 payload |

### 60.2 当前字段映射

| 前端/对账字段 | 当前系统来源 |
|---|---|
| 工序产量 | `mes_workshop_process_records.output_weight_tons`，没有吨字段时用 `output_weight_kg / 1000` |
| 工序投料/上机 | `mes_workshop_process_records.input_weight_tons`，没有吨字段时用 `input_weight_kg / 1000` |
| 全厂入库参考 | `mes_stock_records.net_weight_tons`，没有吨字段时用 `net_weight_kg / 1000` |
| 能耗电量 | `machine_energy_records.energy_kwh` |
| 能耗气量 | `machine_energy_records.gas_m3` |
| 内勤包装入库填报 | `daily_consumable_logs.payload.packaging_inbound_output_tons` |
| 内勤电量填报 | `daily_consumable_logs.payload.electricity_daily` |
| 内勤气量填报 | `daily_consumable_logs.payload.gas_daily` |
| 辅材字段 | `daily_consumable_logs.payload` 里除包装、电、气外的数值字段 |

### 60.3 测试证据

已执行：

```text
python -m pytest backend/tests/test_imports_daily_production_mapping_preview_route.py backend/tests/test_mapping_reconciliation_service.py backend/tests/test_mapping_reconciliation_route.py -q
14 passed
```

已执行：

```text
git diff --check
passed
```

### 60.4 仍未完成

还不能宣称真实输出skill全量匹配率达到 95%。

原因：

- 还没有拿真实 `D:\输出skill` 某个业务日批量试跑。
- 前端 `/manage/mapping-reconciliation` 还没有选择真实文件和业务日的控件。
- 系统侧质量、停机、成本、合同字段还没拉平。
- 还没做运行记录持久化，所以 `/runs/{id}` 一类接口仍未实现。

### 60.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `98.7%` | `98.9%` |
| 系统理解总文档可交接度 | `99.99%` | `99.99%` |

下一步最应该做：

1. 改 `/manage/mapping-reconciliation`，让用户能选文件和业务日跑真实 dry-run。
2. 用一个真实输出skill业务日做只读匹配率样本，不提交原始文件。
3. 补质量、停机、成本、合同字段的系统侧拉平。

## 61. RAG 文本附件后端最小闭环

本轮开始推进第二阶段：文本附件上传和 RAG 入库。当前只做后端最小闭环，没有改前端页面，也没有做云端浏览器真实上传验收。

### 61.1 本轮解决了什么

新增了三张知识库表：

| 表 | 用途 |
|---|---|
| `rag_documents` | 保存上传文档的文件名、编码、大小、切片数量、上传人和状态 |
| `rag_chunks` | 保存文档切片，后续 RAG 查询先从这里找来源 |
| `rag_query_logs` | 保存每次查询、回答、命中来源和查询人 |

新增了 `/api/v1/rag` 后端接口：

| 接口 | 当前能力 |
|---|---|
| `POST /api/v1/rag/documents/upload` | 上传 `.txt/.md/.csv/.json/.log` 文本附件，识别 UTF-8/GBK，切片入库 |
| `GET /api/v1/rag/documents` | 列出知识库文档 |
| `GET /api/v1/rag/documents/{id}` | 查看文档和切片 |
| `DELETE /api/v1/rag/documents/{id}` | 删除文档和切片 |
| `POST /api/v1/rag/query` | 用数据库文本检索 fallback 查询，回答必须带来源 |

### 61.2 安全边界

当前上传入口会拒绝：

| 类型 | 处理 |
|---|---|
| `.exe/.cmd/.bat/.ps1/.sh/.dll/.msi/.scr` 等可执行或脚本文件 | 直接拒绝 |
| 二进制内容 | 直接拒绝 |
| 超过 2MB 的文件 | 直接拒绝 |
| 含 `password/token/secret/api_key/数据库密码/密钥` 等赋值痕迹的文本 | 直接拒绝 |

小白版理解：这一步先保证“资料能安全入库、能被查到、回答能指出来源”，不让系统把程序、二进制、疑似密码文件吞进知识库。

### 61.3 当前查询口径

当前还没有接 pgvector 或 embedding，先用数据库文本检索 fallback。

如果能查到资料，回答格式类似：

```text
根据知识库资料：……
```

并返回 `citations`，里面包含文档 ID、文件名、切片序号和来源标记。

如果查不到资料，系统会回答：

```text
数据不足，知识库没有找到可靠来源。
```

这符合“RAG 没有事实就不能编”的要求。

### 61.4 权限口径

当前 RAG 后端入口允许管理员、管理类角色和审核类角色访问；主操等现场移动端角色不能直接管理知识库。

后续如果要让车间主任只看本车间资料，需要继续给 `rag_documents.scope_payload` 加车间范围过滤。

### 61.5 测试证据

已执行：

```text
python -m pytest backend/tests/test_rag_routes.py -q
4 passed
```

已执行：

```text
python -m pytest backend/tests/test_rag_routes.py backend/tests/test_agent_knowledge_service.py backend/tests/test_mapping_reconciliation_service.py backend/tests/test_mapping_reconciliation_route.py -q
25 passed
```

已执行：

```text
python -m compileall backend/app/models/rag.py backend/app/services/rag_service.py backend/app/routers/rag.py
passed
```

已执行：

```text
DATABASE_URL=sqlite:///<temp-db> python -m alembic upgrade head
passed
```

### 61.6 仍未完成

还不能宣称第二阶段全部完成。

原因：

- `/manage/rag` 前端页面还没做。
- 还没有浏览器真实上传、查看切片、查询、删除的验收截图或记录。
- 还没有把 RAG 查询接入 `/api/v1/agent/command`。
- 还没有 pgvector/embedding，只是文本检索 fallback。
- 还没跑最终要求里的全量 `pytest`、`alembic upgrade head`、`npm test`、`npm run build`。

### 61.7 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `98.9%` | `99.0%` |
| RAG 阶段 | `0%` | `35%` |
| 系统理解总文档可交接度 | `99.99%` | `99.99%` |

下一步最应该做：

1. 做 `/manage/rag` 前端页面：上传、列表、详情、切片预览、删除、测试问答。
2. 用浏览器实际上传一个 UTF-8 和一个 GBK 文本，确认页面、接口、数据库都通。
3. 把 RAG 查询接到 Agent 命令入口，让群问答能引用资料来源。

## 62. RAG 知识库前端入口最小闭环

本轮在上一节后端 RAG 最小闭环基础上，补上了管理端前端入口。当前仍然是“知识库资料管理页”，不是最终的多 Agent 群问答入口。

### 62.1 本轮解决了什么

新增 `/manage/rag` 管理端页面，导航名称为“知识库资料”。

页面已接入真实 `/api/v1/rag` 后端接口：

| 前端动作 | 后端接口 |
|---|---|
| 上传文本附件 | `POST /api/v1/rag/documents/upload` |
| 查看文档清单 | `GET /api/v1/rag/documents` |
| 查看文档切片 | `GET /api/v1/rag/documents/{id}` |
| 删除文档 | `DELETE /api/v1/rag/documents/{id}` |
| 测试问答 | `POST /api/v1/rag/query` |

小白版理解：现在管理员可以从管理端入口上传文本资料，看到资料被切成哪些段，也可以输入问题测试系统能不能从这些资料里找答案和来源。

### 62.2 前端视觉口径

本页先用 Stitch 生成工业资料台方向，再迁移到现有前端工程。

Stitch 项目：

```text
projects/15891304796857737989
```

Stitch 页面稿：

```text
projects/15891304796857737989/screens/46572f9e8bb540cfa6aad09c7c05cb7b
```

实现时只接真实接口，不放长期假数字。

### 62.3 测试证据

已执行：

```text
node --test tests/ragKnowledgePage.test.js tests/mappingReconciliationPage.test.js
6 passed
```

已执行：

```text
python -m pytest backend/tests/test_rag_routes.py -q
4 passed
```

已执行：

```text
npm run test
672 passed
```

已执行：

```text
npm run build
passed
```

已执行：

```text
git diff --check
passed
```

### 62.4 当前边界

还不能宣称 RAG 和钉钉主动汇报全部完成。

原因：

- 本轮做的是 `/manage/rag` 管理端资料入口。
- 还没有做浏览器真实上传文件的线上验证。
- 还没有把 RAG 查询正式接入 `/api/v1/agent/command`。
- 还没有接 embedding 或 pgvector，当前仍是数据库文本检索 fallback。

### 62.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.0%` | `99.15%` |
| RAG 阶段 | `35%` | `55%` |
| 系统理解总文档可交接度 | `99.99%` | `99.99%` |

## 63. Agent 命令入口接入 RAG 最小闭环

本轮继续第二阶段到第三阶段之间的衔接：把已经完成的 RAG 知识库接到统一 Agent 命令入口。当前仍然没有触发真实钉钉发送。

### 63.1 本轮解决了什么

新增 `/api/v1/agent/command`。

最小流程如下：

| 步骤 | 当前实现 |
|---|---|
| 保存外部消息 | 写入 `chat_inbox` |
| 查询知识库 | 调用 `rag_service.query_knowledge` |
| 生成回答 | 使用固定中文模板，不让大模型编数字 |
| 保存运行记录 | 写入 `agent_runs` |
| 外发消息 | 本轮不外发，`outbox_message_id=null` |

小白版理解：现在群消息或管理端测试消息进来后，系统会先把问题记账，再去资料库查答案。查到资料时，回答里会带“数据来源”；查不到时，会明确说数据不足。

### 63.2 新增表

| 表 | 用途 |
|---|---|
| `chat_inbox` | 保存外部聊天入口消息，包括通道、群、发送人、文本和追踪号 |
| `agent_runs` | 保存 Agent 每次运行的答案、状态、RAG 命中数量和结果载荷 |

迁移文件：

```text
backend/alembic/versions/0042_agent_command_audit.py
```

### 63.3 RAG 检索改进

本轮顺手补了中文短句检索。

之前 “换辊超时怎么办” 这种连续中文句子不一定能命中资料里的 “换辊超时”。现在 fallback 会额外生成 4 字中文窗口，例如：

```text
换辊超时
```

这样不接 embedding 的情况下，也能更稳地命中中文现场问题。

### 63.4 权限边界

当前 `/api/v1/agent/command` 仍要求当前登录用户具备管理、审核或管理员权限。

这意味着本轮没有开放匿名钉钉 webhook，也没有绕过系统登录权限。后续如果接 DingTalk Stream 或机器人回调，需要再加签名校验、通道绑定和发送人身份映射。

### 63.5 测试证据

已执行：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py -q
2 passed
```

已执行：

```text
python -m pytest backend/tests/test_rag_routes.py -q
4 passed
```

已执行：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_overview_service.py backend/tests/test_agent_management_router.py backend/tests/test_rag_routes.py -q
17 passed
```

已执行：

```text
python -m compileall backend/app/models/agent_communication.py backend/app/services/agent_command_service.py backend/app/services/rag_service.py backend/app/routers/agent.py
passed
```

已执行：

```text
cd backend && DATABASE_URL=sqlite:///<temp-db> python -m alembic upgrade head
passed
```

已执行：

```text
git diff --check
passed
```

### 63.6 当前边界

还不能宣称 Agent 通讯中台和真实钉钉完成。

原因：

- 本轮只做 `/api/v1/agent/command` 的 RAG 问答和审计留痕。
- 还没有把 Agent command 绑定到真实钉钉 Stream 或机器人回调。
- 还没有把需要外发的回答写入 `agent_outbox_messages`。
- 还没有做真实钉钉测试群发送验证。
- 还没有做浏览器上传资料后再从 Agent command 查询的端到端验证。

### 63.7 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.15%` | `99.25%` |
| RAG 阶段 | `55%` | `65%` |
| Agent 通讯阶段 | `25%` | `35%` |
| 系统理解总文档可交接度 | `99.99%` | `99.99%` |

## 64. Agent 命令回复进入 outbox 最小闭环

本轮继续第三阶段到第四阶段之间的安全闸门：让 `/api/v1/agent/command` 在明确要求外发排队时，把回答放进 `agent_outbox_messages`，但仍然不直接发送钉钉。

### 64.1 本轮解决了什么

`/api/v1/agent/command` 新增 `queue_outbox` 入参。

当前行为：

| 条件 | 结果 |
|---|---|
| `queue_outbox=false` 或不传 | 只返回回答、写 `chat_inbox` 和 `agent_runs` |
| `queue_outbox=true` 且 Agent 已绑定通道 | 写入 `agent_outbox_messages`，状态为 `pending` |
| `queue_outbox=true` 但缺少群 ID 或通道绑定 | 返回错误，不偷偷丢消息 |

小白版理解：现在系统可以把“准备发到群里的回复”先放进发件箱，等待后续调度器或人工确认发送。这比直接发钉钉安全，因为能先看到、能重试、能留痕。

### 64.2 安全边界

本轮没有调用 `dispatch_outbox_message`，所以不会触发真实钉钉发送。

本轮只是复用已有：

```text
agent_communication_service.queue_bound_message
```

这意味着真实发送仍然要经过已有 outbox 分发函数、dry-run 判断、发送结果日志和失败处理。

### 64.3 测试证据

已执行：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py -q
3 passed
```

已执行：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_overview_service.py backend/tests/test_agent_management_router.py backend/tests/test_rag_routes.py -q
18 passed
```

已执行：

```text
python -m compileall backend/app/services/agent_command_service.py backend/app/routers/agent.py
passed
```

已执行：

```text
git diff --check
passed
```

### 64.4 当前边界

还不能宣称真实钉钉已接通。

原因：

- 现在只是进入 outbox。
- 还没有新增 DingTalk Stream 或机器人回调。
- 还没有在云端真实群里触发 `dispatch_outbox_message`。
- 还没有把外发成功或失败结果写入真实生产 `external_message_logs` 做验收。

### 64.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.25%` | `99.32%` |
| Agent 通讯阶段 | `35%` | `42%` |
| 真实钉钉阶段 | `10%` | `12%` |
| 系统理解总文档可交接度 | `99.99%` | `99.99%` |

## 65. outbox 手动分发和外发日志查询后端入口

本轮继续第四阶段前置工作：补管理端后端接口，让管理员可以手动触发 outbox 分发，并查询对应外发日志。

### 65.1 本轮解决了什么

新增两个管理接口：

| 接口 | 用途 |
|---|---|
| `POST /api/v1/agent-management/outbox/{id}/dispatch` | 手动触发某条 outbox 消息分发 |
| `GET /api/v1/agent-management/outbox/{id}/logs` | 查看该 outbox 消息对应的外发日志 |

当前接口复用已有：

```text
agent_communication_service.dispatch_outbox_message
agent_communication_service.list_external_logs
```

小白版理解：以前消息可以进“发件箱”，但管理后端还没有按钮背后的接口去“尝试发送/试跑发送”。现在 dry-run 通道可以走完整的分发路径，并在 `external_message_logs` 留一条“只是试跑，没有真实发送”的记录。

### 65.2 安全边界

本轮测试只覆盖 dry-run 通道。

`communication_channels.dry_run=true` 时：

| 行为 | 结果 |
|---|---|
| 调用 dispatch | 不会调用真实钉钉发送 |
| outbox 状态 | 变为 `dry_run` |
| attempts | 增加 1 |
| external log | 写入 `dry_run only, message not sent` |

日志接口不会返回完整 `channel_key`，只返回脱敏后的 `channel_key_masked`。

### 65.3 测试证据

已执行：

```text
python -m pytest backend/tests/test_agent_management_router.py -q
7 passed
```

已执行：

```text
python -m pytest backend/tests/test_agent_management_router.py backend/tests/test_agent_communication_service.py backend/tests/test_agent_command_rag_route.py backend/tests/test_agent_management_overview_service.py backend/tests/test_rag_routes.py -q
20 passed
```

已执行：

```text
python -m compileall backend/app/routers/agent_management.py
passed
```

已执行：

```text
git diff --check
passed
```

### 65.4 当前边界

还不能宣称真实钉钉测试完成。

原因：

- 本轮没有调用真实非 dry-run 通道。
- 本轮没有在云端测试群收到消息。
- 本轮只是让管理后端具备分发入口和日志查看入口。

### 65.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.32%` | `99.38%` |
| Agent 通讯阶段 | `42%` | `48%` |
| 真实钉钉阶段 | `12%` | `18%` |
| 系统理解总文档可交接度 | `99.99%` | `99.99%` |

## 66. 通讯治理台前端接入 outbox 分发和日志

本轮继续第四阶段前置工作：把上一节已有的 outbox 手动分发和外发日志后端接口接到管理端页面。

### 66.1 本轮解决了什么

新增前端 API 封装：

| 前端函数 | 后端接口 | 用途 |
|---|---|---|
| `dispatchAgentOutboxMessage` | `POST /api/v1/agent-management/outbox/{id}/dispatch` | 管理员手动触发某条发件箱消息分发 |
| `fetchAgentOutboxLogs` | `GET /api/v1/agent-management/outbox/{id}/logs` | 管理员查看某条发件箱消息对应的外发日志 |

`/manage/admin/agents` 的“发件箱”模块从只读状态升级为：

| 能力 | 当前表现 |
|---|---|
| 查看状态 | 继续显示待发送、重试中、演练、已发送、失败 |
| 手动分发 | 对 `pending/retrying/failed` 状态显示操作按钮 |
| 查看外发日志 | 显示通道类型、脱敏通道标识、发送状态、返回信息、创建时间 |
| 错误兜底 | 分发失败或日志读取失败时在发件箱模块内显示中文错误 |

小白版理解：现在管理员不只是能看到“消息在发件箱里”，还能在治理台里点它走分发流程，并查看系统到底有没有留下外发记录。

### 66.2 安全边界

这次没有改后端发送逻辑，也没有直接调用真实钉钉配置。

真实是否发送仍由后端通道配置决定：

| 通道状态 | 结果 |
|---|---|
| `communication_channels.dry_run=true` | 只演练，写日志，不真实发送 |
| `communication_channels.dry_run=false` 且通道类型支持真实发送 | 进入真实发送流程，返回结果写 `external_message_logs` |

前端只展示后端返回的脱敏字段 `channel_key_masked`，不展示完整 `channel_key`。

### 66.3 测试证据

已执行：

```text
cd frontend && node --test tests/agentManagementPage.test.js
6 passed
```

### 66.4 当前边界

还不能宣称真实钉钉测试完成。

原因：

- 本轮只是把管理端页面接到已存在后端接口。
- 还没有登录云端页面点击真实按钮做浏览器验收。
- 还没有对非 dry-run 钉钉通道做测试群真实发送。
- 还没有补 `/manage/channels` 的通道配置页面。

### 66.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.38%` | `99.43%` |
| Agent 通讯阶段 | `48%` | `52%` |
| 真实钉钉阶段 | `18%` | `22%` |
| 系统理解总文档可交接度 | `99.99%` | `99.99%` |

## 67. 通讯通道中心前端最小闭环

本轮继续第四阶段前置工作：补上目标中要求的 `/manage/channels` 页面，让管理员可以单独查看外部通讯通道，而不是只能在通讯治理台里顺带看到。

### 67.1 本轮解决了什么

新增管理端页面：

```text
/manage/channels
```

页面名称为“通讯通道中心”，入口在管理端“系统”导航组中，名称为“通讯通道”。

当前页面复用已有后端安全概览：

```text
GET /api/v1/agent-management/overview
```

新增前端 API 函数：

| 前端函数 | 数据来源 | 用途 |
|---|---|---|
| `fetchCommunicationChannels` | `agent-management/overview.channels` | 读取通道清单和通道统计 |

小白版理解：以前“通道配置”藏在通讯治理台的一块小区域里，现在有了独立页面，管理员能一眼看出哪些通道是演练模式，哪些通道可能走真实发送。

### 67.2 当前页面显示

| 区域 | 内容 |
|---|---|
| 通道总数 | 来自治理概览 summary |
| 启用通道 | 来自治理概览 summary |
| 演练模式 | 统计 `dry_run=true` 的通道 |
| 真实发送 | 统计启用且 `dry_run=false` 的通道 |
| 通道清单 | 名称、类型、范围、脱敏标识、绑定数量、模式、状态 |

### 67.3 安全边界

本轮没有新增后端写接口，也没有新增真实发送按钮。

页面只读展示：

| 字段 | 处理 |
|---|---|
| `channel_key_masked` | 展示脱敏标识 |
| 完整通道 key | 不展示 |
| 凭据引用字段 | 不展示 |
| 真实外发 | 仍必须走发件箱统一分发 |

这意味着 `/manage/channels` 当前是“查看通道和确认风险边界”的页面，不是最终的通道创建/编辑页面。

### 67.4 测试证据

已执行：

```text
cd frontend && node --test tests/channelManagementPage.test.js tests/agentManagementPage.test.js
9 passed
```

已执行：

```text
cd frontend && npm run test
676 passed
```

已执行：

```text
cd frontend && npm run build
passed
```

### 67.5 当前边界

还不能宣称真实钉钉测试完成。

原因：

- 本轮只做通道查看页面。
- 还没有通道创建、编辑、启停、测试发送表单。
- 还没有登录云端页面做浏览器验收。
- 还没有对非 dry-run 通道做测试群真实发送。

### 67.6 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.43%` | `99.48%` |
| Agent 通讯阶段 | `52%` | `54%` |
| 真实钉钉阶段 | `22%` | `24%` |
| 前端治理阶段 | `70%` | `74%` |

## 68. 通讯通道中心接入发件箱和外发日志查看

本轮继续第四阶段的前端验收链路：`/manage/channels` 不再只看通道清单，也能看到最近外发任务，并能按发件箱消息读取外发日志。这样管理员做云端验收时，可以在通道页面直接核对“准备发什么、投递状态是什么、后端返回了什么”，不用来回切到通讯治理台。

### 68.1 本轮解决了什么

`fetchCommunicationChannels` 继续复用安全的治理总览接口：

```text
GET /api/v1/agent-management/overview
```

它现在返回：

| 字段 | 来源 | 用途 |
|---|---|---|
| `summary` | 治理总览统计 | 通道总数、启用通道 |
| `channels` | 治理总览通道清单 | 展示脱敏通道配置 |
| `outbox` | 治理总览发件箱清单 | 展示最近外发任务 |

页面新增“最近外发任务”区域，显示消息标题、通道类型、投递状态、尝试次数、下次重试时间，并提供“查看日志”按钮。

查看日志复用已有接口：

```text
GET /api/v1/agent-management/outbox/{outboxMessageId}/logs
```

日志面板显示结果、脱敏通道标识、返回结果和时间。

小白版理解：现在这个页面更像“通讯通道值班台”。它不会替你发消息，但能看出发件箱里有什么、状态怎样、有没有真实返回记录。

### 68.2 安全边界

本轮没有新增发送按钮，没有新增创建/编辑通道表单，也没有新增后端写接口。

| 能力 | 本轮状态 |
|---|---|
| 查看通道 | 已有 |
| 查看发件箱 | 新增 |
| 查看外发日志 | 新增 |
| 创建通道 | 未做 |
| 编辑通道 | 未做 |
| 测试发送 | 未做 |
| 真实钉钉发送验收 | 未做 |

页面仍只展示 `channel_key_masked` 这类脱敏字段，不展示完整通道 key，也不展示凭据引用字段。

### 68.3 测试证据

先写失败测试后实现，红灯失败点为：

```text
node --test tests/channelManagementPage.test.js
失败原因：fetchCommunicationChannels 未返回 outbox，页面缺少“最近外发任务”和“外发日志”。
```

实现后已执行：

```text
cd frontend && node --test tests/channelManagementPage.test.js
4 passed
```

已执行相关回归：

```text
cd frontend && node --test tests/channelManagementPage.test.js tests/agentManagementPage.test.js
10 passed
```

### 68.4 当前边界

还不能宣称真实钉钉测试完成。

原因：

- 当前只是让通道页能看 outbox 和外发日志。
- 真实发送仍要由治理台或后端分发接口触发。
- 还没有登录云端页面做浏览器验收。
- 还没有对非 dry-run 通道做钉钉测试群真实发送。

### 68.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.48%` | `99.50%` |
| Agent 通讯阶段 | `54%` | `55%` |
| 真实钉钉阶段 | `24%` | `25%` |
| 前端治理阶段 | `74%` | `76%` |

## 69. 通讯链路 dry-run 自检闭环

本轮继续第四阶段的安全验收能力：新增管理员专用的通讯链路 dry-run 自检。它能创建或复用一个演练通道，生成一条发件箱消息，立即走 dry-run 分发，并写入外发日志。这个能力用于验证“outbox 到 external_message_logs”链路是否通，不会调用真实钉钉发送。

### 69.1 本轮解决了什么

新增后端接口：

```text
POST /api/v1/agent-management/outbox/dry-run-smoke
```

它内部复用现有服务：

| 步骤 | 复用函数 | 结果 |
|---|---|---|
| 注册演练 Agent | `register_agent` | `agent_management_smoke` |
| 注册演练通道 | `register_channel` | `dingtalk_group`，强制 `dry_run=true` |
| 绑定 Agent 和通道 | `bind_agent_to_channel` | 允许消息进入 outbox |
| 创建演练消息 | `queue_bound_message` | 生成一条待分发消息 |
| 执行 dry-run 分发 | `dispatch_outbox_message` | 状态变为 `dry_run` |
| 查询日志 | `list_external_logs` | 产生 1 条外发日志 |

返回只包含脱敏通道信息：

```text
outbox_message_id
status
detail
log_total
channel.id
channel.name
channel.channel_type
channel.channel_key_masked
channel.dry_run
```

前端 `/manage/channels` 新增“运行演练自检”按钮。点击后会调用 dry-run 自检接口，刷新通道和发件箱，并自动打开本次 outbox 的外发日志。

### 69.2 安全边界

这个自检入口是管理员专用，非管理员返回 403。

| 风险点 | 处理 |
|---|---|
| 误发真实钉钉 | 演练通道强制 `dry_run=true` |
| 泄露通道标识 | 前端和接口只返回 `channel_key_masked` |
| 绕过 outbox | 不允许，仍走 `queue_bound_message -> dispatch_outbox_message` |
| 绕过日志 | 不允许，dry-run 也写 `external_message_logs` |
| 伪造真实验收 | 文档明确这不是真实钉钉发送验收 |

小白版理解：这像消防演习。系统会完整走一遍“准备发消息、进发件箱、分发、写日志”的动作，但不会真的往钉钉群里发。

### 69.3 测试证据

先写失败测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_agent_management_router.py -q
失败原因：POST /api/v1/agent-management/outbox/dry-run-smoke 返回 404。
```

实现后已执行：

```text
python -m pytest backend/tests/test_agent_management_router.py -q
9 passed
```

已执行相关后端回归：

```text
python -m pytest backend/tests/test_agent_management_router.py backend/tests/test_agent_communication_service.py -q
13 passed
```

前端先写失败测试后实现，红灯失败点为：

```text
node --test tests/channelManagementPage.test.js
失败原因：缺少 runCommunicationDryRunSmoke API 和页面“运行演练自检”入口。
```

实现后已执行：

```text
cd frontend && node --test tests/channelManagementPage.test.js
4 passed
```

已执行相关前端回归：

```text
cd frontend && node --test tests/channelManagementPage.test.js tests/agentManagementPage.test.js
10 passed
```

### 69.4 当前边界

还不能宣称真实钉钉测试完成。

原因：

- 本轮是 dry-run 自检，不是真实钉钉群发送。
- 还没有登录云端系统点击该按钮做浏览器验收。
- 还没有把非 dry-run 通道接到测试群做真实发送。
- 还没有验证群里 @Agent 问答入口。

### 69.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.50%` | `99.53%` |
| Agent 通讯阶段 | `55%` | `56%` |
| 真实钉钉阶段 | `25%` | `28%` |
| 前端治理阶段 | `76%` | `77%` |

## 70. Agent outbox 失败重试与死信规则

### 70.1 本轮新增能力

外部通讯发件箱现在不再把真实发送失败直接记成最终失败，而是按统一规则处理：

| 场景 | 新状态 | 含义 |
|---|---|---|
| 第 1 次发送失败 | `retrying` | 等待下次重试 |
| 第 2 次发送失败 | `retrying` | 仍可继续重试 |
| 第 3 次发送失败 | `dead_letter` | 进入死信，不再自动或手动重复真实发送 |
| dry-run 演练 | `dry_run` | 只写日志，不真实外发 |
| 发送成功 | `sent` | 已真实发送成功 |

小白版理解：这像快递派送。前两次送不到会约下次再送，第三次还送不到就放进异常件柜，不再让系统一直重复骚扰外部群。

### 70.2 数据库和接口链路

本轮新增 `agent_outbox_messages.next_retry_at` 字段，用来记录下一次重试时间。该字段允许为空，不改历史消息原文，也不回填生产数据。

管理端概览接口会返回：

- `status`：当前发件箱状态。
- `attempts`：已尝试次数。
- `last_error`：最近一次失败原因。
- `next_retry_at`：下次重试时间。

前端 `/manage/admin/agents` 已补齐中文状态：

- `retrying` 显示为“重试中”。
- `dead_letter` 显示为“死信”。

### 70.3 测试证据

先写失败测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_agent_communication_service.py -q
失败原因：发送失败后返回 failed，而不是 retrying。

node --test frontend/tests/agentManagementPage.test.js
失败原因：AgentManagementPage 缺少 dead_letter 中文显示。
```

实现后已执行：

```text
python -m pytest backend/tests/test_agent_communication_service.py -q
5 passed

python -m pytest backend/tests/test_agent_management_router.py backend/tests/test_agent_communication_service.py -q
14 passed

node --test frontend/tests/agentManagementPage.test.js frontend/tests/channelManagementPage.test.js
11 passed

python -m compileall backend/app/models/agent_communication.py backend/app/services/agent_communication_service.py backend/app/services/agent_management_overview_service.py backend/app/routers/agent_management.py backend/alembic/versions/0043_agent_outbox_retry_dead_letter.py
通过

git diff --check
通过
```

### 70.4 当前边界

还不能宣称真实钉钉测试完成。

原因：

- 本轮验证的是 outbox 失败状态机，不是真实钉钉测试群发送。
- 还没有运行生产环境 `alembic upgrade head`。
- 还没有做云端浏览器点击验证。
- 还没有验证 DingTalk Stream 或群内 @Agent 问答入口。

### 70.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.53%` | `99.56%` |
| Agent 通讯阶段 | `56%` | `60%` |
| 真实钉钉阶段 | `28%` | `31%` |
| 前端治理阶段 | `77%` | `78%` |

## 71. Agent outbox 同异常 30 分钟去重

### 71.1 本轮新增能力

外部通讯发件箱现在支持“同异常 30 分钟内不重复入队”。调用 `queue_bound_message` 时，如果传入相同 `dedupe_key`，系统会先查同一个 Agent、同一个通道下是否已有未过期消息：

| 场景 | 处理 |
|---|---|
| 未传 `dedupe_key` | 保持旧行为，每次创建新 outbox |
| 传入 `dedupe_key`，30 分钟内重复触发 | 复用原 outbox，不新建消息 |
| 传入 `dedupe_key`，超过 30 分钟后触发 | 创建新 outbox |

小白版理解：同一台机同一个停机问题，半小时内不会反复往群里塞新消息；半小时后如果问题还在，才允许重新提醒。

### 71.2 数据库和代码链路

本轮新增两个字段：

- `agent_outbox_messages.dedupe_key`：同异常识别键。
- `agent_outbox_messages.dedupe_expires_at`：去重保护到期时间。

代码入口仍是 `agent_communication_service.queue_bound_message`。这点很重要：没有新增第二套消息系统，也没有绕过 outbox。以后停机、辅材、质量、催报、日报等 Agent 只要走这个入口并传入稳定 `dedupe_key`，就能共享同一套防刷屏规则。

### 71.3 测试证据

先写失败测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_agent_communication_service.py -q
失败原因：queue_bound_message() got an unexpected keyword argument 'dedupe_key'
```

实现后已执行：

```text
python -m pytest backend/tests/test_agent_communication_service.py -q
6 passed

python -m pytest backend/tests/test_agent_management_router.py backend/tests/test_agent_communication_service.py -q
15 passed

python -m compileall backend/app/models/agent_communication.py backend/app/services/agent_communication_service.py backend/alembic/versions/0044_agent_outbox_dedupe_window.py
通过

git diff --check
通过
```

### 71.4 当前边界

还不能宣称“所有 Agent 都已自动去重”。

原因：

- 本轮补的是统一入队能力。
- 上层停机、辅材、质量、催报等 Agent 还需要逐步传入稳定 `dedupe_key`。
- 还没有做真实钉钉测试群验证。
- 还没有运行生产环境迁移。

### 71.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.56%` | `99.59%` |
| Agent 通讯阶段 | `60%` | `63%` |
| 真实钉钉阶段 | `31%` | `33%` |
| 前端治理阶段 | `78%` | `78%` |

## 72. 主动汇报已接入 outbox 去重键

### 72.1 本轮新增能力

上一轮只是在 `queue_bound_message` 里提供了去重能力。本轮把主动汇报服务接上了这个能力：

| 主动汇报类型 | 去重键范围 |
|---|---|
| 全厂总览主动汇报 | 事件类型 + 全厂范围 + 生产日 + 通道 + 异常签名 |
| 车间状态主动汇报 | 事件类型 + 车间 ID + 生产日 + 通道 + 异常签名 |

如果同一个异常在 30 分钟内再次触发，系统会复用原 outbox，并把新事件标记为 `suppressed`，原因是 `outbox_deduped`。

小白版理解：上一轮是给发件箱装了“防重复锁”，本轮是让主动汇报真的开始使用这把锁。

### 72.2 代码链路

相关入口：

- `agent_active_reporting_service.queue_factory_overview`
- `agent_active_reporting_service.queue_workshop_status`
- `agent_communication_service.queue_bound_message`

关键规则：

- 事件仍然会进入 `agent_events` 留档。
- 重复事件不会创建第二条 `agent_outbox_messages`。
- 重复事件会保留 `deduped_outbox_message_id`，方便追溯它复用了哪条外发消息。
- 真实外发仍然只发生在后续执行 `dispatch_outbox_message` 时。

### 72.3 测试证据

先写失败测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_agent_active_reporting_service.py -q
失败原因：第二次同异常主动汇报仍返回 queued，而不是 suppressed。
```

实现后已执行：

```text
python -m pytest backend/tests/test_agent_active_reporting_service.py -q
6 passed

python -m pytest backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_router.py -q
21 passed

python -m compileall backend/app/services/agent_active_reporting_service.py
通过

git diff --check
通过
```

### 72.4 当前边界

还不能宣称“所有 Agent 都已自动去重”。

原因：

- 本轮只接入了主动汇报服务。
- 后续还要逐步检查催报 Agent、日报秘书、质量异常、辅材超耗、停机升级等是否都走这个入口或传入稳定 `dedupe_key`。
- 还没有做真实钉钉测试群验证。

### 72.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.59%` | `99.62%` |
| Agent 通讯阶段 | `63%` | `66%` |
| 真实钉钉阶段 | `33%` | `35%` |
| 前端治理阶段 | `78%` | `78%` |

## 73. 主动汇报消息已改为固定 Agent 模板

### 73.1 本轮新增能力

主动汇报写入 outbox 的正文，已从旧 Markdown 段落改为固定中文值班模板：

```text
【范围｜时间】状态：绿/黄/红；结论；关键数字；原因；建议动作；数据来源；可回复命令。
```

小白版理解：以前像一份小报告，群里看起来慢；现在像值班员一句话汇报，先看状态，再看数字和动作。

### 73.2 当前模板规则

| 字段 | 规则 |
|---|---|
| 范围 | 全厂或具体车间 |
| 时间 | 优先使用事件发生时间，没有则使用生产日 |
| 状态 | `info=绿`、`warning=黄`、`critical=红` |
| 关键数字 | 来自主动汇报传入的确定性 `metrics` |
| 原因 | 来自主动汇报传入的确定性 `anomalies` |
| 建议动作 | 有严重异常时要求责任人立即确认原因和恢复时间 |
| 数据来源 | 固定为“数据中枢主动汇报” |
| 可回复命令 | `今日产量 / 异常明细 / 辅材明细` |

注意：这里没有让大模型查库或编数字，正文全部由后端确定性代码从已传入的业务事实组织。

### 73.3 测试证据

先写失败测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_agent_active_reporting_service.py -q
失败原因：消息正文仍以 ### 全厂主动汇报 开头，不符合固定模板。
```

实现后已执行：

```text
python -m pytest backend/tests/test_agent_active_reporting_service.py -q
7 passed

python -m pytest backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_router.py -q
22 passed

python -m compileall backend/app/services/agent_active_reporting_service.py
通过

git diff --check
通过
```

### 73.4 当前边界

还不能宣称所有 Agent 都已使用固定模板。

原因：

- 本轮只覆盖主动汇报服务。
- `/api/v1/agent/command`、RAG 问答、日报秘书、催报 Agent 等后续还要逐步统一模板。
- 还没有做真实钉钉测试群验收。

### 73.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.62%` | `99.65%` |
| Agent 通讯阶段 | `66%` | `68%` |
| 真实钉钉阶段 | `35%` | `36%` |
| 前端治理阶段 | `78%` | `78%` |

## 74. Agent command 群回复已接入 outbox 去重

### 74.1 本轮新增能力

`POST /api/v1/agent/command` 在 `queue_outbox=true` 时，现在会为群回复生成稳定 `dedupe_key`。同一个通道、同一个群、同一个 Agent、同一个问题，在 30 分钟内重复触发，会复用同一条 outbox，不再重复创建外发任务。

小白版理解：群里有人连续问同一句“停机超过三十分钟怎么办”，系统会记录两次提问和两次回答审计，但不会往发件箱塞两条一样的待发消息。

### 74.2 代码链路

相关入口：

- `agent.py -> POST /api/v1/agent/command`
- `agent_command_service.handle_agent_command`
- `agent_communication_service.queue_bound_message`

关键边界：

- 每次外部命令仍写 `chat_inbox`。
- 每次 Agent 回答仍写 `agent_runs`。
- 只有 outbox 外发任务会按 `dedupe_key` 复用。
- 真实外发仍然只发生在后续执行 `dispatch_outbox_message` 时。

### 74.3 测试证据

先写失败测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py -q
失败原因：第二次同问题创建了新的 outbox_message_id。
```

实现后已执行：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py -q
4 passed

python -m pytest backend/tests/test_agent_command_rag_route.py backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_router.py -q
26 passed

python -m compileall backend/app/services/agent_command_service.py
通过

git diff --check
通过
```

### 74.4 当前边界

还不能宣称真实钉钉群问答完成。

原因：

- 本轮验证的是本地测试库里的 agent command 和 outbox 去重。
- 还没有接 DingTalk Stream 或机器人入口。
- 还没有在真实钉钉测试群里 @Agent 验证。
- 还没有跑云端浏览器验收。

### 74.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.65%` | `99.68%` |
| Agent 通讯阶段 | `68%` | `70%` |
| 真实钉钉阶段 | `36%` | `38%` |
| 前端治理阶段 | `78%` | `78%` |

## 75. Agent command 今日产量已接实时聚合事实

### 75.1 本轮新增能力

`POST /api/v1/agent/command` 识别到 `production_today` 意图后，已开始复用生产大屏同一条实时聚合链路：

- 业务日来自 `resolve_production_business_date`，仍按生产口径。
- 事实来源来自 `realtime_service.build_live_aggregation`，不是 Agent 自己重新拼 SQL。
- 回答中会同时显示“包装产量”和“全厂入库产量”。
- `facts` 会返回到接口，也会写入 `agent_runs.result_payload`，方便审计。

小白版理解：现在群里问“今日产量”，Agent 不再只说“无新增生产数字”。如果生产大屏聚合能查到事实，它会把同一套数字拿来回答，并写清来源。

### 75.2 当前口径

| 字段 | 口径 |
|---|---|
| 包装产量 | 复用生产大屏 `factory_total.daily_output`，同 `packaging_output`，优先取外部 MES 包装数据 |
| 全厂入库产量 | 复用生产大屏 `factory_total.finished_inbound_output`，保留内勤成品入库对照 |
| 业务日开始 | 当前实时聚合返回 `07:30` |
| 数据来源 | `daily_output_source`、`finished_inbound_source` 原样写入 `facts` |

### 75.3 失败兜底

如果实时聚合不可用，Agent 不会报 500，也不会编数字。它会把 `fact_status` 写成 `not_connected`，回答仍然使用“无新增生产数字”的保守口径。

### 75.4 测试证据

先写失败测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py::test_agent_command_uses_live_production_fact_for_today_output -q
失败原因：agent_command_service 还没有 resolve_production_business_date，说明今日产量意图未接生产事实链路。
```

实现后已执行：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py::test_agent_command_uses_live_production_fact_for_today_output -q
1 passed

python -m pytest backend/tests/test_agent_command_rag_route.py -q
6 passed

python -m pytest backend/tests/test_agent_command_rag_route.py backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_router.py -q
28 passed

python -m compileall backend/app/services/agent_command_service.py backend/app/routers/agent.py
通过

git diff --check
通过
```

### 75.5 当前边界

还不能宣称真实钉钉群问答完成。

原因：

- 本轮只接了 `今日产量` 这一类意图。
- 停机、辅材、质量、异常等意图还没有接各自事实服务。
- 还没有接 DingTalk Stream 或机器人入口。
- 还没有在真实钉钉测试群里 @Agent 验证。
- 还没有跑云端浏览器验收。

### 75.6 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.68%` | `99.71%` |
| Agent 通讯阶段 | `70%` | `73%` |
| 真实钉钉阶段 | `38%` | `39%` |
| 前端治理阶段 | `78%` | `78%` |

## 76. Agent command 哪个车间异常已接实时异常摘要

### 76.1 本轮新增能力

`POST /api/v1/agent/command` 识别到 `anomaly_summary` 意图后，已开始复用生产大屏实时聚合中的两类待处理异常：

- `overall_progress.pending_assignment`：填报卷或补录卷还没有匹配机列/班次。
- `data_quality.missing_output_weight`：正式填报缺下机量。

小白版理解：现在群里问“哪个车间异常”，Agent 不再只查知识库，而是会从生产大屏同一套实时数据里找当前最需要处理的车间。

### 76.2 当前口径

| 字段 | 口径 |
|---|---|
| 未匹配机列/班次 | 生产大屏 `overall_progress.pending_assignment.entry_count` |
| 缺下机量 | 生产大屏 `data_quality.missing_output_weight.entry_count` |
| 重点车间 | 从 `pending_assignment.rows` 和 `missing_output_weight.items` 统计前 5 个车间 |
| 状态灯 | 有异常为橙色，无异常为绿色 |

注意：这不是全量异常中心，只是先接入生产大屏上已经稳定展示的两类现场堵塞项。

### 76.3 测试证据

先写失败测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py::test_agent_command_uses_live_anomaly_fact_for_workshop_summary -q
失败原因：接口仍返回 yellow 知识库兜底，没有读取实时异常事实。
```

实现后已执行：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py::test_agent_command_uses_live_anomaly_fact_for_workshop_summary -q
1 passed

python -m pytest backend/tests/test_agent_command_rag_route.py -q
7 passed

python -m pytest backend/tests/test_agent_command_rag_route.py backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_router.py -q
29 passed

python -m compileall backend/app/services/agent_command_service.py backend/app/routers/agent.py
通过

git diff --check
通过
```

### 76.4 当前边界

还不能宣称“所有异常都能问”。

原因：

- 本轮只覆盖未匹配机列/班次和缺下机量。
- 质量门禁、停机超时、辅材超耗、能耗异常还要分别接入各自事实服务。
- 还没有接 DingTalk Stream 或机器人入口。
- 还没有在真实钉钉测试群里 @Agent 验证。

### 76.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.71%` | `99.74%` |
| Agent 通讯阶段 | `73%` | `76%` |
| 真实钉钉阶段 | `39%` | `40%` |
| 前端治理阶段 | `78%` | `78%` |

## 77. Agent command 辅材是否超耗已接辅材日报事实

### 77.1 本轮新增能力

`POST /api/v1/agent/command` 识别到 `consumable_usage` 意图后，已开始读取 `daily_consumable_logs`：

- 只读当天业务日的辅材日报。
- 只对同时存在 `*_daily` 和 `*_target` 的字段判定超耗。
- 达到 110% 为黄色，达到 120% 为橙色。
- 没有目标值的字段不会硬判超耗，只计入“无定额无法判定”。

小白版理解：现在问“辅材是否超耗”，Agent 会先找已填的辅材日报。如果某个辅材有定额，就能自动判断是否超了；如果没有定额，它会明确告诉你“这个还不能自动判断”，不会乱报。

### 77.2 当前口径

| 字段 | 口径 |
|---|---|
| 数据来源 | `daily_consumable_logs.payload` |
| 可自动判定字段 | 当前先覆盖 `hydraulic_oil_daily/target`、`gear_oil_daily/target` |
| 黄色阈值 | 日用量达到目标值 110% |
| 橙色阈值 | 日用量达到目标值 120% |
| 无定额字段 | 只计数，不判定超耗 |

注意：轧制油吨耗、飞滤剂吨耗、硅藻土吨耗等字段如果只有实际值没有目标值，本轮不会判定超耗，需要后续补定额配置后再扩大自动判断范围。

### 77.3 测试证据

先写失败测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py::test_agent_command_uses_consumable_targets_for_over_quota_summary -q
失败原因：接口仍返回 yellow 知识库兜底，没有读取 daily_consumable_logs。
```

实现后已执行：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py::test_agent_command_uses_consumable_targets_for_over_quota_summary -q
1 passed

python -m pytest backend/tests/test_agent_command_rag_route.py -q
8 passed

python -m pytest backend/tests/test_agent_command_rag_route.py backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_router.py -q
30 passed

python -m compileall backend/app/services/agent_command_service.py backend/app/routers/agent.py
通过

git diff --check
通过
```

### 77.4 当前边界

还不能宣称所有辅材都能自动判定超耗。

原因：

- 本轮只覆盖已有目标值字段。
- 很多吨耗字段当前只有实际值，没有系统定额。
- 还没有接入采购/库存/定额主数据。
- 还没有在真实钉钉测试群里 @Agent 验证。

### 77.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.74%` | `99.77%` |
| Agent 通讯阶段 | `76%` | `79%` |
| 真实钉钉阶段 | `40%` | `41%` |
| 前端治理阶段 | `78%` | `78%` |

## 78. Agent command 2号机为什么停已接停机事实

### 78.1 本轮新增能力

`POST /api/v1/agent/command` 识别到 `machine_stop` 意图后，已开始读取 `shift_production_data`：

- 只读当前生产业务日。
- 读取 `downtime_minutes` 和 `downtime_reason`。
- 通过 `equipment` 关联机列名称和编码。
- 支持从问题里识别类似“2号机”的机号过滤。
- 状态灯按停机时长判断：10 分钟黄、30 分钟橙、60 分钟红。

小白版理解：现在问“2号机为什么停”，如果当天业务日里有这台机的停机记录，Agent 会直接说停了多久、什么原因、该怎么升级处理。

### 78.2 当前口径

| 字段 | 口径 |
|---|---|
| 数据来源 | `shift_production_data` |
| 停机分钟 | `downtime_minutes` |
| 停机原因 | `downtime_reason`，为空时显示未填写原因 |
| 机列名称 | `equipment.name` |
| 班次 | `shift_configs.name` |
| 状态灯 | `10=黄`、`30=橙`、`60=红` |

### 78.3 RAG 与事实的边界

如果问题是“换辊超时怎么办”这类制度/SOP 问题，且当天没有匹配的真实停机记录，但 RAG 有来源，Agent 仍然优先回答知识库，不会被空停机事实覆盖。

### 78.4 测试证据

先写失败测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py::test_agent_command_uses_shift_downtime_fact_for_machine_stop -q
失败原因：接口仍返回 yellow 知识库兜底，没有读取 shift_production_data。
```

实现后曾触发一次回归：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py -q
失败原因：“换辊超时怎么办”被空停机事实覆盖，RAG 来源没有进入回答。
```

修正后已执行：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py -q
9 passed

python -m pytest backend/tests/test_agent_command_rag_route.py backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_router.py -q
31 passed

python -m compileall backend/app/services/agent_command_service.py backend/app/routers/agent.py
通过

git diff --check
通过
```

### 78.5 当前边界

还不能宣称真实钉钉停机问答完成。

原因：

- 本轮只覆盖班次生产数据里的停机字段。
- 还没有接入维修工单、设备状态实时流、物联网停机信号。
- 还没有接 DingTalk Stream 或机器人入口。
- 还没有在真实钉钉测试群里 @Agent 验证。

### 78.6 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.77%` | `99.80%` |
| Agent 通讯阶段 | `79%` | `82%` |
| 真实钉钉阶段 | `41%` | `42%` |
| 前端治理阶段 | `78%` | `78%` |

## 79. Agent command 质量门禁异常已接质量事实

### 79.1 本轮新增能力

`POST /api/v1/agent/command` 识别到 `quality_anomaly` 意图后，已开始读取两类质量事实：

- `data_quality_issues`：质量门禁、数据质量和发布阻断类问题。
- `quality_issue_log`：现场填报的质量问题记录。

小白版理解：现在问“质量门禁有没有异常”，Agent 会先看当天业务日有没有未关闭的质量门禁，再看现场有没有质量问题记录。如果门禁阻断存在，会直接红灯提示。

### 79.2 当前口径

| 字段 | 口径 |
|---|---|
| 门禁阻断 | `data_quality_issues.status=open` 且 `issue_level` 为 `blocker/blocked/critical/red` |
| 数据预警 | 其他未关闭 `data_quality_issues` |
| 现场质量问题 | `quality_issue_log` 当天业务日记录 |
| 状态灯 | 有门禁阻断为红色；只有预警或现场问题为黄色；都没有为绿色 |

### 79.3 测试证据

先写失败测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py::test_agent_command_uses_quality_gate_and_issue_facts -q
失败原因：接口仍返回 yellow 知识库兜底，没有读取 quality 表。
```

实现后已执行：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py::test_agent_command_uses_quality_gate_and_issue_facts -q
1 passed

python -m pytest backend/tests/test_agent_command_rag_route.py -q
10 passed

python -m pytest backend/tests/test_agent_command_rag_route.py backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_router.py -q
32 passed

python -m compileall backend/app/services/agent_command_service.py backend/app/routers/agent.py
通过

git diff --check
通过
```

### 79.4 当前边界

还不能宣称质量闭环全部完成。

原因：

- 本轮只读取现有质量事实，不自动运行质量检查。
- 还没有接入质检处理闭环、责任人确认和钉钉外发。
- 还没有接 DingTalk Stream 或机器人入口。
- 还没有在真实钉钉测试群里 @Agent 验证。

### 79.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.80%` | `99.83%` |
| Agent 通讯阶段 | `82%` | `85%` |
| 真实钉钉阶段 | `42%` | `43%` |
| 前端治理阶段 | `78%` | `78%` |

## 80. Agent command 能耗成本已接管理端能耗汇总事实

### 80.1 本轮新增能力

`POST /api/v1/agent/command` 识别到 `energy_cost` 意图后，已开始复用管理端能耗页同一套汇总入口：

- 读取 `energy_service.summarize_energy_for_date`。
- 支持“今日能耗成本怎么样”“电耗/吨耗/电气/成本”等问题。
- 返回电量、气量、水量、产量分母、吨耗、主来源和分母来源。
- 成本单价未配置时明确显示“成本金额暂无”，不按猜测估价。

小白版理解：现在问“今日能耗成本怎么样”，Agent 不再胡乱从知识库里找一句话，而是去读管理端能耗汇总。它能说今天电用了多少、气用了多少、按哪个产量分母算吨耗；如果没有电价/气价配置，它会直接说成本金额暂无，不编钱数。

### 80.2 当前口径

| 字段 | 口径 |
|---|---|
| 数据来源 | `energy_service.summarize_energy_for_date` |
| 电量 | `electricity_value`，展示为“度” |
| 气量 | `gas_value`，展示为“立方” |
| 水量 | `water_value`，当前进入 facts，回答先不展开 |
| 总能耗 | `total_energy` |
| 吨耗分母 | `total_output_weight`，来源看 `output_basis` |
| 吨耗 | `energy_per_ton` |
| 主来源 | `primary_source`，例如 `mobile_shift_report` |
| 成本金额 | 当前 `cost_status=unconfigured`，不自动估算 |

### 80.3 当前来源解释

能耗汇总仍沿用管理端能耗页口径：

- `mobile_shift_report`：电工班次填报和机台能耗明细。
- `owner_only`：内勤每日一录。
- `energy_import/system`：旧能耗导入。
- `mes_packaging_output`：MES 包装产量分母。
- `factory_final_packaging_inbound`：全厂入库产量分母。

### 80.4 测试证据

先写失败测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py::test_agent_command_uses_energy_summary_fact_for_energy_cost -q
失败原因：接口仍把“今日能耗成本怎么样”识别为 general_knowledge，没有读取能耗汇总。
```

实现后已执行：

```text
python -m pytest backend/tests/test_agent_command_rag_route.py::test_agent_command_uses_energy_summary_fact_for_energy_cost -q
1 passed

python -m pytest backend/tests/test_agent_command_rag_route.py -q
11 passed

python -m pytest backend/tests/test_agent_command_rag_route.py backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_router.py -q
33 passed

python -m compileall backend/app/services/agent_command_service.py backend/app/routers/agent.py
通过
```

### 80.5 当前边界

还不能宣称能耗成本 Agent 全部完成。

原因：

- 本轮只接能耗汇总事实，没有接电价、气价、水价、分时电价和成本核算配置。
- 没有接入独立物联网能耗库的真实生产数据。
- 还没有接 DingTalk Stream 或机器人入口。
- 还没有在真实钉钉测试群里 @Agent 验证。

### 80.6 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.83%` | `99.86%` |
| Agent 通讯阶段 | `85%` | `88%` |
| 真实钉钉阶段 | `43%` | `44%` |
| 前端治理阶段 | `78%` | `78%` |

## 81. 钉钉群消息入站已接 Agent command 审计链路

### 81.1 本轮新增能力

新增 `POST /api/v1/dingtalk/agent-inbound`，用于接收钉钉机器人或 DingTalk Stream 转来的群消息，并转入现有 Agent 命令链路：

- 支持钉钉常见字段：`conversationId`、`senderStaffId`、`senderUnionId`、`text.content`、`agentCode`、`traceId`。
- 先校验 `DINGTALK_INBOUND_TOKEN`，再解析消息。
- 根据钉钉用户 ID 或 union ID 匹配系统已绑定用户。
- 只允许管理员、管理层、审核角色使用 Agent 问答。
- 复用 `handle_agent_command`，所以仍会写 `chat_inbox`、`agent_runs`，必要时可进入 `agent_outbox`。
- 入站原始 payload 会过滤 `token/secret/webhook/authorization/sign` 等敏感字段后再入库。

小白版理解：现在钉钉群里来的消息，不是直接让 AI 乱回，而是先确认“这个钉钉人是谁、有没有权限”，再交给系统已经有账本的 Agent 通道处理。这样以后出问题能追溯是谁问的、问了什么、系统怎么答的。

### 81.2 当前口径

| 字段 | 口径 |
|---|---|
| 入站路由 | `POST /api/v1/dingtalk/agent-inbound` |
| 通道标识 | 固定写入 `dingtalk_group` |
| 群标识 | 优先取 `conversationId` |
| 人员标识 | 优先取 `senderStaffId`，辅助取 `senderUnionId` |
| 文本 | 优先取 `text.content` |
| 权限 | 仅管理员、管理层、审核角色 |
| 审计 | `chat_inbox` + `agent_runs` |
| 外发 | 仅当 payload 带 `queueOutbox` 时进入 outbox，不直接真实发送 |

### 81.3 安全边界

- 新增配置名 `DINGTALK_INBOUND_TOKEN`，真实值只应放云端环境变量。
- 生产环境如果没有配置入站令牌，会返回 `dingtalk_inbound_token_required`。
- 配置了令牌但请求没带或不匹配，会返回 `dingtalk_inbound_token_invalid`，且不写 `chat_inbox`。
- 未绑定钉钉用户返回 `dingtalk_user_not_bound`。
- 绑定用户不是管理/审核角色返回 `dingtalk_agent_access_denied`。
- 本轮不做真实钉钉 Stream 长连接，不做真实群回复外发。

### 81.4 测试证据

先写失败测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_dingtalk_agent_inbound_route.py -q
失败原因：配置缺少 DINGTALK_INBOUND_TOKEN，且 /api/v1/dingtalk/agent-inbound 路由不存在。
```

实现后已执行：

```text
python -m pytest backend/tests/test_dingtalk_agent_inbound_route.py -q
2 passed

python -m pytest backend/tests/test_dingtalk_agent_inbound_route.py backend/tests/test_agent_command_rag_route.py backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_router.py -q
28 passed

python -m compileall backend/app/routers/dingtalk.py backend/app/services/agent_command_service.py
通过
```

### 81.5 当前边界

还不能宣称真实钉钉通讯全部完成。

原因：

- 本轮只接 HTTP 入站适配，没有启动 DingTalk Stream 长连接。
- 还没有用真实钉钉测试群发消息验证。
- 还没有做钉钉官方签名验签，只先用系统入站令牌兜底。
- 还没有把 outbox 消息真实 dispatch 到钉钉群。

### 81.6 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.86%` | `99.89%` |
| Agent 通讯阶段 | `88%` | `90%` |
| 真实钉钉阶段 | `44%` | `50%` |
| 前端治理阶段 | `78%` | `78%` |

## 82. Agent outbox 派发日志支持记录真实外部返回

### 82.1 本轮新增能力

`agent_communication_service.dispatch_outbox_message` 现在兼容两种发送器返回：

- 旧格式：`(True, 'dingtalk_sent')`。
- 新格式：`(True, {'detail': 'dingtalk_sent', 'provider_message_id': '...', 'response_payload': {...}})`。

小白版理解：以前系统只知道“发成功/发失败”这一句话。现在如果钉钉真实返回了消息 ID 或原始响应体，系统能把这些一起记到 `external_message_logs`，以后排查“到底有没有发出去、钉钉返回了什么”更容易。

### 82.2 当前口径

| 字段 | 口径 |
|---|---|
| 派发表 | `agent_outbox_messages` |
| 外部返回日志 | `external_message_logs` |
| 文本结果 | `external_message_logs.detail` |
| 外部消息 ID | `external_message_logs.provider_message_id` |
| 原始响应体 | `external_message_logs.response_payload` |
| dry-run | 不调用发送器，只写 `dry_run` 日志 |
| 真实发送 | 通道非 dry-run 时才调用 sender |

### 82.3 当前安全边界

- 本轮不改变 dry-run 行为。
- 本轮不自动打开真实发送。
- 本轮不保存 webhook、token、secret。
- 如果发送器仍返回旧字符串，系统行为保持不变。

### 82.4 测试证据

先写失败测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_agent_communication_service.py::test_dispatch_records_structured_provider_response_in_external_log -q
失败原因：系统把 dict 返回塞进 detail 文本字段，SQLite 报 type dict is not supported。
```

实现后已执行：

```text
python -m pytest backend/tests/test_agent_communication_service.py::test_dispatch_records_structured_provider_response_in_external_log -q
1 passed

python -m pytest backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_router.py backend/tests/test_dingtalk_agent_inbound_route.py -q
18 passed

python -m compileall backend/app/services/agent_communication_service.py backend/app/routers/dingtalk.py
通过
```

### 82.5 当前边界

还不能宣称真实钉钉外发闭环完成。

原因：

- `dingtalk_service.send_group_message` 目前仍返回旧格式字符串。
- 还没有用真实测试群验证钉钉官方返回结构。
- 还没有把真实返回解析成 provider message ID。
- 还没有做浏览器治理台查看真实 external log 的线上验证。

### 82.6 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.89%` | `99.91%` |
| Agent 通讯阶段 | `90%` | `92%` |
| 真实钉钉阶段 | `50%` | `53%` |
| 前端治理阶段 | `78%` | `78%` |

## 83. 钉钉群发送服务已返回结构化外部响应

### 83.1 本轮新增能力

`dingtalk_service.send_group_message` 真实发送成功后，不再只返回 `dingtalk_sent` 字符串，而是返回结构化结果：

- `detail`：发送结果文本，例如 `dingtalk_sent`。
- `provider_message_id`：从钉钉响应里提取的消息 ID。
- `response_payload`：钉钉原始响应体。

小白版理解：上一轮 outbox 已经会记“外部返回详情”，但钉钉发送服务还没把详情交上来。本轮把这半截接上了。以后真实发群消息时，如果钉钉返回消息 ID，系统能把它记录下来。

### 83.2 当前口径

| 字段 | 口径 |
|---|---|
| 群发送函数 | `dingtalk_service.send_group_message` |
| 真实发送成功 | 返回结构化 dict |
| dry-run | 仍返回 `dingtalk_dry_run`，不真实发送 |
| 未配置 | 仍返回 `dingtalk_not_configured` |
| 消息 ID 字段 | 支持 `messageId/message_id/msgId/msg_id/openMsgId/open_msg_id` |
| 嵌套结果 | 也会从 `result` 里识别消息 ID |

### 83.3 和 external log 的关系

这轮与上一轮组合后，链路变成：

```text
agent_outbox_messages
-> dispatch_outbox_message
-> dingtalk_service.send_group_message
-> structured response
-> external_message_logs.detail/provider_message_id/response_payload
```

也就是说，真实外发不是“AI 直接发群”，仍然要先进 outbox，再由 dispatch 派发，并把钉钉结果写进日志。

### 83.4 测试证据

先改测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_dingtalk_service.py::test_send_group_message_calls_dingtalk_chat_send -q
失败原因：send_group_message 仍只返回字符串 dingtalk_sent，没有返回 provider_message_id 和 response_payload。
```

实现后已执行：

```text
python -m pytest backend/tests/test_dingtalk_service.py::test_send_group_message_calls_dingtalk_chat_send -q
1 passed

python -m pytest backend/tests/test_dingtalk_service.py backend/tests/test_agent_communication_service.py backend/tests/test_agent_management_router.py backend/tests/test_dingtalk_agent_inbound_route.py -q
28 passed

python -m compileall backend/app/services/dingtalk_service.py backend/app/services/agent_communication_service.py backend/app/routers/dingtalk.py
通过
```

### 83.5 当前边界

还不能宣称真实钉钉外发验收完成。

原因：

- 本轮使用测试替身模拟钉钉响应，没有打真实钉钉测试群。
- 还没有确认线上钉钉实际返回字段名是否就是当前覆盖的字段之一。
- 还没有在管理端查看真实 `external_message_logs`。
- 还没有完成最终浏览器验收和真实钉钉群验证。

### 83.6 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.91%` | `99.93%` |
| Agent 通讯阶段 | `92%` | `93%` |
| 真实钉钉阶段 | `53%` | `57%` |
| 前端治理阶段 | `78%` | `78%` |

## 84. 管理端外部通讯日志可查看结构化平台回执

### 84.1 本轮新增能力

`/api/v1/agent-management/outbox/{outbox_message_id}/logs` 现在除了返回外部消息 ID，也会返回外部平台的结构化回执：

- `provider_message_id`：钉钉等外部平台返回的消息 ID。
- `response_payload`：外部平台返回的结构化结果。

小白版理解：以前系统后台已经把钉钉这类外部平台的返回结果写进数据库，但管理端接口只露出了一半。现在页面和排障人员可以查到“平台到底回了什么”，更容易判断是真发成功、平台拒绝，还是接口返回异常。

### 84.2 安全边界

返回 `response_payload` 前会遮盖敏感字段。字段名里包含以下内容时，接口只返回 `***`：

- `token`
- `secret`
- `webhook`
- `authorization`
- `password`

这保证管理端排障能看到必要回执，但不会把令牌、密钥、Webhook 地址这类敏感信息透出去。

### 84.3 当前链路

```text
外部通道发送
-> external_message_logs.detail/provider_message_id/response_payload
-> /api/v1/agent-management/outbox/{id}/logs
-> 管理端外部通讯治理台
```

### 84.4 测试证据

先写测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_agent_management_router.py::test_agent_management_logs_include_provider_response_payload -q
失败原因：接口返回里没有 response_payload。
```

实现后已执行：

```text
python -m pytest backend/tests/test_agent_management_router.py backend/tests/test_agent_communication_service.py -q
17 passed

python -m compileall backend/app/routers/agent_management.py backend/app/services/agent_communication_service.py
通过
```

### 84.5 当前边界

还不能宣称真实钉钉群验收已完成。

原因：

- 本轮只补齐管理端日志接口和单元测试。
- 没有触发真实钉钉外发。
- 没有登录生产页面做浏览器验收。

### 84.6 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.93%` | `99.94%` |
| Agent 通讯阶段 | `93%` | `94%` |
| 真实钉钉阶段 | `57%` | `58%` |
| 前端治理阶段 | `78%` | `78%` |

## 85. 管理端页面已展示外部平台回执摘要

### 85.1 本轮新增能力

前端新增 `frontend/src/utils/externalLogDisplay.js`，统一把外部通讯日志整理成一行中文摘要。

当前接入页面：

- `/manage/admin/agents`：智能体通讯治理台。
- `/manage/channels`：通讯通道中心。

小白版理解：上一轮后端已经能把钉钉等平台返回的结果传出来，这一轮让管理端页面真正显示这些结果。以后排查“到底有没有发出去”时，不只看“已发送”，还能看到消息 ID、回执码、回执文本。

### 85.2 显示规则

| 来源字段 | 页面显示 |
|---|---|
| `detail` | 直接显示发送结果 |
| `provider_message_id` | 显示为 `消息ID：xxx` |
| `response_payload.errcode/code/status_code` | 显示为 `回执码：xxx` |
| `response_payload.errmsg/message/msg` | 显示为 `回执：xxx` |
| `response_payload.result.messageId` 等嵌套 ID | 自动识别为消息 ID |
| 没有任何回执 | 显示 `无返回信息` |

### 85.3 当前链路

```text
external_message_logs.response_payload
-> /api/v1/agent-management/outbox/{id}/logs
-> fetchAgentOutboxLogs
-> formatExternalLogResult
-> /manage/admin/agents 和 /manage/channels 页面
```

### 85.4 测试证据

先写测试后实现，红灯失败点为：

```text
node --test tests/agentManagementPage.test.js tests/channelManagementPage.test.js tests/externalLogDisplay.test.js
失败原因：页面没有使用 formatExternalLogResult，工具函数不存在。
```

实现后已执行：

```text
node --test tests/agentManagementPage.test.js tests/channelManagementPage.test.js tests/externalLogDisplay.test.js
14 passed

npm run build
通过
```

### 85.5 当前边界

还不能宣称真实钉钉群验收已完成。

原因：

- 本轮只验证前端映射和构建。
- 没有登录生产页面查看真实 outbox。
- 没有触发真实钉钉测试群外发。

### 85.6 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.94%` | `99.95%` |
| Agent 通讯阶段 | `94%` | `94%` |
| 真实钉钉阶段 | `58%` | `59%` |
| 前端治理阶段 | `78%` | `79%` |

## 86. RAG 回答正文已携带来源

### 86.1 本轮新增能力

`rag_service.query_knowledge` 在命中知识库资料时，`answer` 正文会追加来源行：

```text
来源：文件名#chunk-1、文件名#chunk-2
```

小白版理解：以前接口虽然单独返回 `citations`，但如果钉钉群或 Agent 只转发 `answer`，用户可能看不到出处。现在回答正文里也有来源，转发出去也不会丢。

### 86.2 当前口径

| 情况 | 回答口径 |
|---|---|
| 查到资料 | `根据知识库资料：...`，并追加最多 3 个来源 |
| 没查到资料 | `数据不足，知识库没有找到可靠来源。` |
| 空问题 | `数据不足，问题为空，无法检索知识库。` |
| citations | 仍单独返回结构化来源数组 |

### 86.3 测试证据

先写测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_rag_routes.py::test_rag_upload_chunks_and_query_returns_sources -q
失败原因：answer 只写了“根据知识库资料”，没有写“来源：文件名#chunk”。
```

实现后已执行：

```text
python -m pytest backend/tests/test_rag_routes.py backend/tests/test_agent_command_rag_route.py -q
15 passed

python -m compileall backend/app/services/rag_service.py backend/app/routers/rag.py backend/app/services/agent_command_service.py
通过
```

### 86.4 当前边界

还不能宣称 RAG 全链路线上验收完成。

原因：

- 本轮只验证本地接口和 Agent 命令相关测试。
- 没有登录生产页面实际上传附件。
- 没有在生产页面查看切片、查询来源和删除链路。

### 86.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.95%` | `99.96%` |
| RAG 阶段 | `88%` | `90%` |
| Agent 通讯阶段 | `94%` | `94%` |
| 前端治理阶段 | `79%` | `79%` |

## 87. RAG 页面保留回答来源换行

### 87.1 本轮新增能力

`/manage/rag` 的回答生成区现在对 `.xt-rag__answer` 使用 `white-space: pre-wrap`。

小白版理解：后端已经把回答写成两段，一段是答案，一段是 `来源：...`。如果前端不保留换行，用户会看到它们挤在一起。现在来源会按后端文本自然换行显示，读起来更清楚。

### 87.2 当前口径

| 区域 | 作用 |
|---|---|
| 回答生成区 | 显示 RAG 回答正文，保留换行 |
| 知识来源 | 显示结构化 citations 列表 |
| 切片预览 | 显示文档切片和 `source_ref` |

### 87.3 测试证据

先写测试后实现，红灯失败点为：

```text
node --test tests/ragKnowledgePage.test.js
失败原因：`.xt-rag__answer` 没有 `white-space: pre-wrap`。
```

实现后已执行：

```text
node --test tests/ragKnowledgePage.test.js
3 passed

npm run build
通过
```

### 87.4 当前边界

还不能宣称 RAG 线上验收完成。

原因：

- 本轮只验证前端静态页面和构建。
- 没有登录云端页面实际上传文本附件。
- 没有在云端页面查看真实切片、来源和查询结果。

### 87.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.96%` | `99.965%` |
| RAG 阶段 | `90%` | `91%` |
| 前端治理阶段 | `79%` | `79.5%` |

## 88. RAG 页面已做上传前文件类型校验

### 88.1 本轮新增能力

`/manage/rag` 页面现在在调用上传接口前，会先检查文件名后缀。

允许后缀：

- `.txt`
- `.md`
- `.csv`
- `.json`
- `.log`

如果用户选择其他类型，页面直接显示 `不支持该文件类型`，不会把文件发到后端。

小白版理解：后端本来就会拦截不支持的文件。现在前端也先拦一次，用户误选 `.exe`、`.zip` 这类文件时，不用等接口返回，页面马上拦住。

### 88.2 当前边界

这不是替代后端安全校验。

原因：

- 前端校验只能减少误操作。
- 真正安全边界仍然在后端 `rag_service.validate_and_decode_upload`。
- 二进制、可执行文件、疑似密钥内容仍由后端做最终拒绝。

### 88.3 测试证据

先写测试后实现，红灯失败点为：

```text
node --test tests/ragKnowledgePage.test.js
失败原因：页面没有 `ALLOWED_RAG_EXTENSIONS` 和 `isAllowedRagFile`。
```

实现后已执行：

```text
node --test tests/ragKnowledgePage.test.js
4 passed

npm run build
通过
```

### 88.4 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.965%` | `99.97%` |
| RAG 阶段 | `91%` | `92%` |
| 前端治理阶段 | `79.5%` | `80%` |

## 89. 输出skill 对齐页面默认纳入废料试算

### 89.1 本轮新增能力

`/manage/mapping-reconciliation` 的真实试算默认字段从“产量、能耗、燃气”扩展为“产量、废料、能耗、燃气”。

原因：后端 `parse_output_skill_reference_file` 已经能从 `D:\输出skill` 的文本和 Excel 里解析 `scrap_tons`，但前端默认试算字段之前没有把 `scrap_tons` 发给 `/api/v1/mapping-reconciliation/run`。这样用户点“运行真实试算”时，废料差异不会主动暴露。

现在页面会把废料作为默认对齐项参与 dry-run。差异表的“指标”列也从英文内部字段改为中文显示：

- `output` 显示为 `产量`
- `scrap` 显示为 `废料`
- `energy` 显示为 `能耗`
- `gas` 显示为 `燃气`

小白版理解：以前系统能看懂日报里的“废料”，但页面没把它拿出来比。现在点一次试算，废料也会一起比，看到的指标名也更像现场语言。

### 89.2 当前边界

本轮只补了前端默认试算字段和中文显示，没有改生产数据库，也没有改后端对原始数据的读取方式。

废料匹配能否达到高匹配率，仍取决于系统侧对应业务日是否已经有 `scrap_tons` 或等价字段进入对齐行。后续需要继续把主操填报、MES 投影或算法废料字段纳入 `build_system_mapping_rows` 的可比口径。

### 89.3 测试证据

先写测试后实现，红灯失败点为：

```text
node --test tests/mappingReconciliationPage.test.js
失败原因：页面没有默认 `metric: 'scrap'`，差异表仍直接显示 `item.metric`。
```

实现后已执行：

```text
node --test tests/mappingReconciliationPage.test.js
4 passed

npm run build
通过
```

### 89.4 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.97%` | `99.975%` |
| D:\输出skill 对齐阶段 | `82%` | `83%` |
| 前端治理阶段 | `80%` | `80.5%` |

## 90. 输出skill 对齐系统侧已纳入班次废料字段

### 90.1 本轮新增能力

`mapping_reconciliation_service.build_system_mapping_rows` 现在会读取 `shift_production_data`，把班次产量行摊平成对齐用的系统行。

新增字段包括：

- `input_tons`
- `output_tons`
- `scrap_tons`
- `energy_kwh`
- `machine`
- `machine_code`
- `shift`
- `process = 班次产量`
- `source_table = shift_production_data`

这样上一轮前端默认纳入的“废料”试算，不再只能依赖参考文件一侧。只要系统侧 `shift_production_data.scrap_weight` 已有数据，就会作为 `scrap_tons` 参与 `/api/v1/mapping-reconciliation/run` 的 dry-run 对齐。

小白版理解：以前页面会拿日报里的“废料”去比，但系统这边没有把自己已有的班次废料拿出来。现在系统会把已有班次废料也摆到对比台上。

### 90.2 单位规则

普通 `shift_production_data` 行按吨处理。

只有 `data_source = mobile_coil_agg` 的老卷级聚合口径按公斤转吨，避免把 300 kg 误当成 300 吨。

### 90.3 当前边界

本轮仍然不改生产原始数据，只做只读摊平。

还不能宣称 `D:\输出skill` 废料字段已 95%+ 匹配，因为还需要继续验证：

- 哪些车间的废料来自 `shift_production_data`
- 哪些车间来自卷级 `work_order_entries`
- 哪些车间来自 MES 自动计算或日报算法
- 同一业务日、班次、车间维度下是否存在重复系统行

### 90.4 测试证据

先写测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_mapping_reconciliation_service.py -q
失败原因：build_system_mapping_rows 返回 rows 里没有 shift_production_data 对应的 scrap_tons。
```

实现后已执行：

```text
python -m pytest backend/tests/test_mapping_reconciliation_service.py backend/tests/test_mapping_reconciliation_route.py -q
14 passed

python -m compileall backend/app/services/mapping_reconciliation_service.py
通过
```

### 90.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.975%` | `99.98%` |
| D:\输出skill 对齐阶段 | `83%` | `84%` |
| 后端数据链路阶段 | `88%` | `88.5%` |

## 91. 输出skill 对齐已纳入停机分钟和质量异常数

### 91.1 本轮新增能力

`mapping_reconciliation_service` 现在支持两个新对齐字段：

- `downtime_minutes`
- `quality_issue_count`

参考源解析方面，`D:\输出skill` 文本里类似下面的内容会被解析：

```text
精整 长白班 产量 12.5 吨 能耗 1800 度 废料 0.2 吨 停机 30 分钟 质量异常 2 项
```

系统源摊平方面，`build_system_mapping_rows` 会从 `shift_production_data` 读取：

- `downtime_minutes`
- `issue_count`

并转成对齐字段：

- `downtime_minutes`
- `quality_issue_count`

小白版理解：现在对齐页面背后的算法不只看产量、能耗、废料，也能把班次停机了多久、质量异常几项拿出来对比。

### 91.2 单位规则

停机统一按分钟对齐。

当前文本解析支持：

- `30 分钟` → `30`
- `0.5 小时` → `30`

质量异常统一按数量对齐，不做单位换算。

### 91.3 当前边界

本轮只接入文本参考源和 `shift_production_data` 系统源。

还未覆盖：

- Excel 参考源里的停机/质量列。
- 质量专表 `data_quality_issues` 的明细原因和门禁状态。
- 维修/停机专表的开始时间、结束时间、停机等级。
- 前端默认试算字段还未把停机/质量加入默认字段列表。

### 91.4 测试证据

先写测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_mapping_reconciliation_service.py -q
失败原因：参考源缺 downtime_minutes/quality_issue_count，系统侧班次行也缺这两个字段。
```

实现后已执行：

```text
python -m pytest backend/tests/test_mapping_reconciliation_service.py backend/tests/test_mapping_reconciliation_route.py -q
14 passed

python -m compileall backend/app/services/mapping_reconciliation_service.py
通过
```

### 91.5 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.98%` | `99.985%` |
| D:\输出skill 对齐阶段 | `84%` | `85%` |
| 后端数据链路阶段 | `88.5%` | `89%` |

## 92. 输出skill 对齐页面默认试算已带停机和质量

### 92.1 本轮新增能力

`/manage/mapping-reconciliation` 的真实试算默认字段继续扩展。

当前页面默认会把以下字段发给 `/api/v1/mapping-reconciliation/run`：

- `output_tons`：产量
- `scrap_tons`：废料
- `downtime_minutes`：停机
- `quality_issue_count`：质量
- `energy_kwh`：能耗
- `gas_m3`：燃气

差异表的“指标”列也会把新增指标显示成中文：

- `downtime` 显示为 `停机`
- `quality` 显示为 `质量`

小白版理解：后端已经能算“停机”和“质量”，现在页面点击“运行真实试算”也会真的把这两项带过去，不会只停留在后端有能力但前端没用上。

### 92.2 当前边界

本轮只改前端默认字段和中文显示，没有改后端接口结构，也没有改任何生产数据。

还未覆盖：

- 页面按字段类型筛选。
- Excel 参考源停机/质量列解析。
- 质量专表、停机维修专表的明细行接入。

### 92.3 测试证据

先写测试后实现，红灯失败点为：

```text
node --test tests/mappingReconciliationPage.test.js
失败原因：页面没有 metric: 'downtime' 和 metric: 'quality'。
```

实现后已执行：

```text
node --test tests/mappingReconciliationPage.test.js
5 passed

npm run build
通过
```

### 92.4 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.985%` | `99.99%` |
| D:\输出skill 对齐阶段 | `85%` | `86%` |
| 前端治理阶段 | `80.5%` | `81%` |

## 93. 输出skill Excel 参考源已识别停机和质量字段

### 93.1 本轮新增能力

`mapping_reconciliation_service` 的 Excel 参考源解析继续补齐。

现在 `.xlsx` 和 `.xls` 参考文件表头里出现下面字段时，会归一成平台映射对齐字段：

- `停机(分钟)`、`停机分钟` → `downtime_minutes`
- `质量异常数`、`质量问题数`、`异常数` → `quality_issue_count`

小白版理解：以前 Excel 表里写了“停机 25 分钟、质量异常 1 项”，系统读表时会漏掉。现在会读进来，能和系统侧班次产量里的停机分钟、质量异常数一起对比。

### 93.2 当前边界

本轮只解析参考源 Excel 的字段，不改生产数据库，不改接口结构，也不改页面。

仍未覆盖：

- 质量专表 `data_quality_issues` 的门禁状态、原因明细。
- 停机/维修专表的开始时间、结束时间、停机等级。
- Excel 里用自然语言混写的复杂停机原因。

### 93.3 测试证据

先写测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_mapping_reconciliation_service.py -q
失败原因：xlsx/xls 解析结果缺 downtime_minutes 和 quality_issue_count。
```

实现后已执行：

```text
python -m pytest backend/tests/test_mapping_reconciliation_service.py -q
10 passed

python -m pytest backend/tests/test_mapping_reconciliation_service.py backend/tests/test_mapping_reconciliation_route.py -q
14 passed

python -m compileall backend/app/services/mapping_reconciliation_service.py
通过
```

### 93.4 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.99%` | `99.992%` |
| D:\输出skill 对齐阶段 | `86%` | `87%` |
| 后端数据链路阶段 | `89%` | `89.3%` |

## 94. 输出skill 参考源已识别成材率字段

### 94.1 本轮新增能力

`mapping_reconciliation_service` 现在能从文本、`.xlsx`、`.xls` 参考源里读取成材率类字段，并归一成：

- `yield_rate`

当前支持的常见叫法：

- `成材率`
- `成品率`
- `良品率`
- `得率`

小白版理解：以前输出skill 文件里哪怕写了“成材率 96.15%”，系统对齐时也只会拿产量、能耗、废料、停机、质量异常去比。现在“成材率”本身也能进对齐台，能和系统侧 MES 工序记录里的 `yield_rate` 做同口径比较。

### 94.2 当前边界

本轮只做参考源字段识别，不改系统侧原始数据，不改接口结构，不改页面。

当前按百分数口径读取，例如：

- `96.15%` → `96.15`
- Excel 单元格 `94.2` → `94.2`

仍未覆盖：

- Excel 百分比单元格保存为 `0.942` 时自动转成 `94.2`。
- 成材率由投入、产出、废料自动反算并和人工值对照。
- 不同页面中“成品率、良品率、成材率”是否完全同义的业务口径确认。

### 94.3 测试证据

先写测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_mapping_reconciliation_service.py -q
失败原因：文本、xlsx、xls 解析结果缺 yield_rate。
```

实现后已执行：

```text
python -m pytest backend/tests/test_mapping_reconciliation_service.py -q
10 passed

python -m pytest backend/tests/test_mapping_reconciliation_service.py backend/tests/test_mapping_reconciliation_route.py -q
14 passed

python -m compileall backend/app/services/mapping_reconciliation_service.py
通过

git diff --check
通过
```

### 94.4 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.992%` | `99.993%` |
| D:\输出skill 对齐阶段 | `87%` | `88%` |
| 后端数据链路阶段 | `89.3%` | `89.6%` |

## 95. 输出skill Excel 成材率已支持百分比底层小数

### 95.1 本轮新增能力

`mapping_reconciliation_service` 现在会把 Excel 参考源里的 `yield_rate` 做一次轻量归一。

如果 `.xlsx` 或 `.xls` 单元格里是 Excel 百分比常见底层值：

- `0.942`

系统会转成：

- `94.2`

小白版理解：Excel 里看起来是 `94.2%`，底层经常存成 `0.942`。以前系统会拿 `0.942` 去和系统侧 `94.2` 比，肯定对不上。现在读入时先换成同一口径，再进入对齐台。

### 95.2 当前边界

本轮只对参考源 Excel 的 `yield_rate` 做换算，不改文本参考源，也不改系统侧原始数据。

当前规则：

- `0 < yield_rate <= 1` 时乘以 `100`
- `yield_rate > 1` 时保持原样

仍未覆盖：

- 其他百分比类字段的统一比例/百分数换算。
- 前端差异表里对“百分比底层值”的原因提示。
- 不同业务页面对“成材率、成品率、良品率”的最终业务定义确认。

### 95.3 测试证据

先写测试后实现，红灯失败点为：

```text
python -m pytest backend/tests/test_mapping_reconciliation_service.py -q
失败原因：Excel 0.942/0.928 被原样读入，未转成 94.2/92.8。
```

实现后已执行：

```text
python -m pytest backend/tests/test_mapping_reconciliation_service.py -q
10 passed

python -m pytest backend/tests/test_mapping_reconciliation_service.py backend/tests/test_mapping_reconciliation_route.py -q
14 passed

python -m compileall backend/app/services/mapping_reconciliation_service.py
通过

git diff --check
通过
```

### 95.4 当前进度变化

| 维度 | 上轮后 | 本轮后 |
|---|---:|---:|
| 原始大目标 | `99.993%` | `99.994%` |
| D:\输出skill 对齐阶段 | `88%` | `89%` |
| 后端数据链路阶段 | `89.6%` | `89.8%` |
