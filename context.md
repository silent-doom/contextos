# ContextOS change log

Append an entry in every implementation commit: change, reason, verification, limitations. Git is the exact file-level history; this is the human-readable decision log. Dates use Asia/Kolkata.

## 2026-10-14 — F01: project foundation

- Read both supplied source documents and existing ignore configuration. No application code or commits existed. The blueprint references SHARED_AGENT_CONTEXT_PLATFORM.md, which is not present.
- Selected the payment-retry cross-role workflow and Challenge 5.
- Added README, requirements, feature ledger, architecture, hackathon checklist and handoff.
- Chose FastAPI plus a buildless web UI to reduce build/deployment complexity. SQLite is the local store; Firestore adapter is the cloud path. Gemini via Google Gen AI SDK.
- Local Git author explicitly requested: Faizan Choudhary <choudharyfaizan15@gmail.com>. Remote GitHub setup deferred at user's request.
- Verified official themes page for broad mandates and scoring; portal-specific constraints remain sourced from supplied notes.
- No implementation or cloud readiness claimed at this stage.

## 2026-10-14 — F02–F04: governed memory core

- Added synthetic checkout contexts and personas; restricted findings are filtered before retrieval and from proposal/activity views.
- Added immutable reviewed publication with independent owner checks, content hashes, stale-base conflicts, new-revision rollback semantics and attributable audit events.
- Added atomic SQLite and bounded Firestore workspace stores; Cloud Run refuses ephemeral SQLite.
- Added deterministic mandatory-context retrieval, lexical ranking, dependency closure, exact serialized manifests and explicit budget overflow.
- Added core regression tests for permissions, review, concurrency, persistence, isolation, rollback and change impact.
- Deliberate limits: 30 contexts and 750 KB per transactional workspace; a byte-based estimate, not actual tokenization; Firestore needs live verification.
- Validation: 8 domain tests passed. Dependency versions captured in requirements.txt.
- User added a peer-review workflow: read forthcoming gemini.md and write reasoned responses to chatgpt.md while preserving the original product scope. File not present at first check.

## 2026-10-14 — F05–F06: API and model workflows

- Added validated FastAPI routes, opaque demo sessions, server-stored personas and Firebase-verified API identity mode.
- Added Gemini/Vertex SDK adapter for structured extraction and grounded persona tasks. Offline mode is an explicit deterministic rehearsal; live failures do not fall back silently.
- Added persistent usage reservations, failed-call accounting, workspace rate limits, exact task manifests, stale-during-inference detection, and filtered export.
- Added same-origin write checks, response security headers and request bounds.
- Fixed an integration-test finding: new demo sessions now persist even when their first API operation returns an error.
- Validation: 14 domain/API tests passing. Two upstream dependency deprecation warnings; live Google services untested without configuration.

## 2026-10-14 — F07–F08: working workspace and deployment preparation

- Built responsive Overview, Shared Knowledge, Agent Workspace, Change Reviews and Context Insights with safe text rendering, keyboard controls, mobile navigation and a source inspector.
- Connected ingestion, proposals, independent approval/rejection, revision history, rollback proposals, search/filtering, reruns, persona switching and visible-evidence export to the API.
- Added Dockerfile, .dockerignore, .env.example, deployment guide, three-minute demo script and non-destructive rehearsal helpers. Docker is not installed locally, so image build remains unverified.
- Read Gemini Round 3 review and recorded all ten dispositions in chatgpt.md; fixed dynamic project labels, cutoff clarity and test explanation. Did not alter gemini.md.
- Browser verification at mobile width: developer task → exact v1 manifest → architecture proposal → independent architect approval → old run marked stale → rerun manifest includes v2. Local preview is http://127.0.0.1:8000.
- Local validation: JavaScript syntax passes, isolated rehearsal passes, 14 Python tests pass. Gemini/Firestore/Firebase live verification still requires project setup.

## 2026-10-14 — correctness hardening and local review handoff

