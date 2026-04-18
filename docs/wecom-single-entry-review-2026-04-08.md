# 企业微信单入口收口复核记录（2026-04-08）

## 本次复核范围
- README 对外口径
- `docs/pilot-sop-minimal.md`
- `docs/pilot-readiness-checklist.md`
- `docs/workflow-rollout.md`
- 现场唯一移动入口 `/mobile`

## 复核结论
- 对外文档口径已收敛为：**企业微信优先、`/mobile` 为唯一现场移动填报入口**。
- 已明确说明：**后端/系统端口保留**，历史 `dingtalk_*` 字段与兼容映射暂不移除。
- 现场 SOP 已补充：登录失败、退回后继续处理、smoke 检查都围绕 `/mobile` 展开。

## 代码侧复核要点
1. 当前 canonical 业务写入口仍是 `/api/v1/mobile/*`。
2. 当前企业微信身份入口仍是 `/api/v1/wecom/*`。
3. 当前历史兼容仍存在于企业微信账号映射：
   - `backend/app/services/wecom_mapping_service.py`
   - 仍兼容 `username / dingtalk_user_id`
4. 前端仍存在历史工人页痕迹（如 `/worker`），不应继续作为现场培训中的并列主入口。

## 本轮继续复核发现的剩余历史引用
- 前端路由仍保留 `/worker`：
  - `frontend/src/router/index.js`
- 历史极简工人页仍存在：
  - `frontend/src/views/WorkerForm.vue`
- 移动 bootstrap / identity 结构仍保留 `dingtalk_*` 命名：
  - `backend/app/schemas/mobile.py`
  - `backend/app/services/dingtalk_service.py`
  - `backend/app/services/mobile_report_service.py`
- `frontend/src/views/mobile/MobileEntry.vue` 仍把部分兼容来源展示为“兼容钉钉入口 / 兼容钉钉身份”。

这些引用与“保留系统端口、暂不移除兼容结构”的共识一致，但不应再被外部 README、SOP 或现场培训材料描述为并列主入口。

## 已完成文档动作
- README 改为“企业微信单入口优先 + 历史系统端口保留”。
- 最小 SOP 改为直接指向 `https://localhost/mobile`。
- Readiness checklist 新增“统一从 `/mobile` 进入”的 smoke 要求。
- Workflow rollout 新增 Step 8，记录本轮单入口收口结论。

## 验证记录
- PASS：`cd frontend && npm run build`
- PASS：`docker compose run --rm backend sh -lc "pytest tests/test_mobile_status_consistency.py tests/test_wecom_login_route.py -q"`
- PASS：`curl -kI https://localhost/mobile`
- PASS：通过 API 手工验证 `/mobile` 相关链路
  - `POST /api/v1/auth/login`
  - `GET /api/v1/auth/me`
  - `GET /api/v1/mobile/bootstrap`
  - `GET /api/v1/mobile/current-shift`
  - 结果：登录成功；`mobile/bootstrap` 返回 `entry_mode=web_debug`、`current_identity_source=dev_fallback`；`current-shift` 返回 `can_submit=True`
- FAIL（环境缺件）：`cd frontend && npx playwright test e2e/mobile-entry-smoke.spec.js`
  - 已补装 Chromium 浏览器缓存，但运行时仍缺少系统库 `libnspr4.so`，当前环境无法启动 Playwright headless browser

## 后续建议
- 前端剩余历史入口文案继续向 `/mobile` 收口。
- 若要完成自动化 `/mobile` smoke，需补齐 Playwright 运行依赖（至少包含 `libnspr4.so` 对应系统库）。
