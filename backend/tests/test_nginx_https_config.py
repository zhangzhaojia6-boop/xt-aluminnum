from tests.path_helpers import REPO_ROOT


def test_nginx_https_config_and_docs_are_present() -> None:
    nginx_conf = (REPO_ROOT / 'nginx' / 'nginx.conf').read_text(encoding='utf-8')
    compose_prod = (REPO_ROOT / 'docker-compose.prod.yml').read_text(encoding='utf-8')
    ssl_docs = (REPO_ROOT / 'docs' / 'ssl-setup.md').read_text(encoding='utf-8')

    assert 'listen 443 ssl http2;' in nginx_conf
    assert 'ssl_certificate /etc/nginx/ssl/cert.pem;' in nginx_conf
    assert 'ssl_certificate_key /etc/nginx/ssl/key.pem;' in nginx_conf
    assert 'Strict-Transport-Security "max-age=63072000"' in nginx_conf
    assert 'return 301 https://$host$request_uri;' in nginx_conf

    assert './ssl:/etc/nginx/ssl:ro' in compose_prod
    assert '"443:443"' in compose_prod

    assert 'Self-signed' in ssl_docs
    assert "Let's Encrypt" in ssl_docs
    assert 'cron' in ssl_docs.lower()
