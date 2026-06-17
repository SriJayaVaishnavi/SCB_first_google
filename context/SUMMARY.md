# Beacon — Summary & What To Do

**One-liner:** A swarm of GCP agents (Google ADK + Gemini on Vertex AI) that triages a crisis
surge of consular messages, floating life-threatening (P1) cases to the top of a duty-officer
dashboard in seconds — built for MFA Singapore "AI Immersion Day", Card 01 "The Crowded Hotline".
**It's a prototype: prioritise a working, deployed demo over model perfection.**

## Doc map (read in this order)
1. **`context/RESUME-HERE.md`** — current state + the exact next command. Start here.
2. **`context/SUMMARY.md`** — this file: the to-do checklist to finish & deploy.
3. **`docs/superpowers/specs/2026-06-17-beacon-crisis-triage-design.md`** — the design (what & why).
4. **`docs/superpowers/plans/2026-06-17-beacon-crisis-triage.md`** — the full 7-phase plan (how).
5. **`context/session-2026-06-17-0935-vertex-auth-troubleshooting.md`** — Vertex auth fixes (local).

## Fixed facts (don't re-derive)
- GCP project **`rapidbuildsingapore`**, region **`us-central1`**, model **gemini-2.5-flash**, Vertex AI.
- Auth: use SA **`beacon-vertex`**, key **`~/beacon-sa-key.json`** (user account 403s; SA works).
- Workflow: Claude pushes to GitHub `SCB_first_google`; user runs in **Cloud Shell**.
- Decisions: **ADK for the agents** (real agents, the pitch); **ADK first, then dashboard**.

## ✅ Done
- Phase 1 GCP setup · Phase 2 data layer (300 msgs + SOP + feed) · Phase 3 triage eval
  (**P1 recall 100%**, gate passed). Triage rebuilt as an ADK `LlmAgent`.
- **Step A — ADK verified:** smoke test PASSED 2026-06-17 14:08 (`e339a6c`), no terminal exports
  (config via `backend/.env`). Timestamped error ledger: `context/BUILD-LOG.md`.

## ⏳ TO DO — to complete & deploy the prototype

### Step B — build the full swarm (Phase 4) ◀ NOW
Build as ADK agents with a visible handoff trace:
- **Intake** — normalise/translate each message.
- **Triage** — score P1–P4 + reason + SOP ref (already an ADK agent).
- **Escalation** — rank queue by danger; attach suggested action + target mission.
- **Responder** — draft a safe reply for P4 routine queries (human confirms).
- `run_swarm(messages) -> ranked queue with trace`. Test on a small batch first.

### Step C — API + dashboard (Phase 5) ✅ BUILT
- FastAPI `backend/app/api.py`: `POST /simulate` (SSE), `GET /queue`, `POST /case/{id}/confirm`,
  `/reset`, `/` health. `stream_swarm()` yields cases as triaged.
- Next.js dashboard `frontend/`: dark command console, live danger-ranked queue (P1 pulsing at
  top), case detail (reason + SOP + routed action / draft + Confirm/Override), Beacon-vs-FIFO
  scoreboard, agent-trace panel. `tsc` + `next build` pass.
- Run: `uvicorn app.api:app --port 8000` + (in `frontend/`) `npm install && npm run dev`.
  Set `NEXT_PUBLIC_API_URL` to the backend URL. Pending: run together vs a live LLM.

### Step D — deploy (Phase 6)
- Dockerise backend + frontend; `gcloud run deploy` both to `rapidbuildsingapore` (us-central1).
- Grant the Cloud Run runtime service account `roles/aiplatform.user` (no key file needed on Cloud Run).
- Smoke-test the deployed URL.

### Step E — demo (Phase 7)
- Run the 300-message surge replay on the deployed app.
- Show the scoreboard: every P1 surfaced in seconds vs ~90 min in a FIFO queue.
- (If latency matters, request a Vertex quota bump so the full run is fast.)

## Definition of done
Deployed Cloud Run URL where a simulated surge of 300 messages streams in and every
life-threatening case surfaces at the top within seconds, each with a reason + SOP basis,
routine queries auto-deflected, humans confirming — demoed live with the baseline-vs-Beacon scoreboard.
