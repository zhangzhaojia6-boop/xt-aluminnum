# Machine-Line User Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让管理员在用户管理页直接把主操/手机端账号绑定到具体机列，支撑机列级填报和二维码登录。

**Architecture:** 不新增数据表，继续以 `equipment.bound_user_id` 作为机列账号绑定真源。后端 `users` 接口接收 `bound_machine_id` 并负责唯一性、车间一致性和解绑；前端 `UserManagement.vue` 加载机台清单，在用户编辑弹窗中配置绑定机列。

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic + pytest；Vue 3 + Element Plus + node:test；不新增依赖。

---

## Tasks

- [x] 扩展 `UserCreateRequest` / `UserUpdateRequest` / `UserListItem` 的机列绑定字段。
- [x] 在 `backend/app/routers/users.py` 增加绑定校验：机台必须启用，不能被其他用户占用，机台车间要与用户车间一致。
- [x] 创建和更新用户时写入/清除 `Equipment.bound_user_id`，并把绑定结果写入审计值。
- [x] 在 `UserManagement.vue` 表格与弹窗显示“绑定机列”，保存时提交 `bound_machine_id`。
- [x] 更新用户路由测试和前端契约测试。
- [x] 运行后端聚焦测试、前端单测、构建和 diff 检查。

## Verification

```powershell
python -m pytest backend/tests/test_users_routes.py -q
npm --prefix frontend test -- userDingtalkSync.test.js
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```
