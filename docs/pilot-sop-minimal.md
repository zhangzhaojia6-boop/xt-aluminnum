# 试点最小SOP（现场值班版）

## 1. 入口怎么进
- 工人：企业微信打开 `https://localhost/mobile`，这是当前唯一移动填报入口（H5）。
- 管理：驾驶舱查看日报与上报率，必要时执行配置与账号自检脚本。

## 2. 登录失败怎么办
- 先看页面提示：
- “未绑定系统用户” -> 联系管理员补齐系统账号映射（当前兼容 `username / dingtalk_user_id` 历史字段）。
- “账号已停用” -> 管理员启用账号后重试。
- “映射不唯一” -> 管理员清理重复账号映射。
- 批量排查命令：
```bash
cd backend
python scripts/check_wecom_account_mapping.py --input wecom_users.txt --json
```

## 3. 被退回怎么办
- 工人按 `returned_reason` 逐条修改后重新提交。
- 始终从 `/mobile` 返回当前班次继续处理，不需要切换到其他工人端页面。
- 重点检查：
- 产出是否大于投入
- 出勤是否缺失
- 数值是否为负
- 如多次退回，班长先用工人端“暂存”保留现场数据，再逐项修正后提交。

## 4. 当班没报怎么办
- 先确认账号可登录、班次配置有效、应报清单存在。
- 管理员可查看催报记录与上报率，必要时人工提醒当班负责人立即补报。
- 若需临时降级（保填报、停外发）：
```env
AUTO_PUSH_ENABLED=false
AUTO_PUBLISH_ENABLED=false
```
- 降级后仍可填报与自动校验，外发推送和自动发布会暂停。

## 5. 值班排查看哪里
- 关键运行日志：`pilot.runtime`（提交、自动校验、确认/退回、汇总、推送）。
- 每日复盘指标：
```bash
cd backend
python scripts/check_pilot_metrics.py --date 2026-04-06 --json
```
- 配置自检：
```bash
cd backend
python scripts/check_pilot_config.py --date 2026-04-06 --json
```


## 6. 上线前先看哪份清单
- 放量前先按 `docs/pilot-readiness-checklist.md` 逐项检查并留痕，再进入现场值班。
