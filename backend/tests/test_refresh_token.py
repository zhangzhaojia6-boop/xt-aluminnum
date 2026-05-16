import pytest
from jose import JWTError

from app.core.auth import create_refresh_token, decode_refresh_token


def test_create_and_decode_refresh_token():
    token = create_refresh_token(subject='42')
    payload = decode_refresh_token(token)
    assert payload['sub'] == '42'
    assert payload['type'] == 'refresh'


def test_decode_refresh_token_rejects_access_token():
    from app.core.auth import create_access_token

    access = create_access_token(subject='42')
    with pytest.raises(JWTError):
        decode_refresh_token(access)
