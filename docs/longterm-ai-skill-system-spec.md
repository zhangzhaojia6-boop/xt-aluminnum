# Aluminum-Bypass 长期 AI 产品体系：Skill System 规范

> 本文是 `aluminum-bypass-longterm-system-consensus-20260406T153425Z.md` 的 Lane 4 交付物。
> 目标不是再加一组零散脚本，而是把“人 + AI + 确定性命令”的协作面收口成长期可复用的 skill 体系。

## 1. 证据基线（2026-04-06）

### 1.1 当前仓库已经存在的确定性操作面
- readiness / rollout 文档：
  - `docs/pilot-readiness-checklist.md`
  - `docs/pilot-sop-minimal.md`
  - `docs/pilot-anomaly-sop-minimal.md`
  - `docs/workflow-rollout.md`
- 现场/运维脚本：
  - `backend/scripts/check_pilot_config.py`
  - `backend/scripts/check_pilot_metrics.py`
  - `backend/scripts/check_pilot_anomalies.py`
  - `backend/scripts/check_wecom_account_mapping.py`
  - `scripts/generate_env.py`
  - `scripts/backup_db.sh|ps1`
  - `scripts/restore_db.sh|ps1`
- 运行时 readiness 面：
  - `backend/app/main.py` 暴露 `/healthz`、`/readyz`
  - `backend/app/core/health.py` 将 `AUTO_PIPELINE_REQUIRE_READY` 与 `inspect_pilot_config()` 绑定为 readyz 门禁

### 1.2 当前 skill 基础设施现状
- 仓库内已经补出第一批 repo-local skill 说明文档：
  - `docs/skill-aluminum-legacy-gap.md`
  - `docs/skill-aluminum-daily-ops.md`
  - `docs/skill-aluminum-go-live-gate.md`
- 当前状态从“完全没有 skill scaffolding”升级为“已有 skill 设计面，但还没全部产品化成真正可加载的 repo-local runtime skill 目录”。

### 1.3 当前 readiness 现实
- `docker compose ps`：`db/backend/nginx` 均为 `Up`。
- `https://localhost/healthz`：返回 `ok`。
- `https://localhost/readyz`：`2026-04-08` 返回 `ready`。
- 当前主阻塞已经从“基础配置门槛”转为“真实试点数据尚未进入主链路，零上报/缺报异常仍未演练消除”。

### 1.4 当前需要被 skill 体系吸收的 brownfield 问题
- `README.md` 仍保留旧审核流措辞（`review / reject / confirm`）和 Windows 绝对路径链接。
- `backend/app/config.py` 已有 `AUTO_PIPELINE_REQUIRE_READY`，但 `.env.example`、`backend/.env.example`、`docker-compose.yml`、`scripts/generate_env.py` 尚未对齐该项。
- 说明本仓库目前缺的不是“再加一个脚本”，而是“把配置一致性、readiness 解释、试点放量决策”变成统一 skill 工作流。

## 2. 先定边界：什么是 skill，什么不是

## 2.1 skill 不是脚本
- **脚本 / CLI**：执行确定性动作，输入明确，输出可重复。
- **skill**：围绕多个脚本、文档、接口和上下文判断，完成一个“可交付的操作流程”。

### 2.2 本仓库 skill 的正式边界
skill 适合负责：
- 读取多个证据面（脚本输出、API、SOP、配置、文档）
- 做 go / no-go / priority / ownership 类判断
- 生成结构化结论、待办、交接说明、异常升级路径

skill 不应直接替代：
- 数据库备份/恢复本身
- `check_*` 脚本本身
- `/healthz`、`/readyz` 这种系统事实接口
- 运行时业务 Agent（`validator / aggregator / reporter / reminder`）

## 2.3 运行时 Agent 与操作 skill 必须分开
- `validator / aggregator / reporter / reminder` 是**产品运行时自动化角色**。
- `readiness-check / ops-diagnose / trial-go-live` 是**人机协作运维技能**。
- 前者处理生产数据流；后者处理部署、上线、巡检、解释、决策。
- 不能把运行时 agent 的职责混进 skill，也不能让 skill 重建“统计员人工中间层”。

## 3. 长期 AI 产品体系中的 skill 分层

| 层级 | 定位 | Aluminum-Bypass 对应物 | 是否跨项目复用 |
|---|---|---|---|
| L0 | 事实层 | DB、模型、业务状态、事件流 | 否 |
| L1 | 确定性执行层 | `/healthz` `/readyz`、`check_*`、`generate_env.py`、backup/restore | 高 |
| L2 | Repo-local skill 层 | 针对本仓库业务语义编排 L1 与 docs 的 skill | 中 |
| L3 | OMX 全局 skill 层 | 跨项目复用的 rollout / readiness / SOP / incident meta-workflow | 高 |
| L4 | 团队协作层 | leader / worker 分工、lane 交付、审批与追踪 | 高 |

结论：**本仓库应该补的是 L2，不是把一切都塞进 L3。**

## 4. Repo-local skills：建议首批正式建设清单

