# Agent 与 Skill 协作面

## 1. 运行时 Agent

这些 Agent 属于系统内运行时执行器，只消费结构化事实，不负责自由推理式聊天。

### validator-agent
- 输入：移动端提交后的单班次数据
- 输出：`approved` / `returned` 与可执行 `returned_reason`
- 非职责：不重建旧统计员人工核对表

### aggregator-agent
- 输入：已确认班次、异常摘要、移动上报概况
- 输出：canonical 生产日报、老板摘要、异常摘要
- 非职责：不把合同表/成品率矩阵/发货图片重新做回主工作流

### reporter-agent
- 输入：已发布日报
- 输出：管理层触达、workflow 留痕
- 非职责：不承担人工复制粘贴式发布

### reminder-agent
- 输入：应报清单 + 当前提交状态
- 输出：催报 / 升级提醒
- 非职责：不做人肉总催收台

## 2. Repo-local Skills

这些 skill 面向人 + AI 协作，负责解释、归因、编排与决策。

### `aluminum-legacy-gap`
- 作用：盘点历史旧报表与当前系统结构的缺口
- 输入：历史 `.xls/.xlsx/.png` 样本、当前 docs / API / 前端
- 输出：缺口清单、旁路信息面、最小补修建议

### `aluminum-daily-ops`
- 作用：把每天试点值班动作收口成固定流程
- 输入：`check_pilot_config` / `check_pilot_metrics` / `check_pilot_anomalies` / `docker compose ps`
- 输出：当天结论、风险、阻塞、下一步

### `aluminum-go-live-gate`
- 作用：上线门禁与降级判断
- 输入：`readyz`、Gate A/B/C、Access / tunnel / rollback 材料
- 输出：是否允许放量、阻塞项、降级建议

## 3. 分工边界

- Agent：做系统内确定性动作
- Skill：做跨证据面的解释、编排、归因、门禁决策
- 网站：看结果、看异常、看阻塞
- 工人端：只负责最小录入
