# Local Evidence Review Verification

Date: 2026-09-10. One-time change verified locally before coordinated publication. Not a public deployment.

## Scope

Read-only freshness/integrity/source-revision warnings and a reproducible human-review JSON packet. Existing cream/green editorial UI, assessment gates and role controls are retained. Original evidence, content and reviews are not rewritten. No new tables or migrations.

## Results

- Baseline: 74 existing Python tests passed before edits.
- Updated core: 83 Python cases passed (`.venv/bin/python -m pytest -q`). Two upstream FastAPI/Starlette deprecation warnings remain non-failing.
- Browser: 10 scenarios passed with installed Chrome, temporary synthetic database, port 5313. New review flows tested at 1440 and 390 pixels; wider existing layout coverage includes 320, 768 and 1024 pixels.
- Production: `npm run build` passed TypeScript and Vite.
- New core coverage: exact 30-day boundary, one-second-before boundary, future/unknown/invalid dates, text/hash mismatch, exact-URL revision comparison, unchanged assessments, reproducible checksum, invalid as-of time, original unresolved verdicts, decision changes, deleted-content purge and unauthenticated/reviewer/private-demo export boundaries.
- New browser coverage: visible stale/changed-source warnings, unresolved result, actual JSON download, source-revision navigation, superseded notice, reload persistence, automated WCAG A/AA and horizontal-overflow checks.

Run UI tests with `PLAYWRIGHT_CHANNEL=chrome VERIFIER_UI_TEST_PORT=5313 VERIFIER_TEST_PYTHON=.venv/bin/python npm run test:ui` after building. All test fixtures remain separate from ordinary workspace data. Existing social-adapter browser scenarios use a local stub; no real account, session, messages, live source or model was contacted.

## Screenshots

- `docs/freshness-1440.png`
- `docs/freshness-390.png`

These are actual browser captures, not generated mockups. The old timestamps, changed source and unresolved assessment are synthetic workflow fixtures, not evidence of factual accuracy.

## Limits

Thirty days is a transparent reminder threshold, not a validated relevance rule. Comparison is only between exact URLs in the nearest earlier and latest later saved assessments of one content item. It cannot detect unseen source edits. Hashes represent extracted text and are not source authentication. A fixed as-of time reproduces warning evaluation only against unchanged stored state; preserve the downloaded packet for an offline snapshot. Exported copies are unencrypted and cannot be recalled. No live fact-check, model-quality benchmark, public deployment, external activity or automatic enforcement was performed.

Suggested portfolio description: Human-reviewed investigations with captured source provenance, local freshness/revision warnings and reproducible review exports, preserving abstention and role boundaries.

## Changed Paths

Implementation: `verifier/review_export.py`, `verifier/app.py`, `frontend/src/pages/investigations.tsx`, `frontend/src/types.ts`, `frontend/src/styles.css`.

Tests/configuration: `tests/test_review_export.py`, `frontend/tests/freshness.spec.ts`, `scripts/ui_test_server.py`, `playwright.config.ts`.

Documentation: `README.md`, this file, and both `docs/freshness-*.png` screenshots.
