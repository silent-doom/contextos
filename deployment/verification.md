# Hackathon MVP deployment — 18 October 2026

## Access

- Team service: https://contextos-443743777956.asia-south1.run.app
- Public synthetic walkthrough: https://contextos-demo-443743777956.asia-south1.run.app
- Project: contextos-512006; region: asia-south1 (Mumbai).
- Team: Three-Way Handshake — Faizan Choudhary, Amogh Prabhu, Ankush Bhagat.
- Scope: a functional hackathon MVP with a polished interface, not enterprise production certification.

Team service requires verified sessions and signed role/workspace claims. Public signup is disabled with the owner's explicit approval. The owner approved creation of an initial member account, a separate judge member account, and disposable two-user verification accounts. Credentials are only in ignored, mode-0600 local files under .data/; never include them in public submissions. The judge account belongs to judges-mvp, a separate workspace seeded with synthetic checkout knowledge, with Developer permissions. Review of Architecture still requires a distinct Architect identity; a member cannot approve its own proposal or switch roles.

The public walkthrough is explicitly synthetic and runs AI_MODE=offline. It supports all five personas and twelve isolated cases, without exposing real member sessions. It is not a recording of live generated model answers. The team service uses AI_MODE=vertex, GEMINI_MODEL=gemini-2.5-flash, STORE_BACKEND=firestore and AUTH_MODE=firebase.

## Provisioned resources

- Firestore Native default database in asia-south1, deletion protection enabled.
- Client database rules deny all direct reads/writes; server access uses IAM and application membership checks.
- Aggregate payload field excluded from indexing; normal 750 KB workspace limit retained.
- Runtime identity: contextos-runtime; roles/datastore.user, roles/aiplatform.user, and custom contextosSession (firebaseauth.users.get and firebaseauth.users.createSession).
- Build identity: contextos-build with roles/run.builder. Cloud Build builds the existing non-root Dockerfile and stores the image in regional Artifact Registry.
- Cloud Run scales to zero; team maximum 2 instances, synthetic demo maximum 1. Both use 512 MiB, one CPU, concurrency 20 and 120-second request timeout.
- Cloud Run platform logs and metrics are available in Cloud Logging/Monitoring. No external alert recipient, backup restore test, load benchmark or automated production deployment is claimed.
- .gcloudignore limits build uploads to application/container inputs; excludes local credentials, reviewer notes, tests, recorder profiles and generated media.

## Verified evidence

- Live Vertex generateContent succeeded with actual provider token usage.
- Firestore verification workspace verification-27439140267d450095f5b928b80b901a: concurrent approval has one winner; recreated/second clients see v2; original snapshot stays v1 and stale.
- Deployed browser-style collaboration workspace cloud-verification-ddf44f6c9866: two real sessions, denied author approval, independent publication, live AI task, v2 publication, stale original manifest, fresh v2 rerun, returning-session persistence and logout pass. Test now sends the actual browser Origin header. Temporary verification users deleted.
- Retained synthetic accepted topic CTX-3a1c270405, initial run RUN-9ce893304d and refreshed run RUN-60899522f3 are diagnostic evidence, not real customer data.
- Judge member: live password sign-in/session exchange, six visible accepted topics, live structured note extraction into a pending proposal, denied role switching and logout/401 pass.
- Local regression suite: 105 Python and 36 JavaScript tests pass. Two existing upstream deprecation warnings remain.

## HTTPS proxy correction

A browser check found that Cloud Run's proxy made request.base_url differ from the browser's HTTPS Origin. PUBLIC_ORIGIN now defines one exact external origin per service. It does not trust arbitrary forwarded headers or permit cross-origin writes. Five regression cases cover allowed HTTPS, rejected hostile/HTTP origins and invalid configuration. The live verifier now includes Origin, preventing an API-only false positive.

## Redeployment and recovery

Set FIREBASE_WEB_API_KEY to this project's public web app key and run scripts/deploy_cloud_run.sh after tests. The script assumes these resources are already provisioned; it does not modify account membership or database location. Keep the advertised URL aligned with PUBLIC_ORIGIN, including when adding a custom domain.

For rollback, inspect ready revisions and route to a previously verified one:

```sh
gcloud run revisions list --service contextos --project contextos-512006 --region asia-south1
gcloud run services update-traffic contextos --to-revisions VERIFIED_REVISION=100 --project contextos-512006 --region asia-south1
```

Do not roll back to the original browser-origin-broken revision. Revisions do not roll back Firestore data. Retain existing immutable history; no destructive migration was performed. The workspace byte/call limits and instance limits are not global budget caps. Keep synthetic evaluation data separate from future real team data.

## Latest integrated revision

Team revision contextos-00003-8k8 and public demo revision contextos-demo-00003-zrp deploy source commit 6a27264, including the late shared-knowledge changes. CI run 39150725586 passed with 114 Python and 41 Node cases. The missing Markdown adapter injection from the upstream merge was repaired before deployment.

Firestore deployments use WorkspaceMarkdownStorage to read exact bodies from canonical database records; only local stores use the temporary file mirror. Deployed context-page verification created project PRJ-431c6c8485 and context CTX-3fe131d906 in synthetic workspace cloud-verification-56263b6a4eb3. Independent approval, exact normalized-body read/export and fresh-session persistence pass. A first assertion compared the request template's trailing newline instead of the normalized reviewed candidate; the targeted verification was corrected to compare the exact accepted candidate, without changing application content. Temporary accounts were deleted, including two leftovers from the interrupted run.

The judge workspace also includes two explicitly synthetic sample projects from the team's fixture for immediate Knowledge/map exploration. The judge remains a Developer member; sample baseline author/reviewer entries are labeled demo fixtures. Judge session/extraction/role-denial/logout checks pass on the latest revision. The pitch/video capture the preceding verified MVP snapshot (105/36 test counts at recording time); new code has the larger integrated suite above.
