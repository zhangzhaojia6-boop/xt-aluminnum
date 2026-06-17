"""配置张兆嘉个人范围 Agent。

默认只输出 dry-run 计划；只有显式传入 --apply 才写入数据库。
写入内容仅包含张兆嘉个人范围 Agent、个人演练通道和绑定关系，
通道始终保持 dry_run=True，不会触发真实钉钉外发。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy.exc import SQLAlchemyError

from app.database import get_sessionmaker
from app.services.agent_personal_bootstrap_service import (
    ZHANG_ZHAOJIA_CHANNEL_KEY,
    ZHANG_ZHAOJIA_DINGTALK_USER_ID,
    build_zhang_zhaojia_personal_agent_plan,
    ensure_zhang_zhaojia_personal_agents,
)


def main() -> int:
    parser = argparse.ArgumentParser(description='配置张兆嘉个人范围 Agent')
    parser.add_argument('--apply', action='store_true', help='写入数据库；默认只输出计划')
    parser.add_argument(
        '--dingtalk-user-id',
        default=ZHANG_ZHAOJIA_DINGTALK_USER_ID,
        help='张兆嘉钉钉 userId',
    )
    parser.add_argument(
        '--channel-key',
        default=ZHANG_ZHAOJIA_CHANNEL_KEY,
        help='个人 dry-run 通道 key；默认使用张兆嘉钉钉 userId，真实工作通知仍只发给本人',
    )
    args = parser.parse_args()

    if not args.apply:
        payload = build_zhang_zhaojia_personal_agent_plan(
            dingtalk_user_id=args.dingtalk_user_id,
            channel_key=args.channel_key,
        )
        payload['applied'] = False
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    try:
        sessionmaker = get_sessionmaker()
        with sessionmaker() as db:
            outcome = ensure_zhang_zhaojia_personal_agents(
                db,
                apply=True,
                dingtalk_user_id=args.dingtalk_user_id,
                channel_key=args.channel_key,
            )
    except SQLAlchemyError as exc:
        print(json.dumps({
            'applied': False,
            'error': exc.__class__.__name__,
            'message': '数据库写入失败，请确认 DATABASE_URL 和连接权限。',
        }, ensure_ascii=False, indent=2))
        return 3

    print(json.dumps({
        'applied': outcome.applied,
        'dingtalk_user_id': outcome.dingtalk_user_id,
        'channel_key': outcome.channel_key,
        'channel_dry_run': outcome.channel_dry_run,
        'agent_codes': outcome.agent_codes,
        'agent_total': outcome.agent_total,
        'binding_total': outcome.binding_total,
        'notes': outcome.notes,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
