# Aluminum-Bypass 角色矩阵与首批 SOP 设计

## 1. 文档目标

本文件定义 `aluminum-bypass` 在“长期 AI 产品体系”中的角色分层、当前仓库映射、以及首批优先 SOP。

本文件明确采用**双层结构**：

1. **长期可复用层**：以后类似制造业 AI 项目都可以复用的角色与职责骨架。
2. **aluminum-bypass 项目层**：当前仓库里真实存在的角色、页面、接口、遗留债务与上线约束。

> 已锁定边界：**统计员不是正式业务角色**。`statistician / stat / reviewer` 只允许作为 brownfield 兼容残留被记录，不得再作为长期业务角色继续设计。

## 2. 2026-04-06 当前 brownfield 证据

### 2.1 运行与 readiness 事实

- `docker compose ps`：`db / backend / nginx` 均为 `Up`。
- `curl -sk https://localhost/healthz`：返回 `ok`。
- `curl -sk -i https://localhost/readyz`：返回 `503 not_ready`。
- 2026-04-06 当下 `/readyz` 硬阻断：
  - `EQUIPMENT_USER_BINDING_INVALID`
  - `SCHEDULE_EMPTY`
- `docker compose run --rm backend sh -lc "pytest -q"`：`5 failed, 238 passed, 1 warning`。

### 2.2 当前角色与语义债务证据

- `backend/app/core/scope.py`
  - 仍把 `statistician / stat / reviewer` 视为 `REVIEWER_ROLES`。
  - 移动端角色仍混用 `team_leader / deputy_leader / mobile_user / shift_leader`。
- `backend/app/core/permissions.py`
  - 仍保留 `assert_reviewer_access()` / `get_current_reviewer_user()`。
- `frontend/src/views/Layout.vue`
  - 仍显示“统计审核看板”“审核端”等旧流程语义。
- `frontend/src/router/index.js`
  - 仍保留 `dashboard/statistics`、`review` access 等历史审核流入口，并存在多处标题乱码。
- `frontend/src/utils/display.js`
  - 仍把 `statistician / stat / reviewer` 作为正式角色标签展示。
- `README.md`
  - 仍写“后台审核台负责 review / reject / confirm”，且文档索引仍指向失效的 Windows 绝对路径。

### 2.3 可直接复用的现有 SOP / rollout 资产

- `docs/pilot-readiness-checklist.md`
- `docs/pilot-sop-minimal.md`
- `docs/pilot-anomaly-sop-minimal.md`
- `docs/workflow-rollout.md`

这些文件证明：当前仓库已经具备**试点值班 SOP 雏形**，但还没有形成“长期可复用角色体系 + repo 现实映射”的统一口径。

## 3. 角色体系：长期可复用层

### 3.1 正式角色层次

| 层级 | 正式角色 | 核心职责 | 是否首批优先 |
| --- | --- | --- | --- |
| 终端业务执行 | `worker` | 采集并提交原始生产事实，不做中间汇总 | 是 |
| 终端业务执行 | `team-lead` | 组织当班填报、处理退回、兜底补报、确认班次完整性 | 是 |
| 业务观察决策 | `workshop-observer` | 看车间聚合结果、异常摘要、上报完整性，不回到人工统计 | 是 |
| 业务观察决策 | `factory-observer` | 看跨车间结果、日报与异常趋势，做经营判断 | 是 |
| 项目运营 / 实施 | `rollout-admin` | 配置主数据、账号、班次、设备绑定、试点门禁与降级 | 是 |
| 项目运营 / 实施 | `ops-implementer` | 巡检、readyz 门禁、脚本执行、部署/回滚、故障定位 | 是 |
| AI 自动化 | `validator-agent` | 自动校验、自动退回、给出可执行 `returned_reason` | 是 |
| AI 自动化 | `aggregator-agent` | 自动汇总、形成日报口径、带出异常摘要 | 是 |
| AI 自动化 | `reporter-agent` | 自动发布 / 自动推送或按开关降级 | 是 |
| AI 自动化 | `reminder-agent` | 识别未报/迟报并催报 | 是 |
| 专业扩展位 | `weigher / qc / energy-recorder / contracts` | 仅在特定工艺链路补充字段，不替代主业务 spine | 否 |

