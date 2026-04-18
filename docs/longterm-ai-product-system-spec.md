# Aluminum-Bypass 长期 AI 产品体系总规范

> 状态：总装版 v1
> 来源：
> - `/mnt/d/zzj/.omx/plans/aluminum-bypass-longterm-system-consensus-20260406T153425Z.md`
> - `docs/superpowers/specs/2026-04-06-role-matrix-and-sops-design.md`
> - `docs/api-system-lane-spec.md`
> - `docs/cli-rollout-lane-spec.md`
> - `docs/longterm-ai-skill-system-spec.md`

## 1. 这份规范要解决什么

这份文档不是继续零散修仓库，也不是 readiness 修复任务单。

它解决的是一个更上层的问题：

- 如何把 `aluminum-bypass` 从一个制造业项目，提升为你长期 AI 产品体系中的一个能力模块
- 如何把角色、API、CLI / scripts、skill、SOP 放到同一套边界里
- 如何让后续施工不再碎片化

这份规范默认服务两个层次：

1. **长期可复用层**
   面向以后类似制造业 AI 项目复用的角色骨架、系统边界、运维门禁和 skill 体系。
2. **Aluminum-Bypass 项目层**
   面向当前仓库的真实代码、真实命令、真实 readiness 现状、真实文档债务。

## 2. 当前现实状态

截至当前样本状态：

- 本地栈可以跑起来
  - `docker compose ps` 可见 `db / backend / nginx` 均为运行态
  - `https://localhost/` 可访问
  - `http://localhost:8000/docs` 可访问
- 服务活性正常
  - `/healthz = ok`
- 但系统**还不 ready**
  - `/readyz = not_ready`
  - 当前硬阻断：
    - `EQUIPMENT_USER_BINDING_INVALID`
    - `SCHEDULE_EMPTY`
- 完整后端回归**未全绿**
  - `pytest -q`：`5 failed, 238 passed, 1 warning`
- 文档、配置、脚本、UI 语义仍未完全收口

因此当前结论只能是：

- `local runnable`: 是
- `can trial`: 接近，但需要先清 readiness 硬阻断
- `formal-use`: 否

## 3. 固定边界

这些边界不是建议，而是已经决定：

1. **统计员角色彻底取消**
   - `statistician / stat / reviewer` 不再是正式业务角色
   - 它们只允许作为 brownfield 兼容残留被记录和清理
2. **首批优先角色**
   - 工人
   - 班长
3. **本轮规范不做**
   - 商业化/盈利模型设计
   - 直接跨项目平台实现
   - 直接把规范替换成零散修 bug
4. **总规范的四个必含核心**
   - 各角色 SOP
   - API 体系
   - CLI / scripts 体系
   - skill 体系

## 4. 长期 AI 产品体系分层

建议把整个产品体系分成四层：

| 层级 | 作用 | 在本项目中的含义 |
| --- | --- | --- |
| 终端业务层 | 一线真实业务动作 | 工人填报、班长组织、观察者看结果 |
| 自动化执行层 | Agent 处理主链路 | 校验、退回、汇总、推送、催报 |
| 工程与运维层 | 配置、巡检、回滚、门禁 | readiness、脚本、部署、排障 |
| AI 协作层 | 把运维与规范沉淀成 skill/工作流 | repo-local skills、全局 OMX skills、队列化协作 |

## 5. 正式角色体系

### 5.1 正式保留角色

| 正式角色 | 定位 |
| --- | --- |
| `worker` | 终端业务执行者，负责提交原始生产事实 |
| `team-lead` | 班组组织者，负责缺报、退回、补报与升级 |
| `workshop-observer` | 车间观察者，只看聚合结果与异常，不做人工审核 |
| `factory-observer` | 厂级观察者，负责经营判断与是否放量 |
| `rollout-admin` | 试点配置与放量门禁负责人 |
| `ops-implementer` | 运维、排障、回滚与环境实施负责人 |
| `validator-agent` | 自动校验、自动退回 |
| `aggregator-agent` | 自动汇总、日报形成 |
| `reporter-agent` | 自动发布 / 自动推送 |
| `reminder-agent` | 催报与迟报闭环 |

### 5.2 正式删除角色

