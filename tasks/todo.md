# Person 3 task backlog

Selected stack: Firebase Auth + Firestore + Cloud Run. Provider contract: design/specs/identity.md. Acceptance criteria are in PERSON3_DELIVERY.md.

- [x] P3-S00: Review module map and choose persistence/auth stack. Verify: owner decision recorded.
- [x] P3-S01: Specify provider config + identity/session contracts. Verify: trusted membership and logout/expiry cases enumerated; no client role authority.
- [ ] P3-S02: Login/logout code and mocked checks complete; live account/browser verification pending. Verify: mock rejection suite + provider test-account browser flow (P3-01/02).
- [ ] P3-S03: Fail-closed config and clean initialization complete; live Firestore contract/concurrency run pending. Verify: transaction rollback and one-winner concurrency (P3-03).
- [ ] P3-S04: Integrate/provision staging store. Verify: redeploy, two-instance visibility, separate-workspace restore; no real data migration without a plan.
- [ ] P3-S05: Finish context/editor and review recovery UX. Verify: draft preservation and owner CTA scope (P3-04/06).
- [ ] P3-S06: Add dedicated relationship screen with accessible list. Verify: restricted-node and keyboard fixtures (P3-05).
- [x] P3-S07: Implement private conversation turn API/storage. Verified locally: per-turn manifests/history, idempotent and concurrent retries, stale refresh and restricted-history filtering (P3-07). Contract: design/specs/conversations.md; live provider/store checks stay open.
- [ ] P3-S08: Build task chat UI and per-turn inspector. Verify: reopen/follow-up/stale refresh, pending/error/retry browser flow.
- [ ] P3-S09: Separate activity view/filters. Verify: actor/outcome/date filtering and export privacy (P3-08).
- [ ] P3-S10: Add readiness and redacted request telemetry. Verify: injected outages and credential/body redaction (P3-10).
- [ ] P3-S11: Configure staging CI deployment + secret references. Verify: immutable artifact, federation trust and revision rollback (P3-09).
- [ ] P3-S12: Configure probe/alerts/global abuse limits. Verify: test alert received; budget policy and audience recorded.
- [ ] P3-S13: Capture live multi-persona release evidence. Verify: full P3-11 flow and measured browser/device conditions.

- [x] P3-V01: Add a reusable authenticated two-user API verifier with independent local sessions, mocked Firebase regression coverage and redacted evidence. Live staging execution remains pending; cloud project setup is deferred at the user's request.
- [x] P3-U01: Simplify primary navigation to Work/Knowledge/Inbox; keep secondary tools and legacy links, exact run sources, proposal filters, attention scoping and draft recovery. Seven Node controller tests added, including late-response cleanup; new visual browser QA remains pending. Conversation backend is P3-S07; chat UI remains P3-S08.
- [x] P3-U02: Restore Overview as first/default tab at the user's request. Add permitted project counts/activity and evidence-based personal priorities, original-run/review links, refresh and protected cleanup. 85 Python + 16 Node tests pass; connected-browser visual QA remains pending. Supersedes U01's three-tab navigation.
- [x] P3-U03: Repair shared-knowledge merge integration on ankush-changes: real module fixtures, current view dispatch/navigation, /knowledge/history compatibility and protected cleanup. 85 Python + 36 Node checks pass locally; hosted CI on the fix remains pending.

Split each implementation task into changes of roughly five source files or fewer, plus required project logs. Test and commit each working slice. A provider-specific task list replaces this proposal only after map review; no tests are skipped to meet a deadline.
