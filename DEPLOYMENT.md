# Deployment and live integration

## Current verification boundary

The application runs locally with SQLite and explicit offline rehearsal. Gemini, Firebase, and Firestore adapters exist but require live project configuration and verification. No cloud deployment or live Google AI result is claimed. GitHub is configured at silent-doom/contextos. Selected stack: Firebase Auth + Firestore + Cloud Run.

## Selected target

- Project: `contextos-512006`.
- Operator account: `choudhary.faizan2002@gmail.com` (selected by owner).
- CLI sign-in initiated using the normal browser flow. Initial lookup from the other locally active account was denied; correct-account access must be rechecked after authorization completes.
- No APIs, billing, IAM grants, database, public exposure or deployment changed during this access check.

For an explicit target check after signing in:

```sh
gcloud projects describe contextos-512006 --account choudhary.faizan2002@gmail.com
gcloud services list --enabled --project contextos-512006 --account choudhary.faizan2002@gmail.com
gcloud firestore databases list --project contextos-512006 --account choudhary.faizan2002@gmail.com
```

Select the database location only after inspecting existing resources; existing Firestore location is not changed casually. Default CLI settings are not a substitute for passing the selected project/account explicitly.

## Local configuration

Python 3.14 is used for development and the container. Install `requirements.txt`. Configure environment variables explicitly in your shell (the app does not auto-load `.env`). `.env.example` documents options and contains no secrets.

```sh
export AUTH_MODE=demo
export AI_MODE=offline
export STORE_BACKEND=sqlite
.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

For live Vertex AI, authenticate with Application Default Credentials through your normal Google Cloud flow and configure:

```sh
export AI_MODE=vertex
export GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
export GOOGLE_CLOUD_LOCATION=global
export GEMINI_MODEL=gemini-2.5-flash
```

Model name is configurable; verify availability and access in your selected project before recording. The model default is a starting configuration, not a guarantee of regional availability. Alternatively `AI_MODE=gemini` accepts a server-only `GEMINI_API_KEY` from Google AI Studio. Never paste secrets into source or review files.

## Google Cloud Run

Prerequisites: a user-selected billing-enabled Google Cloud project, Firestore Native mode database, Artifact Registry/Cloud Build, Cloud Run, and Vertex AI APIs. Runtime service account needs Vertex AI User and Firestore data access (`roles/aiplatform.user` and `roles/datastore.user`). Grant only to the dedicated service account. No service-account key file is required on Cloud Run; use its attached identity.

The Dockerfile listens on `$PORT` and runs as a non-root user. Cloud Run startup refuses SQLite because its filesystem is ephemeral. Configure:

```text
AUTH_MODE=firebase
FIREBASE_WEB_API_KEY=<public Firebase web key>
AI_MODE=vertex
STORE_BACKEND=firestore
GOOGLE_CLOUD_PROJECT=<selected project>
GOOGLE_CLOUD_LOCATION=global
GEMINI_MODEL=<verified model>
```

Example deployment after the project, service account and exposure policy are chosen:

```sh
gcloud run deploy contextos \
  --source . \
  --project YOUR_PROJECT_ID \
  --region asia-south1 \
  --service-account contextos-runtime@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars AUTH_MODE=firebase,AI_MODE=vertex,STORE_BACKEND=firestore,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL=gemini-2.5-flash \
  --memory 512Mi --cpu 1 --max-instances 2 --timeout 120 \
  --no-allow-unauthenticated
