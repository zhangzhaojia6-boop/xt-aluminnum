# Launch Readiness Checklist

## 入口

- `/manage/today` 可访问。
- `/manage/factory`、`/manage/workshop` 可访问。
- `/manage/ai-assistant` 可访问，页面名称使用 AI 助手。
- `/entry` 可访问。

## AI 助手

AI 助手用于读取数据中枢、MES 只读数据、钉钉补充数据，并生成可追溯日报。上线前确认回答带数据来源、时间窗口和缺口提示。

## 发布

1. GitHub main 已合并。
2. 云主机可拉取。
3. 数据库迁移到 head。
4. `/healthz` 与 `/readyz` 通过。
