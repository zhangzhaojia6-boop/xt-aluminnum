# 第二轮清洗与软件测试审计

日期：2026-05-02
范围：后端接口与测试、前端路由与页面测试、安全配置、部署脚本、Docker 构建上下文、仓库卫生。
方法：本地静态扫描 + 三个并行只读审计 agent + 针对性测试验证。敏感值已脱敏，报告不记录真实口令、密钥或数据库连接串。

## 已直接修复

| ID | 问题 | 证据 | 修复 |
|---|---|---|---|
| R01 | 生产部署脚本硬编码 SSH 登录密码 | `backend/scripts/deploy_production.py` | 改为 `DEPLOY_SSH_PASSWORD`，缺失时 fail-fast |
| R02 | 生产部署脚本硬编码数据库 DSN | `backend/scripts/deploy_production.py` | 改为 `DEPLOY_DATABASE_URL` |
| R03 | 生产部署脚本硬编码应用密钥 | `backend/scripts/deploy_production.py` | 改为 `DEPLOY_SECRET_KEY` |
| R04 | 生产部署脚本硬编码弱初始管理员密码 | `backend/scripts/deploy_production.py` | 改为 `DEPLOY_INIT_ADMIN_PASSWORD` |
| R05 | 生产部署脚本主机、用户、域名不可覆盖 | `backend/scripts/deploy_production.py` | 支持 `DEPLOY_HOST`、`DEPLOY_USER`、`DEPLOY_DOMAIN` |
| R06 | 后端 Docker build context 可能包含本地 `.env` | `backend/.dockerignore` | 增加 `.env`、`.env.*`、证书私钥排除 |
| R07 | 根 Docker build context 可能包含根 `.env` | `.dockerignore` | 增加 `.env`、`.env.*`、`.env.example` 例外 |
| R08 | 根 Docker build context 可能包含证书目录 | `.dockerignore` | 增加 `ssl/`、`*.pem`、`*.key` |
| R09 | 根 Docker build context 可能包含数据库备份 | `.dockerignore` | 增加 `backups/` |
| R10 | 临时视觉 diff 脚本被跟踪且名字仍是 `tmp_*` | `frontend/tmp_visual_diff.py` | 迁移到 `frontend/tools/visual-audit/visual-diff.py` |
| R11 | 视觉 diff 脚本绑定本机绝对路径 | `frontend/tools/visual-audit/visual-diff.py` | 改为 `REFERENCE_UI_TARGET_IMAGE` 或 `--target` |
| R12 | `.gitignore` 未覆盖 Python 临时脚本 | `.gitignore` | 增加 `frontend/tmp_*.py` |
| R13 | 部署脚本敏感值外置缺少回归保护 | `backend/tests/test_quick_cloud_trial_docs_and_ops.py` | 增加静态契约测试 |
| R14 | Docker ignore 安全规则缺少回归保护 | `backend/tests/test_quick_cloud_trial_docs_and_ops.py` | 增加 `.env`、证书、备份排除断言 |
| R15 | 视觉 diff 工具迁移缺少回归保护 | `backend/tests/test_reference_command_center_spec.py` | 更新路径并断言不含本机路径 |
| R16 | 文档泄漏本机绝对路径 | `docs/superpowers/*reference-ui-pixel-rebuild*` | 改为仓库外目标图占位说明 |
| R17 | 前端 node 单测缺少标准入口 | `frontend/package.json` | 增加 `test` 与 `test:unit` |
| R18 | `BrainCenter.vue` 零引用问题已处理 | `frontend/src/views/assistant/BrainCenter.vue` | 删除死代码，正式 AI 入口保留 `AiWorkstation.vue` |
| R19 | `ReviewLayout.vue` 零引用问题已处理 | `frontend/src/views/review/ReviewLayout.vue` | 删除死代码，正式审阅/管理壳层保留 `ManageShell.vue` |
| R20 | 兼容重定向缺少 query/hash 保留 | `frontend/src/router/index.js` | `/review/*`、`/admin/*` 改为 `preserveRouteState(...)` |
| R21 | 移动深链参数保留缺少测试 | `backend/tests/test_mobile_entry_copy_consistency.py` | 增加 `/mobile/report/*`、`/mobile/report-advanced/*`、`/mobile/ocr/*` 契约测试 |
| R22 | `/manage/admin` 占位页审计项已过期 | `frontend/src/router/index.js`、`frontend/e2e/admin-surface.spec.js` | `/manage/admin` 跳转真实运行页 `/manage/admin/settings`，E2E 断言 `live-dashboard` 可见且 `.xt-placeholder-page` 为 0 |
| R23 | 侧栏折叠记忆缺少刷新验证 | `frontend/e2e/manage-shell.spec.js` | 折叠后断言 `localStorage`，刷新后仍保持折叠，再展开并断言状态回写 |
| R24 | 管理壳层抽屉与搜索缺少 E2E | `frontend/e2e/manage-shell.spec.js` | 增加移动抽屉跳转、搜索弹层打开、关键词过滤和搜索结果跳转验证 |
| R25 | `desktop=1` 桌面豁免未契约化 | `frontend/e2e/login-delivery-smoke.spec.js` | 小屏填报可用账号默认 `/manage/overview` 回 `/entry`，带 `desktop=1` 时保留管理端 |
| R26 | 统一填报缺少重量业务规则 | `frontend/src/views/mobile/UnifiedEntryForm.vue`、`frontend/src/utils/entryWeightValidation.js` | 提交前校验可见重量非负、产出不大于投入、产出加废料不大于投入，并用 node 单测锁定 |
| R27 | 路由守卫缺少单元决策覆盖 | `frontend/src/router/guardRules.js`、`frontend/src/router/index.js` | 抽出纯决策层并覆盖 fill-only、admin、小屏桌面豁免和运行时 auth code |
| R28 | 日报审核路由只要求登录 | `backend/app/routers/reports.py`、`backend/tests/test_report_route_permissions.py` | 审核动作限制为 reviewer/manager/admin，并验证填报角色 403 且不调用服务 |
| R29 | 日报发布路由只要求登录 | `backend/app/routers/reports.py`、`backend/tests/test_report_route_permissions.py` | 发布动作限制为 manager/admin，并验证 reviewer 403、manager 可发布 |
| R30 | 日报流水线可由任意登录用户触发 | `backend/app/routers/reports.py`、`backend/tests/test_report_route_permissions.py` | 流水线执行复用发布权限，验证填报角色 403、manager 可执行 |
| R31 | 日报最终确认角色边界过宽 | `backend/app/services/report/report_generation.py`、`backend/tests/test_report_generation.py` | 最终确认限制为 manager/admin；有质量 blocker 的强制最终确认仍仅 admin，并用服务层测试锁定 |
| R32 | 报表路由 ValueError 到 400 缺少测试 | `backend/app/routers/reports.py`、`backend/tests/test_report_route_permissions.py` | 覆盖生成、审核、发布、最终确认、日报流水线的 ValueError 映射；日报流水线补齐 400 映射 |
| R33 | 报表列表与详情没有接口测试 | `backend/tests/test_report_export.py` | 覆盖列表过滤参数传递、详情命中和详情 404 |
| R34 | 导出仅覆盖 json/csv happy path | `backend/tests/test_report_export.py` | 补 xlsx happy path、缺 pandas 400、非法格式 400、缺报表 404 |
| R35 | 工单主链路多路由无行为测试 | `backend/tests/test_work_order_routes.py` | 覆盖工单创建、详情、列表过滤、entry 更新和 amendment 创建的路由参数转发与响应契约 |
| R36 | 非法 `X-Idempotency-Key` 400 分支无测 | `backend/tests/test_work_order_routes.py` | 覆盖非法 UUID header 返回 400，并验证服务层不会被调用 |
| R37 | `work_order_service.py` 动态兼容壳增加导入复杂度 | `backend/tests/test_service_compat_shims.py` | 锁定旧 `app.services.work_order_service` 路径与 package identity，并验证 monkeypatch 传播到子模块 |
| R38 | `report_service.py` 动态兼容壳增加导入复杂度 | `backend/tests/test_service_compat_shims.py` | 锁定旧 `app.services.report_service` 路径与 package identity，并验证 monkeypatch 传播到子模块 |
| R39 | 空白搜索会返回全部导航 | `backend/app/routers/search.py`、`backend/tests/test_search_routes.py` | strip 后为空的 query 返回 422，正常 AI 搜索行为保持 |
| R40 | 一个测试混合 search/export/notification | `backend/tests/test_platform_upgrade_api_routes.py` | 拆成搜索、导出、通知三个单行为测试 |
| R41 | `/api/v1/auth/login` 缺少真正接口测试 | `backend/tests/test_auth_routes.py` | 覆盖登录成功、错密、禁用用户、初始管理员创建，并验证登录审计记录 |
| R42 | `/me` 与 `/logout` 无接口测试 | `backend/tests/test_auth_routes.py` | 覆盖 `/me` 成功/无效 token 失败和 `/logout` 响应契约 |
| R43 | `virtual_workshop_qr` 分支未测 | `backend/tests/test_qr_login.py` | 覆盖虚拟车间二维码返回 `workshop_redirect` 且不签发 token |
| R44 | `virtual_role_qr` 自动建号和异常分支未测 | `backend/tests/test_qr_login.py` | 覆盖角色码自动建号、已存在用户复用、缺车间 404 和无效角色码 400 |
| R45 | 通知已读状态跨用户污染 | `backend/app/routers/notifications.py`、`backend/tests/test_notification_routes.py` | 通知模板与已读状态拆分，已读状态按用户 id 隔离 |
| R46 | 通知不存在时返回 `ok=false` 缺少契约 | `backend/app/routers/notifications.py`、`backend/tests/test_notification_routes.py` | 缺失通知改为 404 `通知不存在`，并用接口测试锁定 |
| R47 | QR 登录 schema 与真实返回不一致 | `backend/app/schemas/auth.py`、`backend/app/routers/auth.py`、`backend/tests/test_auth_schema_contract.py` | `QrLoginResponse` 改为 token/车间跳转 union，并挂到 `/auth/qr-login` OpenAPI 响应 |
| R48 | QR 首次建号使用统一初始密码 | `backend/app/routers/auth.py`、`backend/tests/test_qr_login.py` | 虚拟角色 QR 自动建号改为不可知随机密码 hash，账号登录需管理员显式重置 |
| R49 | 批量 seeded 账号默认口令一致 | `backend/scripts/seed_multi_role_accounts.py`、`backend/tests/test_seed_multi_role_accounts.py` | 多角色 seed 每个新账号单独生成不可知随机密码 hash，不再共享默认口令 |
| R50 | 生产启动可能重置已有管理员密码 | `backend/scripts/create_admin.py`、`backend/app/services/bootstrap.py`、`backend/tests/test_admin_bootstrap.py` | 已存在管理员保留原密码 hash，仅首次创建时写入初始化密码 |
| R51 | 后端配置保留带密码样式的默认数据库 URL | `backend/app/config.py`、`backend/tests/test_runtime_config.py` | 默认 `DATABASE_URL` 改为无嵌入口令的开发占位，并用 SQLAlchemy URL 解析测试锁定 |
| R52 | Alembic 配置保留默认 DSN | `backend/alembic.ini`、`backend/tests/test_runtime_config.py` | `sqlalchemy.url` 改为无嵌入口令占位，运行时仍由 `alembic/env.py` 从 `Settings` 覆盖 |
| R53 | 试运行环境弱默认只 warning | `backend/app/config.py`、`backend/tests/test_runtime_config.py` | `trial`、`uat`、`preprod` 等试运行环境纳入 production-like，弱密钥/初始密码 fail-fast |
| R54 | 车间主数据弹窗缺少前端必填校验 | `frontend/src/views/master/Workshop.vue`、`frontend/tests/workshopFormValidation.test.js` | 对 `code` / `name` 增加 Element Plus 必填校验，保存前 trim，并用前端 node 测试锁定 |
| R55 | 质量处置原因可为空 | `frontend/src/views/quality/QualityCenter.vue`、`backend/app/schemas/quality.py`、`backend/tests/test_quality_checks.py` | 前端 prompt 增加非空校验并 trim 后提交，后端 action schema/service 拒绝空说明，路由测试锁定 |
| R56 | 差异处理理由硬编码或允许空值 | `frontend/src/views/reconciliation/ReconciliationCenter.vue`、`backend/app/schemas/reconciliation.py`、`backend/tests/test_reconciliation_flow.py` | 确认/忽略/修正三类动作都要求输入说明，前端 trim 后提交，后端 action schema/service 拒绝空说明 |
| R57 | 总览页永久使用 mock/fallback 在制料数据 | `frontend/src/views/review/OverviewCenter.vue`、`frontend/tests/overviewWipSummary.test.js` | 移除 `mesWipSnapshotMock`，改读 factory-command overview 真实/本地口径，失败时显示 `--` 和明确来源状态 |
| R58 | 差异核对中心缺少浏览器级关键流覆盖 | `frontend/e2e/reconciliation-center.spec.js` | 覆盖列表与详情、生成差异请求、确认/忽略/修正三类处置说明，以及填报角色隔离 |
| R59 | 质量中心缺少浏览器级关键流覆盖 | `frontend/e2e/quality-center.spec.js` | 覆盖列表与详情、运行质量检查请求、标记已解决/忽略处置说明，以及填报角色隔离 |
| R60 | 日报与交付中心缺少浏览器级关键流覆盖 | `frontend/e2e/reports-center.spec.js` | 覆盖列表过滤请求参数、日报详情跳转与关键字段，以及填报角色隔离 |
| R61 | 二级浏览器上下文硬编码 baseURL | `frontend/e2e/workshop-template-config.spec.js` | 改为继承 Playwright 全局 `baseURL`，二级机台端页面用相对路径进入 |
| R62 | owner 工具车间 E2E 使用 UTC fallback 业务日期 | `frontend/e2e/owner-only-utility-workshop.spec.js` | fallback 改为本地业务日期格式，避免跨时区日期漂移 |

