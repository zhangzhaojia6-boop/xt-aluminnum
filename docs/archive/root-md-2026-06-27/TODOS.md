# TODOS

按组件/功能分组，每项标注优先级（P0 最高 → P4 最低）。已完成的项移至文末 `## Completed`。

## Open

- **合并 3 份 canAccess 重复函数**
  - **Priority:** P4
  - `manage-navigation.js`、`manage-settings-drawer.js`、`navigation.js` 各有一份 `canAccess`，逻辑类似但不完全相同。合并为一份共享函数。

- **清理 backend factory-command API/store 死代码**
  - **Priority:** P4
  - 前端 factory-command 视图已大量删除，backend `routers/factory_command.py` 和 frontend `stores/factory-command.js` 可能有不再被调用的端点和 action。

- **补导航配置单元测试**
  - **Priority:** P4
  - `manage-navigation.js`、`manage-settings-drawer.js`、`navigation.js` 的分组逻辑和权限过滤缺少完整单元测试覆盖。

## Completed

- **Phase C-1：异常与补录单列时间线**
  - **Priority:** P1
  - 重写 `/manage/alerts` 为 EventTimeline + DomainFilterChips + EventCard，4 域筛选；新增 `useAlertsTimeline` composable（allSettled + 单端点 fallback + inflight 防竞态）
  - **Completed:** v0.2.0.0 (2026-05-25)

- **Phase B：管理端三主视图骨架**
  - **Priority:** P1
  - `/manage/today` `/manage/production` `/manage/alerts` 三页面骨架；KpiBar、WorkshopBarChart、KeyEventList、CostLine 组件落地；旧入口统一 redirect
  - **Completed:** v0.2.0.0 (2026-05-25)

- **设计系统 token 收敛**
  - **Priority:** P2
  - 补全 `--xt-color-*` 别名；ManageShell hex/rgba → token + color-mix；ECharts 颜色运行时读取 token
  - **Completed:** v0.2.0.0 (2026-05-25)

- **首次建立版本管理三件套**
  - **Priority:** P3
  - 引入 `VERSION`（0.1.0.0）、`CHANGELOG.md`、`TODOS.md`，作为后续 /ship 流程的基础
  - **Completed:** v0.1.0.0 (2026-05-09)

- **落地前/后流程对比文档**
  - **Priority:** P3
  - 新增 `docs/落地前-旧流程`、`docs/落地后-新流程`、`docs/落地前后对比` 三组 HTML + PDF 文档
  - **Completed:** v0.1.0.0 (2026-05-09)