### 3.2 已删除角色

| 删除项 | 处理原则 |
| --- | --- |
| `statistician` | 彻底从正式业务角色删除；原“接收-核对-汇总-上报”职责改由 `worker / team-lead + agents + observers` 分担 |
| `stat` | 同上，只允许作为兼容残留代码名被清理，不得再作为产品文档角色 |
| `reviewer` | 只可作为 brownfield 兼容访问层存在，不能继续代表未来流程中的人工审核岗位 |

## 4. 角色体系：aluminum-bypass 项目层映射

### 4.1 正式角色与当前仓库映射

| 长期正式角色 | 当前仓库真实映射 | 现状说明 | 规范结论 |
| --- | --- | --- | --- |
| `worker` | 当前移动端填报执行人，代码里多由 `shift_leader` 或机台账号承担 | `mobile.py` 已是主写入口；真实业务含义是“录入原始值的人” | 保留为正式角色 |
| `team-lead` | `team_leader / deputy_leader / shift_leader / mobile_user` 的混合别名 | `scope.py` 中别名混杂，前台文案也混用“班长/移动端用户” | 统一收敛到 `team-lead` |
| `workshop-observer` | `manager / workshop_director` | 当前还能看桌面端聚合与异常，但语义仍夹杂 reviewer 口径 | 保留观察角色，不承担人工审核链 |
| `factory-observer` | `factory_director / senior_manager / admin` 的一部分观察行为 | 当前看厂长驾驶舱与日报 | 保留观察角色 |
| `rollout-admin` | `admin` | 当前负责账号、车间、班组、机台、模板、班次等主数据 | 保留正式角色 |
| `ops-implementer` | 当前主要还是 `admin` + 本地脚本操作者 | `check_pilot_config.py`、`check_pilot_metrics.py`、`check_pilot_anomalies.py` 已形成雏形 | 保留正式角色 |
| `validator-agent` | `backend/app/agents/validator.py` | 已实际承担自动确认/退回 | 保留正式系统角色 |
| `aggregator-agent` | `backend/app/agents/aggregator.py` | 已承担日报聚合与异常摘要汇总 | 保留正式系统角色 |
| `reporter-agent` | `backend/app/agents/reporter.py` | 已承担发布/推送 | 保留正式系统角色 |
| `reminder-agent` | `backend/app/agents/reminder.py` | 已承担催报 | 保留正式系统角色 |

### 4.2 当前不应再被当作正式业务 spine 的对象

| 当前对象 | 原因 | 后续定位 |
| --- | --- | --- |
| `dashboard/statistics` | 名称延续“统计审核”旧世界 | 改为观察/异常总览兼容入口，最终并入 observer 口径 |
| `assert_reviewer_access()` 一系 | 表达旧人工审核角色 | 视为兼容访问控制，后续迁移到 observer / compatibility 层 |
| README 中 review / reject / confirm 叙述 | 重新引入人工统计链 | 改为“自动校验/退回/汇总/推送”口径 |

## 5. 正式角色矩阵

