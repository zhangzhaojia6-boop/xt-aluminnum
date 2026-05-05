"""Incremental deploy: upload changed files, run migration + seed, restart."""
import paramiko
import os
import re
import shlex
import time

PORT = int(os.environ.get('ZXTF_DEPLOY_SSH_PORT', '2222'))
SUDO = os.environ.get('ZXTF_DEPLOY_SUDO', 'sudo -n').strip() or 'sudo -n'
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
SAFE_LINUX_USERNAME = re.compile(r'^[a-z_][a-z0-9_-]{0,31}$')


def require_env(name: str) -> str:
    value = os.environ.get(name, '').strip()
    if not value:
        raise RuntimeError(f'{name} is required')
    return value


def require_existing_file_env(name: str) -> str:
    value = require_env(name)
    if not os.path.isfile(value):
        raise RuntimeError(f'{name} must point to an existing file')
    return value


def require_deploy_user() -> str:
    user = require_env('ZXTF_DEPLOY_USER')
    if user == 'root':
        raise RuntimeError('ZXTF_DEPLOY_USER must be a least-privilege non-root user')
    if not SAFE_LINUX_USERNAME.fullmatch(user):
        raise RuntimeError('ZXTF_DEPLOY_USER must be a safe Linux username')
    return user


def sudo_cmd(cmd: str) -> str:
    return f'{SUDO} sh -lc {shlex.quote(cmd)}'


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
                ssh.exec_command(f'mkdir -p {shlex.quote(remote_item)}')[1].read()
            upload_dir_recursive(sftp, local_item, remote_item, ssh)
        else:
            if item.endswith(('.pyc', '.pyo')):
                continue
            sftp.put(local_item, remote_item)


def main():
    host = require_env('ZXTF_DEPLOY_HOST')
    deploy_user = require_deploy_user()
    ssh_key_path = require_existing_file_env('ZXTF_DEPLOY_SSH_KEY_PATH')
    known_hosts_path = require_existing_file_env('ZXTF_DEPLOY_KNOWN_HOSTS')
    ssh_key_passphrase = os.environ.get('ZXTF_DEPLOY_SSH_KEY_PASSPHRASE') or None

    print(f'Connecting to {deploy_user}@{host}:{PORT}...')
    ssh = paramiko.SSHClient()
    ssh.load_host_keys(known_hosts_path)
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    ssh.connect(
        host,
        port=PORT,
        username=deploy_user,
        key_filename=ssh_key_path,
        passphrase=ssh_key_passphrase,
        timeout=15,
        allow_agent=False,
        look_for_keys=False,
    )
    print('Connected!')

    run(ssh, sudo_cmd(f'chown -R {deploy_user}:{deploy_user} {shlex.quote(BACKEND_DIR)} {shlex.quote(FRONTEND_DIR)}'))

    print('\n[1/5] Uploading changed backend files...')
    sftp = ssh.open_sftp()
    for rel_path in CHANGED_BACKEND_FILES:
        local_file = os.path.join(LOCAL_BACKEND, rel_path.replace('/', os.sep))
        remote_file = f'{BACKEND_DIR}/{rel_path}'
        remote_dir = os.path.dirname(remote_file)
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            ssh.exec_command(f'mkdir -p {shlex.quote(remote_dir)}')[1].read()
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
    run(ssh, sudo_cmd(f'chown -R www-data:www-data {shlex.quote(BACKEND_DIR)}'))
    run(ssh, sudo_cmd(f'chown -R www-data:www-data {shlex.quote(FRONTEND_DIR)}'))
    run(ssh, sudo_cmd('systemctl restart aluminum-bypass'))
    time.sleep(3)
    out, _ = run(ssh, sudo_cmd('systemctl is-active aluminum-bypass'))
    if 'active' in out:
        print('\n  Backend service is running!')
    else:
        print('\n  WARNING: service may not be running')
        run(ssh, sudo_cmd('journalctl -u aluminum-bypass --no-pager -n 15'))

    print('\n=== Verification ===')
    run(ssh, 'curl -s -o /dev/null -w "healthz: %{http_code}" http://127.0.0.1:8000/healthz')

    print('\n=== Deployment complete! ===')
    ssh.close()


if __name__ == '__main__':
    main()
