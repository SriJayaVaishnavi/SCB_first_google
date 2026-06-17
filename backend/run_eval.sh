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

echo "Project : $GOOGLE_CLOUD_PROJECT"
echo "Location: $GOOGLE_CLOUD_LOCATION"
echo "Model   : $TRIAGE_MODEL"
echo

python -m app.eval.score
