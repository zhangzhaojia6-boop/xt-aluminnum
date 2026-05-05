"""Full production deployment to 8.140.218.13 for xtmijd.com"""
import os
import paramiko
import re
import shlex
import stat

HOST = os.environ.get('DEPLOY_HOST', '8.140.218.13')
PORT = int(os.environ.get('DEPLOY_SSH_PORT', '2222'))
DOMAIN = os.environ.get('DEPLOY_DOMAIN', 'xtmijd.com')
SUDO = os.environ.get('DEPLOY_SUDO', 'sudo -n').strip() or 'sudo -n'
BACKEND_DIR = '/srv/aluminum-bypass/backend'
FRONTEND_DIR = '/srv/aluminum-bypass/frontend/dist'

LOCAL_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LOCAL_FRONTEND_DIST = os.path.abspath(os.path.join(LOCAL_BACKEND, '..', 'frontend', 'dist'))

SKIP_DIRS = {'.venv', 'venv', '.git', 'node_modules', '__pycache__', 'dist',
             '.pytest-cache', '.pytest-cache-2', '.pytest-run-2', 'uploads'}
SKIP_FILES = {'.env', '.env.example', '.dockerignore', '.codex-preview.db'}
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
    user = require_env('DEPLOY_USER')
    if user == 'root':
        raise RuntimeError('DEPLOY_USER must be a least-privilege non-root user')
    if not SAFE_LINUX_USERNAME.fullmatch(user):
        raise RuntimeError('DEPLOY_USER must be a safe Linux username')
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
        print(out[:2000])
    if err and code != 0:
        for line in err.split('\n')[:8]:
            print(f'    [err] {line}')
    return out, code


def sudo_install_file(ssh, sftp, content: str, remote_path: str, mode: str = '0644'):
    """Install a root-owned remote file through a non-root SSH account."""
    temp_path = f'/tmp/aluminum-bypass-deploy-{os.getpid()}-{os.path.basename(remote_path)}'
    with sftp.open(temp_path, 'w') as f:
        f.write(content)
    run(
        ssh,
        sudo_cmd(
            f'install -m {shlex.quote(mode)} -o root -g root '
            f'{shlex.quote(temp_path)} {shlex.quote(remote_path)}'
        ),
    )
    run(ssh, f'rm -f {shlex.quote(temp_path)}')


def upload_dir(sftp, local_path, remote_path, ssh):
    """Upload directory recursively."""
    for item in sorted(os.listdir(local_path)):
        if item in SKIP_DIRS or item in SKIP_FILES:
            continue
        local_item = os.path.join(local_path, item)
        remote_item = f'{remote_path}/{item}'
        if os.path.isdir(local_item):
            if item.startswith('.'):
                continue
            try:
                sftp.stat(remote_item)
            except FileNotFoundError:
                ssh.exec_command(f'mkdir -p {shlex.quote(remote_item)}')[1].read()
            try:
                upload_dir(sftp, local_item, remote_item, ssh)
            except PermissionError:
                continue
        else:
            if item.endswith(('.pyc', '.pyo')):
                continue
            sftp.put(local_item, remote_item)


NGINX_CONF = f'''server {{
    listen 80;
    server_name {DOMAIN} www.{DOMAIN};
    server_tokens off;

    root {FRONTEND_DIR};
    index index.html;
    client_max_body_size 50m;

    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/javascript application/javascript application/json application/xml image/svg+xml;

    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    location /.well-known/acme-challenge/ {{
        root /var/www/letsencrypt;
    }}

    location /assets/ {{
        expires 30d;
        add_header Cache-Control "public, immutable" always;
        try_files $uri =404;
    }}

    location ~* \\.(?:ico|png|jpg|jpeg|gif|svg|webp|woff|woff2)$ {{
        expires 30d;
        add_header Cache-Control "public, immutable" always;
        try_files $uri =404;
    }}

    location = /index.html {{
        add_header Cache-Control "no-store, must-revalidate" always;
        try_files $uri =404;
    }}

    location /api/ {{
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    location /uploads/ {{
        proxy_pass http://127.0.0.1:8000/uploads/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    location /healthz {{
        proxy_pass http://127.0.0.1:8000/healthz;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }}

    location / {{
        add_header Cache-Control "no-store, must-revalidate" always;
        try_files $uri $uri/ /index.html;
    }}
}}
'''

