# 🛠️ Beacon — Build Log (timestamped stage → error → fix)

Purpose: a running, timestamped ledger of every build stage, the errors hit, their root
cause, and the fix. Raw material for a **generic "build prototypes in GCP" workflow** —
see the distilled catalog at the bottom. Append new entries; never rewrite history.

Times are local (Asia/Kolkata, the dev machine). Commit hashes link to the repo
`SriJayaVaishnavi/SCB_first_google`.

---

## 2026-06-17 — Phase 4: verify ADK on Vertex

| Time | Stage | Error / event | Root cause | Fix |
|------|-------|---------------|-----------|-----|
| 09:10 | Phase 3 eval | Vertex `429 RESOURCE_EXHAUSTED` under eval load | free/low quota + too much concurrency | backoff + `EVAL_WORKERS=2` (`32386ce`) |
| 09:22 | Phase 3 auth | Vertex `403` on user creds in Cloud Shell | user account lacks `aiplatform.endpoints.predict` | dedicated SA `beacon-vertex` + key, force in `run_eval.sh` (`ca2b30d`) |
| 09:27 | Phase 3 auth | wrong/stale key still used | a stale `GOOGLE_APPLICATION_CREDENTIALS` from the Cloud Shell profile pointed at another project's SA | `run_eval.sh` force-exports the beacon key, overriding it (`981107c`) |
| 09:55 | Phase 4 | ADK `LlmAgent` + smoke test written & pushed (`dc32a84`); not yet run | — | — |
| ~13:45 | Write `.env` | shell hangs at `>` continuation prompt | heredoc closing `EOF` was **indented** → not recognized as terminator; indentation would also prefix every key with spaces | put terminator at column 0, or skip heredoc and use `printf '%s\n' 'K=v' ... > .env` |
| ~13:50 | Run smoke test | `ModuleNotFoundError: No module named app.agents.adk_agents` | Cloud Shell checkout not `git pull`ed → file from `dc32a84` absent | `git pull`; install deps with `python -m pip ...` into the **same** interpreter being run (`/usr/bin/python` here) |
| ~14:00 | Run smoke test | `403 PERMISSION_DENIED` on `aiplatform.endpoints.predict` (us-central1, gemini-2.5-flash) | SA key not applied: `load_dotenv()` does **not** override a var already set in the shell, so the stale `GOOGLE_APPLICATION_CREDENTIALS` won; user creds 403 anyway | `load_dotenv(override=True)` so `.env` wins (`e339a6c`) + `.env` holds the **absolute** SA-key path |
| 14:08 | Run smoke test | ✅ **PASS** — `[P1]` trapped-child (conf 1.00), `[P4]` flight-status (conf 1.00), "ADK smoke test OK"; ADK v1.27.2 | — | — |
| ~14:20 | Full swarm built (`d60d4db`) | Intake/Escalation/Responder + `run_swarm()` + 5-msg demo | — | — |
| 14:30 | Run swarm demo | `429 RESOURCE_EXHAUSTED` on the first Intake call | the ADK rebuild **lost the backoff** the direct-genai path had; ADK's own retries gave up; the swarm fires ~2–3 calls/msg and burst-tripped the low new-project Vertex quota | add `_run()` backoff wrapper (4→60s, 6 retries) around every ADK invoke (`triage/intake/escalation/responder`) — mirrors `triage.py`'s `_generate_with_backoff` |

**Region note (locked earlier):** `asia-southeast1` does **not** serve `gemini-2.5-flash` on
Vertex → use `us-central1`.

---

## Generic GCP-prototype workflow & error catalog (distilled)

Recurring failure classes when building agent prototypes on GCP / Vertex AI, with the
pre-emptive fix. Use this as a checklist before each new prototype.

1. **IAM / auth — the #1 time sink.**
   - A logged-in *user account* often lacks `aiplatform.endpoints.predict`. Create a
     **dedicated service account** (`roles/aiplatform.user`) + key file from the start.
   - Beware a **stale `GOOGLE_APPLICATION_CREDENTIALS`** inherited from the shell profile —
     it silently shadows your intended creds. Make your config authoritative.

2. **Env-var propagation — never rely on terminal `export`.**
   - Exports die on session restart. Put config in a **persistent `.env`** (gitignored).
   - `python-dotenv` does **not** override already-set vars → use `load_dotenv(override=True)`.
   - dotenv does **not** expand `~` → store **absolute paths**.

3. **Region availability.** Not every region serves every model. Pick a region that serves
   your model (e.g. `us-central1` for `gemini-2.5-flash`) before debugging "permission/exist" 403s.

4. **Quota / rate limits.** New projects hit `429` fast. Add **retry-with-backoff** and keep
   **concurrency low** until a quota bump.

5. **Repo & interpreter sync (Cloud Shell loop).** `git pull` before every run; install deps
   into the **same** interpreter you invoke (`python -m pip`, watch `/usr/bin/python` vs others).

6. **Shell gotchas.** Heredoc terminators must be at column 0; prefer `printf` to write config
   files to avoid paste-indentation corruption.

7. **Workflow shape that worked here.** Claude (Windows) writes → commits → pushes; user pulls
   in **Cloud Shell** (where the SA + Vertex auth work) and runs. Windows lacks `gcloud`, so all
   Vertex calls happen in Cloud Shell.
