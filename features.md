# Feature ledger

Update status with each feature commit. Planned does not mean implemented.

| ID | Feature | Status |
|---|---|---|
| F01 | Project plan, requirements, judging alignment, resumable handoff | Complete |
| F02 | Durable sandbox, seeded personas, accepted context and protected views | Implemented and locally tested |
| F03 | Propose, diff, independent review, conflict checks, rollback, audit | Implemented and locally tested |
| F04 | Permission-filtered retrieval, mandatory constraints, bounded source manifests | Implemented and locally tested |
| F05 | Gemini adapter, offline rehearsal, note extraction, persona tasks | Local tested; live AI gate open |
| F06 | Transitive dependency alerts, explicit rerun, usage insights | API and browser workflow verified |
| F07 | Responsive five-view workspace | Implemented; core browser workflow verified |
| F08 | Regression suite and deployment package | Local tests pass; cloud image not yet built |
| F09 | Live Google Cloud deployment and model verification | Deferred by user pending local review |
| F10 | Public GitHub, prescribed pitch PDF and demo video | Deferred until app verified |

Post-MVP backlog: see blueprint section 3; prioritize based on observed demo friction and judging evidence.

Round 4 refinement: manual topic authoring is implemented under F03/F07; search preserves the active input during filtering, dialogs support safe backdrop dismissal, and direct pytest invocation works.

| ID | Feature | Status |
|---|---|---|
| F11 | Dedicated Demo tab: five persona perspectives, 12 executable scenarios, evidence, run-all and hands-on entry points | Implemented; 12/12 browser scenarios passed |

Demo coverage: cross-role handoff; note candidates; manual authoring; owner authorization and exact review hashes; stale work and refresh; restricted sources/derived views; competing revisions; rollback; mandatory budget constraints; rejection; audit provenance; truthful usage. Live cloud flows and advanced roadmap are visibly separate.

| ID | Feature | Status |
|---|---|---|
| F12 | GitHub-ready documentation, ignore rules, contribution/security guidance, templates, CI and dependency updates | Prepared locally; hosted CI and publication pending |

| ID | Feature | Status |
|---|---|---|
| F13 | Next-action guidance for all five personas, direct CTAs and attributed action ledger | Implemented locally; ownership and privacy tests pass |

F11 now reveals a single checkpoint at a time with Next/Back, actor attribution and an expandable activity record. Original light/green theme restored per user direction.

Visual refinement: restored palette/typography from 4e1bd51 per clarified user direction; current F11/F13 workflows remain intact.

18 October visual refinement: user selected royal-blue navigation/buttons/accents with an off-white canvas and white cards. Palette and favicon updated; existing typography and F11/F13 workflows retained. This supersedes earlier palette directions.

## Person 3 delivery backlog — 18 October 2026

Full candidate features, priorities and verification: [PERSON3_DELIVERY.md](PERSON3_DELIVERY.md). These are proposed scope, not implemented features.

| ID | Capability | Priority | Current gap |
|---|---|---|---|
| P3-01 | Provider login/logout | P0 | Developer token bridge only |
| P3-02 | Session lifecycle and verified identity handoff | P0 | Backend token checks exist; normal session UX missing |
| P3-03 | Managed database and durable workspace | P0 | SQLite works; Firestore adapter unverified; Supabase proposed alternative |
| P3-04 | Dashboard/context/editor completion | P0 | Existing screens need authenticated states and recovery checks |
| P3-05 | Dedicated relationship explorer | P1 | Dependency buttons only |
| P3-06 | Review queue completion | P0 | Existing governance; add filters and reconciliation UX |
| P3-07 | Persisted task chat | P1 | Backend complete locally; Work chat UI remains open |
| P3-08 | Activity destination and per-turn inspector | P0 | Existing audit/inspector; add filters and conversation selection |
| P3-09 | Staging hosting/CI promotion/secrets/rollback | P0 | Configured local package; live evidence open |
| P3-10 | Readiness/logging/monitoring | P0 | Basic health and domain audit; operational controls missing |
| P3-11 | Release/judge-access evidence | P0 | Real sign-in, store and deployment flow unverified |

