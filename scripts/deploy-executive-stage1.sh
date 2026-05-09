#!/bin/bash
# One-shot deploy: 经营驾驶舱阶段 1
# Run on: xt@local
# Target: root@8.140.218.13
set -e

DEST="/srv/aluminum-bypass"
TS=$(date +%Y%m%d-%H%M%S)

echo "=== 1. Backup ==="
ssh root@8.140.218.13 "
  set -e
  cd $DEST
  mkdir -p backups
  tar czf backups/backend-src-${TS}.tgz -C backend app scripts alembic
  tar czf backups/frontend-dist-${TS}.tgz -C frontend dist
  ls -lah backups/ | tail -4
  echo BACKUP_OK
"

echo "=== 2. Upload backend files ==="
cd "D:/zzj Claude code/aluminum-bypass"
tar cf - --exclude='__pycache__' --exclude='.pytest_cache' \
  backend/app/models/executive.py \
  backend/app/agents/aluminum_price_fetcher.py \
  backend/app/agents/cost_aggregator.py \
  backend/app/agents/profit_snapshot.py \
  backend/app/routers/executive.py \
  backend/app/services/processing_fee_service.py \
  backend/app/services/executive_service.py \
  backend/app/services/executive_constants.py \
  backend/app/models/__init__.py \
  backend/app/main.py \
  backend/alembic/versions/0027_executive_dashboard.py \
  | ssh root@8.140.218.13 "cd $DEST && mkdir -p .deploy-staging && rm -rf .deploy-staging/backend && tar xf - -C .deploy-staging && echo UPLOAD_OK"

echo "=== 3. Apply backend code ==="
ssh root@8.140.218.13 "
  set -e
  cd $DEST
  STAGING=.deploy-staging/backend
  cp \$STAGING/app/models/executive.py backend/app/models/executive.py
  cp \$STAGING/app/models/__init__.py backend/app/models/__init__.py
  cp \$STAGING/app/main.py backend/app/main.py
  cp \$STAGING/app/agents/aluminum_price_fetcher.py backend/app/agents/aluminum_price_fetcher.py
  cp \$STAGING/app/agents/cost_aggregator.py backend/app/agents/cost_aggregator.py
  cp \$STAGING/app/agents/profit_snapshot.py backend/app/agents/profit_snapshot.py
  cp \$STAGING/app/routers/executive.py backend/app/routers/executive.py
  cp \$STAGING/app/services/processing_fee_service.py backend/app/services/processing_fee_service.py
  cp \$STAGING/app/services/executive_service.py backend/app/services/executive_service.py
  cp \$STAGING/app/services/executive_constants.py backend/app/services/executive_constants.py
  cp \$STAGING/alembic/versions/0027_executive_dashboard.py backend/alembic/versions/0027_executive_dashboard.py
  chown -R www-data:www-data backend/app backend/alembic
  rm -rf .deploy-staging
  echo APPLY_OK
"

echo "=== 4. Alembic upgrade + restart backend ==="
ssh root@8.140.218.13 "
  set -e
  cd $DEST/backend
  sudo -u www-data .venv/bin/alembic -c alembic.ini upgrade head 2>&1 | tail -5
  systemctl restart aluminum-bypass
  sleep 3
  systemctl is-active aluminum-bypass
  curl -sw '\nHTTP %{http_code}\n' http://127.0.0.1:8000/readyz | head -c 800
  echo BACKEND_OK
"

echo "=== 5. Upload + swap frontend dist ==="
cd "D:/zzj Claude code/aluminum-bypass/frontend"
tar cf - dist | ssh root@8.140.218.13 "
  set -e
  cd $DEST/frontend
  rm -rf dist.new
  mkdir dist.new
  tar xf - -C dist.new --strip-components=1
  mv dist dist.old.${TS}
  mv dist.new dist
  chown -R www-data:www-data dist
  md5sum dist/index.html
  nginx -t 2>&1 | tail -2
  systemctl reload nginx
  echo FRONTEND_OK
"

echo "=== 6. Smoke tests ==="
ssh root@8.140.218.13 "
  echo '-- /healthz --'
  curl -sw '\nHTTP %{http_code}\n' http://127.0.0.1:8000/healthz
  echo '-- /readyz --'
  curl -sw '\nHTTP %{http_code}\n' http://127.0.0.1:8000/readyz | head -c 600
  echo
  echo '-- homepage --'
  curl -sk --resolve xtmijd.com:443:127.0.0.1 -o /dev/null -w 'HTTP %{http_code}  size=%{size_download}\n' https://xtmijd.com/
  echo '-- new API /executive/processing-fees (expect 401 without auth) --'
  curl -sk --resolve xtmijd.com:443:127.0.0.1 -o /dev/null -w 'HTTP %{http_code}\n' https://xtmijd.com/api/v1/executive/processing-fees
  echo SMOKE_OK
"

echo ""
echo "=========================================="
echo "  DEPLOY COMPLETE"
echo "  Visit: https://xtmijd.com/#/manage/executive"
echo "  Processing fees admin: https://xtmijd.com/#/manage/executive/processing-fees"
echo "=========================================="
