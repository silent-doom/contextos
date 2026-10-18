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

## Person 3 workstream — 18 October

See PERSON3_DELIVERY.md for the proposed capability map and measurable acceptance criteria, P3-01 through P3-11. Real sign-in/session/logout, authoritative identity handoff, managed persistence, relationship UI, conversation UX, dedicated activity, readiness, CI promotion, secrets, monitoring and judge access are tracked separately. Preserve current governance/privacy and the selected 4e1bd51 theme. Provider selection is open: recommend Firebase/Firestore/Cloud Run to reuse existing adapters; Supabase Auth/Postgres on Cloud Run is an explicit alternative. No cloud resources are provisioned by this planning task.

Login presentation: user-facing copy must use ContextOS product terminology and actionable recovery messages, without provider names, public API-key instructions or infrastructure setup jargon. Keep exact Firebase/Firestore setup in operator docs and preserve truthful availability states. Selected cloud project is contextos-512006 under choudhary.faizan2002@gmail.com.