SYSTEMD_UNIT = f'''[Unit]
Description=Aluminum Bypass Backend (uvicorn)
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory={BACKEND_DIR}
Environment=PATH={BACKEND_DIR}/.venv/bin:/usr/bin:/bin
EnvironmentFile={BACKEND_DIR}/.env
ExecStart={BACKEND_DIR}/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
'''

# PLACEHOLDER_MAIN

def main():
    deploy_user = require_deploy_user()
    ssh_key_path = require_existing_file_env('DEPLOY_SSH_KEY_PATH')
    known_hosts_path = require_existing_file_env('DEPLOY_KNOWN_HOSTS')
    ssh_key_passphrase = os.environ.get('DEPLOY_SSH_KEY_PASSPHRASE') or None
    db_url = require_env('DEPLOY_DATABASE_URL')
    secret_key = require_env('DEPLOY_SECRET_KEY')
    admin_password = require_env('DEPLOY_INIT_ADMIN_PASSWORD')
    admin_username = os.environ.get('DEPLOY_INIT_ADMIN_USERNAME', 'admin').strip() or 'admin'
    admin_name = os.environ.get('DEPLOY_INIT_ADMIN_NAME', '系统管理员').strip() or '系统管理员'

    ssh = paramiko.SSHClient()
    ssh.load_host_keys(known_hosts_path)
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    print(f'Connecting to {deploy_user}@{HOST}:{PORT}...')
    ssh.connect(
        HOST,
        port=PORT,
        username=deploy_user,
        key_filename=ssh_key_path,
        passphrase=ssh_key_passphrase,
        allow_agent=False,
        look_for_keys=False,
        timeout=15,
    )

    # Step 1: Stop old Docker containers
    print('\n[1/7] Stopping old Docker containers...')
    run(ssh, sudo_cmd('docker stop aluminum-bypass-backend-fast 2>/dev/null; docker rm aluminum-bypass-backend-fast 2>/dev/null; echo done'))
    run(ssh, sudo_cmd('docker stop aluminum-bypass-db-1 2>/dev/null; docker rm aluminum-bypass-db-1 2>/dev/null; echo done'))

    # Step 2: Create directory structure
    print('\n[2/7] Preparing directories...')
    run(ssh, sudo_cmd(f'mkdir -p {shlex.quote(BACKEND_DIR)} {shlex.quote(FRONTEND_DIR)} /var/www/letsencrypt'))
    run(ssh, sudo_cmd(f'chown -R {deploy_user}:{deploy_user} {shlex.quote(BACKEND_DIR)} {shlex.quote(FRONTEND_DIR)}'))

    # Step 3: Upload backend
    print('\n[3/7] Uploading backend code...')
    sftp = ssh.open_sftp()
    upload_dir(sftp, LOCAL_BACKEND, BACKEND_DIR, ssh)
    # Upload all __init__.py explicitly
    for root, dirs, files in os.walk(LOCAL_BACKEND):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f == '__init__.py':
                local_path = os.path.join(root, f)
                rel = os.path.relpath(local_path, LOCAL_BACKEND).replace('\\', '/')
                remote = f'{BACKEND_DIR}/{rel}'
                rdir = os.path.dirname(remote)
                try:
                    sftp.stat(rdir)
                except FileNotFoundError:
                    ssh.exec_command(f'mkdir -p {shlex.quote(rdir)}')[1].read()
                sftp.put(local_path, remote)

    # Write .env
    env_lines = [
        f'DATABASE_URL={db_url}',
        f'SECRET_KEY={secret_key}',
        f'INIT_ADMIN_USERNAME={admin_username}',
        f'INIT_ADMIN_PASSWORD={admin_password}',
        f'INIT_ADMIN_NAME={admin_name}',
    ]
    with sftp.open(f'{BACKEND_DIR}/.env', 'w') as f:
        f.write('\n'.join(env_lines) + '\n')
    print('  .env written')

    # Step 4: Upload frontend dist
    print('\n[4/7] Uploading frontend dist...')
    upload_dir(sftp, LOCAL_FRONTEND_DIST, FRONTEND_DIR, ssh)
    sftp.close()
    print('  frontend uploaded')

    # Step 5: Setup backend venv and deps
    print('\n[5/7] Installing backend dependencies...')
    run(ssh, f'cd {BACKEND_DIR} && python3 -m venv .venv 2>/dev/null || true')
    run(ssh, f'cd {BACKEND_DIR} && .venv/bin/pip install --upgrade pip -q 2>&1 | tail -1', timeout=120)
    run(ssh, f'cd {BACKEND_DIR} && .venv/bin/pip install -q -r requirements.txt 2>&1 | tail -3', timeout=300)

    # Run alembic
    print('  Running migrations...')
    run(ssh, f'cd {BACKEND_DIR} && .venv/bin/alembic upgrade head 2>&1 | tail -5')

    # Fix ownership
    run(ssh, sudo_cmd(f'chown -R www-data:www-data {shlex.quote(BACKEND_DIR)}'))
    run(ssh, sudo_cmd(f'mkdir -p {shlex.quote(BACKEND_DIR)}/uploads && chown -R www-data:www-data {shlex.quote(BACKEND_DIR)}/uploads'))

    # Step 6: Configure systemd service
    print('\n[6/7] Configuring systemd service...')
    sftp = ssh.open_sftp()
    sudo_install_file(ssh, sftp, SYSTEMD_UNIT, '/etc/systemd/system/aluminum-bypass.service')
    sftp.close()
    run(ssh, sudo_cmd('systemctl daemon-reload'))
    run(ssh, sudo_cmd('systemctl enable aluminum-bypass'))
    run(ssh, sudo_cmd('systemctl restart aluminum-bypass'))
    import time; time.sleep(2)
    out, _ = run(ssh, sudo_cmd('systemctl is-active aluminum-bypass'))
    if 'active' in out:
        print('  Backend service is running!')
    else:
        run(ssh, sudo_cmd('journalctl -u aluminum-bypass --no-pager -n 20'))

    # Step 7: Configure nginx
    print('\n[7/7] Configuring nginx...')
    sftp = ssh.open_sftp()
    sudo_install_file(ssh, sftp, NGINX_CONF, f'/etc/nginx/sites-enabled/{DOMAIN}.conf')
    sftp.close()
    run(ssh, sudo_cmd('nginx -t 2>&1'))
    run(ssh, sudo_cmd('systemctl reload nginx'))

    # Verify
    print('\n=== Verification ===')
    run(ssh, f'curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:8000/healthz')
    run(ssh, f'curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1/api/v1/healthz 2>/dev/null || echo "nginx proxy not ready yet"')

    print(f'\n{"="*60}')
    print(f'Deployment complete!')
    print(f'Backend: systemd service "aluminum-bypass" on port 8000')
    print(f'Frontend: {FRONTEND_DIR}')
    print(f'Nginx: /etc/nginx/sites-enabled/{DOMAIN}.conf')
    print(f'')
    print(f'Next: point {DOMAIN} DNS A record to {HOST}')
    print(f'Then run: acme.sh --issue -d {DOMAIN} -w /var/www/letsencrypt')
    print(f'{"="*60}')

    ssh.close()


if __name__ == '__main__':
    main()
