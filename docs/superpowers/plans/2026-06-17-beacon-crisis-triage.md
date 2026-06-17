# Beacon — Crisis Triage Agent Swarm — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deployed GCP-native multi-agent system that reads a simulated surge of ~300 consular messages, scores true-urgency, and floats life-threatening (P1) cases to the top of a duty-officer dashboard in seconds — each with a reason and SOP basis — while safely deflecting routine queries.

**Architecture:** Python backend using Google ADK orchestrates four agents (Intake → Triage → Escalation → Responder) calling Gemini 2.x Flash on Vertex AI. SOP + country-conditions feed are injected into context (no vector DB). A Next.js dashboard streams the live triage queue. Both deploy to Cloud Run; state/audit in Firestore (in-memory acceptable for demo).

**Tech Stack:** Python 3.11+, `google-adk`, `google-cloud-aiplatform` (Vertex AI), Gemini 2.x Flash, FastAPI, Cloud Run, Firestore, Next.js 14 + Tailwind.

## Global Constraints

- Synthetic data only — no real PII; nothing leaves the GCP region (Sensitive tier).
- **Bias-to-escalate:** a missed P1 (false-negative) is the catastrophic error. On low model confidence, default to the *higher* severity.
- **No auto-dismiss:** the system re-ranks/recommends; a human confirms every action.
- Every triage decision must carry a `reason` and a `sop_reference` (explainability is non-negotiable).
- Acceptance: P1 recall ≥ 99% on holdout; time-to-first-P1 < 5s; zero P1 auto-dismissed.
- Region: single region, in-region (decide exact region in Task 1, e.g. `asia-southeast1` Singapore).

---

## Parallel ownership

- **YOU (user):** Phase 1 — GCP account setup (you own the billing account).
- **ME (Claude):** Phases 2–7 — code, agents, dashboard, deploy.
- **Shared gate:** I cannot run agents until Phase 1 gives me a project ID + auth + enabled APIs. You hand those back and I proceed.

---

## Phase 1 — GCP setup (YOU execute, in parallel)

**Files:** none (account configuration). Hand the values back to me.

Run these in a terminal where `gcloud` is installed (or Cloud Shell at console.cloud.google.com).

- [ ] **Step 1: Authenticate**

```bash
gcloud auth login
gcloud auth application-default login
```

- [ ] **Step 2: Pick or create a project, set it active**

```bash
# reuse an existing project:
gcloud config set project YOUR_PROJECT_ID
# OR create a new one and link your billing account:
gcloud projects create beacon-triage-demo --name="Beacon Triage"
gcloud billing accounts list                       # copy your billing account ID
gcloud billing projects link beacon-triage-demo --billing-account=BILLING_ACCOUNT_ID
gcloud config set project beacon-triage-demo
```

- [ ] **Step 3: Set region (Singapore, in-region for Sensitive tier)**

```bash
gcloud config set compute/region asia-southeast1
```

