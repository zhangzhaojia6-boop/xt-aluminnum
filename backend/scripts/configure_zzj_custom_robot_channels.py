"""配置张兆嘉调试总群的 6 个钉钉自定义机器人通道。

默认只输出计划；只有显式传入 --apply 才写入数据库。
写入数据库的只是环境变量引用名，不包含 webhook/secret 明文。
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
from app.services import agent_communication_service
from app.services.agent_robot_bootstrap_service import (
    build_zzj_custom_robot_plan,
    ensure_zzj_custom_robot_channels,
)


def main() -> int:
    parser = argparse.ArgumentParser(description='配置张兆嘉调试总群自定义机器人通道')
    parser.add_argument('--apply', action='store_true', help='写入数据库；默认只输出计划')
    parser.add_argument('--enable-send', action='store_true', help='将通道切为正式发送；默认保持 dry-run')
    args = parser.parse_args()

    if not args.apply:
        payload = build_zzj_custom_robot_plan(dry_run=not args.enable_send)
        payload['applied'] = False
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    try:
        sessionmaker = get_sessionmaker()
        with sessionmaker() as db:
            outcome = ensure_zzj_custom_robot_channels(db, apply=True, dry_run=not args.enable_send)
    except agent_communication_service.AgentCommunicationError as exc:
        print(json.dumps({
            'applied': False,
            'error': str(exc),
            'message': '请先执行 configure_zhang_zhaojia_agents.py --apply 创建个人 Agent。',
        }, ensure_ascii=False, indent=2))
        return 2
    except SQLAlchemyError as exc:
        print(json.dumps({
            'applied': False,
            'error': exc.__class__.__name__,
            'message': '数据库写入失败，请确认 DATABASE_URL 和连接权限。',
        }, ensure_ascii=False, indent=2))
        return 3

    print(json.dumps({
        'applied': outcome.applied,
        'channel_total': outcome.channel_total,
        'binding_total': outcome.binding_total,
        'channel_keys': outcome.channel_keys,
        'notes': outcome.notes,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
