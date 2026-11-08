"""按名单开采购账号和办理岗位。默认只预览，加 --apply 才写库。

名单是 JSON：[{"name": "姓名", "dingtalk_user_id": "...", "roles": ["warehouse"]}]
名单含人员信息，不放进仓库。
"""
from __future__ import annotations

import argparse
import json
import secrets
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.auth import get_password_hash
from app.database import get_sessionmaker
from app.domain import procurement_flow as flow
from app.models.agent_communication import CommunicationChannel
from app.models.system import User
from app.services import procurement_service as service
from app.services.agent_communication_service import bind_agent_to_channel, register_channel
from app.services.audit_service import log_action


def _plan_entry(db: Session, entry: dict) -> dict:
    name = str(entry.get('name') or '').strip()
    dingtalk_user_id = str(entry.get('dingtalk_user_id') or '').strip()
    roles = list(entry.get('roles') or [])
    unknown = [role for role in roles if role not in flow.ASSIGNABLE_ROLES]
    if not name or not dingtalk_user_id or unknown:
        return {'name': name, 'action': 'invalid', 'reason': f'缺姓名或钉钉 ID，或岗位不存在：{unknown}', 'roles': roles}
    user = db.query(User).filter(User.dingtalk_user_id == dingtalk_user_id).first()
    if user is not None and not user.is_active:
        return {'name': name, 'action': 'skip', 'reason': f'账号 {user.username} 已停用，不自动恢复', 'roles': roles}
    if user is not None:
        return {'name': name, 'action': 'assign', 'user': user, 'roles': roles}
    same_name = db.query(User).filter(User.name == name).first()
    if same_name is not None:
        return {'name': name, 'action': 'skip', 'reason': f'已有同名账号 {same_name.username}，不按姓名绑定，要人工确认', 'roles': roles}
    return {'name': name, 'action': 'create', 'dingtalk_user_id': dingtalk_user_id, 'roles': roles}


def sync_accounts(db: Session, entries: list[dict], *, actor: User, apply: bool) -> list[dict]:
    plans = [_plan_entry(db, entry) for entry in entries]
    if not apply:
        return plans
    for plan in plans:
        if plan['action'] == 'create':
            plan['user'] = User(
                username=f"pc-{plan['dingtalk_user_id']}",
                password_hash=get_password_hash(secrets.token_urlsafe(24)),
                name=plan['name'],
                role=flow.PROCUREMENT_ONLY_ROLE,
                dingtalk_user_id=plan['dingtalk_user_id'],
                data_scope_type='self_workshop',
                is_active=True,
            )
            db.add(plan['user'])
            db.flush()
        if plan['action'] not in {'create', 'assign'}:
            continue
        user = plan['user']
        for role in plan['roles']:
            service.set_assignment(db, actor=actor, user_id=user.id, role=role, enabled=True)
        key = service.channel_key_for(user.id)
        exists = db.query(CommunicationChannel).filter(CommunicationChannel.channel_type == service.NOTIFY_CHANNEL_TYPE, CommunicationChannel.channel_key == key).first()
        if exists is None:
            register_channel(db, channel_type=service.NOTIFY_CHANNEL_TYPE, channel_key=key, name=f'采购待办-{user.name}', target_type='user', target_key=user.dingtalk_user_id, dry_run=True)
            bind_agent_to_channel(db, agent_code=service.NOTIFY_AGENT, channel_key=key, channel_type=service.NOTIFY_CHANNEL_TYPE)
        log_action(
            db, user_id=actor.id, user_name=actor.name, action='procurement_account_sync', module='procurement',
            table_name='users', record_id=user.id, new_value={'roles': plan['roles'], 'created': plan['action'] == 'create'},
            reason='sync_procurement_accounts', auto_commit=False,
        )
    db.commit()
    return plans


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('roster', type=Path)
    parser.add_argument('--actor', required=True, help='执行人的管理员账号')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    entries = json.loads(args.roster.read_text(encoding='utf-8'))
    with get_sessionmaker()() as db:
        actor = db.query(User).filter(User.username == args.actor, User.role == 'admin', User.is_active.is_(True)).first()
        if actor is None:
            raise SystemExit('找不到这个管理员账号')
        for plan in sync_accounts(db, entries, actor=actor, apply=args.apply):
            print(plan['action'], plan['name'], ','.join(plan['roles']), plan.get('reason', ''))
    print('已写入' if args.apply else '只是预览，没有写入')


if __name__ == '__main__':
    main()
