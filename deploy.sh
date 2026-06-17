#!/usr/bin/env bash
# One-shot Cloud Run deploy for Beacon (run from the repo root in Cloud Shell).
#   bash deploy.sh groq     # deploy on Groq  (works now; reads GROQ_API_KEY from backend/.env)
#   bash deploy.sh vertex   # deploy on Vertex (the MFA pitch; needs the per-day quota bumped)
set -euo pipefail

MODE="${1:-vertex}"
PROJECT="${PROJECT:-rapidbuildsingapore}"
REGION="${REGION:-us-central1}"
echo "▶ Deploying Beacon in '$MODE' mode → $PROJECT / $REGION"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com aiplatform.googleapis.com --project "$PROJECT"

# ── backend env per mode ──────────────────────────────────────────────────
if [ "$MODE" = "groq" ]; then
  KEY=$(grep -E '^GROQ_API_KEY=' backend/.env 2>/dev/null | cut -d= -f2- || true)
  [ -n "$KEY" ] || { echo "✗ GROQ_API_KEY not found in backend/.env"; exit 1; }
  GROQ_MODEL=$(grep -E '^GROQ_MODEL=' backend/.env 2>/dev/null | cut -d= -f2- || echo "groq/llama-3.3-70b-versatile")
  ENV="BEACON_MODE=groq,GROQ_MODEL=${GROQ_MODEL},GROQ_API_KEY=${KEY}"
else
  ENV="GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${PROJECT},GOOGLE_CLOUD_LOCATION=${REGION},TRIAGE_MODEL=gemini-2.5-flash"
fi

# ── backend ───────────────────────────────────────────────────────────────
gcloud run deploy beacon-api --source backend --project "$PROJECT" --region "$REGION" \
  --allow-unauthenticated --memory 1Gi --cpu 1 --timeout 600 --set-env-vars "$ENV"

if [ "$MODE" = "vertex" ]; then
  PROJNUM=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:${PROJNUM}-compute@developer.gserviceaccount.com" \
    --role=roles/aiplatform.user >/dev/null
  echo "✓ Granted roles/aiplatform.user to the Cloud Run runtime SA"
fi

API_URL=$(gcloud run services describe beacon-api --project "$PROJECT" --region "$REGION" \
  --format='value(status.url)')
echo "✓ Backend: $API_URL"

# ── frontend (bake the backend URL at build) ───────────────────────────────
IMAGE="gcr.io/${PROJECT}/beacon-web"
gcloud builds submit frontend --config frontend/cloudbuild.yaml --project "$PROJECT" \
  --substitutions=_API_URL="$API_URL",_IMAGE="$IMAGE"
gcloud run deploy beacon-web --image "$IMAGE" --project "$PROJECT" --region "$REGION" \
  --allow-unauthenticated --memory 512Mi

WEB_URL=$(gcloud run services describe beacon-web --project "$PROJECT" --region "$REGION" \
  --format='value(status.url)')
echo ""
echo "✓ Backend : $API_URL   (curl \$API_URL/ → {\"mode\":\"$MODE\"})"
echo "✓ Dashboard: $WEB_URL   ← open this, click ▶ Simulate surge"
