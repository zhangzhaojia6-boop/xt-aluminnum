from __future__ import annotations

import base64
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.agent_communication import MultimodalEvidence
from app.models.imports import ImportBatch
from app.services import dingtalk_energy_ingest_service as ingest
from app.services.daily_energy_report_service import parse_workshop_electricity_workbook


SCREENSHOT_TABLE = '\n'.join(
    [
        '车间/日期\t1日\t2日',
        '铸锭\t110\t100',
        '热轧\t320\t300',
        '2050\t480\t500',
        '生活区\t30\t20',
        '合计\t940\t920',
        '高压合计\t1000\t1000',
        '差值\t60\t80',
    ]
)


def _ingest_screenshot(monkeypatch, tmp_path, *, table_text: str, business_date: str):
    monkeypatch.setattr(ingest.settings, 'UPLOAD_DIR', str(tmp_path), raising=False)
    image_urls = []

    def fake_read_table_image_text(*, image_data_url: str) -> str:
        image_urls.append(image_data_url)
        return table_text

    monkeypatch.setattr(ingest, 'read_table_image_text', fake_read_table_image_text)
    engine = create_engine('sqlite:///:memory:', future=True)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, future=True)()
    evidence = MultimodalEvidence(evidence_type='attachment', payload={'file_name': 'image.png'})
    db.add(evidence)
    db.commit()
    result = ingest.ingest_dingtalk_energy_file(
        db,
        payload={
            'fileName': 'image.png',
            'fileContentBase64': base64.b64encode(b'png-bytes').decode('ascii'),
            'businessDate': business_date,
        },
        evidence=evidence,
        trace_id='msg-image-001',
    )
    assert image_urls == [f"data:image/png;base64,{base64.b64encode(b'png-bytes').decode('ascii')}"]
    return db, evidence, result


def test_checked_screenshot_table_is_staged_as_electricity_workbook(monkeypatch, tmp_path) -> None:
    db, evidence, result = _ingest_screenshot(
        monkeypatch, tmp_path, table_text=f'```\n{SCREENSHOT_TABLE}\n```', business_date='2026-11-02'
    )
    try:
        assert result['status'] == 'staged'
        assert result['batch_id']
        assert Path(result['stored_file']).name == 'msg-image-001_各车间电耗统计表-截图.xlsx'
        rows = parse_workshop_electricity_workbook(result['stored_file'], report_date=date(2026, 11, 2))
        fields = {row.mapped_data['report_field']: row.energy_value for row in rows if row.mapped_data['report_field']}
        assert fields == {'total_electricity_kwh': 1000, 'subitem_electricity_kwh': 920}
        assert evidence.payload['energy_ingest']['status'] == 'staged'
    finally:
        db.close()


def test_screenshot_day_whose_rows_do_not_add_up_is_blocked(monkeypatch, tmp_path) -> None:
    misread_table = SCREENSHOT_TABLE.replace('热轧\t320\t', '热轧\t302\t')
    assert misread_table != SCREENSHOT_TABLE
    db, evidence, result = _ingest_screenshot(
        monkeypatch, tmp_path, table_text=misread_table, business_date='2026-11-01'
    )
    try:
        assert result['status'] == 'blocked'
        assert result['reason'] == 'image_table_check_failed'
        assert evidence.payload['energy_ingest']['reason'] == 'image_table_check_failed'
        assert db.query(ImportBatch).count() == 0
        assert not list(tmp_path.rglob('*.xlsx'))
    finally:
        db.close()


def test_screenshot_without_energy_table_header_is_skipped(monkeypatch, tmp_path) -> None:
    db, evidence, result = _ingest_screenshot(
        monkeypatch, tmp_path, table_text='品名\t数量\n铝卷\t12\n', business_date='2026-11-12'
    )
    try:
        assert result == {'status': 'skipped', 'reason': 'not_energy_table'}
        assert db.query(ImportBatch).count() == 0
    finally:
        db.close()
