# Skill: aluminum-go-live-gate

## Purpose

Decide whether `aluminum-bypass` may proceed to pilot rollout or production release.

## Decision Rules

1. If `/readyz` is blocked, fail the gate.
2. If real pilot data is still zero-reporting or dominated by missing-report anomalies, fail the gate.
3. If rollback or access material is missing, fail production release even if app tests pass.
4. Prefer downgrade switches over risky release.