| 正式角色 | 主要输入 | 主要动作 | 系统直接反馈 | 不应承担的工作 | 升级路径 |
| --- | --- | --- | --- | --- | --- |
| `worker` | 当班原始生产数据、设备现场事实 | 填报、修改、重提、补充照片 | `approved` / `returned` / `returned_reason` | 跨班组汇总、人工拼日报、替代系统做统计 | 升级给 `team-lead` |
| `team-lead` | 本班应报清单、退回原因、未报名单 | 组织填报、兜底补报、核对缺报、处理异常升级 | 上报率、退回率、催报记录、异常摘要 | 手工改造日报口径、替代管理员修系统配置 | 升级给 `rollout-admin` 或 observer |
| `workshop-observer` | 车间驾驶舱、异常摘要、日报 | 观察、追问、定责、安排纠偏 | 聚合结果、异常趋势、缺报清单 | 回到一线手工录数、承担统计中间层 | 升级给 `factory-observer` / `rollout-admin` |
| `factory-observer` | 全厂日报、异常摘要、跨车间对比 | 经营判断、资源调度、是否放量 | 厂级驾驶舱、发布摘要 | 审核每条明细、代替班组做修数 | 升级给 `rollout-admin` / 平台工程 |
| `rollout-admin` | 主数据、账号、设备、班次、readyz 结果 | 配置、门禁检查、降级开关、现场支持 | `readyz`、config check、审计日志 | 代替业务长期值守录数 | 升级给 `ops-implementer` |
| `ops-implementer` | 脚本输出、日志、部署状态 | 巡检、回滚、发布、问题定位 | `healthz/readyz`、metrics、anomalies、compose 状态 | 替代业务做数据判断 | 升级给平台工程负责人 |
| `validator-agent` | 移动端提交数据 | 自动校验、自动确认/退回 | `approved/returned`、可执行原因 | 让人手点“通过” | 向 `team-lead` / `rollout-admin` 暴露异常 |
| `aggregator-agent` | 已确认数据、异常检测结果 | 汇总、生成日报 | canonical 汇总结果、异常摘要 | 依赖统计员手工总表 | 向 observer 暴露结果 |
| `reporter-agent` | 汇总结果、开关配置 | 自动发布 / 自动推送 | 发布记录、推送记录 | 人工值守后再二次发布 | 按开关降级给 ops |
| `reminder-agent` | 应报清单、提交状态 | 催报、记录提醒状态 | reminder records | 靠人工逐个盯表 | 升级给 `team-lead` / observer |

## 6. 首批优先 SOP

> 首批优先角色固定为：`worker`、`team-lead`。同时补齐计划要求的观察/实施角色位：`workshop-observer`、`factory-observer`、`rollout-admin`、`ops-implementer`。

### 6.1 `worker` SOP（工人 / 机台填写人）

#### 长期可复用层

- **输入**：当班原始数值、设备状态、照片证据、备注。
- **触发动作**：进入移动端 -> 选择当前班次 -> 填报 -> 提交。
- **系统反馈**：
  - 正常：自动进入 `approved`。
  - 异常：自动进入 `returned`，并给出中文 `returned_reason`。
- **异常处理**：
  - 登录失败：先看绑定/停用/冲突/账号无效提示。
  - 被退回：按原因逐条修正后重新提交。
  - 无法提交：立即通知 `team-lead`，不要私下转 Excel 或微信文本代填。
- **不该做什么**：
  - 不手工汇总全班数据。
  - 不绕过系统把数据先发给统计员。
  - 不把“未 ready”的系统问题伪装成业务已完成。
- **升级路径**：先升 `team-lead`，如属账号/排班/设备绑定问题，再由 `team-lead` 升 `rollout-admin`。

#### aluminum-bypass 项目层落地

- 当前主要入口：`/api/v1/mobile/*` 与前端 `/mobile`。
- 当前文档基线：`docs/pilot-sop-minimal.md` 已覆盖入口、登录失败、退回处理。
- 当前上线前置：由于 2026-04-06 `/readyz` 仍有 `EQUIPMENT_USER_BINDING_INVALID`、`SCHEDULE_EMPTY`，worker SOP 只能用于**本地验证/试点演练**，不能当作正式投产 SOP。

### 6.2 `team-lead` SOP（班长）

#### 长期可复用层

