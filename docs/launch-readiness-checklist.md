# 上线试用就绪清单（前端重构版）

## A. 构建与可达性

- [x] `npm --prefix frontend run build` 通过
- [x] `/login` 可访问
- [x] `/entry` 可访问
- [x] `/review/overview` 可访问
- [x] `/review/factory`、`/review/workshop` 可访问
- [x] legacy 路径（`/mobile/*`、`/dashboard/*`）可兼容跳转

## B. 权限边界

- [x] fill-only 角色登录后默认落地 `/entry`
- [x] fill-only 访问 `/review/*` 被拦截并回跳 `/entry`
- [x] 管理/审阅角色可访问 review + desktop 配置面
- [x] 未登录访问受保护路由会回到 `/login`

## C. 核心页面

- [x] 登录页具备角色入口感知
- [x] 总览中心具备 KPI + 快捷入口 + 风险摘要
- [x] 总览中心具备 AI 今日摘要 + AI 风险摘要专题卡
- [x] 审阅中心首页为任务化视图（待审/已审/驳回）
- [x] 数据接入中心统一展示数据源状态、映射、历史、成功率
- [x] 数据接入中心具备 AI 字段映射建议 + 错误解释专题卡
- [x] 成本中心已接入策略引擎（非静态页）
- [x] AI 大脑中心已可访问

## D. 成本策略引擎

- [x] 铸造策略可跑（CASTING_MACHINE_LABOR_SPLIT）
- [x] 精整策略可跑（FINISHING_PARALLEL_PROCESS）
- [x] 热轧策略可跑（HOT_ROLLING_SHIFT_DAILY）
- [x] 拉矫策略可跑（TENSION_LEVELING_MAIN_PLUS_AUX）
- [x] 损耗双口径策略可跑（LOSS_DUAL_CALIBER）
- [x] 支持按产量 / 通货量口径切换
- [x] 成本中心展示价格主数据、表模型快照、校差记录

## E. AI 与运维

- [x] AI 抽屉可在壳层打开
- [x] Brain Center 展示摘要/风险/成本/接入/运维
- [x] 运维页可见 health/probe/version/错误率骨架

## F. 验证与记录

- [x] 关键 e2e 通过（按当前可运行子集）
- [x] 视觉审计脚本执行并有产物
- [x] `docs/known-gaps-and-todos.md` 已记录遗留项
