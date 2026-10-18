# Verification record

Verified locally on 14 October 2026 (IST), Python 3.14.6.

## Automated

```sh
.venv/bin/python -m pytest -q
node --check web/app.js
.venv/bin/python scripts/rehearsal.py
```

25 tests pass covering:

- Document visibility and filtering of restricted proposals, events, outputs and retrieval.
- Owner authorization, independent review, content hashes and duplicate decisions.
- Immutable history and rollback through a new reviewed revision.
- Stale-base rejection and actual concurrent SQLite publication (one winner).
- SQLite persistence, workspace isolation and rollback on storage-limit failure.
- Mandatory context retention, explicit budget overflow, exact serialized manifests.
- Transitive change impact and a revision changing during model inference.
- Firebase identity claims, denied demo-role switching, cross-workspace denial (verification SDK mocked).
- Gemini prompt/schema contract, reported usage and malformed output (provider mocked).
- Known token usage preserved when downstream validation fails; visible provider errors.
- HTTP validation, same-origin write checks, rate limits, assets and security headers.

Two upstream deprecation warnings remain: Starlette's httpx compatibility and google-genai's Python union alias. They do not fail the suite. No warning suppression is configured.

## Browser checks

Tested the running application using the Codex in-app browser at mobile width (~358 px) and desktop width (1440 px):

1. Overview loads real workspace counts and navigation.
2. Developer runs a payment task; inspector shows source bodies and v1 architecture.
3. Developer proposes a retry-limit change without publishing.
4. Architect reviews before/after text and publishes v2.
5. Previous run shows “Needs review”; rerun inspector shows architecture v2.
6. Stakeholder note becomes a pending candidate; Product Manager independently publishes it.
7. Insights shows dependency links, audit events, actual zero offline model usage, and disclosed estimates.
8. No browser console errors observed during this workflow.

Screenshot: `artifacts/contextos-desktop.jpg` (synthetic demo state, not a live-AI claim).

## Unverified / intentionally deferred

- Live Gemini, real Firebase credentials, Firestore transactions and multi-instance behavior.
- Linux container build (Docker unavailable locally).
- Cloud deployment, public access and load/abuse testing.
- Broad assistive-technology audit and multi-browser compatibility.
- Retrieval-quality and end-to-end productivity/cost benchmarks.

User explicitly deferred cloud setup until local review, and GitHub setup until later. These remain open gates, not completed work.

Round 4 follow-up: direct `.venv/bin/pytest -q` now also passes all 25 tests via pytest.ini. Root favicon is included in the HTTP asset check. Browser verified search filtering while focus remains on the input, and a manually authored Quality topic becomes a pending independent-review proposal.

Demo-center verification: 39 total tests pass, including each of the 12 scenarios, an API test proving scenario runs preserve workspace state and model usage, unknown-scenario rejection, and Firebase-mode denial. Browser verified run-all → 12/12, Security case filtering, displayed permission denials, and the hands-on link switching to Security context. These are local domain demonstrations, not live Google service verification.

GitHub preparation: candidate-file and README-link checks pass via `scripts/check_repo.py`; all workflow, issue-template and Dependabot YAML files parse. Ignore checks cover local env, SQLite, dependency directories, service-account files and workspace exports while retaining .env.example. These checks do not replace a content/history secret review before publishing. GitHub-hosted CI and its container build have not run.

15 October refinement: 42 automated tests pass. Added all-five-persona task/inspection attribution, independent owner recommendation scope, blocked-attempt persistence, and restricted activity/export checks. Browser verified the suggested Security task, source inspection, corresponding audit receipts, QA review CTA, and Demo Next/Back. Original light/green design restored; walkthrough checkpoints are computed rehearsal playback, not paused live model calls.

Theme restoration verification (15 October): 42 tests pass; JavaScript syntax passes. Browser checked at 320, 768, 1024 and 1440 widths, with overview CTA and Demo Next controls usable. No browser console errors observed. README screenshot refreshed. Review: CSS restored from 4e1bd51, latest action extensions retained, no business logic reverted, CSP narrowed to named Google font origins without unsafe-inline.

18 October identity slice: 50 Python tests pass, including session creation/expiry/revocation, recent authentication, trusted claims, CSRF/origin checks, secure/HttpOnly cookie flags, logout and Bearer precedence. Four Node auth contract tests prove direct provider password delivery, no token-persistence APIs, generic provider errors, missing-config refusal and CSRF logout. Browser verified sign-in configuration state and local Demo. Real provider sign-in/revocation remains unverified.

Selected-store preparation: five tests cover unknown backend rejection, empty real-account vs seeded demo initialization, data preservation, Cloud Run SQLite refusal, explicit Firestore project requirement and factory initializer. Total: 55 Python + 4 Node tests. Firestore rules/index JSON parse and verifier CLI help checked; actual transaction/emulator/live verification remains open.

Final identity/storage checkpoint: 56 Python tests + 4 Node auth contract tests pass. Added a regression showing that logout clears the browser session even when its audit write fails. Live provider/cloud checks remain pending.

18 October sign-in copy: browser DOM confirms product-only sign-in text, no provider/setup branding. Auth Node contract tests and JavaScript syntax checks pass. Cloud project access attempt using the prior account was denied; selected-account browser authorization is pending. No live sign-in/deployment was verified by that attempt.