```

This example starts private. Decide explicitly how judges will access the deployment. A public synthetic demo exposes live-model usage to visitors; per-workspace call limits are not a global cost-control mechanism and creating new sessions can bypass them. Before public launch add an access gate or service-level quota/budget controls, and confirm the audience. Do not put real confidential data into demo mode.

Firestore stores each bounded workspace as one transactionally updated document, capped at 750 KB, with 30 contexts and 50 model calls. It preserves revisions/audits rather than silently evicting them. This suits the small demo; larger adoption requires collection-level decomposition and archival. Browser-session workspaces persist until explicitly cleaned up by an operator; configure retention before public operation.

## Firebase authentication mode

Set `AUTH_MODE=firebase` and provision accounts with administrator-set custom claims:

```json
{"contextos_workspace":"team-checkout","contextos_role":"developer"}
```

Allowed roles: `pm`, `architect`, `developer`, `qa`, `security`. Members sharing the same workspace claim share the accepted project state. Verify signed ID tokens server-side with revocation checks. All mutation authority uses verified claims, never client-selected personas. Role switching is denied in this mode.

The browser now offers email/password sign-in and a protected eight-hour Firebase session cookie. Enable Email/Password in Firebase Authentication and set `FIREBASE_WEB_API_KEY` to the Firebase web app public API key. The key is public configuration; it is not a service-account credential. Restrict it appropriately in the Google console for your application. Server authentication uses attached Google identity/ADC, never that public key as authorization.

Accounts must already have administrator-set custom claims. No self-signup role picker exists. Passwords go directly from the browser to Firebase's documented REST endpoint. The browser exchanges a recent ID token through `/api/auth/session`, with a CSRF nonce, then discards ID/refresh tokens. The session cookie is HttpOnly, SameSite=Strict and Secure on HTTPS/Cloud Run. Reload retains identity; expiry/revocation returns the user to sign-in. Sessions do not auto-extend. Sign out clears the current browser session and local app buffers; it does not revoke other devices. For compromised sessions or changed memberships, an administrator must revoke refresh tokens so the backend's per-request revocation check rejects old cookies. Existing verified Bearer tokens remain supported for API clients.

A live provider test account, correct project ID and working ADC are still needed to verify this flow end-to-end. Local tests mock Firebase. `/api/auth/config` exposes only the public web key, mode, CSRF nonce and session lifetime; it never exposes model/service secrets. Contract: [design/specs/identity.md](design/specs/identity.md).

## Deployment acceptance checks

- [ ] Container builds on Linux and runs as non-root.
- [ ] `/api/health` reports intended AI/auth modes.
- [ ] Live extraction and task calls succeed; real usage recorded.
- [ ] Two app instances see the same Firestore revisions.
- [ ] Concurrent stale proposals fail without overwriting accepted state.
- [ ] Restricted data is absent from sources, tasks, activity, export and metrics for unprivileged roles.
- [ ] A new revision flags dependent runs, while original manifests remain intact.
- [ ] Restart/redeployment retains knowledge and audit history.
- [ ] Public/private judge access, abuse limits and retention are explicitly configured.
- [ ] Prototype remains available during evaluation.

References: [Google Gen AI SDK](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/sdks/overview), [Cloud Run](https://cloud.google.com/run/docs), [Firestore](https://firebase.google.com/docs/firestore). Confirm current deployment prerequisites against official documentation when configuring the project.

## Selected Firestore integration

New authenticated workspaces start empty; only demo workspaces seed synthetic checkout data. Changing modes never deletes or replaces existing workspace records. Use separate Firestore projects/collections or fresh workspace IDs when transitioning from synthetic demos to real members.

`firebase.json`, `firestore.rules` and `firestore.indexes.json` prepare client access rules and exclude the aggregate payload from indexing. Deploy them explicitly to the selected project with Firebase CLI after reviewing the target:

```sh
firebase deploy --only firestore:rules,firestore:indexes --project YOUR_PROJECT_ID
```

Client rules deny direct browser reads/writes. The FastAPI server SDK uses its runtime service account and IAM; these rules do not replace backend membership/role checks. Do not deploy this deny-all rule set into an unrelated shared project. No .firebaserc default project is committed.

After Firestore Native mode, ADC and IAM are configured, run:

```sh
.venv/bin/python scripts/verify_firestore.py --project YOUR_PROJECT_ID
```

This explicitly creates and retains a separately named synthetic verification workspace. It checks two clients/recreated client visibility, competing approvals and preserved stale snapshots. It is also usable with a configured Firestore emulator. The script has not been run against a live project here; it does not prove deployed multi-instance behavior or backups/restoration. Record its workspace ID and clean up according to the selected environment's retention policy.
