from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Callable, Sequence


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
FRONTEND_ROOT = REPO_ROOT / 'frontend'
OUTPUT_PATH = REPO_ROOT / 'docs' / 'ops' / 'full_completion_gate.json'
BACKEND_GATE_AUDIT = REPO_ROOT / 'docs' / 'audits' / '2026-05-17-backend-completion-gate-audit.md'
SYSTEM_SMOKE_AUDIT = REPO_ROOT / 'docs' / 'audits' / '2026-05-17-system-smoke-audit.md'
COMMAND_TIMEOUT_SECONDS = 600


@dataclass
class CommandResult:
    command: list[str]
    cwd: Path
    returncode: int
    stdout: str
    stderr: str
    duration_s: float


CommandRunner = Callable[[Sequence[str], Path, int, dict[str, str] | None], CommandResult]


def run_command(
    command: Sequence[str],
    cwd: Path,
    timeout: int = COMMAND_TIMEOUT_SECONDS,
    env: dict[str, str] | None = None,
) -> CommandResult:
    started = time.monotonic()
    completed = subprocess.run(
        list(command),
        cwd=str(cwd),
        env=env,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return CommandResult(
        command=list(command),
        cwd=cwd,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_s=round(time.monotonic() - started, 2),
    )


def bin_cmd(name: str) -> str:
    if os.name == 'nt' and name in {'npm', 'npx'}:
        return f'{name}.cmd'
    return name


def command_text(result: CommandResult) -> str:
    return ' '.join(result.command)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def tail(text: str, max_chars: int = 4000) -> str:
    return text[-max_chars:]


def parse_python_test_counts(output: str) -> dict[str, int]:
    return {
        'passed': _first_count(output, 'passed'),
        'failed': _first_count(output, 'failed'),
        'skipped': _first_count(output, 'skipped'),
        'deselected': _first_count(output, 'deselected'),
    }


def parse_node_test_counts(output: str) -> dict[str, int]:
    counts = {
        'passed': _tap_count(output, 'pass'),
        'failed': _tap_count(output, 'fail'),
        'skipped': _tap_count(output, 'skipped'),
    }
    if counts['passed'] == 0:
        counts['passed'] = _first_count(output, 'pass')
    return counts


def parse_playwright_json(path: Path) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    stats = payload.get('stats', {})
    return {
        'passed': int(stats.get('expected') or 0),
        'failed': int(stats.get('unexpected') or 0),
        'skipped': int(stats.get('skipped') or 0),
        'flaky': int(stats.get('flaky') or 0),
    }


def parse_build_duration(output: str) -> float | None:
    match = re.search(r'built in ([\d.]+)(m?s)', output)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2)
    return round(value / 1000 if unit == 'ms' else value, 2)


def _first_count(output: str, label: str) -> int:
    match = re.search(rf'(\d+)\s+{re.escape(label)}', output)
    return int(match.group(1)) if match else 0


def _tap_count(output: str, label: str) -> int:
    match = re.search(rf'^#\s+{re.escape(label)}\s+(\d+)\s*$', output, re.MULTILINE)
    return int(match.group(1)) if match else 0


def make_command_check(name: str, result: CommandResult, counts: dict[str, int] | None = None) -> dict:
    output = result.stdout + result.stderr
    check = {
        'ok': result.returncode == 0,
        'command': command_text(result),
        'cwd': display_path(result.cwd),
        'duration_s': result.duration_s,
    }
    if counts:
        check.update(counts)
    if result.returncode != 0:
        check['exit_code'] = result.returncode
        check['output_tail'] = tail(output)
    return check


def run_backend_pytest(runner: CommandRunner) -> dict:
    result = runner([sys.executable, '-m', 'pytest'], BACKEND_ROOT, COMMAND_TIMEOUT_SECONDS, None)
    return make_command_check('backend_pytest', result, parse_python_test_counts(result.stdout + result.stderr))


def run_backend_completion_gate(runner: CommandRunner) -> dict:
    live_gate_enabled = os.getenv('FULL_COMPLETION_BACKEND_GATE_MODE') == 'live'
    if live_gate_enabled:
        result = runner(
            [
                sys.executable,
                'scripts/check_backend_completion_gate.py',
                '--json',
                '--dingtalk-userid',
                os.getenv('FULL_COMPLETION_DINGTALK_USERID', 'admin'),
            ],
            BACKEND_ROOT,
            COMMAND_TIMEOUT_SECONDS,
            None,
        )
        check = make_command_check('backend_completion_gate', result)
        check['mode'] = 'live'
        if result.returncode == 0:
            try:
                payload = json.loads(result.stdout)
                check['blockers'] = payload.get('blockers', [])
            except json.JSONDecodeError:
                check['ok'] = False
                check['output_tail'] = tail(result.stdout + result.stderr)
        return check

    if not BACKEND_GATE_AUDIT.exists():
        return {
            'ok': False,
            'mode': 'audit',
            'audit': str(BACKEND_GATE_AUDIT.relative_to(REPO_ROOT)),
            'error': 'backend completion gate audit is missing',
        }

    audit_text = BACKEND_GATE_AUDIT.read_text(encoding='utf-8')
    ok = '返回 `ok=true`' in audit_text and ('`blockers=[]`' in audit_text or 'blockers=[]' in audit_text)
    mtime = datetime.fromtimestamp(BACKEND_GATE_AUDIT.stat().st_mtime, tz=timezone.utc)
    age_days = max(0, (datetime.now(timezone.utc) - mtime).days)
    return {
        'ok': ok,
        'mode': 'audit',
        'audit': str(BACKEND_GATE_AUDIT.relative_to(REPO_ROOT)),
        'audit_last_modified': mtime.date().isoformat(),
        'audit_age_days': age_days,
        'mode_advisory': 'audit-mode reads a static doc; set FULL_COMPLETION_BACKEND_GATE_MODE=live to run the production gate command',
        'production_command': 'PYTHONPATH=. .venv/bin/python scripts/check_backend_completion_gate.py --json --dingtalk-userid admin',
    }