## 待处理问题清单

| ID | 等级 | 类别 | 问题 | 位置 | 建议 |
|---|---|---|---|---|---|
| F04 | 低 | 死代码 | 多个主数据旧页面零引用但兼容路由还在 | `frontend/src/views/master/*` | 清理孤儿页面或补兼容路由测试 |
| F05 | 低 | 原型残留 | `reference-command/pages/*` 整套参考页未挂载 | `frontend/src/reference-command/pages` | 迁出原型树或加 README 标识 |
| F08 | 中 | 登录测试 | 免登、机台、车间 query 分支未覆盖 | `frontend/src/views/Login.vue` | 增加登录分支和 query 清洗用例 |
| F13 | 低 | 死分支 | 移动首页存在无模板绑定函数 | `frontend/src/views/mobile/MobileEntry.vue` | 删除死分支或恢复入口 |
| F22 | 中 | 凭据卫生 | E2E 内置账号口令 | `frontend/e2e/*.spec.js` | 改为环境变量注入 |
| S01 | 高 | SSH 安全 | 部署脚本仍使用 root + 密码登录 + `AutoAddPolicy` | `backend/scripts/deploy_production.py` | 改 SSH key、固定 known_hosts、最小权限用户 |
| S08 | 中 | CI 凭据 | CI 写死测试密码和固定密钥 | `.github/workflows/ci.yml` | 使用 GitHub Secrets 或运行时随机值 |
| S09 | 中 | CI 权限 | CI 使用 `chmod 777 backend/uploads` | `.github/workflows/ci.yml` | 改最小权限和明确 owner/group |
| S10 | 中 | 测试鉴权 | E2E 直接写 token 到 storage | `frontend/e2e/helpers` | 关键链路走真实登录 |
| S11 | 中 | TLS 测试 | Playwright 默认忽略 HTTPS 错误 | `frontend/playwright.config.js` | 仅本地自签名场景打开 |
| S12 | 中 | 脚本可复现性 | 后端手工测试脚本打固定 localhost 和 live token | `backend/scripts/test_*.py` | 改 pytest + TestClient |
| S14 | 中 | 制品入库 | QR PDF 已跟踪 | `docs/role_qr_codes.pdf`、`docs/workshop_qr_codes.pdf` | 改脱敏样例或迁移制品仓库 |
| S15 | 低 | 仓库体积 | 高分辨率 UI 截图较多 | `docs/ui-reference/highres/*.png` | 压缩或转 manifest/缩略图 |
| B01 | 高 | 测试边界 | 后端测试直接断言前端源码，本次后端全测 5 个失败均来自这类断言 | `backend/tests/test_*copy*`、`backend/tests/test_reference_command_center_spec.py` | 迁出前端规范断言或用 marker 隔离 |
| B21 | 低 | 未接入代码 | `deterministic_orchestration_service.py` 无引用无测试 | `backend/app/services` | 确认废弃后删除或补入口和测试 |

## 测试记录

- 前端 agent 基线：`node --test frontend/tests/mobileSwipe.test.js frontend/tests/offlineResilience.test.js frontend/tests/submitGuard.test.js frontend/tests/useRealtimeStream.test.js`，结果 `11 passed / 0 failed`。
- 后端 agent 基线：`python -m pytest backend/tests -q`，结果 `513 passed / 5 failed`；失败点来自后端测试读取前端源码的跨层断言。
- 本轮修复后的最终验证记录以提交前命令输出为准。
