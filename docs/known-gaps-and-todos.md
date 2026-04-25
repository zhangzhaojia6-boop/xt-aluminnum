# 已知缺口与 TODO（持续更新）

## 1. 成本后端物理落表未完全接入

- 当前前端已实现策略引擎、价格主数据、表模型快照与校差记录展示
- `cost_price_master / cost_workshop_strategy / cost_daily_result / cost_monthly_rollup / cost_variance_record` 已作为前端表模型 contract 输出
- 后续待接入后端物理表、持久化写入与月度结账流程

## 2. AI 多专题接口仍有 mock 兜底

- 当前基于 `/api/v1/assistant/*`、现有 dashboard 数据与专题 AI 卡片拼装
- 若 live-probe 不可用，前端保持可视化 fallback，不阻塞主流程

## 3. 旧 E2E 用例对结构依赖较强

- 已完成首轮重构对齐（13 条前端 e2e 全部通过）
- 后续新增页面结构时继续优先复用 `frontend/e2e/helpers/review-mocks.js`，避免环境依赖导致假失败

## 4. Entry 独立端与 mobile 兼容期并存

- 现阶段保留 `/mobile/*` -> `/entry/*` 前端重定向
- 待线上稳定后再评估是否彻底收口到 `/entry/*`

## 5. Desktop legacy 页面样式统一尚未完全完成

- 优先保证运行与权限正确
- 分批迁移到统一 AppShell card/table/form 组件

## 6. 上线闸门依赖“次日应报清单”预置

- 当前 `readyz` 使用 UTC 自然日校验排班，跨日后若无次日排班会触发 `SCHEDULE_EMPTY`
- 试跑前需执行一次 `docker compose exec -T backend python scripts/init_real_master_data.py` 预置当日应报清单

## 7. 主数据与模板中心仍为只读 fallback/mixed 配置面

- `/admin/master` 已对齐高清目标图 14，当前使用 `masterCenterMock` 展示车间、班组、员工、机台、用户、班次、别名、模板和字段规则状态
- 导出配置、发布模板、保存字段规则保持 disabled；后续若接入真实主数据接口，需要先补接口方案和权限边界文档
