from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.system import User


MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts' / 'dingtalk_cli.py'
SPEC = spec_from_file_location('dingtalk_cli', MODULE_PATH)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class _FakeDingTalkService:
    def __init__(
        self,
        *,
        corp_id: str | None = None,
        app_key: str | None = None,
        app_secret: str | None = None,
        agent_id: str | None = None,
        token: str = 'token-value',
    ) -> None:
        self.config = SimpleNamespace(
            corp_id=corp_id,
            app_key=app_key,
            app_secret=app_secret,
            agent_id=agent_id,
        )
        self._token = token

    @property
    def enabled(self) -> bool:
        return bool(
            self.config.corp_id
            and self.config.app_key
            and self.config.app_secret
            and self.config.agent_id
        )

    def _get_access_token(self) -> str:
        return self._token

    def fetch_department_users(self, department_id: int = 1) -> list[dict]:
        _ = department_id
        return [
            {
                'userid': 'dt-user-1',
                'unionid': 'union-1',
                'mobile': '13800000000',
                'name': '生产主操',
            },
            {
                'userid': 'dt-user-2',
                'name': '无手机号员工',
            },
        ]


def test_status_payload_reports_missing_fields_without_leaking_secret() -> None:
    service = _FakeDingTalkService(
        corp_id='ding-corp',
        app_key='ding-app-key',
        app_secret='very-secret-value',
    )

    payload = MODULE.build_status_payload(service)

    assert payload['configured'] is False
    assert payload['missing'] == ['DINGTALK_AGENT_ID']
    assert payload['fields']['DINGTALK_APP_SECRET']['set'] is True
    assert payload['fields']['DINGTALK_APP_SECRET']['masked'] != 'very-secret-value'


def test_token_check_does_not_call_api_when_unconfigured() -> None:
    class BrokenService(_FakeDingTalkService):
        def _get_access_token(self) -> str:
            raise AssertionError('should not request token without full config')

    payload = MODULE.check_access_token(BrokenService())

    assert payload['ok'] is False
    assert payload['configured'] is False
    assert 'DINGTALK_CORP_ID' in payload['missing']


def test_main_status_json_uses_nonzero_exit_when_unconfigured(capsys) -> None:
    exit_code = MODULE.main(['status', '--json'], service=_FakeDingTalkService(app_key='ak'))

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload['configured'] is False
    assert 'DINGTALK_APP_SECRET' in payload['missing']


def test_main_token_json_reports_success_without_printing_token(capsys) -> None:
    exit_code = MODULE.main(
        ['token', '--json'],
        service=_FakeDingTalkService(
            corp_id='corp',
            app_key='key',
            app_secret='secret',
            agent_id='agent',
            token='real-access-token',
        ),
    )

    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 0
    assert payload['ok'] is True
    assert payload['token_length'] == len('real-access-token')
    assert 'real-access-token' not in output


def test_contacts_check_reports_sanitized_counts_and_local_matches(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'dingtalk-cli-users.db'}", future=True)
    Base.metadata.create_all(engine, tables=[User.__table__])
    Session = sessionmaker(bind=engine, future=True)
    with Session() as db:
        db.add(
            User(
                username='13800000000',
                password_hash='x',
                name='本地机台账号',
                role='machine_operator',
                is_mobile_user=True,
                is_active=True,
            )
        )
        db.commit()

    payload = MODULE.check_department_contacts(
        department_id=1,
        service=_FakeDingTalkService(
            corp_id='corp',
            app_key='key',
            app_secret='secret',
            agent_id='agent',
        ),
        sessionmaker_factory=lambda: Session,
    )

    assert payload['ok'] is True
    assert payload['dry_run_only'] is True
    assert payload['department_id'] == 1
    assert payload['contact_count'] == 2
    assert payload['contacts_with_mobile'] == 1
    assert payload['contacts_with_user_id'] == 2
    assert payload['would_match_existing_by_mobile_count'] == 1
    assert payload['active_user_with_dingtalk_binding_count'] == 0
    assert 'contacts' not in payload


def test_main_contacts_json_reports_permission_scope_without_leaking_contact_values(capsys) -> None:
    class PermissionDeniedService(_FakeDingTalkService):
        def fetch_department_users(self, department_id: int = 1) -> list[dict]:
            _ = department_id
            raise RuntimeError('missing scope qyapi_get_department_member for 13800000000')

    exit_code = MODULE.main(
        ['contacts', '--department-id', '1', '--json'],
        service=PermissionDeniedService(
            corp_id='corp',
            app_key='key',
            app_secret='secret',
            agent_id='agent',
        ),
    )

    output = capsys.readouterr().out
    payload = json.loads(output)

    assert exit_code == 3
    assert payload['ok'] is False
    assert payload['configured'] is True
    assert payload['department_access'] is False
    assert payload['missing_scope'] == 'qyapi_get_department_member'
    assert '13800000000' not in output
