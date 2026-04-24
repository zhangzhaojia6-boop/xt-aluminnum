# Parse 10 Review Analysis Section Matrix Design

## 背景

parse9 已经让 `analysis_handoff` 具备：

- 当前 readiness 与 blocking reasons
- priority / attention flags
- trend / freshness / data_gaps
- reporting / delivery / energy / contracts / risk 五个 typed section

现在后续 AI 已经能读到完整 section 内容，但仍缺一个更快的入口：
它还需要自己遍历每个 section 的 `status`，才能知道哪些块健康、哪些块告警、哪些块阻塞、哪些块空置。

## parse10 目标

给 `analysis_handoff` 增加顶层 `section_matrix`，把五个核心 section 的状态整理成稳定的 quick index。

建议首批输出：

- `healthy_sections`
- `warning_sections`
- `blocked_sections`
- `idle_sections`

## 设计原则

- 继续只做 deterministic contract
- `section_matrix` 只复用 handoff 已有的 section status
- 不新增数据库查询
- 不生成自然语言结论

## 本阶段不做

- 不增加新的 section
- 不做权重评分
- 不改前端审阅页面

## 验收标准

- `analysis_handoff.section_matrix` 有 typed contract
- route tests 锁定 section matrix 字段
- build_factory_dashboard 定向测试锁定真实派生结果
- focused 回归通过，若容器可用则补后端全量
