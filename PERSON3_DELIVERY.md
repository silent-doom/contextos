# Person 3 — UI, identity, persistence and reliable operation

Date: 18 October 2026 · Status: Firebase Auth + Firestore + Cloud Run selected by owner; implementation underway.

Primary question: **Can an authorized user sign in, find their next action, do governed work, inspect its sources, and return after a deployment without losing it?**

This document defines the next workstream. It does not claim these gaps are implemented or that cloud resources exist. Preserve the royal-blue/off-white palette selected on 18 October, the typography from 4e1bd51, and the current shorter CTA-led layout.

## Current evidence

- Implemented locally: dashboard with scoped next actions; searchable accepted topics; proposal editor; independent review/diffs/history; standalone task runs; source inspector; activity and evidence export; isolated step-by-step Demo.
- Firebase session-cookie exchange, email/password login/logout UI and token/claim checks are implemented with mocked tests. Real provider sign-in is not yet verified.
- SQLite is the working local store. Firestore adapter exists, uses atomic aggregate transactions, and has not been verified live. No Supabase adapter exists.
- Relationships appear as dependency buttons in Insights; no dedicated interactive relationship view exists.
- Private persisted conversation APIs now support exact per-turn sources/history, explicit refresh and safe retries. The Work UI still uses standalone runs; conversation UI remains P3-S08.
- CI is configured; hosted CI, container, cloud deployment, real auth, monitoring and restore evidence must be inspected or produced rather than assumed.
- Latest local verification: 85 Python tests and 11 Node contract tests pass on 18 October. Identity/UI, storage configuration, simplified navigation and conversation backend slices are implemented; cloud resources and live behavior are unverified.

## Capability map

Provider APIs and data contracts will be specified after this map is reviewed. Arrows point from consumer to dependency.

| Stable module ID | Person 3 responsibility | Depends on | Candidate feature IDs |
|---|---|---|---|
| identity | Login/logout screens, provider flow, session lifecycle, verified identity handoff | — | P3-01, P3-02 |
| persistence | Durable workspace access through existing store boundary, provisioning and restore evidence | identity for access tests | P3-03 |
| workspace-ui | Dashboard, context detail/proposal editor, relationships, review queue | identity; persistence | P3-04, P3-05, P3-06 |
| task-experience | Task conversation UI, per-turn inspection, activity exploration | workspace-ui; backend task contract | P3-07, P3-08 |
| operations | Hosting, delivery, secret references, health and monitoring | identity; persistence | P3-09, P3-10 |
| release-evidence | Repeatable demo, browser/accessibility verification, judge access and runbook | all above | P3-11 |

Build order: identity + chosen persistence path → workspace-ui → task-experience → operations → release-evidence. Existing standalone offline rehearsal remains usable between increments. Implement one tested vertical slice per commit; deployment has an additional live verification gate.

## Selected stack and alternatives

**Recommended first release: Firebase Authentication + Firestore + Cloud Run + Vertex AI.** This extends the existing code and avoids changing both identity and storage on the submission day. The supplied event notes require Google AI and hosting on Cloud Run/GCP/Firebase; a Supabase database alone would not satisfy the hosting requirement.

| Option | What we reuse | New work | Appropriate when |
|---|---|---|---|
| Firebase Auth + Firestore | Existing signed claims, Firestore store, Google SDK dependencies | Real login/session UX, project provisioning, live tests, monitoring | Fastest path to the current Google Cloud MVP |
| Supabase Auth + Postgres; app on Cloud Run | FastAPI/domain rules, UI and Google model adapter | Supabase verified identity mapping, transactional Postgres store, schema/migrations, pooling and policy verification | SQL and Supabase are explicit product priorities |
| Firebase Auth + Cloud SQL for PostgreSQL | Existing identity checks and Google hosting | SQL adapter, schema/migrations, IAM/connection/pool configuration | Relational database required with Google-managed operations |

Do not implement multiple new database paths at once. Owner selected Firebase Auth + Firestore + Cloud Run. Supabase/Postgres remains an evaluated alternative, not an active implementation path. SQLite stays the local demo/test backend.

For a Supabase MVP, keep privileged database credentials only in the server. The browser uses identity APIs; business writes still pass through FastAPI governance. A server key that bypasses RLS does not replace backend tenant/role checks. Initially preserve the bounded workspace aggregate and atomic mutation semantics; normalization is a later, explicitly designed migration. If using Data API RPC, publication must be one transactional compare-and-write operation, not separate GET/PATCH calls. If using direct PostgreSQL, require TLS, parameterized queries and transaction-safe connection pooling. Unknown STORE_BACKEND values must fail closed instead of silently selecting SQLite.