- **输入**：本班应报清单、未报名单、退回原因、异常摘要。
- **触发动作**：班前核对谁应报；班中跟踪是否已报；班后清缺、处理退回、确认补报。
- **系统反馈**：上报率、退回率、催报记录、异常摘要持续更新。
- **异常处理**：
  - 有人未报：先催报，再确认是否账号/班次/设备绑定问题。
  - 连续退回：先保留现场原始事实，再逐项修正，不得口头“估一个数”。
  - 班次不存在或应报清单为空：直接升级 `rollout-admin`，这不是班组自行兜底能解决的问题。
- **不该做什么**：
  - 不重新扮演“统计员”，不手工做全班汇总总表。
  - 不跨班组替别人长期代填。
  - 不把系统异常当作班组责任硬压现场人员背锅。
- **升级路径**：
  - 业务真实性问题 -> 升 `workshop-observer`
  - 账号/主数据/排班/设备绑定问题 -> 升 `rollout-admin`
  - 平台不可用 / 回滚 / 日报发布异常 -> 升 `ops-implementer`

#### aluminum-bypass 项目层落地

- 当前代码别名混乱：`team_leader / deputy_leader / mobile_user / shift_leader` 实际都在分担班长职责。
- 规范要求：下一阶段施工统一口径为 `team-lead`，现有别名只保留兼容映射。
- 当前 readiness 直接影响班长 SOP 的两条硬前提：
  - `SCHEDULE_EMPTY`：班长拿不到可信应报清单。
  - `EQUIPMENT_USER_BINDING_INVALID`：机台账号可能无法在正确车间提交。

### 6.3 `workshop-observer` SOP（车间观察者）

#### 长期可复用层

- **输入**：车间驾驶舱、日报摘要、异常摘要、上报率、退回率。
- **触发动作**：每班/每日查看聚合结果；发现异常时要求班组纠偏。
- **系统反馈**：车间级汇总、异常分布、缺报班组列表。
- **异常处理**：
  - 异常量上升：要求 `team-lead` 先完成补报与修正。
  - 多班次重复异常：要求 `rollout-admin` 排查模板、班次或主数据问题。
- **不该做什么**：
  - 不逐条充当人工审核员。
  - 不自己维护影子 Excel 总表。
- **升级路径**：重大跨班组问题升级 `factory-observer`；配置问题升级 `rollout-admin`。

#### aluminum-bypass 项目层落地

- 当前主要对应 `manager / workshop_director` 能访问的桌面端观察面。
- `Layout.vue` 仍混有“统计审核看板”，说明观察角色尚未与 reviewer 债务完全切开。

### 6.4 `factory-observer` SOP（厂级观察者）

#### 长期可复用层

- **输入**：厂级驾驶舱、日报、跨车间异常摘要。
- **触发动作**：按日查看经营结果与异常趋势，决定是否扩面、降级、停放量。
- **系统反馈**：跨车间对比、日报发布状态、关键异常摘要。
- **异常处理**：
  - readiness 未通过：不得宣布正式投用。
  - 日报口径不稳定：要求 `ops-implementer` 与 `rollout-admin` 联合复盘。
- **不该做什么**：
  - 不回到旧流程要求中间层人工总表。
  - 不跳过 readiness 门禁直接放量。
- **升级路径**：交由 `rollout-admin` / `ops-implementer` 执行纠偏和降级。

#### aluminum-bypass 项目层落地

- 当前主要落在厂长驾驶舱与日报观察面。
- 2026-04-06 当前系统层级仍应判定为“本地可运行，但不可正式投用”。

### 6.5 `rollout-admin` SOP（实施管理员）

#### 长期可复用层

- **输入**：主数据、用户、班次、设备绑定、readyz/config 检查结果。
- **触发动作**：试点前配齐主数据；试点中处理账号、绑定、排班、模板和降级开关。
- **系统反馈**：`readyz`、配置检查、审计日志、主数据页面反馈。
- **异常处理**：
  - 设备绑定异常：修复账号与设备同车间绑定。
  - 应报清单为空：先导入/生成排班再放量。
  - 文档/配置不一致：列入放量前阻断，不靠口头约定替代。