- Expanded verification to 25 tests, including actual simultaneous SQLite publication, Firebase-claim isolation with mocked verification, Gemini schema/prompt contracts, storage rollback and stale-during-inference behavior.
- Fixed known provider usage being lost when extraction validation or subsequent persistence fails. Insights counts available usage even for failed processing; unknown usage is not represented as measured savings.
- Preserved new-item proposal hashes by recording published_context_id separately from the original candidate. Offline note titles derive from note text, avoiding a fixed-title collision on repeated imports.
- Expanded CSS formatting for maintainability and clarified the task persona wording.
- Browser-verified desktop layout, ingestion/review and insights after the mobile governed-change workflow; no console errors observed. Saved a synthetic demo screenshot and TESTING.md.
- User explicitly deferred cloud setup until they approve the local solution. GitHub remains deferred. No cloud services or remote repositories were configured.
- Rechecked gemini.md after UI verification and hardening; latest observed review remains Round 3. Responses are recorded in chatgpt.md.

## 2026-10-14 — Gemini Round 4 follow-up

- Reproduced direct pytest collection errors; fixed import discovery with pytest.ini. All 25 tests now pass through the direct entry point.
- Changed knowledge search/filter updates to replace only result cards/count, retaining input focus and respecting IME composition.
- Added manual topic proposal mode using the existing independent-review pipeline; no AI call required. Browser verified PM → pending QA review.
- Added safe backdrop dismissal (protects edited drafts and in-flight work), plus root favicon route and HTTP regression coverage.
- Recorded factual corrections about Python 3.14 stability, single-stage Dockerfile, current test count and unverified cloud claims in chatgpt.md. No infrastructure changes.

## 2026-10-14 — F11: dedicated interactive Demo tab

- User requested a proper demo tab showing personas and cases. Added a sixth navigation view with five persona cards, category filters, 12 runnable cases, per-step computed checks, expandable evidence and run-all progress.
- Added backend/demo.py using the same domain logic against fresh synthetic in-memory state. Explicit offline adapter avoids model calls even when live AI is configured; endpoints reject Firebase mode.
- Added hands-on entry points that switch the demo persona, prepare a task prompt and open the relevant workspace view. Normal workspace actions retain their existing review rules.
- Added scenario regression tests and API checks proving that all cases pass without altering the persisted workspace or usage ledger. 39 tests pass.
- Browser verified 12/12 scenarios, Security filtering, permission results, and hands-on navigation to restricted Security context. Local UI clearly separates implemented behavior, deferred cloud setup and roadmap.
- Read Gemini Round 6; no new defects, earlier changes verified. Saved Round 4 fixes in commit 17d74ed before starting this feature. Cloud/GitHub remain deferred.

## 2026-10-14 — GitHub preparation

- Reworked README with local quickstart, screenshots, demo entry point, architecture, verification and explicit cloud limitations.
- Added contribution/security guidance, GitHub readiness checklist, issue and PR templates, EditorConfig and Git attributes. Expanded ignore rules for runtime artifacts, keys, local cloud auth and workspace exports.
- Added GitHub Actions for offline tests, JavaScript validation, rehearsal, repository hygiene and a container build without publishing; added weekly Dependabot updates. Hosted CI and container build remain unverified.
- Added scripts/check_repo.py to check candidate Git paths, required documentation and README links. It is explicitly not a content/history secret scanner.
- No remote, push, deployment or license grant created. Owner chooses repository visibility and license before publication. Gemini Round 6 file unchanged at this milestone.

## 2026-10-15 — Persona actions and a shorter UI

