# 2026-07-16 投产闭环基线

## 证据说明

- 复核时间：2026-07-16 13:38:30 +08:00。
- 本地环境：Windows 工作站，隔离 Git worktree。
- 生产环境：GitHub Actions 通过受控 SSH 在生产 Ubuntu 主机执行只读状态检查。
- 结构化证据清单：`docs/superpowers/reports/2026-07-16-production-readiness-baseline-evidence.json`。
- 生产同步状态：[GitHub Actions #29468271590](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29468271590)。
- 钉钉 Stream 配置状态：[GitHub Actions #29468904272](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29468904272)。
- Hermes 20 问失败证据：[GitHub Actions #29450363271](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29450363271)，artifact `hermes-20q-production-29450363271`。
- 日报对齐失败证据：[GitHub Actions #29450406503](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29450406503)，artifact `daily-report-alignment-production-29450406503`。

生产执行入口分别固定在 `.github/workflows/production-sync-status.yml`、`.github/workflows/configure-dingtalk-stream-prod.yml`、`.github/workflows/hermes-acceptance-prod.yml` 和 `.github/workflows/daily-report-alignment-prod.yml`。调用参数、退出码和核心命令记录在结构化证据清单中；成功状态检查退出码为 0，两项业务门禁失败退出码为 1。

## 版本

- 数据中枢本地、远端和生产基线：`c3961c3852c3459fed98c3e15537189cb9eeb9eb`
- Hermes 本地、远端和生产基线：`7e99a11319721d7c7d4c14af17620f88f58d7144`
- 执行分支：`feat/production-readiness-closure-20260716`
- 隔离工作树：`.worktrees/production-readiness-closure-20260716`

## 当前已证明

- 数据中枢、Nginx 和 Hermes Gateway 生产服务处于 active。
- `/readyz` 数据库、设备、MES、pipeline、排产和上传检查正常。
- MES/WMS 生产适配器为 SQL Server 只读链路，最近同步成功。
- 钉钉 Stream 生产配置已启用，Hermes Gateway 已建立连接。
- 当前业务口径为 13 个活跃生产车间；数据库宽口径为 15 项。
- 当前时间合同为标准生产 07:50、铸二/铸三/热轧 10:00、责任人每日一录 09:30、责任人迟报截止 10:00。
- 能耗数据库尚未配置，状态为 `unconfigured`。

上述生产状态来自 #29468271590 的 `status` 模式：数据中枢与 Hermes HEAD、tracked state、三个 systemd service、`/readyz`、`/versionz`、MES sync 和 Stream runtime state 均在同一次远端命令中采集。该证据只能证明采集时刻状态，不代表后续业务门禁已通过。

## 当前未证明或失败

- 钉钉服务启动后真实消息和文件持久化尚无验收证据；检查时 `chat_inbox=0`、`multimodal_evidence=0`。
- Hermes 正式 20 问核心答案为 12/20；发送链路为 20/20。
- 20 问当前主要验证数据中枢确定性 Agent，尚未完整证明 NousResearch Hermes 原生循环。
- 最近三个业务日 compare-only 日报匹配结果为：

| 业务日 | 匹配字段 | 总字段 | 匹配率 | 真实源门禁 |
|---|---:|---:|---:|---|
| 2026-07-11 | 11 | 127 | 8.66% | 失败 |
| 2026-07-12 | 8 | 127 | 6.30% | 失败 |
| 2026-07-13 | 7 | 120 | 5.83% | 失败 |

规范日报合同固定为 127 个字段。2026-07-13 的答案钥匙没有出现以下 7 个字段，且未声明 N/A，因此当前只能标记为 `reference_absent`，不能把分母静默缩小后用于最终投产判定：

- `daily_contract_weight`
- `daily_hot_roll_contract_weight`
- `cold_roll_input_daily`
- `cold_2050_input_daily`
- `cold_1850_input_daily`
- `medium_plate_input_daily`
- `remaining_contract_weight`

当前 `5.83%` 是答案钥匙已出现的 120 字段匹配率；按 127 字段规范覆盖口径为 `7/127 = 5.51%`。Phase 2 必须让门禁同时输出这两个指标，并要求上述 7 字段取得明确 N/A 或补证结论。

- 2026-07-12 在制品真实值为 1798.5，答案钥匙为 1758.5，差值 40；系统保留了真实值，没有采用答案钥匙填数。
- Hermes 原生回复和数据中枢业务 Agent 回复仍存在双轨职责。
- 旧 Understand 图谱提交落后当前 HEAD，只能作为历史地图；2026-06-14 历史汇总中的生产业务日 07:30 也已被 2026-06-19 的现行代码更新。

## 隔离工作树自动基线

### 后端关键链路

执行范围：业务时间、SQL Server MES 只读适配器、钉钉入站、日报事实包、责任人生产编排器、Hermes 20 问 runner。

执行命令：`uv run --with-requirements backend/requirements.txt --with pytest pytest -q backend/tests/test_business_time_contract.py backend/tests/test_sqlserver_mes_adapter.py backend/tests/test_dingtalk_agent_inbound_route.py backend/tests/test_daily_fact_bundle_service.py backend/tests/test_hermes_root_owner_production_orchestrator.py backend/tests/test_hermes_20_question_runner.py`。

结果：退出码 0，`176 passed, 9 warnings`。

警告为 Pydantic 受保护命名空间和 openpyxl UTC 时间弃用警告，不影响当前基线通过，但必须在后续质量阶段登记处理。

### 前端

- 在 `frontend` 目录执行 `npm ci`：退出码 0，安装成功，审计发现 0 个漏洞。
- 在 `frontend` 目录执行 `npm test`：退出码 0，`727 passed, 0 failed`。
- 在 `frontend` 目录执行 `npm run build`：退出码 0，生产构建成功。
- 构建存在单个大于 500 kB 的 chunk 警告，归入 Phase 10 性能与构建质量检查。

## 基线结论

基础代码和生产服务具备继续施工的稳定起点，但业务事实闭环尚未达到投产标准。后续任何“完成”声明必须同时引用本计划定义的阶段门禁和新产生的真实证据。
