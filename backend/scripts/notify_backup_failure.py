"""每日备份失败时，用钉钉工作通知告诉运维告警接收人（默认张兆嘉）。

由 systemd 的 OnFailure 调用：python scripts/notify_backup_failure.py "<失败原因>"
遵守 DINGTALK_NOTIFY_DRY_RUN：外发关闭时只写日志，不真实发送。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.database import get_sessionmaker  # noqa: E402
from app.models.system import User  # noqa: E402
from app.services import dingtalk_service  # noqa: E402


def build_message(reason: str, now: datetime) -> str:
    reason = (reason or '').strip() or '未取到失败原因'
    return (
        f"【数据中枢】每日备份失败（{now:%m-%d %H:%M}）\n"
        f"原因：{reason[:200]}\n"
        "今天没有新的备份，上一次成功的备份仍保留。请让运维查看：journalctl -u xintai-daily-backup"
    )


def recipient_ids() -> list[int]:
    return [int(x) for x in str(settings.OPS_ALERT_USER_IDS or '').split(',') if x.strip().isdigit()]


def main(argv: list[str]) -> int:
    message = build_message(' '.join(argv[1:]), datetime.now())
    db = get_sessionmaker()()
    try:
        users = db.query(User).filter(User.id.in_(recipient_ids())).all()
        sent = 0
        for user in users:
            ok, detail = dingtalk_service.send_work_notification(user.dingtalk_user_id or '', message)
            print(f'user={user.id} ok={ok} detail={detail}')
            sent += 1 if ok else 0
        return 0 if sent else 1
    finally:
        db.close()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