- Followed the user's revert direction: restored the original light/green CSS and system typography while retaining walkthrough controls. Removed external font dependencies and restored self-only CSP styles. Reference prototypes remain untouched.
- Replaced the overview hero/explanatory panels with a permission-scoped next-action card and direct CTAs. Added role-specific task goals and review/stale-run priority; suggestions never auto-publish or impersonate another role.
- Collapsed completed review diffs and optional demo persona, knowledge, and scope details. Retained one-step Next/Back walkthroughs with a revealed-step activity log and next persona hint.
- Added actor/role/outcome/source visibility to audit events. Log tasks, extraction, assembly, inspection, exports, switches and domain-level failures in addition to existing governance actions. Validation/auth failures and simple navigation are not workspace action events.
- Added tests for all five personas, owner-scoped recommendations, blocked attempts and restricted audit visibility. Updated README workflow, action matrix, logging scope and screenshot.
- Read Gemini Round 8; its theme adoption is superseded by the user's explicit revert request.

## 2026-10-15 — GitHub push and persona capitalization

- User authorized pushing to https://github.com/silent-doom/contextos. Existing origin matches that repository.
- Preserved canonical persona capitalization in overview headings and review instructions, including “QA engineer”.
- Rechecked Gemini Round 9; style disposition remains unchanged per human direction.

## 2026-10-15 — Restore the chosen heritage theme

User clarified that palette/idea from 4e1bd51 should be restored. Restored that stylesheet and font families, preserving the current action-first extension rules with matching theme tokens. Retained all current JS flows, QA capitalization, persona suggestions and activity logging. CSP permits only the named Google stylesheet/font origins; no inline-style relaxation.

## 2026-10-18 — Person 3 scope and managed data plan

- Audited existing UI, identity checks, store adapters, CI/deployment docs and latest Gemini audit. Distinguished working offline flows from missing live auth/session/conversation/operations evidence.
- Created PERSON3_DELIVERY.md: six-module capability map, eleven candidate features, P0/P1 acceptance criteria, security/ownership boundaries, store comparison and live verification gates. Added tasks/plan.md and tasks/todo.md.
- Recommended Firebase Auth + Firestore + Cloud Run based on existing adapters and supplied event requirements; requested owner choice versus Supabase Auth/Postgres on Cloud Run. Choice remains open. No provider credentials requested in chat.
- Used spec/documentation workflows; map is proposed and needs owner review before provider-specific contracts/implementation. No application behavior, cloud resources or database contents changed.

## 2026-10-18 — P3 identity backend slice

Owner selected Firebase Auth + Firestore + Cloud Run. Added identity contract and Firebase session endpoints with recent-auth checks, trusted claims, HttpOnly eight-hour cookies, CSRF nonce binding and idempotent browser logout. Existing verified Bearer API clients remain supported; invalid explicit Bearer cannot fall back to a cookie. Added rejection/expiry/cookie/privacy tests before implementation. Sign-out clears its browser cookie even if activity storage is unavailable. No live project or database provisioned.

## 2026-10-18 — P3 sign-in UI slice

Replaced the developer token-entry bridge with an email/password sign-in screen, protected-cookie exchange and sign-out. Firebase mode hides demo persona selection. Logout/401/page-cache restoration clears protected content, dialogs and drafts. Added web/auth.js with no persisted credentials, four Node contract tests and CI coverage. Browser verified Firebase missing-config entry screen and demo-mode regression; no real login claimed.

## 2026-10-18 — Selected persistence configuration slice

Added clean authenticated-workspace initialization without synthetic knowledge, preserved existing data, made unknown backend/missing Firestore project settings fail explicitly, and retained the Cloud Run SQLite guard. Added five config/init tests. Prepared Firestore client-deny rules, payload index exclusions and a separate live/emulator verification script; only its CLI help was exercised, no cloud writes occurred. 55 Python + 4 Node tests pass.

## 2026-10-18 — Selected cloud project and professional sign-in copy

Owner selected contextos-512006 and corrected the Google identity to choudhary.faizan2002@gmail.com. Initial lookup using the previously active account returned permission denied. Started the normal gcloud browser authorization for the selected account; user completion is pending. Removed provider branding/setup jargon from rendered sign-in and auth errors, preserving explicit temporary-unavailable/retry states. Technical provider details remain in operator docs.
