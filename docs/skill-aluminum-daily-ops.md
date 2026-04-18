# Skill: aluminum-daily-ops

## Purpose

Run the minimal daily pilot operations review without rebuilding a manual statistics middle layer.

## Workflow

1. Check `docker compose ps`.
2. Check `/healthz` and `/readyz`.
3. Run:
- `check_pilot_config.py`
- `check_pilot_metrics.py`
- `check_pilot_anomalies.py`
4. Explain whether the day is healthy, degraded, or blocked.
5. Point only to exception handling and next actions.