def run_frontend_unit(runner: CommandRunner) -> dict:
    result = runner([bin_cmd('npm'), 'test'], FRONTEND_ROOT, COMMAND_TIMEOUT_SECONDS, None)
    return make_command_check('frontend_unit', result, parse_node_test_counts(result.stdout + result.stderr))


def run_frontend_build(runner: CommandRunner) -> dict:
    result = runner([bin_cmd('npm'), 'run', 'build'], FRONTEND_ROOT, COMMAND_TIMEOUT_SECONDS, None)
    output = result.stdout + result.stderr
    check = make_command_check('frontend_build', result)
    check['duration_s'] = parse_build_duration(output) or result.duration_s
    check['sw_generated'] = (FRONTEND_ROOT / 'dist' / 'sw.js').exists()
    check['ok'] = check['ok'] and check['sw_generated']
    return check


def playwright_env(json_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env['PLAYWRIGHT_JSON_OUTPUT_FILE'] = str(json_path)
    if os.getenv('FULL_COMPLETION_REUSE_PLAYWRIGHT_SERVERS') == '1':
        env['PLAYWRIGHT_REUSE_SERVERS'] = '1'
    else:
        env.pop('PLAYWRIGHT_REUSE_SERVERS', None)
    return env


def run_playwright(
    runner: CommandRunner,
    command: list[str],
    json_path: Path,
    output_dir: Path,
) -> dict:
    env = playwright_env(json_path)
    result = runner(
        command + ['--reporter=list,json', '--output', str(output_dir)],
        FRONTEND_ROOT,
        COMMAND_TIMEOUT_SECONDS,
        env,
    )
    counts = parse_playwright_json(json_path) if json_path.exists() else {'passed': 0, 'failed': 1, 'skipped': 0, 'flaky': 0}
    check = make_command_check('playwright', result, counts)
    check['ok'] = result.returncode == 0 and counts['failed'] == 0
    return check


def run_playwright_e2e(runner: CommandRunner, temp_dir: Path) -> dict:
    return run_playwright(
        runner,
        [bin_cmd('npx'), 'playwright', 'test', '--project=chromium', '--project=mobile'],
        temp_dir / 'playwright-e2e.json',
        temp_dir / 'playwright-e2e',
    )


def run_playwright_a11y(runner: CommandRunner, temp_dir: Path) -> dict:
    check = run_playwright(
        runner,
        [bin_cmd('npx'), 'playwright', 'test', 'e2e/a11y/contrast.spec.js', '--project=chromium'],
        temp_dir / 'playwright-a11y.json',
        temp_dir / 'playwright-a11y',
    )
    check['violations'] = 0 if check['ok'] else check.get('failed', 1)
    return check


def run_system_smoke(runner: CommandRunner, temp_dir: Path) -> dict:
    check = run_playwright(
        runner,
        [
            bin_cmd('npx'),
            'playwright',
            'test',
            'e2e/compose-smoke.spec.js',
            'e2e/zd1-machine-smoke.spec.js',
            'e2e/mobile-entry-smoke.spec.js',
            '--project=chromium',
        ],
        temp_dir / 'system-smoke.json',
        temp_dir / 'system-smoke',
    )
    check['audit'] = str(SYSTEM_SMOKE_AUDIT.relative_to(REPO_ROOT))
    check['ok'] = check['ok'] and SYSTEM_SMOKE_AUDIT.exists()
    return check


def blocker_for(name: str, check: dict) -> dict[str, str] | None:
    if check.get('ok'):
        return None
    return {
        'code': name.upper(),
        'message': f'{name} failed',
    }


def build_payload(checks: dict[str, dict]) -> dict:
    blockers = [
        blocker
        for name, check in checks.items()
        for blocker in [blocker_for(name, check)]
        if blocker is not None
    ]
    return {
        'ok': not blockers,
        'checks': checks,
        'blockers': blockers,
    }


def write_payload(payload: dict, output_path: Path = OUTPUT_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run_full_completion_gate(runner: CommandRunner = run_command) -> dict:
    with tempfile.TemporaryDirectory(prefix='full-completion-gate-') as temp_root:
        temp_dir = Path(temp_root)
        checks = {
            'backend_pytest': run_backend_pytest(runner),
            'backend_completion_gate': run_backend_completion_gate(runner),
            'frontend_unit': run_frontend_unit(runner),
            'frontend_build': run_frontend_build(runner),
            'playwright_e2e': run_playwright_e2e(runner, temp_dir),
            'playwright_a11y': run_playwright_a11y(runner, temp_dir),
            'system_smoke': run_system_smoke(runner, temp_dir),
        }
    return build_payload(checks)


def main(argv: list[str] | None = None, *, runner: CommandRunner = run_command) -> int:
    parser = argparse.ArgumentParser(description='Run full completion gate checks.')
    parser.add_argument('--output', default=str(OUTPUT_PATH), help='JSON output path.')
    args = parser.parse_args(argv)

    payload = run_full_completion_gate(runner)
    output_path = Path(args.output).resolve()
    write_payload(payload, output_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
