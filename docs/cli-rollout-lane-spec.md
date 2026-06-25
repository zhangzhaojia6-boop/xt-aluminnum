# CLI Rollout Lane Spec

> 日期：当前 main 基线

## Checks

- `python scripts/check_pilot_config.py --date <目标日期> --json`
- `python scripts/check_owner_account_bindings.py --target-workshop-code <车间编码> --json`
- `python scripts/dingtalk_cli.py status --json`
- 验证基线：`669 passed，124 deselected，30 warnings`
- 入口范围：浏览器 / 钉钉
- 企业微信群机器人默认关闭：`WECOM_BOT_ENABLED=false`
