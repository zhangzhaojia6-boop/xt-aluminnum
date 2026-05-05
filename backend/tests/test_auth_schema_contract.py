from __future__ import annotations

import json

from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from app.main import app
from app.schemas.auth import QrLoginResponse


def test_qr_login_response_schema_accepts_route_shapes() -> None:
    adapter = TypeAdapter(QrLoginResponse)

    adapter.validate_python(
        {
            'access_token': 'token',
            'token_type': 'bearer',
            'user': {
                'id': 1,
                'username': 'LW-EN',
                'name': '冷轧电工',
                'role': 'energy_stat',
            },
            'machine_info': None,
        }
    )
    adapter.validate_python(
        {
            'type': 'workshop_redirect',
            'workshop_code': 'LW',
            'workshop_name': '冷轧车间',
        }
    )


def test_qr_login_openapi_documents_token_and_workshop_responses() -> None:
    openapi = TestClient(app).get('/openapi.json').json()

    response_schema = openapi['paths']['/api/v1/auth/qr-login']['post']['responses']['200']['content'][
        'application/json'
    ]['schema']
    schema_text = json.dumps(response_schema)

    assert 'LoginResponse' in schema_text
    assert 'WorkshopQrResponse' in schema_text
