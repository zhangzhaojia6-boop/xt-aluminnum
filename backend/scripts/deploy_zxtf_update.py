"""Incremental deploy: upload changed files, run migration + seed, restart."""
import paramiko
import os
import time

HOST = os.environ.get('ZXTF_DEPLOY_HOST', '')
USER = os.environ.get('ZXTF_DEPLOY_USER', '')
PASS = os.environ.get('ZXTF_DEPLOY_PASSWORD', '')
BACKEND_DIR = '/srv/aluminum-bypass/backend'
FRONTEND_DIR = '/srv/aluminum-bypass/frontend/dist'

LOCAL_BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
LOCAL_BACKEND = os.path.join(LOCAL_BASE, 'backend')
LOCAL_FRONTEND_DIST = os.path.join(LOCAL_BASE, 'frontend', 'dist')

CHANGED_BACKEND_FILES = [
    'app/core/workshop_templates.py',
    'app/models/energy.py',
    'app/models/__init__.py',
    'app/services/mobile_report_service.py',
    'app/services/work_order_service.py',
    'scripts/seed_machine_operator_qr.py',
    'scripts/seed_annealing_workshop.py',
    'alembic/versions/0021_machine_energy_records.py',
]

SKIP = {'.venv', 'venv', '.git', 'node_modules', '__pycache__', 'dist', '.pytest-cache', 'uploads'}


def run(ssh, cmd, timeout=120):
    print(f'  $ {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    code = stdout.channel.recv_exit_status()
    if out:
        for line in out.split('\n')[:20]:
            print(f'    {line}')
    if err and code != 0:
        for line in err.split('\n')[:8]:
            print(f'    [err] {line}')
    return out, code


def upload_dir_recursive(sftp, local_path, remote_path, ssh):
    for item in sorted(os.listdir(local_path)):
        if item in SKIP or item.startswith('.'):
            continue
        local_item = os.path.join(local_path, item)
        remote_item = f'{remote_path}/{item}'
        if os.path.isdir(local_item):
            try:
                sftp.stat(remote_item)
            except FileNotFoundError:
                ssh.exec_command(f'mkdir -p {remote_item}')[1].read()
            upload_dir_recursive(sftp, local_item, remote_item, ssh)
        else:
            if item.endswith(('.pyc', '.pyo')):
                continue
            sftp.put(local_item, remote_item)


def main():
    missing = [
        name
        for name, value in (
            ('ZXTF_DEPLOY_HOST', HOST),
            ('ZXTF_DEPLOY_USER', USER),
            ('ZXTF_DEPLOY_PASSWORD', PASS),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing deploy environment variables: {', '.join(missing)}")

    print(f'Connecting to {HOST}...')
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=15, allow_agent=False, look_for_keys=False)
    print('Connected!')

    print('\n[1/5] Uploading changed backend files...')
    sftp = ssh.open_sftp()
    for rel_path in CHANGED_BACKEND_FILES:
        local_file = os.path.join(LOCAL_BACKEND, rel_path.replace('/', os.sep))
        remote_file = f'{BACKEND_DIR}/{rel_path}'
        remote_dir = os.path.dirname(remote_file)
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            ssh.exec_command(f'mkdir -p {remote_dir}')[1].read()
        sftp.put(local_file, remote_file)
        print(f'  uploaded {rel_path}')

    print('\n[2/5] Uploading frontend dist...')
    upload_dir_recursive(sftp, LOCAL_FRONTEND_DIST, FRONTEND_DIR, ssh)
    sftp.close()
    print('  frontend dist uploaded')

    print('\n[3/5] Running database migration...')
    run(ssh, f'cd {BACKEND_DIR} && .venv/bin/alembic upgrade head 2>&1')

    print('\n[4/5] Seeding ZXTF workshop and QR codes...')
    run(ssh, f'cd {BACKEND_DIR} && .venv/bin/python scripts/seed_annealing_workshop.py 2>&1')

    print('\n[5/5] Restarting backend service...')
    run(ssh, f'chown -R www-data:www-data {BACKEND_DIR}')
    run(ssh, f'chown -R www-data:www-data {FRONTEND_DIR}')
    run(ssh, 'systemctl restart aluminum-bypass')
    time.sleep(3)
    out, _ = run(ssh, 'systemctl is-active aluminum-bypass')
    if 'active' in out:
        print('\n  Backend service is running!')
    else:
        print('\n  WARNING: service may not be running')
        run(ssh, 'journalctl -u aluminum-bypass --no-pager -n 15')

    print('\n=== Verification ===')
    run(ssh, 'curl -s -o /dev/null -w "healthz: %{http_code}" http://127.0.0.1:8000/healthz')

    print('\n=== Deployment complete! ===')
    ssh.close()


if __name__ == '__main__':
    main()
