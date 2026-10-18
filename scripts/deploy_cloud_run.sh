#!/usr/bin/env bash
# Redeploy the provisioned team MVP. Provider web key is public configuration.
set -euo pipefail
cd "$(dirname "$0")/.."
: "${FIREBASE_WEB_API_KEY:?Set the selected project public web API key.}"
contextos_project="${CONTEXTOS_PROJECT:-contextos-512006}"
contextos_region="${CONTEXTOS_REGION:-asia-south1}"
contextos_number="$(gcloud projects describe "$contextos_project" --format='value(projectNumber)')"
contextos_origin="https://contextos-${contextos_number}.${contextos_region}.run.app"
if [[ "$(gcloud billing projects describe "$contextos_project" --format='value(billingEnabled)')" != True ]]; then
  echo 'Project billing is not enabled.' >&2
  exit 1
fi
contextos_env_file="$(mktemp)"
trap 'rm -f "$contextos_env_file"' EXIT
export CONTEXTOS_DEPLOY_PROJECT="$contextos_project" CONTEXTOS_DEPLOY_ORIGIN="$contextos_origin"
python3 - "$contextos_env_file" <<'PY'
import json, os, sys
with open(sys.argv[1], 'w') as output:
    json.dump({'AUTH_MODE':'firebase', 'AI_MODE':'vertex', 'STORE_BACKEND':'firestore',
               'GOOGLE_CLOUD_PROJECT':os.environ['CONTEXTOS_DEPLOY_PROJECT'],
               'GOOGLE_CLOUD_LOCATION':'global', 'GEMINI_MODEL':'gemini-2.5-flash',
               'PUBLIC_ORIGIN':os.environ['CONTEXTOS_DEPLOY_ORIGIN'],
               'FIREBASE_WEB_API_KEY':os.environ['FIREBASE_WEB_API_KEY']}, output)
PY
gcloud run deploy contextos --source . --project "$contextos_project" \
  --region "$contextos_region" \
  --service-account "contextos-runtime@${contextos_project}.iam.gserviceaccount.com" \
  --build-service-account "projects/${contextos_project}/serviceAccounts/contextos-build@${contextos_project}.iam.gserviceaccount.com" \
  --env-vars-file "$contextos_env_file" --memory 512Mi --cpu 1 \
  --min-instances 0 --max-instances 2 --concurrency 20 --timeout 120 \
  --allow-unauthenticated
