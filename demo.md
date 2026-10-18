# Three-minute demo

## Preparation

1. Start the server using README instructions. Use a private browser window for a fresh sandbox; old workspaces remain intact. `scripts/new_sandbox.py` verifies fresh API-session creation without deleting data.
2. Run `.venv/bin/python scripts/rehearsal.py` for an isolated deterministic governance rehearsal.
3. For the final competition recording, configure and verify live Gemini plus durable Google Cloud hosting first. An offline rehearsal is not evidence of live AI.
4. Reconfirm the active portal's duration requirement. Current public themes page says three minutes; supplied portal notes say 3–4 minutes. Aim at 3:00 pending confirmation.

## Story and actions

| Time | Action | Point to communicate |
|---|---|---|
| 0:00–0:20 | Work, show the shared workflow | Separate agents lose accepted decisions during handoffs. ContextOS gives them governed project memory. |
| 0:20–0:45 | Add a stakeholder note as Developer; review it as PM | Gemini extracts a candidate; it becomes accepted only after human review. |
| 0:45–1:15 | Switch to Developer; ask “Implement payment retries without duplicate charges” | An agent receives existing accepted decisions without re-explanation. Inspect exact IDs and revisions. |
| 1:15–1:45 | Knowledge → Payment retry architecture → Propose change | Replace “3 times” with “2 times,” preserving all other text. Explain reduced maximum latency. The accepted version stays v1. |
| 1:45–2:10 | Switch to Architect; Inbox → Approve & publish | Independent owner approves exact content. Architecture is now v2 with a preserved history. |
| 2:10–2:35 | Inbox → Changed context; open old run in Work, inspect stale warning; rerun | The old manifest still records v1. The new run uses v2. Change impact is visible and attributable. |
| 2:35–3:00 | Activity & usage and Security/Developer visibility contrast | Show actual telemetry separately from estimates. Restricted knowledge and derived outputs are filtered. End on shared, accountable memory. |

## Suggested note

“Customers must receive a clear explanation when a card is declined. Do not automatically retry a declined card. Support should receive a correlation ID without payment credentials.”

## Evidence to retain

Export visible workspace JSON after the workflow. Record actual model usage and provider mode, source manifests, revision history and audit events. Do not claim measured time/cost savings from one rehearsal.

## Known boundaries

Demo personas are deliberately switchable synthetic identities. Production API auth is separate. Documents are rendered as safe plain text. Search is lexical. Ingestion creates one candidate; automatic topic matching and merge assistance are not implemented. Full-context and selected-context numbers are byte-based estimates, not actual token counts.

## Interactive Demo tab

Open `http://127.0.0.1:8000/#demo` or select Walkthroughs in secondary navigation (More on mobile). Choose Product Manager, Architect, Developer, QA or Security to filter relevant cases, or show all personas. Run one case or all twelve. Each produces computed step results and an expandable evidence record. Cases use isolated synthetic state and consume no model quota.

The cases cover shared-intent handoffs, note extraction rehearsal, manual proposals, review permissions, changed-source impact, restricted retrieval and derived views, stale competing proposals, rollback, budget overflow, rejection, audit provenance and usage transparency. “Try in workspace” switches to the appropriate demo persona and opens the relevant screen with a prepared task prompt when applicable. This mode uses your normal persistent demo workspace; the isolated scenario runner does not.

Live AI/cloud capabilities and deferred roadmap items are separately labeled. Use the interactive tab for local walkthroughs; live Gemini verification is still necessary for the final competition submission.

Guided Demo: choose a case → Start walkthrough → Next step → Finish walkthrough. Back revisits captured checkpoints. Expand Step activity for the revealed persona actions, or Inspect knowledge for source revisions at that step. Work offers a role-specific task suggestion; Inbox shows independent owned reviews and affected personal runs. Task submission and publication remain explicit actions.
