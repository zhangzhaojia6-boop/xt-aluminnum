# SSL Setup

## Local trial

Use a Self-signed certificate only for local or closed-network trial runs. Put the files at:

- `ssl/cert.pem`
- `ssl/key.pem`

The production nginx container reads them as `/etc/nginx/ssl/cert.pem` and `/etc/nginx/ssl/key.pem`.

## Production

For a public domain, use Let's Encrypt after DNS and filing are ready. Keep certificate renewal on the server, and add a `cron` renewal check so nginx can reload the refreshed certificate without manual work.