## Candidate features and acceptance criteria

### P3-01 — Sign in and sign out (P0)

- Entry screen provides chosen provider sign-in, progress, actionable failure and retry, and clearly separated synthetic demo access.
- Logout clears the app session and sensitive rendered data and returns to sign-in; browser Back cannot restore an authorized API session.
- Unprovisioned or disabled accounts receive an access-required screen; users cannot select their own role/workspace through login fields.
- Verify: provider adapter mocks; browser login/logout using test accounts on the selected provider; expired/revoked/invalid credentials rejected.

### P3-02 — Session and verified identity boundary (P0)

- Backend derives actor, workspace and role from verified provider identity plus trusted membership/claims; reject client overrides.
- Document chosen session strategy (server HttpOnly Secure SameSite cookie or provider SDK token refresh), expiry, renewal and revocation behavior before implementation.
- If cookies are selected, enforce CSRF/origin protection on session establishment and business writes. Logout behavior and revocation are tested for that strategy.
- No access/refresh tokens or service credentials in logs, browser URLs, source, screenshots or public config. Avoid hand-rolled token storage/refresh.
- Test same user across refresh, two tenants with identical context IDs, author self-review, tampered role, expiry and logout. Authenticated deployment denies demo impersonation routes.

### P3-03 — Managed database and durable workspace (P0)

- Choose one provider and apply versioned provisioning/schema configuration. Real workspace initialization is explicit; do not silently seed real users with synthetic checkout data.
- Preserve accepted revisions, proposals, runs/manifests, events, usage and trusted membership/identity references. Model calls remain outside retryable database transactions.
- Concurrent approvals have one winner; a stale base fails without overwriting content. Publication/history/audit commit atomically.
- Restart and two-instance tests show the same accepted revision. Export/restore in a separate staging workspace preserves revision/history counts; rollback never destroys production history.
- Keep current 30-context/750 KB aggregate limit disclosed until storage is deliberately decomposed. Set retention and cost controls for the selected provider; do not promise unlimited audit history.
- Supabase alternative additionally requires migration execution/rollback plan, restricted grants/RLS or server-only schema access, safe role mapping and pooled transaction tests.
- Verify: reusable store contract tests, selected-provider emulator/local database tests where available, then live staging durability/concurrency/restore evidence.

### P3-04 — Dashboard and context workspace (P0)

- Dashboard leads with a next action permitted for the signed-in user. No demo role switch in real-auth mode.
- Topic detail shows accepted version, owner, policy, sources and dependencies. Editor saves a proposal with exact base revision; accepted content is not overwritten directly.
- Preserve drafts across recoverable errors and warn before discarding them. Search/filter retains keyboard focus. Loading/empty/error states provide a CTA.
- Verify keyboard flow and desktop/mobile layouts; failed save and stale-base conflict preserve the draft.

### P3-05 — Dedicated relationship explorer (P1)

- Display only authorized nodes and edges from explicit dependencies, with selectable topic and inbound/outbound links.
- Provide a keyboard-operable list alternative to any graph. Clicking a topic opens its accepted detail and version.
- Show downstream impact from explicit links; do not suggest a semantic/inferred relationship is implemented. Restricted IDs, titles and hidden node counts must not leak.
- Verify restricted-node fixture and cycles; empty/deleted dependency handling; mobile and keyboard navigation.

### P3-06 — Reviews as a work queue (P0)

- Pending/my-review/history filters, clear author/owner handoff, exact before/after text and proposal hash inspection.
- Approve/reject only for an independent domain owner. Server rechecks authority, hash and base revision even if the UI CTA is stale.
- Publication returns a receipt and next action (inspect affected work or continue queue). Conflicts offer reload/reconcile while preserving proposed content.
- Verify unauthorized, self-review, changed-hash, concurrent-publication and stale-proposal cases.

### P3-07 — Persisted task chat (P1)

- User can create, reopen and continue a task conversation; each turn records user goal, response, actor and exact accepted-source manifest.
- Follow-up contract specifies whether/how prior messages reach the model, their budget, and access checks. Existing task endpoint remains backward-compatible.
- Each turn has pending/succeeded/failed state, retry without duplicate successful turns, and clear offline/live label. No false claims that implementation/tests executed.
- Recheck access to every included turn/source before showing or sending history; a former privileged role cannot retain restricted transcript access.
- If a source changes, preserve the old response and provide an explicit refresh action. Inspector is selected per turn.
- Verify reopen, follow-up context, revocation, restricted-history filtering, stale source and failed-model retries.

