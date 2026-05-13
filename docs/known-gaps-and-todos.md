# 已知缺口与 TODO（持续更新）

## 1. 成本经营复核与月结闭环未完全接入

- 当前前端已实现策略引擎、价格主数据、表模型快照与校差记录展示
- `cost_price_master / cost_workshop_strategy / cost_daily_result / cost_monthly_rollup / cost_variance_record` 已作为前端表模型 contract 输出
- 后端已新增对应 SQLAlchemy 模型与 Alembic `0028_cost_strategy_tables` 物理表迁移，`cost_price_master` 会种入当前前端默认价格主数据
- 后端已新增 admin-only `POST /api/v1/executive/cost-strategy-snapshots`，可把前端表模型快照按业务唯一键 upsert 到 5 张成本表
- 管理端已新增 `/manage/factory/cost/accounting` 策略核算页，并接入“保存快照”动作
- 后续待接入人工复核权限边界与月度结账流程；当前仍不作为财务正式结账凭证

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
- 后端启动时会先运行一次 `seed_default_pilot_schedule()`，APScheduler 每天 `00:05` 自动补种目标业务日应报清单
- 手工执行 `python scripts/init_real_master_data.py` 仍作为应急兜底，用于已停用调度器、旧部署未升级或现场需要立即恢复 `SCHEDULE_EMPTY` 时
- 容器内 `/readyz` 已可返回 `target_date_schedule_available`

## 7. 主数据与模板中心仍需补齐一站式覆盖

- `/admin/master` 已重定向到 `/manage/master`；`/manage/master` 运行页已标为 `车间主数据`，当前由 `Workshop.vue` 通过 `/api/v1/master/workshops` 真实接口承接车间主数据查看、新增、编辑和删除
- 班组、员工、机台、别名、字典与字段模板仍分散在独立页面或后续配置面；后续若做一站式主数据中心，需要先补接口聚合方案和权限边界文档

## 8. 外部正式联通闸门仍未通过

- 生产 `/readyz` 已为 ready，外部 MES 同步也可用，但这只代表系统地基和 MES 投影链路可用，不能把 `/readyz` ready 误判为外部联通完成
- 当前 `python scripts/check_statistics_module_ready.py --json` 仍返回 hard fail：`LLM_DISABLED`、`APP_CONNECTION_DISABLED`
- 正式试用闸门应加跑 `python scripts/check_statistics_module_ready.py --json --check-live-aggregation`，用实时聚合只读探针确认管理端实时数据服务可计算；当天无填报不算失败，服务异常才算 `LIVE_AGGREGATION_UNAVAILABLE`
- 对外索取现场输入前应先跑 `python scripts/check_statistics_module_ready.py --missing-inputs`，输出用途、所在位置、缺失字段、影响范围和建议取值，不凭记忆手写清单
- 当前 warning 仍为 `DINGTALK_NO_BOUND_USERS`：钉钉应用已启用，但 active 用户/员工没有绑定 `dingtalk_user_id`，真实人员触达和客户端 UAT 未闭环
- 若正式试用前要自动同步通讯录，应加跑 `python scripts/check_statistics_module_ready.py --json --check-dingtalk-contacts`；当前仍返回 `DINGTALK_CONTACTS_PERMISSION_MISSING`，缺钉钉开放平台权限 `qyapi_get_department_member`
- 后续正式试用前需要在服务器 `backend/.env` 补齐真实 LLM、应用连接 API 和钉钉人员绑定；缺密钥时只能保留清单，不能猜值或写入仓库

## 9. `2026-04-22` 每日产量源表仍阻断

- `2026-04-22` 原始每日产量源表解析结果仍为 `blocked / rows=0`
- `D:\鑫泰报表\4.22\鑫泰每日产量4月22日.xls` 的综合页表头显示 `2026年4月23日`，且 `投料量/日产量/产生废料` 生产列为空，不能作为 `2026-04-22` 正式事实源
- `D:\鑫泰报表\输出skill\2026-4-22_日均报表.xls` 解析为 `no_daily_production_summary_sheet`，不是当前综合日报格式
- 同日 `日报正文.txt` 写明热轧日产 `262t`，但 `日均报表.xls` 的“各工序产量报表”中 `热轧` 行日产量为 `0t`，且表内混有明细、合计、包装/入库和在制类行
- 该日只能继续列为参考资产和缺口，不能用当前空表或口径冲突表强行入库；补齐时必须先找到同日非空综合日报源表或现场确认替代表
