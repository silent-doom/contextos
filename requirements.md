# Requirements

Source of product intent: ContextOS_Complete_Project_Blueprint.md. Event constraints: original event notes and hackathon.md. The broader blueprint is a roadmap, not a claim of implemented scope.

| ID | MVP acceptance requirement | Verification |
|---|---|---|
| R01 | Persistent shared accepted knowledge with immutable revisions | store + API tests |
| R02 | Server-side document and workspace access checks, including derived views | negative access tests |
| R03 | Proposals do not change accepted context; designated reviewer publishes exact content | review tests |
| R04 | Stale-base and repeated publication detected; history preserved | concurrency/idempotency tests |
| R05 | Task retrieval uses only accepted permitted sources and all mandatory rules | retrieval tests |
| R06 | Explicit budget overflow rather than silently dropping mandatory context | budget tests |
| R07 | Every task stores exact source bodies, IDs and revisions actually supplied | manifest tests |
| R08 | Publishing a dependency marks affected tasks stale; rerun explicitly adopts latest sources | impact tests |
| R09 | Ingested notes create review candidates; model output cannot grant authority | ingestion tests |
| R10 | Gemini generates grounded persona output and extraction through server SDK | mocked contract + live cloud gate |
| R11 | Actual model usage is separate from estimated context sizes; no invented savings | telemetry tests |
| R12 | Responsive accessible overview, knowledge, tasks, reviews and insights | browser QA |
| R13 | Google Cloud deployment with durable storage and explicit authentication mode | deployment gate |
| R14 | Rollback proposes a historical body as a new revision | rollback test |
| R15 | Useful errors, input limits, no secrets in browser or Git | API tests + review |

## Boundaries

One workspace per demo browser; synthetic persona identities. Production API identities use verified Firebase tokens with administrator-provisioned workspace/role claims. No arbitrary persona selection outside demo mode. New context items require domain-owner review. The initial search is lexical with explicit dependency expansion, not semantic search. Token budgeting uses a disclosed byte-based upper-bound estimate and live provider usage when available. No claims of measured productivity gains.

## Deferred

Enterprise organizations and SSO, MCP, repository synchronization, embeddings, automatic splitting/merging, arbitrary policy administration, agent delegation, file uploads, distributed background workers, and end-to-end cost/quality benchmarking.

## R16 — Dedicated demo center

Show all five implemented personas and their responsibilities, and provide repeatable coverage of the implemented core use cases. Every scenario must use actual application rules on fresh synthetic state, report computed outcomes and inspectable evidence, and avoid changing the persisted workspace or invoking a live model. Provide persona/category filtering, run-all, and explicit hands-on links into the normal workspace. Clearly distinguish deferred cloud workflows and future product capabilities.

## Repository readiness

- Keep a local Git repository with README quickstart, .gitignore, contribution and security guidance, issue/PR templates and automated offline verification.
- Do not publish or configure a remote until the user resumes GitHub setup. License and visibility are owner decisions, documented in GITHUB_READY.md.

## Persona workflow and usability refinement

- Lead with a persona-specific next action; prioritize independent owned reviews and stale runs before a suggested task. Actions must keep existing authorization and review gates.
- Record meaningful workspace actions with actor, persona, timestamp and outcome. Filter activity derived from restricted sources before returning it.
- Reveal demo steps individually; retain Back/Next, checkpoint evidence and a step activity trail.
- Reduce introductory copy and show prominent CTAs; keep optional explanation expandable. Restore original styling per user request.

Design clarification (15 October): use the palette and typography from 4e1bd51 with the current shorter CTA-focused interface and persona workflows. This supersedes the original-style rollback requirement above.

Design clarification (18 October): replace the brown/beige palette with royal-blue navigation and accents, an off-white background, and white cards. Retain current typography, layout, persona workflows, and distinct success/warning/error indicators. This supersedes earlier palette instructions.

Collaboration verification (18 October): provide one repeatable API scenario for two distinct authenticated members sharing an accepted decision, independent review/audit, exact source revisions, stale warnings, fresh-session persistence and logout. Local mocks and explicit offline runs must remain distinct from live evidence; verifier output must exclude credentials and content. Cloud project selection/setup is deferred by the user.

Workspace simplification (18 October): Work, Knowledge and Inbox are primary destinations. Activity/usage and synthetic walkthroughs remain secondary, including mobile access. Preserve legacy routes, explicit independent publication and source snapshots. Inbox scopes review badges to independent owners and affected runs to the current actor, with a persona fallback for legacy runs. Drafts/budgets survive navigation and clear with protected session data. This supersedes the earlier overview next-action-card layout; persistent multi-turn chat remains separate work.

Overview restoration (18 October): restore Overview as the first navigation tab and default landing page alongside Work, Knowledge and Inbox. Show accessible project counts, recent activity and personal actions with direct inspection/review links. Mark changed required-source revisions Critical, without inventing overall project health or severity metadata. Surface independent reviews, pending proposal/base conflicts for authors or reviewers, stale personal runs and the latest visible failed model attempt. Refresh permitted state on entry/manual request; preserve protected-session cleanup and mobile access. This supersedes redirecting Overview to Work.

Shared-knowledge integration: preserve /knowledge and contextpages bookmarks, URL query strings and Back/Forward behavior alongside current workspace routes. Load and clear the page module through the controller lifecycle; late workspace/page responses and context-page 401s must preserve sign-out protections. Frontend CI must cover the real module integration and existing map/page suite.

Conversation backend (18 October): persist private actor/role-scoped task conversations with ordered turns, immutable accepted-source manifests and explicit working-history references. Retries reuse the same turn/request key and source snapshot; concurrent or expired attempts cannot overwrite newer results. Enforce current access on all historical sources, activity and exports. Context changes require explicit refresh to start a new working segment; retain prior turns. Bound history/output and share existing quotas. Keep standalone task API compatibility; chat UI and live provider/store verification remain separate.

## Person 3 workstream — 18 October

See PERSON3_DELIVERY.md for the proposed capability map and measurable acceptance criteria, P3-01 through P3-11. Real sign-in/session/logout, authoritative identity handoff, managed persistence, relationship UI, conversation UX, dedicated activity, readiness, CI promotion, secrets, monitoring and judge access are tracked separately. Preserve current governance/privacy and the selected royal-blue/off-white palette with existing typography. Provider selection is open: recommend Firebase/Firestore/Cloud Run to reuse existing adapters; Supabase Auth/Postgres on Cloud Run is an explicit alternative. No cloud resources are provisioned by this planning task.