### P3-08 — Activity and source inspector (P0)

- Separate Activity destination with persona/actor, action, outcome and date filters. Every persisted business action has attributable scope; inspections and exports remain permission-filtered.
- Inspector shows selected turn/run, actual source text, accepted versions, required guardrails, budget/estimate and reported usage; expose exact payload without calling it a cryptographic seal.
- Keep critical outcome visible; optional evidence is expandable. Display last-100-events limitation until pagination/archive is implemented.
- Verify cross-role/cross-tenant export and activity privacy, empty history, failed/blocked events, and keyboard operation.

### P3-09 — Hosting and controlled delivery (P0)

- Build one immutable container artifact in CI; test that artifact, deploy to staging, verify health/auth/store behavior, then promote explicitly to production.
- Retain non-root runtime, least-privilege service identity and managed database. No ephemeral SQLite in cloud mode.
- Use short-lived CI federation (e.g. GitHub OIDC) rather than committed service-account keys. Restrict deploy identity to the selected repository/environment.
- Runtime secrets supplied by secret references; browser receives only explicitly allowlisted public identity config. Rotation requires no source changes.
- Previous revision rollback is rehearsed and does not roll back accepted data. Judge audience and synthetic-vs-real app exposure are explicit.
- Verify fresh Linux image build, staging smoke suite, redeploy durability, secret-free artifact and revision rollback.

### P3-10 — Health, logs and monitoring (P0)

- Separate liveness (process) from readiness (configured identity/storage available) with bounded checks and redacted public output.
- Structured request/action logs include request ID, route template, status and duration; redact tokens, prompts, source bodies and credential-bearing connection URLs.
- Proposed launch thresholds: external probe every minute, alert after three failed probes; alert on 5xx >5% over 5 minutes with >=20 requests; track p95 latency and provider failures separately. Owner confirms tuning during deployment.
- Track model usage and global abuse exposure; per-workspace limits alone do not stop session farming. Budget alerts are not hard spend caps.
- Verify injected database/model failures, visible user recovery, log redaction and one received test alert. Record alert recipient and runbook.

### P3-11 — Release evidence and usable access (P0)

- End-to-end demo: sign in as one provisioned persona → task → proposal → independent owner review → source change → stale warning → refreshed run → inspector/activity → logout.
- UI works at 320/768/1024/1440 widths, no horizontal clipping, visible keyboard focus and labeled forms/dialogs. Target WCAG AA contrast; verify rather than assume from colors.
- Proposed performance target: dashboard usable within 3 seconds of a successful workspace response on the stated test device; model latency measured separately. Publish measured evidence and device/network details.
- Judge link works from a fresh browser according to chosen audience, data survives redeploy, test alert reaches owner, rollback instructions are usable.
- Keep live identity/database/model checks separate from mocks. No claim of production readiness or improved productivity without evidence.

## Scope and ownership

Person 3 owns UI, provider integration, session transport, storage integration/configuration and operations. Existing domain governance/retrieval remain the authority. Coordinate new backend contracts (conversation turns, membership, relationship projection, readiness) with the domain owner rather than duplicating authorization in the UI. Data access checks must live on the server regardless of provider.

Do not expand into semantic retrieval, arbitrary organization administration, payment billing or automatic agent publication in this workstream.

## Decision inputs before live provisioning

1. Confirm the capability map/build order and choose Firebase/Firestore or Supabase/Postgres.
2. Supply target project identifier/region through normal environment configuration, and identify the operator with provisioning access; no secrets pasted into chat.
3. Choose login provider, initial trusted members/roles, staging vs real data, judge audience and alert recipient.
4. Confirm provisioning/deployment scope and budget before billable resources are created.

The earlier cloud deferral is not treated as permission to create billable resources. Code and local verification can be prepared once the map is reviewed; live evidence needs the selected environment.

## Source notes

- [Firestore server access uses IAM](https://firebase.google.com/docs/firestore/security/overview); client security rules do not automatically protect server SDK calls.
- [Firebase session cookies](https://firebase.google.com/docs/auth/admin/manage-cookies) support a server-cookie option; session creation and CSRF handling are explicit design work.
- [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security) and [secure server access](https://supabase.com/docs/guides/database/secure-data): privileged server credentials must stay off the client, and bypassing RLS requires authoritative server checks.
- [Supabase user data](https://supabase.com/docs/guides/auth/managing-user-data): application profiles/membership must be protected; signup data cannot grant its own privilege.
- Hosting requirement: supplied ai_builder_cup_challenges_and_themes.txt, mandatory prototype section. Supabase storage is an architectural option, not a substitute for the required Google-hosted application.
