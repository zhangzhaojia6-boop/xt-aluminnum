# Parse 15 Release Freeze And WeCom Entry Runtime Plan

**Goal:** 把当前工作从“继续扩实现”切到“冻结发布基线 + 准备企业微信生产入口 + 准备现场 UAT”。  

## Task 1: 冻结发布边界

**Files:**
- Verify: `docs/发布冻结基线清单.md`
- Verify: `docs/部署文档.md`
- Verify: `README.md`

- [ ] 确认 Phase 1 发布包含项
- [ ] 确认 Phase 1 暂不包含项
- [ ] 确认验证基线已经写明

## Task 2: 收企业微信生产入口准备项

**Files:**
- Verify: `docs/企业微信生产入口准备清单.md`
- Verify: `.env.example`
- Verify: `backend/app/routers/wecom.py`
- Verify: `backend/app/config.py`

- [ ] 确认系统侧已具备企业微信登录与 JS-SDK 入口
- [ ] 确认生产环境变量清单可直接执行
- [ ] 明确缺失的真实外部输入

## Task 3: 收现场 UAT 闸门

**Files:**
- Verify: `docs/现场UAT清单.md`
- Modify: `.omx/notepad.md`

- [ ] 确认 UAT 参与角色
- [ ] 确认最小必跑场景
- [ ] 记录当前外部阻塞与下一步用户输入

## Task 4: 阶段交接

**Files:**
- Modify: `.omx/notepad.md`

- [ ] 记录 parse14 已完成
- [ ] 记录 parse15 已启动
- [ ] 写明本阶段是“发布闸门”，不是“继续堆功能”
