from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.services.mobile_report_service import store_report_photo


def test_store_report_photo_updates_report_and_writes_file(tmp_path: Path) -> None:
    report = SimpleNamespace(
        id=9,
        business_date='2026-03-27',
        shift_config_id=1,
        owner_user_id=15,
        last_action_by_user_id=None,
        photo_file_path=None,
        photo_file_name=None,
        photo_uploaded_at=None,
    )
    now = datetime(2026, 3, 27, 9, 30, tzinfo=timezone.utc)

    payload = store_report_photo(
        report,
        file_bytes=b'fake-image-content',
        original_name='现场照片.png',
        upload_dir=tmp_path,
        actor_user_id=15,
        now=now,
        public_prefix='/uploads',
    )

    stored_path = tmp_path / payload['relative_path']
    assert stored_path.exists()
    assert stored_path.read_bytes() == b'fake-image-content'
    assert report.photo_file_name == '现场照片.png'
    assert report.last_action_by_user_id == 15
    assert report.photo_uploaded_at == now
    assert payload['file_url'].startswith('/uploads/')
