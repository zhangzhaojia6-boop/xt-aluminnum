"""登记能源统计员的能耗表为约定文件，并把他已发来、已暂存的表补入库。

第一份《各车间电耗统计表》《各车间天然气用量统计表》到了以后用：
  只读列出：python scripts/register_energy_file_sender.py --since 2026-11-01
  登记并补入库：python scripts/register_energy_file_sender.py --apply --evidence-id N --owner 姓名 --owner-key 拼音

--apply 会按所选证据的发送人和会话登记电、气两条约定规则，再把同一发送人、同一会话里已暂存
但还没入库的能耗表按时间先后补入库。写生产库前先备份。
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import date
import json
from pathlib import Path
import sys
from typing import Any

from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import get_sessionmaker
from app.models.agent_communication import MultimodalEvidence
from app.models.hermes_factory_brain import HermesDingTalkSamplingRule
from app.services.hermes_dingtalk_sampling_service import (
    REGISTERED_ENERGY_FILE_MODE,
    promote_registered_energy_file_evidence,
)

FILE_NAME_PATTERNS = {'electricity': '各车间电耗统计表', 'gas': '各车间天然气用量统计表'}


def _section(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, Mapping) else {}


def list_energy_workbooks(db: Session, *, since: str) -> list[dict[str, Any]]:
    rows = []
    for evidence in db.query(MultimodalEvidence).all():
        payload = evidence.payload if isinstance(evidence.payload, Mapping) else {}
        file_name = str(payload.get('file_name') or '')
        event_time = str(payload.get('event_time') or '')
        if event_time < since or not any(pattern in file_name for pattern in FILE_NAME_PATTERNS.values()):
            continue
        ingest = _section(payload, 'energy_ingest')
        rows.append(
            {
                'id': evidence.id,
                'sender_name': payload.get('senderName') or _section(payload, 'raw_metadata').get('senderName'),
                'sender': payload.get('dingtalk_sender_id'),
                'conversation': payload.get('group_id'),
                'file_name': file_name,
                'event_time': event_time,
                'ingest_status': ingest.get('status'),
                'batch_id': ingest.get('batch_id'),
                'business_date': ingest.get('business_date'),
                'promotion': _section(payload, 'energy_promotion').get('status'),
            }
        )
    return sorted(rows, key=lambda row: (row['event_time'], row['id']))


def register_energy_sender(
    db: Session,
    *,
    evidence: Mapping[str, Any],
    owner: str,
    owner_key: str,
    approved_by: str,
    approved_at: date,
) -> list[str]:
    created = []
    for energy_type, pattern in FILE_NAME_PATTERNS.items():
        rule_key = f'registered-energy-file:{energy_type}:{owner_key}'
        if db.query(HermesDingTalkSamplingRule).filter(HermesDingTalkSamplingRule.rule_key == rule_key).first():
            continue
        db.add(
            HermesDingTalkSamplingRule(
                rule_key=rule_key,
                channel_key=evidence['conversation'],
                specialist_user_id=evidence['sender'],
                content_types=['file'],
                time_window_payload={
                    'mode': REGISTERED_ENERGY_FILE_MODE,
                    'days': 'daily',
                    'file_name_pattern': pattern,
                    'owner': owner,
                    'approved_by': approved_by,
                    'approved_at': approved_at.isoformat(),
                },
                priority='high',
                status='active',
            )
        )
        created.append(rule_key)
    db.commit()
    return created


def promote_staged_workbooks(
    db: Session,
    *,
    workbooks: list[dict[str, Any]],
    sender: str,
    conversation: str,
) -> dict[int, str | None]:
    results: dict[int, str | None] = {}
    for row in workbooks:
        if (
            row['sender'] == sender
            and row['conversation'] == conversation
            and row['ingest_status'] == 'staged'
            and not row['promotion']
        ):
            results[row['id']] = promote_registered_energy_file_evidence(db, evidence_id=row['id'])
            db.commit()
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='登记能源统计员的能耗表约定来源，并补入库已暂存的表')
    parser.add_argument('--since', default=date.today().replace(day=1).isoformat(), help='只看这一天以后收到的能耗表')
    parser.add_argument('--apply', action='store_true', help='登记规则并补入库；不加则只读列出')
    parser.add_argument('--evidence-id', type=int, help='用哪条能耗表证据的发送人和会话来登记')
    parser.add_argument('--owner', help='发送人姓名')
    parser.add_argument('--owner-key', help='发送人拼音，用于规则编号')
    parser.add_argument('--approved-by', default='张兆嘉')
    args = parser.parse_args(argv)

    with get_sessionmaker()() as db:
        workbooks = list_energy_workbooks(db, since=args.since)
        print(json.dumps(workbooks, ensure_ascii=False, indent=1))
        if not args.apply:
            return 0
        if not (args.evidence_id and args.owner and args.owner_key):
            parser.error('--apply 需要 --evidence-id、--owner 和 --owner-key')
        chosen = next((row for row in workbooks if row['id'] == args.evidence_id), None)
        if chosen is None:
            parser.error(f'证据 {args.evidence_id} 不是 {args.since} 以后收到的能耗表')
        created = register_energy_sender(
            db,
            evidence=chosen,
            owner=args.owner,
            owner_key=args.owner_key,
            approved_by=args.approved_by,
            approved_at=date.today(),
        )
        promoted = promote_staged_workbooks(
            db,
            workbooks=workbooks,
            sender=chosen['sender'],
            conversation=chosen['conversation'],
        )
    print(json.dumps({'registered': created, 'promoted': promoted}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
