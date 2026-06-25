# CLI Rollout Lane Spec

> 日期：当前 main 基线

## 生产前检查

```bash
python scripts/check_pilot_config.py --date <目标日期> --json
python scripts/check_owner_account_bindings.py --target-workshop-code <车间编码> --json
python scripts/dingtalk_cli.py status --json
```

当前验收记录：669 passed，124 deselected，30 warnings。

## 入口边界

- 浏览器 / 钉钉 是当前用户入口。
- `WECOM_BOT_ENABLED=false` 表示企业微信群机器人默认不开启。
- 企业微信群机器人只作为 workflow publisher，不作为用户身份入口。