| 删除角色 | 说明 |
| --- | --- |
| `statistician` | 不再存在为正式岗位定义 |
| `stat` | 同上，只能作为历史兼容名 |
| `reviewer` | 不再作为长期主流程角色，只能作为兼容访问层残留 |

### 5.3 职责重分配

原来统计员承担的“收数 -> 核对 -> 汇总 -> 上报”链路，改为：

- 工人：提交原始事实
- 班长：盯班次完整性、处理退回、组织补报
- Agent：校验、退回、汇总、推送
- 观察者：看聚合结果、发现异常、做管理决策
- rollout-admin / ops-implementer：处理配置、readyz、部署、回滚

## 6. 首批角色 SOP

### 6.1 工人 SOP

**输入**
- 当班真实生产数据
- 设备状态
- 现场照片或补充备注

**动作**
- 进入移动端
- 填报当前班次
- 提交
- 如被退回，按 `returned_reason` 修改后重提

**系统反馈**
- 正常：进入 `approved`
- 异常：进入 `returned`，并显示可执行中文原因

**不该做什么**
- 不手工汇总全班数据
- 不绕过系统发给“统计员”
- 不私下用 Excel / 微信替代主流程

**升级路径**
- 先找 `team-lead`
- 若是账号/设备/排班问题，再由 `team-lead` 升级 `rollout-admin`

### 6.2 班长 SOP

**输入**
- 本班应报清单
- 未报名单
- 退回原因
- 催报与异常摘要

**动作**
- 组织本班按时填报
- 处理未报、迟报、退回
- 确认当班数据闭环

**系统反馈**
- 上报率
- 退回率
- 催报记录
- 缺报/异常摘要

**不该做什么**
- 不再扮演“统计员”
- 不手工做总表
- 不长期代替别人跨班组填报

**升级路径**
- 业务真实性问题：升 `workshop-observer`
- 账号/排班/绑定问题：升 `rollout-admin`
- 平台/发布/回滚问题：升 `ops-implementer`

### 6.3 观察与实施角色

这轮总规范先明确角色位，不把全部 SOP 写满：

- `workshop-observer`
- `factory-observer`
- `rollout-admin`
- `ops-implementer`

下一阶段施工时，按同样模板继续展开。

## 7. API 体系

### 7.1 正式分层

| 层级 | 作用 |
| --- | --- |
| 身份与权限横切层 | 统一登录、企业微信入口、权限与 scope |
| 生产主流程 API | 工人/班长写一手业务事实 |
| 观察与驾驶舱 API | 管理者看聚合结果、异常与交付状态 |
| 管理与主数据 API | 配置、导入、治理、例外处理 |
| readiness / health / observability API | 回答系统是否活着、是否 ready、为什么不 ready |

### 7.2 长期主口径

正式主链路必须是：

`worker/team-lead 提交 -> 系统自动校验 -> Agent 自动汇总/推送 -> observer 查看结果`

长期 canonical 语义：

- canonical scope：`auto_confirmed`
- compatibility input：仍可暂时接受 `confirmed_only` / `include_reviewed`
- 但兼容参数不再代表长期主设计中心

### 7.3 长期边界

- `dashboard/*` 和 `reports` 读接口是观察面，不是主流程写入口
- `production review/confirm/reject/void`、`report review/publish/finalize` 这类接口只能降级为兼容/例外入口
- `/healthz`、`/readyz` 属于系统面，不放到 `/api/v1/` 业务层里
- 运维观察接口未来应新增到：
  - `/api/v1/system/*` 或 `/api/v1/ops/*`

## 8. CLI / Scripts 体系

### 8.1 四类命令面

| 分类 | 用途 |
| --- | --- |
| `dev` | 本地开发、构建、基本验证 |
| `trial` | 试运行前检查、现场预检 |
| `ops` | 巡检、部署、恢复、问题定位 |
| `rollback` | 降级与回滚 |

### 8.2 当前代表命令

**dev**
- `docker compose up -d --build`
- `docker compose ps`
- `curl -k https://localhost/healthz`
- `cd frontend && npm run build`
- `scripts/generate_env.py`

**trial**
- `curl -k https://localhost/readyz`
- `python scripts/check_pilot_config.py --date ... --json`
- `python scripts/check_pilot_metrics.py --date ... --json`
- `python scripts/check_pilot_anomalies.py --date ... --json`
- `python scripts/check_wecom_account_mapping.py ...`

