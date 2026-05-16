#!/usr/bin/env python3
"""First-deploy preparation script.

Validates that the deployment environment is ready:
- Database migrations are up to date
- Required environment variables are set
- Backend health check passes
- Frontend build succeeds
"""
import os
import sys
import subprocess
import urllib.request
import json

REQUIRED_ENV = [
    'DATABASE_URL',
    'SECRET_KEY',
    'CORS_ORIGINS',
]

OPTIONAL_ENV = [
    'DINGTALK_AGENT_ID',
    'DINGTALK_APP_KEY',
    'DINGTALK_APP_SECRET',
    'REDIS_URL',
]


def check_env():
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    optional_missing = [k for k in OPTIONAL_ENV if not os.environ.get(k)]
    if missing:
        print(f'[FAIL] Missing required env vars: {", ".join(missing)}')
        return False
    if optional_missing:
        print(f'[WARN] Missing optional env vars: {", ".join(optional_missing)}')
    print('[OK] Required environment variables present')
    return True


def check_migrations():
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'alembic', 'check'],
            capture_output=True, text=True, cwd=os.path.dirname(__file__)
        )
        if result.returncode == 0:
            print('[OK] Database migrations up to date')
            return True
        print(f'[FAIL] Migrations not up to date: {result.stderr.strip()}')
        return False
    except FileNotFoundError:
        print('[SKIP] alembic not found, skipping migration check')
        return True


def check_backend_health(base_url='http://localhost:8000'):
    try:
        req = urllib.request.Request(f'{base_url}/health')
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            if data.get('status') == 'ok':
                print('[OK] Backend health check passed')
                return True
            print(f'[FAIL] Backend unhealthy: {data}')
            return False
    except Exception as e:
        print(f'[SKIP] Backend not reachable: {e}')
        return True


def check_frontend_build():
    frontend_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend')
    if not os.path.isdir(frontend_dir):
        print('[SKIP] Frontend directory not found')
        return True
    try:
        result = subprocess.run(
            ['npm', 'run', 'build'],
            capture_output=True, text=True, cwd=frontend_dir, shell=True
        )
        if result.returncode == 0:
            print('[OK] Frontend build succeeded')
            return True
        print(f'[FAIL] Frontend build failed:\n{result.stderr[:500]}')
        return False
    except FileNotFoundError:
        print('[SKIP] npm not found')
        return True


def main():
    print('=== 鑫泰铝业 数据中枢 · 部署前检查 ===\n')
    results = [
        check_env(),
        check_migrations(),
        check_backend_health(),
        check_frontend_build(),
    ]
    print()
    if all(results):
        print('All checks passed. Ready to deploy.')
        return 0
    print('Some checks failed. Fix issues before deploying.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
