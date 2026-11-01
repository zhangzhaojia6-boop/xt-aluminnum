from __future__ import annotations

from datetime import date
import importlib.util
import json
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import Table, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.agent_communication import MultimodalEvidence
from app.models.hermes_factory_brain import HermesDingTalkSamplingRule


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / 'scripts' / 'register_energy_file_sender.py'
    spec = importlib.util.spec_from_file_location('register_energy_file_sender', script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def session_factory():
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=[cast(Table, MultimodalEvidence.__table__), cast(Table, HermesDingTalkSamplingRule.__table__)],
    )
    return sessionmaker(bind=engine)


def _workbook(
    db: Session,
    *,
    file_name: str,
    event_time: str,
    sender: str = 'lu-sender',
    conversation: str = 'cid-private',
    ingest_status: str | None = 'staged',
    promotion: str | None = None,
) -> int:
    payload = {
        'file_name': file_name,
        'event_time': event_time,
        'dingtalk_sender_id': sender,
        'group_id': conversation,
        'senderName': '卢龙超',
    }
    if ingest_status:
        payload['energy_ingest'] = {'status': ingest_status, 'batch_id': 31, 'business_date': event_time[:10]}
    if promotion:
        payload['energy_promotion'] = {'status': promotion}
    evidence = MultimodalEvidence(evidence_type='dingtalk_file', confirmation_status='machine_only', payload=payload)
    db.add(evidence)
    db.flush()
    return evidence.id


def test_lists_only_energy_workbooks_since_the_given_day(session_factory) -> None:
    module = _load_script_module()
    with session_factory() as db:
        gas = _workbook(db, file_name='11月份各车间天然气用量统计表.xls', event_time='2026-11-02T08:11:00+08:00')
        electricity = _workbook(db, file_name='11月份各车间电耗统计表.xls', event_time='2026-11-02T08:10:00+08:00')
        _workbook(db, file_name='各车间成品率.xlsx', event_time='2026-11-02T08:26:00+08:00')
        _workbook(db, file_name='7月份各车间电耗统计表.xls', event_time='2026-07-24T10:00:00+08:00')

        rows = module.list_energy_workbooks(db, since='2026-11-01')

    assert [row['id'] for row in rows] == [electricity, gas]
    assert rows[0]['sender'] == 'lu-sender'
    assert rows[0]['conversation'] == 'cid-private'
    assert rows[0]['sender_name'] == '卢龙超'
    assert rows[0]['ingest_status'] == 'staged'


def test_registers_electricity_and_gas_rules_once(session_factory) -> None:
    module = _load_script_module()
    with session_factory() as db:
        _workbook(db, file_name='11月份各车间电耗统计表.xls', event_time='2026-11-02T08:10:00+08:00')
        evidence = module.list_energy_workbooks(db, since='2026-11-01')[0]

        created = module.register_energy_sender(
            db, evidence=evidence, owner='卢龙超', owner_key='lu-longchao', approved_by='张兆嘉', approved_at=date(2026, 11, 2)
        )
        again = module.register_energy_sender(
            db, evidence=evidence, owner='卢龙超', owner_key='lu-longchao', approved_by='张兆嘉', approved_at=date(2026, 11, 2)
        )
        rules = {rule.rule_key: rule for rule in db.query(HermesDingTalkSamplingRule).all()}

    assert created == ['registered-energy-file:electricity:lu-longchao', 'registered-energy-file:gas:lu-longchao']
    assert again == []
    electricity_rule = rules['registered-energy-file:electricity:lu-longchao']
    assert electricity_rule.channel_key == 'cid-private'
    assert electricity_rule.specialist_user_id == 'lu-sender'
    assert electricity_rule.content_types == ['file']
    assert electricity_rule.status == 'active'
    assert electricity_rule.time_window_payload == {
        'mode': 'registered_energy_file',
        'days': 'daily',
        'file_name_pattern': '各车间电耗统计表',
        'owner': '卢龙超',
        'approved_by': '张兆嘉',
        'approved_at': '2026-11-02',
    }
    assert rules['registered-energy-file:gas:lu-longchao'].time_window_payload['file_name_pattern'] == '各车间天然气用量统计表'


def test_promotes_only_staged_workbooks_from_the_registered_sender_in_order(session_factory, monkeypatch) -> None:
    module = _load_script_module()
    promoted = []
    monkeypatch.setattr(
        module,
        'promote_registered_energy_file_evidence',
        lambda db, *, evidence_id: promoted.append(evidence_id) or 'registered-energy-file:electricity:lu-longchao',
    )
    with session_factory() as db:
        later = _workbook(db, file_name='11月份各车间天然气用量统计表.xls', event_time='2026-11-03T08:11:00+08:00')
        earlier = _workbook(db, file_name='11月份各车间电耗统计表.xls', event_time='2026-11-02T08:10:00+08:00')
        _workbook(db, file_name='11月份各车间电耗统计表.xls', event_time='2026-11-02T09:00:00+08:00', promotion='promoted')
        _workbook(db, file_name='11月份各车间电耗统计表.xls', event_time='2026-11-02T09:30:00+08:00', sender='someone-else')
        _workbook(db, file_name='11月份各车间电耗统计表.xls', event_time='2026-11-02T09:40:00+08:00', ingest_status='failed')
        rows = module.list_energy_workbooks(db, since='2026-11-01')

        results = module.promote_staged_workbooks(db, workbooks=rows, sender='lu-sender', conversation='cid-private')

    assert promoted == [earlier, later]
    assert results == {
        earlier: 'registered-energy-file:electricity:lu-longchao',
        later: 'registered-energy-file:electricity:lu-longchao',
    }


def test_main_lists_without_writing_and_apply_needs_owner(session_factory, monkeypatch, capsys) -> None:
    module = _load_script_module()
    monkeypatch.setattr(module, 'get_sessionmaker', lambda: session_factory)
    with session_factory() as db:
        evidence_id = _workbook(db, file_name='11月份各车间电耗统计表.xls', event_time='2026-11-02T08:10:00+08:00')
        db.commit()

    assert module.main(['--since', '2026-11-01']) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [row['id'] for row in listed] == [evidence_id]

    with pytest.raises(SystemExit):
        module.main(['--apply', '--evidence-id', str(evidence_id)])
    with session_factory() as db:
        assert db.query(HermesDingTalkSamplingRule).count() == 0