- **不该做什么**：
  - 不代替班组长期填报。
  - 不在未审计情况下做强制性数据改写。
- **升级路径**：技术故障升级 `ops-implementer`；流程冲突升级产品/架构决策。

#### aluminum-bypass 项目层落地

- 当前主阵地：主数据维护、账号维护、`check_pilot_config.py`、`readyz`。
- 当前最优先动作已被 `readyz` 明确指出：
  1. 修机台绑定异常。
  2. 补当日排班/应报清单。

### 6.6 `ops-implementer` SOP（运维实施）

#### 长期可复用层

- **输入**：compose 状态、healthz/readyz、pytest、巡检脚本、日志。
- **触发动作**：发布前验证、试点巡检、故障定位、回滚/降级。
- **系统反馈**：服务状态、测试结果、metrics、anomalies、config gate。
- **异常处理**：
  - `healthz` 异常：先恢复基本可用性。
  - `readyz` 阻断：禁止放量。
  - 自动发布或自动推送异常：用开关降级，保留填报与校验。
- **不该做什么**：
  - 不把“服务能起”误判为“现场可用”。
  - 不绕过门禁让业务承担未准备好的风险。
- **升级路径**：平台级故障升级工程负责人；业务口径冲突拉 `rollout-admin` 和 observer 共同裁决。

#### aluminum-bypass 项目层落地

- 2026-04-06 已验证：
  - 运行层：`docker compose ps` 正常。
  - 活性层：`/healthz` 正常。
  - readiness 层：`/readyz` 503。
  - 回归层：`pytest -q` 仍为 `5 failed, 238 passed, 1 warning`。
- 因此 ops 结论必须是：**系统是可运行样本，不是正式上线成品。**

## 7. 角色边界决策

### 7.1 主业务 spine

正式主链路固定为：

`worker -> team-lead -> agents -> observers`

其中：

- `worker / team-lead` 负责原始事实与修正。
- `validator / aggregator / reporter / reminder` 负责自动校验、汇总、触达。
- `workshop-observer / factory-observer` 只看结果、做决策。
- `rollout-admin / ops-implementer` 负责配置、门禁、发布、降级。

### 7.2 禁止回流到旧流程

以下行为在长期体系中明确禁止：

1. 重新设立“统计员”接收各班数据再手工汇总。
2. 让 reviewer 成为主流程必经的人肉点击关卡。
3. 用 Excel / 微信 / 电话链路替代系统完成正式上报。
4. 将管理者角色设计成“可直接改一线原始值”的默认使用者。

## 8. 直接驱动下一阶段施工的角色整改顺序

1. **先统一正式角色命名**
   - `worker`
   - `team-lead`
   - `workshop-observer`
   - `factory-observer`
   - `rollout-admin`
   - `ops-implementer`
2. **再把兼容残留单列出来**
   - `statistician / stat / reviewer`
   - `dashboard/statistics`
   - reviewer access helpers
3. **最后才做 UI / API / 权限收敛**
   - 把“统计审核看板 / 审核端”改为观察/异常语义
   - 将移动端别名收敛到 `team-lead`
   - 将 reviewer 权限改造成 compatibility 层，而非正式产品角色层

## 9. 本 lane 结论

- `statistician` 已在规范层被正式删除，不再是业务角色。
- 首批优先角色固定为 `worker` 与 `team-lead`。
- 当前仓库已具备 SOP 雏形，但角色语义仍与旧 reviewer / statistics 世界纠缠。
- 在 2026-04-06 当前状态下，**角色体系可以定稿，正式投用不能定稿**；因为 `/readyz` 仍被 `EQUIPMENT_USER_BINDING_INVALID` 与 `SCHEDULE_EMPTY` 阻断，且完整回归仍有 5 个失败测试。
- 下一阶段施工必须围绕“正式角色层”而不是“历史 reviewer 层”推进 UI、API、CLI、skill 的统一收敛。