## 4.1 `readiness-check`
**目的**：把“能不能进入试点前检查”从脚本调用升级为结构化 readiness 结论。

**必须消费的证据**：
- `/readyz`
- `backend/scripts/check_pilot_config.py`
- `docs/pilot-readiness-checklist.md`
- `backend/app/core/health.py`

**输出**：
- 当前属于：本地可运行 / 可试运行 / 不可放量
- hard issue / warning issue 分层
- 缺口责任归属（主数据、账号映射、排班、配置）

**为什么必须是 skill**：
单个脚本只能报错；真正的现场问题是“这是否阻断试点、由谁处理、先修哪个”。这需要上下文判断。

## 4.2 `trial-go-live`
**目的**：把 Gate A/B/C 串成一次标准化放量前决策流程。

**必须消费的证据**：
- `docs/pilot-readiness-checklist.md`
- Gate A/B/C 对应 pytest 命令
- `check_pilot_config.py`
- `check_pilot_metrics.py`
- `check_pilot_anomalies.py`

**输出**：
- go / no-go 结论
- 若 no-go：阻断项、可带病放行项、降级建议
- 若 go：当班值守重点、复盘命令、降级责任人

**为什么必须是 skill**：
放量不是单条命令，而是把测试、配置、异常、SOP、降级开关综合成一次上线判断。

## 4.3 `ops-diagnose`
**目的**：面向管理员/实施/值班人，解释“系统能跑但为什么还不能正式用”。

**必须消费的证据**：
- `/healthz` `/readyz`
- `check_pilot_metrics.py`
- `check_pilot_anomalies.py`
- `check_wecom_account_mapping.py`
- `docs/pilot-sop-minimal.md`
- `docs/pilot-anomaly-sop-minimal.md`

**输出**：
- 故障定位分类：配置类 / 数据类 / 账号类 / 运营类 / 文档一致性类
- 建议先执行的命令
- 是否需要降级 `AUTO_PUBLISH_ENABLED` / `AUTO_PUSH_ENABLED`
- 是否需要停止放量

**为什么必须是 skill**：
当前异常面跨脚本、跨文档、跨配置；需要统一解释层，不能让现场人员手工拼接。

## 4.4 `role-sop-review`
**目的**：让仓库文档、页面文案、培训材料都回到“工人/班长/管理观察/管理员运维”的正式角色体系。

**必须消费的证据**：
- `README.md`
- `docs/pilot-sop-minimal.md`
- `docs/pilot-anomaly-sop-minimal.md`
- 长期总规范中的角色边界

**输出**：
- 是否残留“统计员 / 审核台中心角色”语义
- 哪些文档或页面仍在重建旧流程
- 角色文案修订建议

**为什么必须是 skill**：
这不是 lint；它依赖产品边界理解，尤其要防止“历史 reviewer 兼容语义”重新变成正式角色。

## 4.5 `rollout-gate`
**目的**：把“本地可运行 / 可试运行 / 可正式投入使用”三层标准固定成同一种判断模板。

**必须消费的证据**：
- `/healthz` `/readyz`
- 完整或定向 pytest 结果
- `.env.example`、`docker-compose.yml`、`scripts/generate_env.py`
- `docs/workflow-rollout.md`

**输出**：
- 当前所处层级
- 晋级到下一层级的前三个缺口
- 回滚/降级路径

**为什么必须是 skill**：
这是长期体系最核心的“门禁解释器”，未来每个类似项目都要复用。

## 4.6 `config-surface-sync`
**目的**：专门收口“配置项已经进代码，但没同步到 env/example/compose/docs/script”的 brownfield 漏洞。

**必须消费的证据**：
- `backend/app/config.py`
- `.env.example`
- `backend/.env.example`
- `docker-compose.yml`
- `scripts/generate_env.py`
- README / rollout docs

**当前直接触发它的证据**：
- `AUTO_PIPELINE_REQUIRE_READY` 已存在于 `backend/app/config.py`，但其他配置入口面未对齐。

**输出**：
- 配置项存在矩阵
- 缺口清单
- 哪些缺口会造成“能跑但误判 ready / 不可运维”

**为什么必须是 skill**：
单纯 grep 能发现差异，但不能判断哪些差异会影响 rollout 语义与现场使用。

## 5. 哪些动作应该 skill 化，哪些只保留 CLI / API

## 5.1 必须 skill 化的动作
1. **试点前放量判断**：本质是跨证据面的决策。
2. **现场异常归因**：需要把配置、排班、账号、日报、SOP 串起来解释。
3. **角色/文档一致性审查**：需要理解“统计员已删除”的产品边界。
4. **配置面一致性审查**：需要识别“配置项是否影响 ready / rollout / 降级语义”。
5. **正式投入前分层判断**：需要解释当前只能本地跑、能试点、还是能正式用。

