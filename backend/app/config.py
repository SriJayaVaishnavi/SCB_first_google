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

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "asia-southeast1")
USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() == "true"
TRIAGE_MODEL = os.getenv("TRIAGE_MODEL", "gemini-2.5-flash")
# Lower floor => fewer automatic tier bumps (the prompt already handles genuine
# P1/P2 ambiguity, so reserve the bump for only very-low-confidence calls).
CONFIDENCE_FLOOR = float(os.getenv("TRIAGE_CONFIDENCE_FLOOR", "0.5"))

# Deterministic split seed so the holdout scoreboard is reproducible.
SPLIT_SEED = 42
HOLDOUT_FRACTION = 0.2
