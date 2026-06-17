# Deploying Beacon to Cloud Run (Vertex mode)

Two services: **`beacon-api`** (FastAPI) and **`beacon-web`** (Next.js dashboard), both on
Cloud Run in `rapidbuildsingapore` / `us-central1`. The deployed demo runs on **Vertex AI** —
auth is via each service's **runtime service account** (no key file).

## Prerequisites
1. **Verify it runs locally first** (don't deploy untested) — see README / run both services.
2. **Vertex per-day quota bumped** for `gemini-2.5-flash` in `us-central1` (else it 429s live).
   Console → IAM & Admin → Quotas → `aiplatform.googleapis.com` `generate_content` → request increase.
3. APIs enabled:
   ```bash
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
     artifactregistry.googleapis.com aiplatform.googleapis.com --project rapidbuildsingapore
   ```

## 1 — Deploy the backend (Vertex via runtime SA)
```bash
cd ~/SCB_first_google
gcloud run deploy beacon-api --source backend \
  --project rapidbuildsingapore --region us-central1 \
  --allow-unauthenticated --memory 1Gi --cpu 1 --timeout 600 \
  --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=rapidbuildsingapore,GOOGLE_CLOUD_LOCATION=us-central1,TRIAGE_MODEL=gemini-2.5-flash
```
> No `GOOGLE_APPLICATION_CREDENTIALS` — on Cloud Run, ADC uses the runtime SA. `--timeout 600`
> gives the `/simulate` SSE stream room. (To run Groq instead: drop the Vertex vars and set
> `BEACON_MODE=groq`, `GROQ_API_KEY` via Secret Manager.)

Grant that runtime SA access to Vertex (default = the Compute Engine SA):
```bash
PROJNUM=$(gcloud projects describe rapidbuildsingapore --format='value(projectNumber)')
gcloud projects add-iam-policy-binding rapidbuildsingapore \
  --member="serviceAccount:${PROJNUM}-compute@developer.gserviceaccount.com" \
  --role=roles/aiplatform.user
```

Grab the backend URL:
```bash
API_URL=$(gcloud run services describe beacon-api --region us-central1 \
  --project rapidbuildsingapore --format='value(status.url)')
echo "$API_URL"
```

## 2 — Build + deploy the dashboard (backend URL baked in at build)
```bash
IMAGE="gcr.io/rapidbuildsingapore/beacon-web"
gcloud builds submit frontend --config frontend/cloudbuild.yaml \
  --project rapidbuildsingapore \
  --substitutions=_API_URL="$API_URL",_IMAGE="$IMAGE"

gcloud run deploy beacon-web --image "$IMAGE" \
  --project rapidbuildsingapore --region us-central1 \
  --allow-unauthenticated --memory 512Mi
```

## 3 — Lock CORS (optional, after URLs are known)
In `backend/app/api.py`, replace `allow_origins=["*"]` with the `beacon-web` URL, redeploy the API.

## Smoke test
```bash
WEB_URL=$(gcloud run services describe beacon-web --region us-central1 \
  --project rapidbuildsingapore --format='value(status.url)')
curl "$API_URL/"            # {"status":"ok","mode":"vertex",...}
echo "open $WEB_URL"        # the dashboard → Simulate surge
```
