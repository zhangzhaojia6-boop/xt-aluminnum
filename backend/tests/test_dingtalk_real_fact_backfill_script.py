from __future__ import annotations

from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
import json
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import MultimodalEvidence
from app.services import dingtalk_stream_gateway_service as gateway_service
from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'dingtalk_real_fact_backfill.py'


def _load_script_module():
    spec = spec_from_file_location('dingtalk_real_fact_backfill_script', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _db_sessionmaker():
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)


def _write_jsonl(path, rows: list[dict]) -> None:
    path.write_text('\n'.join(json.dumps(row, ensure_ascii=False) for row in rows), encoding='utf-8')


def _prepare(monkeypatch):
    module = _load_script_module()
    Session = _db_sessionmaker()
    monkeypatch.setattr(module, 'get_sessionmaker', lambda: Session)
    monkeypatch.setattr(module, 'last_completed_production_business_date', lambda: date(2026, 7, 8))
    monkeypatch.setattr(gateway_service.settings, 'DINGTALK_AUTHORIZED_GROUP_IDS', 'group-001', raising=False)
    monkeypatch.setattr(gateway_service.settings, 'DINGTALK_FILE_TEXT_MAX_BYTES', 1_000_000, raising=False)
    return module, Session


def test_jsonl_text_row_writes_message_text(monkeypatch, tmp_path) -> None:
    module, Session = _prepare(monkeypatch)
    files_root = tmp_path / 'files'
    files_root.mkdir()
    input_jsonl = tmp_path / 'messages.jsonl'
    _write_jsonl(
        input_jsonl,
        [
            {
                'group_id': 'group-001',
                'message_id': 'msg-text-001',
                'message_text': '今日日报：产量 32 吨',
                'businessDate': '2026-07-07',
            }
        ],
    )
    captured = StringIO()

    exit_code = module.main(
        ['--input-jsonl', str(input_jsonl), '--files-root', str(files_root), '--days', '3'],
        stdout=captured,
    )

    assert exit_code == 0
    assert json.loads(captured.getvalue()) == {
        'accepted': 1,
        'duplicates': 0,
        'rejected': 0,
        'file_text': 0,
        'message_text': 1,
    }
    db = Session()
    try:
        evidence = db.query(MultimodalEvidence).one()
        assert evidence.payload['message_text'] == '今日日报：产量 32 吨'
    finally:
        db.close()


def test_jsonl_file_row_writes_file_text(monkeypatch, tmp_path) -> None:
    module, Session = _prepare(monkeypatch)
    files_root = tmp_path / 'files'
    files_root.mkdir()
    (files_root / 'report.csv').write_text('日期,产量\n2026-07-07,32\n', encoding='utf-8')
    input_jsonl = tmp_path / 'messages.jsonl'
    _write_jsonl(
        input_jsonl,
        [
            {
                'group_id': 'group-001',
                'message_id': 'msg-file-001',
                'fileName': 'report.csv',
                'localFilePath': 'report.csv',
                'businessDate': '2026-07-07',
            }
        ],
    )
    captured = StringIO()

    exit_code = module.main(
        ['--input-jsonl', str(input_jsonl), '--files-root', str(files_root), '--days', '3'],
        stdout=captured,
    )

    assert exit_code == 0
    summary = json.loads(captured.getvalue())
    assert summary['accepted'] == 1
    assert summary['file_text'] == 1
    db = Session()
    try:
        evidence = db.query(MultimodalEvidence).one()
        assert evidence.payload['file_text'] == '日期\t产量\n2026-07-07\t32'
        assert evidence.payload['download_url_host'] == 'local-backfill'
    finally:
        db.close()


def test_path_traversal_is_rejected(monkeypatch, tmp_path) -> None:
    module, Session = _prepare(monkeypatch)
    files_root = tmp_path / 'files'
    files_root.mkdir()
    (tmp_path / 'secret.csv').write_text('不该读取', encoding='utf-8')
    input_jsonl = tmp_path / 'messages.jsonl'
    _write_jsonl(
        input_jsonl,
        [
            {
                'group_id': 'group-001',
                'message_id': 'msg-file-escape',
                'fileName': 'secret.csv',
                'localFilePath': '../secret.csv',
                'businessDate': '2026-07-07',
            }
        ],
    )
    captured = StringIO()

    exit_code = module.main(
        ['--input-jsonl', str(input_jsonl), '--files-root', str(files_root), '--days', '3'],
        stdout=captured,
    )

    assert exit_code == 0
    assert json.loads(captured.getvalue())['rejected'] == 1
    db = Session()
    try:
        assert db.query(MultimodalEvidence).count() == 0
    finally:
        db.close()


def test_unauthorized_group_is_rejected(monkeypatch, tmp_path) -> None:
    module, Session = _prepare(monkeypatch)
    files_root = tmp_path / 'files'
    files_root.mkdir()
    input_jsonl = tmp_path / 'messages.jsonl'
    _write_jsonl(
        input_jsonl,
        [
            {
                'group_id': 'group-999',
                'message_id': 'msg-unauthorized',
                'message_text': '今日日报：产量 32 吨',
                'businessDate': '2026-07-07',
            }
        ],
    )
    captured = StringIO()

    exit_code = module.main(
        ['--input-jsonl', str(input_jsonl), '--files-root', str(files_root), '--days', '3'],
        stdout=captured,
    )

    assert exit_code == 0
    assert json.loads(captured.getvalue())['rejected'] == 1
    db = Session()
    try:
        assert db.query(MultimodalEvidence).count() == 0
    finally:
        db.close()


def test_duplicate_file_is_counted_as_duplicate(monkeypatch, tmp_path) -> None:
    module, Session = _prepare(monkeypatch)
    files_root = tmp_path / 'files'
    files_root.mkdir()
    (files_root / 'report.csv').write_text('日期,产量\n2026-07-07,32\n', encoding='utf-8')
    input_jsonl = tmp_path / 'messages.jsonl'
    row = {
        'group_id': 'group-001',
        'message_id': 'msg-file-duplicate',
        'fileName': 'report.csv',
        'localFilePath': 'report.csv',
        'businessDate': '2026-07-07',
    }
    _write_jsonl(input_jsonl, [row, row])
    captured = StringIO()

    exit_code = module.main(
        ['--input-jsonl', str(input_jsonl), '--files-root', str(files_root), '--days', '3'],
        stdout=captured,
    )

    assert exit_code == 0
    summary = json.loads(captured.getvalue())
    assert summary['accepted'] == 1
    assert summary['duplicates'] == 1
    assert summary['file_text'] == 1
    db = Session()
    try:
        assert db.query(MultimodalEvidence).count() == 1
    finally:
        db.close()