## 5.2 只保留为 CLI / 脚本的动作
1. 生成 `.env`：`scripts/generate_env.py`
2. 备份/恢复数据库：`scripts/backup_db.*` / `scripts/restore_db.*`
3. 单项巡检：`check_pilot_config.py` / `check_pilot_metrics.py` / `check_pilot_anomalies.py`
4. 企业微信账号清单核对：`check_wecom_account_mapping.py`

原则：**能确定执行的动作留给 CLI；需要解释、编排、归因、决策的动作升级为 skill。**

## 6. Repo-local skill 与 OMX 全局 skill 的边界

## 6.1 应留在 repo-local 的内容
这些内容高度依赖 `aluminum-bypass` 业务语义，不应上提到全局 OMX：
- `auto_confirmed` / `confirmed_only` / `returned_reason` 等当前主链路语义
- 车间 / 班组 / 设备 / 应报清单 / 企业微信账号映射等主数据结构
- `docs/pilot-readiness-checklist.md`、`docs/pilot-sop-minimal.md`、`docs/pilot-anomaly-sop-minimal.md` 的现场约束
- `WORKFLOW_ENABLED`、`AUTO_PUBLISH_ENABLED`、`AUTO_PUSH_ENABLED` 在本仓库中的 rollout 语义
- 当前 `/readyz` 阻断项如何映射到现场整改动作

## 6.2 应上提为 OMX 全局 skill 的内容
这些是未来类似项目都可复用的共性：
- readiness 结论模板
- rollout gate 分层模板（本地可运行 / 可试运行 / 可正式投入）
- incident / ops diagnose 元流程
- config-surface-sync 检查框架
- role-SOP consistency review 框架
- 文档/脚本/API/配置四面一致性审查方法

## 6.3 正式分工规则
- **OMX 全局 skill**：提供通用方法、判断模板、产出格式。
- **Repo-local skill**：填入本仓库业务名词、脚本名、API 路径、配置键、SOP 文档。
- **脚本/API**：提供可执行事实，不承担解释层。

## 7. 与长期 AI 产品体系的映射

## 7.1 对 aluminum-bypass 本仓库
- 该仓库不是“全局平台本体”，而是**制造业 AI 产品体系中的一个项目样本模块**。
- 它应该沉淀：
  - 本项目的 repo-local skills
  - 本项目的 rollout / readiness / SOP 证据面
  - 本项目的业务语义边界
- 它不应该承担：
  - 全局通用 skill 的唯一实现
  - 跨项目统一平台的全部抽象

## 7.2 对未来类似项目
未来换到别的工厂/制造场景时，可直接复用：
- `readiness-check` 的方法框架
- `trial-go-live` 的门禁框架
- `ops-diagnose` 的问题分类框架
- `rollout-gate` 的三层投入标准
- `config-surface-sync` 的配置一致性审查框架

只需要替换：
- 业务实体（设备/工单/排班/账号体系）
- 现场 SOP 文档
- 项目脚本名与 API 端点
- 具体 hard issue / warning issue 代码集合

## 7.3 对长期产品线的建议结构
建议未来采用“双层 skill 目录”：
- **OMX 全局层**：沉淀可跨项目复用的框架 skill
- **项目层（repo-local）**：每个仓库用最薄的一层做业务绑定与上下文封装

也就是说，长期目标不是“只有全局 OMX skill”，而是：
**全局给框架，项目给绑定，脚本/API 给执行。**

## 8. 下一阶段施工建议（按优先级）

### P0：先补 repo-local skill scaffolding
- 建立项目内 skill 目录与最小规范
- 首批只落 3 个高价值 skill：
  1. `readiness-check`
  2. `trial-go-live`
  3. `ops-diagnose`

### P1：把现有脚本与 skill 套牢
- 每个 skill 明确它调用的脚本、读取的 docs、引用的 API
- 统一 skill 输出模板：结论 / 风险 / 阻断 / 下一步 / 责任人

### P2：补 config-surface-sync
- 先修 `AUTO_PIPELINE_REQUIRE_READY` 跨配置入口不一致
- 然后把此类检查抽成固定 skill

### P3：补 role-sop-review
- 与角色矩阵 lane 联动
- 把 README、页面文案、培训材料中的旧审核语义逐步清除

## 9. 最终结论

当前仓库已经具备 **脚本 + readiness + SOP + rollout 文档**，但还没有 **repo-local skill 层**。

因此本 lane 的核心结论是：
1. `aluminum-bypass` 不应只依赖全局 OMX skill，必须补项目级 repo-local skills。
2. 首批 repo-local skill 应围绕 **readiness、go-live、ops diagnose、rollout gate、config consistency、role/SOP consistency** 展开。
3. skill 必须站在 CLI / API 之上，负责解释与决策，不能替代确定性动作。
4. 长期体系应采用 **OMX 全局框架 + 项目层绑定 + 脚本/API 执行** 的三段式结构。
5. 以 2026-04-06 当前现实看，系统仍处于“本地可运行但未 ready、可作为试点样本底座”的阶段；因此 skill 体系的第一职责不是自动化炫技，而是把“是否能试点、为什么还不能正式上量、先修什么”解释清楚。
