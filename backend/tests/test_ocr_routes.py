from fastapi.testclient import TestClient

from app.core.deps import get_current_user, get_db
from app.main import app
from app.models.system import User


class DummyDB:
    pass


def test_ocr_routes_are_registered() -> None:
    assert app.url_path_for('ocr-extract') == '/api/v1/ocr/extract'
    assert app.url_path_for('ocr-verify') == '/api/v1/ocr/verify'


def test_ocr_extract_endpoint_calls_service(monkeypatch) -> None:
    calls = []

    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=7,
            username='leader',
            password_hash='x',
            name='Leader',
            role='shift_leader',
            workshop_id=1,
            is_mobile_user=True,
            is_active=True,
        )

    def fake_extract(db, *, file_name, file_bytes, workshop_type, current_user):
        assert workshop_type == 'casting'
        assert file_name == 'paper-form.jpg'
        assert file_bytes == b'fake-image'
        assert current_user.id == 7
        calls.append((file_name, workshop_type))
        return {
            'ocr_submission_id': 12,
            'image_url': '/uploads/ocr/2026/03/ocr-12.jpg',
            'raw_text': '投入铝锭重量 9430',
            'fields': {
                'input_weight': {'value': '9430', 'confidence': 0.88},
            },
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.ocr.ocr_service.extract_submission', fake_extract)

    client = TestClient(app)
    response = client.post(
        '/api/v1/ocr/extract',
        data={'workshop_type': 'casting'},
        files={'file': ('paper-form.jpg', b'fake-image', 'image/jpeg')},
    )

    assert response.status_code == 200
    assert response.json()['ocr_submission_id'] == 12
    assert response.json()['fields']['input_weight']['value'] == '9430'
    assert calls == [('paper-form.jpg', 'casting')]

    app.dependency_overrides.clear()


def test_ocr_verify_endpoint_calls_service(monkeypatch) -> None:
    calls = []

    def fake_get_db():
        yield DummyDB()

    def fake_get_user() -> User:
        return User(
            id=7,
            username='leader',
            password_hash='x',
            name='Leader',
            role='shift_leader',
            workshop_id=1,
            is_mobile_user=True,
            is_active=True,
        )

    def fake_verify(db, *, submission_id, corrected_fields, rejected, current_user):
        assert submission_id == 12
        assert corrected_fields == {'input_weight': '9440', 'output_weight': '9220'}
        assert rejected is False
        assert current_user.id == 7
        calls.append(submission_id)
        return {
            'ocr_submission_id': 12,
            'status': 'verified',
            'prefill_payload': {
                'input_weight': 9440,
                'output_weight': 9220,
                'ocr_submission_id': 12,
            },
        }

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_user] = fake_get_user
    monkeypatch.setattr('app.routers.ocr.ocr_service.verify_submission', fake_verify)

    client = TestClient(app)
    response = client.post(
        '/api/v1/ocr/verify',
        json={
            'ocr_submission_id': 12,
            'corrected_fields': {'input_weight': '9440', 'output_weight': '9220'},
            'rejected': False,
        },
    )

    assert response.status_code == 200
    assert response.json()['status'] == 'verified'
    assert response.json()['prefill_payload']['ocr_submission_id'] == 12
    assert calls == [12]

    app.dependency_overrides.clear()
