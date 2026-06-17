#!/usr/bin/env bash
# One-command Triage eval for Cloud Shell.
# Usage:  bash run_eval.sh
set -euo pipefail

# us-central1: asia-southeast1 does not serve gemini-2.5-flash on Vertex.
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-rapidbuildsingapore}"
export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
export GOOGLE_GENAI_USE_VERTEXAI=true
export TRIAGE_MODEL="${TRIAGE_MODEL:-gemini-2.5-flash}"
export EVAL_WORKERS="${EVAL_WORKERS:-2}"

# The user account gets 403 on aiplatform.endpoints.predict in Cloud Shell, but
# the beacon-vertex service account works. A fresh Cloud Shell session drops any
# manual `export`, so auto-use the SA key if it's present in the home dir.
if [ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ] && [ -f "$HOME/beacon-sa-key.json" ]; then
  export GOOGLE_APPLICATION_CREDENTIALS="$HOME/beacon-sa-key.json"
fi

if [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]; then
  echo "Auth    : service account ($GOOGLE_APPLICATION_CREDENTIALS)"
else
  echo "Auth    : default ADC — WARNING: ~/beacon-sa-key.json not found, will likely 403"
fi

echo "Project : $GOOGLE_CLOUD_PROJECT"
echo "Location: $GOOGLE_CLOUD_LOCATION"
echo "Model   : $TRIAGE_MODEL"
echo

python -m app.eval.score