**ops**
- `alembic upgrade head`
- 初始化脚本
- 主数据/账号/配置修复

**rollback**
- `AUTO_PUBLISH_ENABLED=false`
- `AUTO_PUSH_ENABLED=false`
- `WORKFLOW_ENABLED=false`
- `WECOM_BOT_ENABLED=false`
- `WECOM_APP_ENABLED=false`
- 备份/恢复脚本

### 8.3 当前分层结论

- `local runnable`: 已满足
- `can trial`: 差一点，主要卡在 live readiness
- `formal-use`: 未满足

### 8.4 当前最关键的正式投用阻断

1. `EQUIPMENT_USER_BINDING_INVALID`
2. `SCHEDULE_EMPTY`
3. 完整后端测试仍有 5 个失败
4. 根目录脚本/文档/配置与 backend 容器内测试覆盖面不一致

## 9. Skill 体系

### 9.1 原则

- CLI / scripts：负责确定性执行
- skill：负责跨证据面判断、解释、归因、编排和决策
- 运行时 Agent 与运维 skill 必须分开

### 9.2 Skill 分层

| 层级 | 定位 |
| --- | --- |
| L1 | 脚本 / API / readiness probe 提供事实 |
| L2 | repo-local skills 负责编排本项目上下文 |
| L3 | 全局 OMX skills 提供可复用框架 |
| L4 | team / leader / worker 协作层 |

### 9.3 首批 repo-local skills

- `readiness-check`
- `trial-go-live`
- `ops-diagnose`
- `role-sop-review`
- `rollout-gate`
- `config-surface-sync`

### 9.4 与全局 OMX 的分工

**全局 OMX skill**
- 提供方法框架、判断模板、输出格式

**repo-local skill**
- 填入本项目的业务语义、脚本名、配置键、SOP 文档、API 路径

**脚本/API**
- 提供可执行事实，不负责解释层

## 10. 当前系统在三层投入标准中的位置

### 10.1 本地可运行

已经满足：
- 首页可开
- docs 可开
- `healthz` 正常
- compose 三个核心服务能起

### 10.2 可试运行 / 灰度

接近，但当前不应直接判通过。  
原因：
- `readyz` 未通过
- 硬阻断仍在
- Gate A/B/C 还没有完整留痕跑满

### 10.3 可正式投入使用

当前明确不满足。  
至少还差：
- live readiness 全绿
- 完整后端回归全绿
- 配置示例、docs、scripts、README 完整对齐
- UI 语义与角色语义彻底收口

## 11. 下一阶段施工路线图

### P0：收口 readiness 与测试

- 清掉 `readyz` 硬阻断
- 清掉完整后端 `pytest -q` 的 5 个失败

### P1：收口配置与命令面

- 把 `AUTO_PIPELINE_REQUIRE_READY` 同步进：
  - `.env.example`
  - `docker-compose.yml`
  - `scripts/generate_env.py`
  - 相关 rollout / README 文档

### P2：收口角色与 UI 语义

- 从正式角色里清掉统计员语义
- 清掉 `Layout.vue`、`README.md`、`router` 等旧审核世界的表达

### P3：补 repo-local skill scaffolding

- 先落地 3 个最高价值技能：
  - `readiness-check`
  - `trial-go-live`
  - `ops-diagnose`

### P4：把 4 个体系继续固化成统一交付

- 角色矩阵
- SOP
- API 体系
- CLI/scripts
- skill
- rollout 标准

## 12. 最终结论

这套系统现在已经不该再被当成“一个有几个页面和几个脚本的项目”，而应被定义成：

**一个以工人/班长为终端入口、以 Agent 为自动化中枢、以观察者为结果消费者、以 rollout-admin / ops-implementer 为实施与运维角色、以 CLI/scripts/skills 为操作面、以 readiness / rollout 标准为放量门禁的长期 AI 产品能力模块。**

但要注意：

- 这个“总规范”现在已经有了骨架
- 真正的“正式投入使用”还没有达到
- 下一步最该做的不是继续散修，而是按这份总规范推进收口施工

如果一句话概括当前状态：

**体系已经能定义，产品还不能宣布正式 ready。**
