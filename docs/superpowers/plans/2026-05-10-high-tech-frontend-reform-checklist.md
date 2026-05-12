# HUD Reform Release Checklist

> Acceptance gate for merging the HUD reform branch. Every box must be ticked
> before merge. Run `scripts/hud-guardrails.sh` (bash) or `scripts/hud-guardrails.ps1`
> (PowerShell) to mechanize items 1-5.

## 1. Scope

- [ ] `frontend/src/design/xt-hud.css` only contains selectors scoped under
      `:root[data-xt-theme="hud"]` or `[data-xt-theme="hud"] …`.
- [ ] No `.el-card / .el-dialog / .el-drawer` global overrides in
      `frontend/src/design/`.
- [ ] No `!important` anywhere in `xt-hud.css`.

## 2. Bundle

- [ ] `npm run build` emits a standalone `vendor-three-*.js` chunk.
- [ ] Gzip size of `vendor-three` chunk ≤ 180 KB (reference: 171 KB on 2026-05-10).
- [ ] Main bundle size delta vs `main` branch ≤ +10 KB gzip (excluding HUD CSS).

## 3. Reversibility

- [ ] Deleting `data-xt-theme` from `<html>` in devtools instantly restores the
      industrial theme on `/manage/overview` and `/login`.
- [ ] `git checkout main -- frontend/src/design/xt-hud.css` produces a visual
      diff only on the Login backdrop + manage panels (not forms, buttons, or
      business content).

## 4. A11y

- [ ] With `prefers-reduced-motion: reduce` enabled, `ParticleField` canvas
      is not rendered; gradient fallback is visible.
- [ ] Contrast on HUD text (`rgba(224,236,255,0.92)` on
      `var(--xt-hud-canvas)`) ≥ 7:1 (AAA body) and muted
      (`rgba(176,196,224,0.62)`) ≥ 4.5:1 (AA).
- [ ] HUD backdrop uses `aria-hidden="true"` so SR users skip it.

## 5. Product language

- [ ] No `cyberpunk / palantir / quantum / sci-fi` strings in code, specs,
      plans, team-workflow docs.
- [ ] Brand text on Login + ManageShell reads `数据中枢`.

## 6. Design review (Claude / design-review skill)

- [ ] `/design-review http://localhost:5173/login --quick` — AI-slop score
      not worse than baseline.
- [ ] `/design-review http://localhost:5173/manage/overview --quick` — same.
- [ ] Baseline archived under
      `~/.gstack/projects/<slug>/designs/design-audit-<date>/design-baseline.json`.

## 7. Rollback drill

- [ ] Revert commit for Task 1 (ParticleField) produced by running
      `git revert <sha>` locally restores the pre-HUD Login without
      leaving dangling imports.
- [ ] Disabling HUD via `localStorage.removeItem('xt-theme-preference')` on a
      logged-in manage session returns the shell to light theme on next route
      mount (no refresh required).

## 8. Contract (Task 6)

- [ ] `GET /api/v1/user/preferences` returns 200 `{ "theme": null }` when no
      row exists.
- [ ] `PUT /api/v1/user/preferences` with body `{ "theme": "hud" }` returns
      200 + persists; subsequent GET returns same body.
- [ ] `PUT` with body `{ "theme": "palantir" }` returns 422.
- [ ] Unauthenticated requests return 401 on both verbs.
- [ ] Alembic `0028_user_preferences` is idempotent (running `upgrade head`
      twice does not fail).
