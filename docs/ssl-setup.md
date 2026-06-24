# SSL Setup

## Self-signed

内网试跑可先生成 Self-signed 证书：

```bash
mkdir -p ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout ssl/key.pem -out ssl/cert.pem
```

## Let's Encrypt

正式域名建议使用 Let's Encrypt。证书文件放在：

- `ssl/cert.pem`
- `ssl/key.pem`

## Renewal

用 `cron` 定期续期，并在续期后 reload nginx。续期前先确认 80/443 端口和域名解析正常。
