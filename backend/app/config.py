"""Central config loaded from environment (.env)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# override=True so values in backend/.env always win over any stale variable already
# in the shell (e.g. a Cloud Shell profile's leftover GOOGLE_APPLICATION_CREDENTIALS
# pointing at another project's SA key, which 403s on Vertex here). Lets us configure
# everything via the persistent .env file with no terminal `export` needed.
load_dotenv(override=True)

DATA_DIR = Path(__file__).parent / "data"

# ── Backend modes, selected in backend/.env (all code paths stay live, nothing removed) ─
#   MODE = "vertex"   (GOOGLE_GENAI_USE_VERTEXAI=true)  → Gemini on Vertex AI. Needs
#                      GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION + GOOGLE_APPLICATION_
#                      CREDENTIALS (beacon SA key). The final MFA pitch ("agents in GCP").
#   MODE = "aistudio" (GOOGLE_GENAI_USE_VERTEXAI=false) → Gemini Developer API. Needs
#                      GOOGLE_API_KEY. No project/SA.
#   MODE = "groq"     (BEACON_MODE=groq) → open model (Llama) via Groq + LiteLLM. Needs
#                      GROQ_API_KEY. TEMPORARY DEV backend only — off-GCP, fast/generous
#                      free tier; NOT for the Vertex pitch. Lets us build while Gemini is
#                      throttled. `pip install litellm` required.
# BEACON_MODE (if set) wins; otherwise the Vertex flag picks vertex|aistudio.
USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() == "true"
MODE = os.getenv("BEACON_MODE", "").strip().lower() or ("vertex" if USE_VERTEXAI else "aistudio")

# Vertex-mode settings (ignored otherwise).
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# AI-Studio-mode setting (ignored otherwise). The genai SDK reads either name.
API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")

# Groq-mode settings (ignored otherwise). LiteLLM reads GROQ_API_KEY from the env.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "groq/llama-3.3-70b-versatile")

TRIAGE_MODEL = os.getenv("TRIAGE_MODEL", "gemini-2.5-flash")
# Lower floor => fewer automatic tier bumps (the prompt already handles genuine
# P1/P2 ambiguity, so reserve the bump for only very-low-confidence calls).
CONFIDENCE_FLOOR = float(os.getenv("TRIAGE_CONFIDENCE_FLOOR", "0.5"))

# Deterministic split seed so the holdout scoreboard is reproducible.
SPLIT_SEED = 42
HOLDOUT_FRACTION = 0.2
