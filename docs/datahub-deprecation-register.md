# 数据中枢冻结与候选删除登记表

本文件记录可以冻结、合并或进入候选删除的对象。

硬规则：

- 不直接删除生产表。
- 不删除原始证据。
- 不删除审计日志。
- 不删除 Hermes、DingTalk、DailyFactBundle、MES/WMS 投影依赖链。
- 候选删除必须先观察 7 到 14 天。

| 对象 | 分类 | 当前动作 | 观察期 | 回滚方式 |
|---|---|---|---|---|
| `/manage/today` | protect | keep | 长期保留 | 保持当前管理日报主路由 |
| `/manage/live` | protect | keep | 长期保留 | 保持当前管理实时主路由 |
| `/manage/production` | protect | keep | 长期保留 | 保持当前生产分析主路由 |
| `/manage/coils` | protect | keep | 长期保留 | 保持当前卷追踪主路由 |
| `/entry/*` | protect | keep | 长期保留 | 保持当前填报主入口与子路由 |
| `frontend/src/reference-command/pages/*` | freeze | 仅作为历史参考资产 | 14 天 | 保留 git 文件，不挂载生产路由 |
| `/review/*` 旧入口 | freeze | 保留重定向 | 14 天 | 恢复当前路由配置 |
| `/mobile/*` 旧入口 | freeze | 保留到 `/entry/*` 的兼容跳转 | 14 天 | 恢复当前路由配置 |
