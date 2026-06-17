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
| 14:36 | Re-run swarm demo (`8fc7442`) | backoff **works** (Intake+Triage of msg 1 passed) but Escalation kept 429ing → user Ctrl-C'd; also `Task exception … Event loop is closed` spam | (a) **quota wall**: gemini-2.5-flash per-minute quota is effectively near-zero, so ~12 sequential calls can't sustain even with backoff; (b) **bug**: per-call `asyncio.run()` opened/closed a new event loop each call, orphaning the genai HTTP client's async cleanup | (b) refactor swarm to one event loop — async `_run_async`/`run_swarm_async`, sync wrappers via single `asyncio.run`; demo now degrades gracefully + `DEMO_BATCH_SIZE`/`DEMO_PACE_SEC`. (a) needs a **Vertex quota bump** (decision pending) |
| 14:50 | Limp demo `DEMO_BATCH_SIZE=2 DEMO_PACE_SEC=20` (`463b279`) | 5 calls landed (intake×2, triage×2, escalation×1), then Responder **failed all 6 retries over ~120s** → graceful exit. Meter: 11 total calls | 120s backoff did NOT recover → not per-minute. **Corrected analysis (see note):** quota is NOT near-zero — Phase-3 eval did ~60 calls fine; this is a **per-DAY cap drained** by today's repeated runs | harden the swarm (below) + Console quota check; stay on Vertex |
| 15:1x | Hardening (`<this commit>`) | n/a (code) | **Why Phase 3 worked, Phase 4 didn't**: same SA/model/region/backoff. Eval ran AM on a fresh daily budget and ground 60 calls through patiently; by PM we'd fired 100+ requests (eval + smokes + ~4 swarm attempts, **failed retries count as requests**) → daily cap hit. Not a code regression | add per-call pacing (`CALL_INTERVAL_SEC`), tunable `MAX_RETRIES`, and a `QuotaExhausted` exception (429 surviving full backoff ⇒ per-day cap ⇒ stop fast, don't burn retries). Knobs live in `.env` (no export) |
| 15:3x | AI Studio mode, full swarm (`2618226`) | mode flipped to AISTUDIO ✓, but `429` then a `503 UNAVAILABLE` crashed the run | (a) AI Studio free tier ≈10 req/min → the ~14-call burst trips it; (b) **bug**: retry only caught 429, so the transient **503** propagated and killed the run; (c) swarm was call-heavy (Intake called the LLM even for English) | retry now covers **503/UNAVAILABLE** too (transient → backoff; distinct from QuotaExhausted); **Intake skips the LLM for English** (ASCII pass-through) cutting ~4 calls; pace with `CALL_INTERVAL_SEC=7` in `.env` to stay under the per-minute cap (`1f62e9c`) |
| 15:4x | Add Groq dev backend (`e629c4e`) | both Gemini surfaces throttled (Vertex daily cap; AI Studio 429+503) | both unreliable today | add **3rd mode `BEACON_MODE=groq`** via ADK LiteLLM (Llama, off-GCP, fast/generous free tier) — **temporary dev unblock, NOT the Vertex pitch**. Llama lacks Gemini's strict schema, so groq mode drops `output_schema`, injects the JSON shape into the prompt, and parses tolerantly (`_extract_json` strips ```json fences). `pip install litellm` |
| 16:2x | `pip install litellm` | `dependency conflict: google-adk requires websockets<16.0.0 but you have websockets 16.0` | litellm pulled websockets 16.0, outside ADK's pinned range | pin `websockets>=15.0.1,<16.0.0` in requirements + install it (`29d22b9`); litellm works on <16 |
| 16:3x | Write Groq `.env` (heredoc/printf) | `bash: GROQ_MODEL=…: No such file or directory`; only BEACON_MODE + GROQ_API_KEY landed | a **trailing space after the `\`** broke printf's line continuation, so the next line ran as a command | harmless — `GROQ_MODEL` defaults in config; add it cleanly with `echo '…' >> .env` if wanted. (Lesson → shell gotchas) |

> **Correction (15:1x):** earlier rows called the quota "near-zero" — wrong. Phase 3's eval
> completed ~60 Vertex calls, so the quota is usable. The real story is a **per-DAY cap**: fine
> in the morning, drained by an afternoon of repeated testing (every 429'd retry is a billable
> request). Generic lesson for the GCP catalog below: **failed retries consume quota too** — under
> a daily cap, fewer retries + pacing beats blind backoff.

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
   **concurrency low** until a quota bump. Know your cap type: a **per-minute** limit resets in
   ~60s (backoff/pacing wins) but a **per-DAY** cap does not (backoff just burns more quota —
   **every 429'd retry is a billable request**). If a 429 survives ~120s of backoff, treat it as
   a daily cap: stop fast (low MAX_RETRIES), pace calls under the per-minute rate, and wait for
   the reset (~midnight US-Pacific) or bump the quota. Gemini 2.5 also uses dynamic shared quota,
   so fresh projects with no usage history get the smallest slice. Also retry **503 UNAVAILABLE**
   ("high demand") — transient model overload, separate from quota. Have a **fallback backend**
   ready (AI Studio key, or an off-GCP model via LiteLLM/Groq) so dev isn't blocked when one
   surface is throttled — gate behind a single config flag, don't fork the code.

4b. **Dependency conflicts.** Adding a bridge lib can drag in versions another lib rejects
   (here `litellm` pulled `websockets 16.0`, but `google-adk` needs `<16`). Pin the shared dep to
   the stricter range in requirements; read pip's conflict warning — it names the exact bound.

5. **Repo & interpreter sync (Cloud Shell loop).** `git pull` before every run; install deps
   into the **same** interpreter you invoke (`python -m pip`, watch `/usr/bin/python` vs others).

6. **Shell gotchas.** Heredoc terminators must be at column 0; prefer `printf` to write config
   files to avoid paste-indentation corruption. A line-continuation `\` must be the **last**
   character on the line — a **trailing space after `\`** breaks the continuation and the next
   line runs as a command. For secrets, append single lines with `echo 'KEY=val' >> .env` rather
   than fighting multi-line paste. Never set env via `export` (dies on restart — see §2).

7. **Workflow shape that worked here.** Claude (Windows) writes → commits → pushes; user pulls
   in **Cloud Shell** (where the SA + Vertex auth work) and runs. Windows lacks `gcloud`, so all
   Vertex calls happen in Cloud Shell.
