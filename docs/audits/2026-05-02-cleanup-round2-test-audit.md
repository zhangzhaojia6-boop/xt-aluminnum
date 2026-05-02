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

## 待处理问题清单

| ID | 等级 | 类别 | 问题 | 位置 | 建议 |
|---|---|---|---|---|---|
| F01 | 中 | 前端路由 | `/manage/admin` 仍是占位页，E2E 还断言占位页可见 | `frontend/src/router/index.js`、`frontend/e2e/admin-surface.spec.js` | 替换为真实后台页面或让测试验证真实模块 |
| F02 | 低 | 死代码 | `BrainCenter.vue` 处于零引用状态 | `frontend/src/views/assistant/BrainCenter.vue` | 删除、恢复挂载或标记为历史样例 |
| F03 | 低 | 死代码 | `ReviewLayout.vue` 零引用 | `frontend/src/views/review/ReviewLayout.vue` | 删除或恢复使用 |
| F04 | 低 | 死代码 | 多个主数据旧页面零引用但兼容路由还在 | `frontend/src/views/master/*` | 清理孤儿页面或补兼容路由测试 |
| F05 | 低 | 原型残留 | `reference-command/pages/*` 整套参考页未挂载 | `frontend/src/reference-command/pages` | 迁出原型树或加 README 标识 |
| F06 | 中 | 路由测试 | 兼容重定向未覆盖 query/hash 保留 | `frontend/src/router/index.js` | 为 `/review/*`、`/admin/*` 增加路由回归 |
| F07 | 中 | 移动深链 | `/mobile/report/*`、`/mobile/ocr/*` 重定向缺少测试 | `frontend/src/router/index.js` | 增加深链参数保留测试 |
| F08 | 中 | 登录测试 | 免登、机台、车间 query 分支未覆盖 | `frontend/src/views/Login.vue` | 增加登录分支和 query 清洗用例 |
| F09 | 低 | 测试准确性 | 侧栏折叠记忆只点击不刷新验证 | `frontend/e2e/manage-shell.spec.js` | reload 后断言 localStorage 状态生效 |
| F10 | 中 | 导航测试 | 抽屉导航、搜索弹层、关键词过滤无测试 | `frontend/src/layout/ManageShell.vue` | 增加键盘搜索和移动抽屉 E2E |
| F11 | 中 | 路由守卫 | `installRouterGuards` 缺少单元测试 | `frontend/src/router/index.js` | 覆盖 fill-only、admin、compact、runtime auth code |
| F12 | 中 | 移动适配 | `desktop=1` 桌面豁免未被契约化 | `frontend/src/router/index.js` | 移动视口下验证默认跳转和豁免 |
| F13 | 低 | 死分支 | 移动首页存在无模板绑定函数 | `frontend/src/views/mobile/MobileEntry.vue` | 删除死分支或恢复入口 |
| F14 | 高 | 数据校验 | 统一填报仅校验非空，缺少重量业务规则 | `frontend/src/views/mobile/UnifiedEntryForm.vue` | 增加非负、投入产出关系校验 |
| F15 | 中 | 表单校验 | 车间主数据弹窗缺少前端必填校验 | `frontend/src/views/master/Workshop.vue` | 对 code/name 增加 rules 和失败用例 |
| F16 | 中 | 审计链 | 质量处置原因可为空 | `frontend/src/views/quality/QualityCenter.vue` | prompt 增加非空校验 |
| F17 | 中 | 审计链 | 差异处理理由硬编码或允许空值 | `frontend/src/views/reconciliation/ReconciliationCenter.vue` | 三类处置动作都要求输入说明 |
| F18 | 中 | 数据真实性 | 总览页仍永久使用 mock/fallback 标记 | `frontend/src/views/review/OverviewCenter.vue` | 区分真实数据和回退数据 |
| F19 | 中 | 报表测试 | 报表页 E2E 只测静态外观 | `frontend/e2e/review-runtime.spec.js` | 断言请求参数和详情跳转 |
| F20 | 中 | 质量测试 | 质量页关键动作无 E2E | `frontend/src/views/quality/QualityCenter.vue` | 覆盖运行检查、详情、处置 |
| F21 | 高 | 核对测试 | 差异核对中心几乎无自动化 | `frontend/src/views/reconciliation/ReconciliationCenter.vue` | 新增生成和三类处置 E2E |
| F22 | 中 | 凭据卫生 | E2E 内置账号口令 | `frontend/e2e/*.spec.js` | 改为环境变量注入 |
| F23 | 低 | 测试配置 | 次级 browser context 硬编码 baseURL | `frontend/e2e/workshop-template-config.spec.js` | 复用 Playwright 全局 baseURL |
| F24 | 低 | 测试稳定性 | 测试用 UTC 截业务日期 | `frontend/e2e/owner-only-utility-workshop.spec.js` | 使用固定业务日期或本地时区 |
| S01 | 高 | SSH 安全 | 部署脚本仍使用 root + 密码登录 + `AutoAddPolicy` | `backend/scripts/deploy_production.py` | 改 SSH key、固定 known_hosts、最小权限用户 |
| S02 | 中 | 配置默认 | 后端配置保留带密码样式的默认数据库 URL | `backend/app/config.py` | 要求显式注入或使用无密码占位 |
| S03 | 中 | 迁移配置 | Alembic 配置保留默认 DSN | `backend/alembic.ini` | 从环境变量读取迁移 DSN |
| S04 | 中 | 弱默认 | 非 production 环境弱密钥只 warning | `backend/app/config.py` | staging/试运行环境也 fail-fast |
| S05 | 高 | 默认密码 | QR 首次建号使用统一初始密码 | `backend/app/routers/auth.py` | 改随机 PIN、一次性激活或禁用密码回退 |
| S06 | 高 | 默认密码 | 批量 seeded 账号默认口令一致 | `backend/scripts/seed_multi_role_accounts.py` | 随机生成并强制首次改密 |
| S07 | 高 | 管理员重置 | 生产 compose 每次启动可能重置 admin 密码 | `docker-compose.prod.yml`、`backend/scripts/create_admin.py` | 仅首次初始化，已存在用户禁止覆盖密码 |
| S08 | 中 | CI 凭据 | CI 写死测试密码和固定密钥 | `.github/workflows/ci.yml` | 使用 GitHub Secrets 或运行时随机值 |
| S09 | 中 | CI 权限 | CI 使用 `chmod 777 backend/uploads` | `.github/workflows/ci.yml` | 改最小权限和明确 owner/group |
| S10 | 中 | 测试鉴权 | E2E 直接写 token 到 storage | `frontend/e2e/helpers` | 关键链路走真实登录 |
| S11 | 中 | TLS 测试 | Playwright 默认忽略 HTTPS 错误 | `frontend/playwright.config.js` | 仅本地自签名场景打开 |
| S12 | 中 | 脚本可复现性 | 后端手工测试脚本打固定 localhost 和 live token | `backend/scripts/test_*.py` | 改 pytest + TestClient |
| S14 | 中 | 制品入库 | QR PDF 已跟踪 | `docs/role_qr_codes.pdf`、`docs/workshop_qr_codes.pdf` | 改脱敏样例或迁移制品仓库 |
| S15 | 低 | 仓库体积 | 高分辨率 UI 截图较多 | `docs/ui-reference/highres/*.png` | 压缩或转 manifest/缩略图 |
| B01 | 高 | 测试边界 | 后端测试直接断言前端源码，本次后端全测 5 个失败均来自这类断言 | `backend/tests/test_*copy*`、`backend/tests/test_reference_command_center_spec.py` | 迁出前端规范断言或用 marker 隔离 |
| B02 | 高 | 认证测试 | `/api/v1/auth/login` 缺少真正接口测试 | `backend/app/routers/auth.py` | 覆盖成功、错密、禁用用户、首登初始化 |
| B03 | 中 | 认证测试 | `/me` 与 `/logout` 无接口测试 | `backend/app/routers/auth.py` | 补鉴权成功/失败和响应契约 |
| B04 | 中 | QR 兼容 | `virtual_workshop_qr` 分支未测 | `backend/app/routers/auth.py` | 覆盖 workshop_redirect |
| B05 | 高 | QR 兼容 | `virtual_role_qr` 自动建号和异常分支未测 | `backend/app/routers/auth.py` | 覆盖角色码、缺车间、已存在用户 |
| B06 | 中 | 状态隔离 | 通知数据是模块级全局列表 | `backend/app/routers/notifications.py` | 用户维度隔离并补测试 |
| B07 | 低 | 错误语义 | 通知不存在时返回 `ok=false` 缺少契约 | `backend/app/routers/notifications.py` | 明确 404 或锁定 200 语义 |
| B08 | 中 | 搜索校验 | 空白搜索会 strip 成空串并返回全部导航 | `backend/app/routers/search.py` | strip 后空串返回 422 或空结果 |
| B09 | 低 | 测试设计 | 一个测试混合 search/export/notification | `backend/tests/test_platform_upgrade_api_routes.py` | 拆成三个单行为测试 |
| B10 | 中 | 报表测试 | 报表列表与详情没有接口测试 | `backend/app/routers/reports.py` | 覆盖过滤、详情命中、404 |
| B11 | 中 | 导出测试 | 导出仅覆盖 json/csv happy path | `backend/app/routers/reports.py` | 补 xlsx、缺 pandas、400、404 |
| B12 | 高 | 权限边界 | review_report 仅要求登录，无角色限制 | `backend/app/routers/reports.py` | 明确角色并加拒绝测试 |
| B13 | 高 | 权限边界 | publish_report 仅要求登录，无角色限制 | `backend/app/routers/reports.py` | 增加角色校验和 403 测试 |
| B14 | 高 | 权限边界 | finalize_report 无 blocker 时角色边界过宽 | `backend/app/services/report/report_generation.py` | 明确最终确认角色 |
| B15 | 高 | 权限边界 | run_daily_pipeline 可由任意登录用户触发 | `backend/app/routers/reports.py` | 增加角色限制和阻断分支测试 |
| B16 | 中 | 错误映射 | 报表路由 ValueError 到 400 缺少测试 | `backend/app/routers/reports.py` | 每个路由补异常映射用例 |
| B17 | 高 | 工单测试 | 工单主链路多路由无行为测试 | `backend/app/routers/work_orders.py` | 覆盖创建、详情、列表、entry 更新、amendment |
| B18 | 低 | Header 校验 | 非法 `X-Idempotency-Key` 400 分支无测 | `backend/app/routers/work_orders.py` | 增加非法 UUID 测试 |
| B19 | 中 | 兼容壳 | `work_order_service.py` 动态兼容壳增加导入复杂度 | `backend/app/services/work_order_service.py` | 补兼容导出测试，长期收敛 |
| B20 | 中 | 兼容壳 | `report_service.py` 动态兼容壳增加导入复杂度 | `backend/app/services/report_service.py` | 补兼容导出测试，长期收敛 |
| B21 | 低 | 未接入代码 | `deterministic_orchestration_service.py` 无引用无测试 | `backend/app/services` | 确认废弃后删除或补入口和测试 |
| B22 | 低 | Schema 漂移 | 未引用 auth schema 与 QR 返回模型不一致 | `backend/app/schemas/auth.py` | 删除未用 schema 或声明 response_model |

## 测试记录

- 前端 agent 基线：`node --test frontend/tests/mobileSwipe.test.js frontend/tests/offlineResilience.test.js frontend/tests/submitGuard.test.js frontend/tests/useRealtimeStream.test.js`，结果 `11 passed / 0 failed`。
- 后端 agent 基线：`python -m pytest backend/tests -q`，结果 `513 passed / 5 failed`；失败点来自后端测试读取前端源码的跨层断言。
- 本轮修复后的最终验证记录以提交前命令输出为准。
