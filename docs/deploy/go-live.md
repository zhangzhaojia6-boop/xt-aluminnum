# Go-Live Checklist — 鑫泰铝业 数据中枢

**Date:** 2026-05-16
**Version:** v2.0.0-rc1

## Environment Variables

| Variable | Purpose | File | Missing Impact |
|----------|---------|------|----------------|
| DATABASE_URL | PostgreSQL connection | .env | Fatal — no DB |
| SECRET_KEY | JWT signing | .env | Fatal — no auth |
| CORS_ORIGINS | Allowed origins | .env | 403 on frontend |
| REDIS_URL | Cache + realtime | .env | Degraded — no cache |
| DINGTALK_AGENT_ID | DingTalk push | .env | No mobile push |
| DINGTALK_APP_KEY | DingTalk auth | .env | No mobile push |
| DINGTALK_APP_SECRET | DingTalk auth | .env | No mobile push |
| AI_API_KEY | AI briefing/insights | .env | AI shows "未开启" |
| AI_BASE_URL | AI endpoint | .env | AI shows "未开启" |

## Migration Sequence

```bash
cd backend
alembic upgrade head
```

Key migrations after 0028_user_preferences:
- 0029_audit_trail (AuditTrail model)
- 0030_mobile_shift_reports (MobileShiftReport + dedup constraint)
- 0031_work_order_entries_dedup (UniqueConstraint on entries)

## Data Cleanup (Production)

```bash
python scripts/clean_bad_production_rows.py --dry-run --before 2026-05-01
# Review output, then:
python scripts/clean_bad_production_rows.py --apply --before 2026-05-01
```

## Deployment Steps

1. Pull latest code on server
2. Run `scripts/first_deploy_prep.py` to validate environment
3. Run `alembic upgrade head`
4. Build frontend: `cd frontend && npm run build`
5. Restart backend: `systemctl restart xintai-backend`
6. Verify health: `curl http://localhost:8000/health`
7. Verify frontend loads at configured domain

## Rollback

Each feature was committed independently. To rollback:

```bash
git revert <commit-sha>  # Revert specific feature
alembic downgrade -1     # If migration was involved
systemctl restart xintai-backend
```

## Post-Deploy Verification

- [ ] Health endpoint returns `{"status": "ok"}`
- [ ] Login flow works (DingTalk + password)
- [ ] Mobile entry form submits successfully
- [ ] Dashboard shows real-time data
- [ ] Review/approve flow completes
- [ ] AI briefing shows "未开启" or real content (depending on AI_API_KEY)
