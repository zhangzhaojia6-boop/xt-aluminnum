from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
import sys

from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'check_full_completion_gate.py'


def _load_script_module():
    spec = spec_from_file_location('check_full_completion_gate_script', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _command_result(module, command, cwd, returncode=0, stdout='', stderr=''):
    return module.CommandResult(
        command=list(command),
        cwd=cwd,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        duration_s=1.0,
    )


def test_full_completion_gate_writes_ok_payload(tmp_path, monkeypatch) -> None:
    module = _load_script_module()
    repo_root = tmp_path / 'repo'
    backend_audit = repo_root / 'docs' / 'audits' / '2026-05-17-backend-completion-gate-audit.md'
    smoke_audit = repo_root / 'docs' / 'audits' / '2026-05-17-system-smoke-audit.md'
    backend_audit.parent.mkdir(parents=True, exist_ok=True)
    backend_audit.write_text('返回 `ok=true` 且 `blockers=[]`', encoding='utf-8')
    smoke_audit.write_text('E5 smoke passed', encoding='utf-8')
    monkeypatch.setattr(module, 'REPO_ROOT', repo_root)
    monkeypatch.setattr(module, 'BACKEND_GATE_AUDIT', backend_audit)
    monkeypatch.setattr(module, 'SYSTEM_SMOKE_AUDIT', smoke_audit)

    def runner(command, cwd, timeout, env):
        command_text = ' '.join(command)
        if '-m pytest' in command_text:
            return _command_result(module, command, cwd, stdout='947 passed, 3 skipped, 124 deselected')
        if command[:2] in (['npm', 'test'], ['npm.cmd', 'test']):
            return _command_result(module, command, cwd, stdout='# pass 236\n# fail 0\n# skipped 0\n')
        if command[:3] in (['npm', 'run', 'build'], ['npm.cmd', 'run', 'build']):
            return _command_result(module, command, cwd, stdout='✓ built in 2.44s')
        json_path = env.get('PLAYWRIGHT_JSON_OUTPUT_FILE')
        assert json_path
        assert 'PLAYWRIGHT_REUSE_SERVERS' not in env
        payload = {'stats': {'expected': 100, 'unexpected': 0, 'skipped': 3, 'flaky': 0}}
        if any('contrast.spec.js' in part for part in command):
            payload['stats']['expected'] = 12
            payload['stats']['skipped'] = 0
        if any(name in part for part in command for name in ['compose-smoke.spec.js', 'zd1-machine-smoke.spec.js', 'mobile-entry-smoke.spec.js']):
            payload['stats']['expected'] = 13
            payload['stats']['skipped'] = 0
        module.Path(json_path).write_text(json.dumps(payload), encoding='utf-8')
        return _command_result(module, command, cwd, stdout=f"{payload['stats']['expected']} passed")

    monkeypatch.setattr(module, 'FRONTEND_ROOT', tmp_path)
    (tmp_path / 'dist').mkdir()
    (tmp_path / 'dist' / 'sw.js').write_text('// sw', encoding='utf-8')
    output = tmp_path / 'gate.json'

    exit_code = module.main(['--output', str(output)], runner=runner)
    payload = json.loads(output.read_text(encoding='utf-8'))

    assert exit_code == 0
    assert payload['ok'] is True
    assert payload['blockers'] == []
    assert payload['checks']['backend_pytest']['passed'] == 947
    assert payload['checks']['frontend_unit']['passed'] == 236
    assert payload['checks']['frontend_build']['sw_generated'] is True
    assert payload['checks']['playwright_a11y']['violations'] == 0


def test_full_completion_gate_reports_failed_check(monkeypatch) -> None:
    module = _load_script_module()

    checks = {
        'backend_pytest': {'ok': True},
        'frontend_unit': {'ok': False},
    }
    payload = module.build_payload(checks)

    assert payload['ok'] is False
    assert payload['blockers'] == [
        {'code': 'FRONTEND_UNIT', 'message': 'frontend_unit failed'}
    ]


def test_backend_completion_gate_audit_mode_exposes_visibility(tmp_path, monkeypatch) -> None:
    module = _load_script_module()
    audit_path = tmp_path / 'audit.md'
    audit_path.write_text('生产返回 `ok=true` 且 `blockers=[]`', encoding='utf-8')
    monkeypatch.setattr(module, 'BACKEND_GATE_AUDIT', audit_path)
    monkeypatch.setattr(module, 'REPO_ROOT', tmp_path)
    monkeypatch.delenv('FULL_COMPLETION_BACKEND_GATE_MODE', raising=False)

    def runner(*args, **kwargs):
        raise AssertionError('audit-mode must not invoke any subprocess')

    check = module.run_backend_completion_gate(runner)

    assert check['ok'] is True
    assert check['mode'] == 'audit'
    assert 'audit_age_days' in check
    assert isinstance(check['audit_age_days'], int)
    assert check['audit_age_days'] >= 0
    assert 'audit_last_modified' in check
    assert 'mode_advisory' in check
    assert 'FULL_COMPLETION_BACKEND_GATE_MODE=live' in check['mode_advisory']

