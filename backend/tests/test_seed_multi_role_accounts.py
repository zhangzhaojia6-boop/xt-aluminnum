from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'seed_multi_role_accounts.py'


def _read_seed_script() -> str:
    return SCRIPT_PATH.read_text(encoding='utf-8-sig')


def _load_seed_module():
    spec = importlib.util.spec_from_file_location('seed_multi_role_accounts_under_test', SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_multi_role_accounts_has_no_shared_default_password() -> None:
    source = _read_seed_script()

    assert 'xt123456' not in source
    assert 'DEFAULT_PASSWORD' not in source
    assert 'pw_hash =' not in source
    assert 'password_hash=pw_hash' not in source


def test_seed_multi_role_password_hash_uses_fresh_random_token(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_seed_module()
    tokens = iter(['token-one', 'token-two'])
    seen_passwords: list[str] = []

    def fake_token_urlsafe(size: int) -> str:
        assert size == 24
        return next(tokens)

    def fake_hash(password: str) -> str:
        seen_passwords.append(password)
        return f'hash:{password}'

    monkeypatch.setattr(module.secrets, 'token_urlsafe', fake_token_urlsafe)
    monkeypatch.setattr(module, 'get_password_hash', fake_hash)

    assert module._create_random_password_hash() == 'hash:token-one'
    assert module._create_random_password_hash() == 'hash:token-two'
    assert seen_passwords == ['token-one', 'token-two']
