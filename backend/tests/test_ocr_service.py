from datetime import datetime, timezone
from pathlib import Path

from app.services import ocr_service


def test_store_ocr_image_writes_under_ocr_folder(tmp_path: Path) -> None:
    now = datetime(2026, 3, 28, 9, 15, tzinfo=timezone.utc)

    payload = ocr_service.store_ocr_image(
        file_bytes=b'fake-image-content',
        original_name='paper-form.png',
        upload_dir=tmp_path,
        now=now,
        public_prefix='/uploads',
    )

    stored_path = tmp_path / payload['relative_path']
    assert stored_path.exists()
    assert stored_path.read_bytes() == b'fake-image-content'
    assert payload['relative_path'].startswith('ocr/2026/03/')
    assert payload['file_url'].startswith('/uploads/ocr/2026/03/')


def test_extract_fields_uses_numeric_regex_for_template_fields(monkeypatch) -> None:
    monkeypatch.setattr('app.services.ocr_service.preprocess_image', lambda _image_bytes: object())
    monkeypatch.setattr(
        'app.services.ocr_service.get_workshop_template',
        lambda workshop_type, user_role=None: {
            'entry_fields': [
                {'name': 'input_weight', 'label': '投入铝锭重量', 'type': 'number'},
                {'name': 'output_weight', 'label': '铸锭产出重量', 'type': 'number'},
            ],
            'extra_fields': [
                {'name': 'furnace_temp', 'label': '炉温', 'type': 'number'},
            ],
            'qc_fields': [],
        },
    )
    monkeypatch.setattr(
        'app.services.ocr_service.pytesseract.image_to_string',
        lambda *_args, **_kwargs: '投入铝锭重量 9430\n铸锭产出重量 9220\n炉温 735',
    )
    monkeypatch.setattr(
        'app.services.ocr_service.pytesseract.image_to_data',
        lambda *_args, **_kwargs: {
            'text': ['投入铝锭重量', '9430', '铸锭产出重量', '9220', '炉温', '735'],
            'conf': ['88', '92', '84', '93', '80', '87'],
        },
    )

    payload = ocr_service.extract_fields(b'fake-image', workshop_template_type='casting')

    assert payload['raw_text'].startswith('投入铝锭重量')
    assert payload['fields']['input_weight']['value'] == '9430'
    assert payload['fields']['output_weight']['value'] == '9220'
    assert payload['fields']['furnace_temp']['value'] == '735'
    assert payload['fields']['output_weight']['confidence'] >= 0.9
