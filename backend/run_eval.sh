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

# IMPORTANT: always prefer our dedicated rapidbuildsingapore SA key, overriding any
# stale GOOGLE_APPLICATION_CREDENTIALS inherited from the Cloud Shell profile
# (e.g. a different project's service-account.json that 403s on Vertex here).
if [ -f "$HOME/beacon-sa-key.json" ]; then
  export GOOGLE_APPLICATION_CREDENTIALS="$HOME/beacon-sa-key.json"
  echo "Auth    : service account ($GOOGLE_APPLICATION_CREDENTIALS)"
elif [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]; then
  echo "Auth    : INHERITED key ($GOOGLE_APPLICATION_CREDENTIALS) — may be the wrong project!"
  echo "          Create ~/beacon-sa-key.json (see README) to fix 403s."
else
  echo "Auth    : default ADC"
fi

echo "Project : $GOOGLE_CLOUD_PROJECT"
echo "Location: $GOOGLE_CLOUD_LOCATION"
echo "Model   : $TRIAGE_MODEL"
echo

python -m app.eval.score
