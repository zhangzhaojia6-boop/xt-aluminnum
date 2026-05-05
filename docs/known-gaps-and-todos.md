# 已知缺口与 TODO（持续更新）

## 1. 成本后端物理落表未完全接入

- 当前前端已实现策略引擎、价格主数据、表模型快照与校差记录展示
- `cost_price_master / cost_workshop_strategy / cost_daily_result / cost_monthly_rollup / cost_variance_record` 已作为前端表模型 contract 输出
- 后续待接入后端物理表、持久化写入与月度结账流程

## 2. AI 多专题接口仍有 mock 兜底

- 当前基于 `/api/v1/assistant/*`、现有 dashboard 数据与专题 AI 卡片拼装
- 若 live-probe 不可用，前端保持可视化 fallback，不阻塞主流程

## 3. 旧 E2E 用例对结构依赖较强

- 当前 `frontend/e2e` 已有 20 个 Playwright spec 文件；质量、差异核对、日报交付等审阅中心关键流已分别落到 `quality-center.spec.js`、`reconciliation-center.spec.js`、`reports-center.spec.js`
- 后续新增页面结构时继续优先复用 `frontend/e2e/helpers/review-mocks.js`，避免环境依赖导致假失败

## 4. Entry 独立端与 mobile 兼容期并存

- 现阶段保留 `/mobile/*` -> `/entry/*` 前端重定向
- 待线上稳定后再评估是否彻底收口到 `/entry/*`

## 5. Desktop legacy 页面样式统一尚未完全完成

- 优先保证运行与权限正确
- 分批迁移到统一 AppShell card/table/form 组件

## 6. 上线闸门依赖目标业务日应报清单

- 当前 `readyz` 与试跑排班种子脚本均使用 `DEFAULT_TIMEZONE=Asia/Shanghai` 解析目标业务日
- compose 启动链路已自动执行 `python scripts/init_real_master_data.py`，会在服务启动时初始化目标业务日应报清单
- 已运行容器跨目标业务日或跳过重启时，正式试跑前再执行 `docker compose exec -T backend python scripts/init_real_master_data.py` 刷新目标日应报清单，避免 `SCHEDULE_EMPTY`
- 容器内 `/readyz` 已可返回 `target_date_schedule_available`

## 7. 主数据与模板中心仍需补齐一站式覆盖

- `/admin/master` 已重定向到 `/manage/master`；`/manage/master` 运行页已标为 `车间主数据`，当前由 `Workshop.vue` 通过 `/api/v1/master/workshops` 真实接口承接车间主数据查看、新增、编辑和删除
- 班组、员工、机台、别名、字典与字段模板仍分散在独立页面或后续配置面；后续若做一站式主数据中心，需要先补接口聚合方案和权限边界文档