- [ ] **Step 4: Enable the APIs**

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  firestore.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com
```

- [ ] **Step 5: Create the Firestore database (Native mode, Singapore)**

```bash
gcloud firestore databases create --location=asia-southeast1
```

- [ ] **Step 6: Verify and report back to me**

```bash
gcloud config get-value project
gcloud services list --enabled --filter="aiplatform OR run OR firestore"
```

Expected: project ID prints; the three services show as enabled.
**Hand me:** the project ID and the region. That unblocks Phase 3+.

---

## Phase 2 — Project scaffold + data layer (ME)

**Files:**
- Create: `backend/pyproject.toml`, `backend/.env.example`, `backend/app/config.py`
- Create: `backend/app/data/messages.json` (the ~300 labelled messages), `backend/app/data/sop.md`, `backend/app/data/country_feed.json`
- Create: `backend/app/data_loader.py`
- Test: `backend/tests/test_data_loader.py`

**Interfaces:**
- Produces: `load_dataset() -> Dataset` where `Dataset` has `.train: list[Message]`, `.holdout: list[Message]`, `.sop: str`, `.country_feed: dict`. `Message` = `{id: str, text: str, true_label: "P1"|"P2"|"P3"|"P4"}`.

> **BLOCKER to resolve first:** we need the actual data pack (the 300 labelled messages, SOP extract, country feed). If MFA hasn't provided it, Task 2.0 generates a realistic synthetic stand-in so the build is not blocked.

- [ ] **Step 1: Confirm or generate the data pack.** If the real pack exists, drop it into `backend/app/data/`. Otherwise generate ~300 synthetic messages with a balanced label mix (small % P1, larger % P4) reflecting a flood/crisis scenario, plus a one-page SOP with explicit escalation thresholds, plus a country-conditions feed.
- [ ] **Step 2: Write failing test** that `load_dataset()` returns a 80/20 train/holdout split, all labels in {P1..P4}, sop non-empty.
- [ ] **Step 3: Run test → FAIL** (`load_dataset` not defined).
- [ ] **Step 4: Implement `data_loader.py`** with a deterministic (seeded) split.
- [ ] **Step 5: Run test → PASS.**
- [ ] **Step 6: Commit** `feat: data layer + loader with train/holdout split`.

---

## Phase 3 — Triage Agent + prove recall (ME) — riskiest first

This validates hypothesis H1 *before* we build anything else. If recall isn't there, we learn now.

**Files:**
- Create: `backend/app/agents/triage.py`, `backend/app/schemas.py`
- Create: `backend/app/eval/score.py`
- Test: `backend/tests/test_triage.py`, `backend/tests/test_eval.py`

**Interfaces:**
- Consumes: `Dataset` from Phase 2.
- Produces: `triage_message(text: str, sop: str, feed: dict) -> TriageResult` where `TriageResult = {severity, category, confidence: float, reason: str, sop_reference: str}`. Also `evaluate(results, holdout) -> {p1_recall, p1_precision, deflection_rate, avg_latency}`.

- [ ] **Step 1: Define `TriageResult` schema** (pydantic) with severity enum P1–P4.
- [ ] **Step 2: Write failing test** for `triage_message` on 3 hand-written cases (one obvious P1 "I am detained, no one can reach me", one P4 "is my flight delayed"), asserting P1 case → severity P1 and a non-empty `sop_reference`.
- [ ] **Step 3: Run test → FAIL.**
- [ ] **Step 4: Implement `triage_message`** as a Gemini Flash call via Vertex AI, SOP + feed injected into the prompt, structured (JSON) output, bias-to-escalate on confidence < threshold.
- [ ] **Step 5: Run test → PASS** (requires Phase 1 done + auth).
- [ ] **Step 6: Write `evaluate()`** and a script `python -m app.eval.score` that runs triage over the holdout and prints P1 recall / precision / deflection / latency.
- [ ] **Step 7: Run eval → assert P1 recall ≥ 0.99.** If below, tune prompt with SOP examples / escalate hard cases to Gemini Pro; iterate until met. **This is the gate for the whole project.**
- [ ] **Step 8: Commit** `feat: triage agent + eval harness, P1 recall validated`.

---

## Phase 4 — Wrap the swarm (ME)

**Files:**
- Create: `backend/app/agents/intake.py`, `backend/app/agents/escalation.py`, `backend/app/agents/responder.py`, `backend/app/agents/swarm.py`
- Test: `backend/tests/test_swarm.py`

**Interfaces:**
- Consumes: `triage_message` (Phase 3).
- Produces: `run_swarm(messages: list[Message]) -> RankedQueue` — `RankedQueue` = ordered list of `{message, triage: TriageResult, suggested_action, target_mission, draft_reply|None, trace: list[str]}`, sorted P1→P4. `intake()` normalizes/translates; `escalation()` ranks + adds action/mission; `responder()` drafts replies for P4 only.

- [ ] **Step 1–5 per agent (TDD):** failing test → fail → implement → pass, for intake, escalation, responder.
- [ ] **Step 6: Compose `run_swarm`** with ADK agent handoffs Intake→Triage→Escalation→Responder; collect a `trace` of handoffs for the dashboard.
- [ ] **Step 7: Test** `run_swarm` on a 10-message fixture → P1s first, every item has trace + sop_reference, no P1 has an auto-sent reply.
- [ ] **Step 8: Commit** `feat: full triage agent swarm with handoff trace`.

---

## Phase 5 — API + dashboard (ME)

**Files:**
- Create: `backend/app/main.py` (FastAPI: `POST /simulate` streams the surge via SSE, `GET /queue`, `POST /case/{id}/confirm`)
- Create: `frontend/` (Next.js): `app/page.tsx` (queue), `app/case/[id]/page.tsx` (detail), `components/QueueList.tsx`, `components/CaseDetail.tsx`, `components/OpsScoreboard.tsx`, `components/AgentTrace.tsx`
- Test: `backend/tests/test_api.py`, frontend smoke via `npm run build`

**Interfaces:**
- Consumes: `run_swarm` (Phase 4).
- Produces: SSE event stream of ranked cases; scoreboard payload `{p1_count, surfaced_seconds, fifo_baseline_seconds, deflected_count}`.

- [ ] **Step 1: API tests** for `/simulate` (returns events), `/case/{id}/confirm` (marks handled). FAIL → implement → PASS.
- [ ] **Step 2: Build dashboard** — live queue (P1 red at top, severity chips, one-line reason), case detail (full message + reasoning trace + SOP citation + suggested action + draft reply + Confirm/Override), ops scoreboard (Beacon vs FIFO 90-min), agent-trace panel.
- [ ] **Step 3: Run `npx next lint` + `npx tsc --noEmit`** → PASS (pre-commit-lint).
- [ ] **Step 4: Commit** `feat: triage API + live dashboard`.

---

## Phase 6 — Deploy to Cloud Run (ME, needs your project)

**Files:** Create `backend/Dockerfile`, `frontend/Dockerfile`, `deploy.sh`

- [ ] **Step 1: Containerize** backend + frontend.
- [ ] **Step 2: Deploy** via `gcloud run deploy` to your project, region `asia-southeast1`, with Vertex AI access.
- [ ] **Step 3: Smoke test** the deployed URL — run `/simulate`, confirm P1s surface.
- [ ] **Step 4: Commit** `chore: Cloud Run deploy config`.

---

## Phase 7 — Measure & demo (ME + YOU)

- [ ] **Step 1: Run the surge replay** on the deployed app; capture the baseline-vs-Beacon scoreboard.
- [ ] **Step 2: Verify acceptance criteria** — P1 recall ≥ 99%, time-to-first-P1 < 5s, zero P1 auto-dismissed, every P1 card has reason + SOP ref.
- [ ] **Step 3: Record the demo narrative** — "found on minute 90" → "surfaced in 4 seconds."

---

## Self-review notes
- **Spec coverage:** every spec section maps to a phase (problem→3, agents→4, dashboard→5, guardrails→global constraints + 3/4, acceptance→7, GCP stack→1/6). ✓
- **Open blocker:** real data pack availability (Phase 2 Step 1) — synthetic stand-in keeps us unblocked.
- **Type consistency:** `TriageResult` fields used identically across Phases 3–5. ✓
