# Private task conversations — backend contract

Implemented locally on 18 October 2026. The Work screen still uses standalone
runs; conversation UI and live provider/storage verification are separate slices.

## API and ownership

All routes use the existing authenticated workspace, actor, role and same-origin
write checks. Input cannot grant roles, membership or publication authority.

| Route | Contract |
|---|---|
| POST /api/conversations | `{title, request_id}` creates a private task; title is 3–120 characters |
| GET /api/conversations | Lists the current actor's accessible conversation metadata |
| GET /api/conversations/{id} | Returns metadata and ordered turns, including pending/failed turns |
| POST /api/conversations/{id}/turns | `{query, budget, request_id, refresh_context?}` records one user/reply pair |

Request IDs contain 8–80 letters, digits, underscores or hyphens. Creation keys
are scoped to actor + role + workspace; turn keys to a conversation. Reusing a
key with different normalized input returns 409. The title, creator and role are
fixed. Conversation access requires the original actor and role, plus current
permission to every historical source. Loss of any source hides the entire
conversation, its outputs, linked events and usage, even after a context refresh.
Start a new task with permitted knowledge when an old task becomes unavailable.
This conservative policy avoids leaking restricted information through history.

The existing POST /api/tasks contract and historical standalone runs are retained.
Old workspaces gain a conversations collection lazily; no reset or migration is
required. Workspace snapshots include conversation metadata and successful runs;
conversation detail and permitted exports include all turn states.

## Stored turns and context

A turn records its ID, conversation ID, request ID, actor/role, query, status,
response, usage, timestamps, attempt count, stale flag and immutable manifest.
The manifest retains exact accepted bodies/revisions, serialized context payload,
retrieval budget/estimate, prior turn IDs, historical source IDs and history
budget/estimate. Prior turn IDs resolve to their preserved query, response and
source snapshot, so context use remains reconstructable per turn.

Follow-up retrieval uses the current query and earlier user goals in the active
working segment. The model receives that segment's exact user/reply pairs as
untrusted working notes, separately from accepted context. Access is checked
again immediately before invocation and before returning the result. Suggestions
in conversation never become accepted project decisions automatically.

Publishing a relevant source/dependency flags affected turns, including turns
that used it through history. If active history is stale, a new turn returns 409
until `refresh_context: true` is supplied. Refresh uses current accepted sources
and starts a new working segment without sending earlier messages to the model;
earlier persisted turns/manifests remain inspectable. Subsequent turns use only
the refreshed segment. A source changing during inference marks that result
stale. A failed turn's retry deliberately retains its original source snapshot;
refresh after successful retry or start a new conversation to use newer sources.

## Transactions and retries

1. Atomically validate ownership/input, reserve quota and persist a pending turn
   with an attempt ID and a 120-second lease.
2. Call the model outside the store transaction. Repeated pending requests return
   the same turn with HTTP 202; a new turn waits for the current turn to succeed.
3. Atomically save the reply, usage and attributed completion/failure event. A
   successful repeated request returns the stored turn without another model call.
4. A failed turn can be retried with its original request ID. An expired pending
   lease can be reclaimed with that key. Each attempt consumes quota; an older
   attempt cannot overwrite its replacement's result. Preserve known usage from
   failed or superseded calls. Unexpected provider errors use generic messages.

This guarantees one stored turn per request key, not exactly-once provider calls:
a process/network failure followed by lease recovery may call the model again.
There is no background worker or automatic retry loop. The future UI must retain
request IDs and poll/retry the same turn rather than generate a new key on error.

## Prototype limits and verification

- 20 conversations per workspace and 12 turns per conversation.
- Existing 200–16,000 budget range for accepted-source retrieval; mandatory
  overflow fails before any call. No required constraint is silently dropped.
- 16,000 UTF-8 bytes of serialized history, independently of retrieval budget.
  Overflow requires explicit refresh instead of silent truncation.
- 24,000 UTF-8 bytes per stored response. Empty/oversized responses fail visibly,
  with known provider usage retained. Offline replies remain labeled rehearsals.
- Existing shared allowance of 50 model attempts and six attempts/minute, plus
  750 KB total serialized workspace storage. These remain demo bounds, not a
  scalable transcript store or a model-specific tokenizer/window allocator.
- SQLite regression tests cover reopening, private history/exports, exact
  follow-ups, refresh, failure, idempotency, simultaneous requests, lease recovery,
  attempt fencing and preflight transaction rollback. Provider contracts are
  mocked; Firestore multi-instance and live Gemini evidence remain open.