P0 = launch-critical. P1 = complete Person 3 scope after the critical path; not silently marked done if deferred.

P3-01/02 backend slice: session exchange/config/logout and verified cookie identity implemented with mocked Firebase tests. UI sign-in and live provider verification remain open. Chosen stack: Firebase Auth + Firestore + Cloud Run.

P3-01/02 UI slice: normal email/password login/logout, session recovery, hidden persona switching and protected-buffer cleanup implemented. 50 Python + 4 Node tests pass; live provider-account verification remains open.

P3-03 configuration slice: authenticated workspaces start empty; Firestore selection validates project/config, Cloud Run refuses SQLite. Firestore rules/index config and explicit concurrency verification script prepared. Five new tests pass; no live Firestore durability/restore claim.

P3 release-verification slice: `scripts/verify_collaboration.py` exercises two independent Firebase session exchanges, shared decisions, owner review, publication audit, immutable v1/v2 task snapshots, stale warnings, fresh-session history and logout through the API. Ten local regression cases use mocked Firebase and offline AI. Live staging execution and cloud setup remain pending.

P3 workspace slice: Work/Knowledge/Inbox replace six primary navigation entries. Work has one task form, advanced budget controls, draft recovery and original source revisions. Inbox includes scoped attention, affected runs and Pending/My review/History filters; Activity & usage and Walkthroughs remain secondary. Legacy links/demo entry points resolve to current destinations. Seven Node controller regressions pass, including late-response cleanup; visual browser verification remains pending. Standalone runs remain distinct from future multi-turn conversations.

P3-S07 conversation backend: private saved conversations and follow-up turns now
have exact manifests/history references, pending/succeeded/failed states,
idempotent retries with attempt fencing, explicit stale-context refresh and
permission-filtered activity/exports. Seventeen conversation tests and two model
contract tests added; total 85 Python + 11 Node tests. Existing task API remains
compatible. Work still uses standalone runs; P3-S08 chat UI and live checks remain
open. See design/specs/conversations.md for bounds and recovery behavior.

Overview restoration: Overview is again the first tab and default landing page,
alongside Work/Knowledge/Inbox. Accessible project counts, recent activity and
scoped personal actions show changed required constraints as Critical, independent
reviews, proposal/base conflicts and affected work, with source/review links and
refresh. No backend or policy changes. 85 Python + 16 Node tests pass; new visual
browser QA remains unavailable. This supersedes the Overview-to-Work redirect.

Shared-knowledge merge repair: /knowledge and its page/map lifecycle now coexist
with Overview/Work/Inbox, secondary tools, legacy routes and protected refresh
cleanup. The controller fixture loads real modules and models location/history.
Six new integration checks plus the existing map/page suite bring local totals
to 85 Python + 36 Node. CI includes that suite; hosted verification is pending.

## Live deployment evidence — 18 October

Team sign-in, role/workspace claims, session cookies, Firestore persistence, independent review and live Vertex AI are verified on Cloud Run. A separate synthetic demo is authorized for judge exploration and recording; it does not make live model calls. Product remains a hackathon MVP. Pitch and narrated video are being prepared under deliverables/.

Submission media delivered: three-minute narrated/captioned MP4 with title cards, five personas across representative workflows and all twelve cases verified; 14-slide editable landscape PPTX and matching PDF cover problem, differentiation, workflow, architecture, SWOT, limits and roadmap. Dedicated judge member login and synthetic shared workspace verified with live AI extraction; credentials remain private.

- Reviewed d01509d: local Knowledge project registry persists across sessions/restarts, with immutable Markdown, atomic registry replacement, missing-metadata recovery notices and no automatic sample seeding. Cloud Knowledge stays workspace-scoped in Firestore.
- Demo delivery refresh: matching branded opening/closing cards, five-role shared-context diagram, judge CTAs and hosted links; original three-minute narrated walkthrough preserved.
