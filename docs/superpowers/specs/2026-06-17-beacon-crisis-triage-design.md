# Beacon — Crisis Triage Agent Swarm

**Design spec · 2026-06-17**
**Challenge:** MFA Singapore "AI Immersion Day" — Card 01 *"The Crowded Hotline"* (Consular · Triage · P1 Consular & Crisis)
**Method:** TCS Rapid Build Squad framework (Learn → Widen → Diagnose → Ideate & Converge → Brief → Build)
**Status:** Design — awaiting user review before implementation planning.

---

## 1. Problem

During a consular crisis, a surge of *routine* queries (transit/travel-status questions) buries the citizens who are in immediate physical danger. The 24/7 Duty Office reads one undifferentiated queue in arrival order, by fatigued, finite, rotating officers. The hardest cases are the easiest to miss in a full queue, and quality degrades exactly when volume peaks (e.g. Hat Yai floods, Middle-East travel disruptions).

**Root cause (from Five Whys):** There is no danger-aware triage layer between message intake and the human queue. Ordering is temporal, not risk-based, so officer attention is allocated by arrival luck instead of severity.

**Who feels the pain:** Consular Duty Officer (primary), citizens in high-risk situations, Crisis/Ops lead.

## 2. Goal & success criteria

Build a **deployed, GCP-native multi-agent system** that reads every inbound message during a simulated surge, scores true-urgency, and floats life-threatening (P1) cases to the top of the duty officer's queue in seconds — each with a reason and SOP basis — while safely deflecting routine queries. **Humans confirm; nothing auto-dismisses.**

| Metric | Baseline (FIFO) | Target |
|---|---|---|
| Time-to-first-P1 surfaced | ~90 min (anecdotal) | **< 5 sec** |
| P1 recall | unmeasured | **≥ 99%** |
| Routine deflection (no officer time) | ~0% | **≥ 50%** |
| Officer messages read per P1 found | up to ~300 | **≤ 5** |

**Success sentence:** *"In a simulated surge of 300 messages, the agent swarm surfaces every life-threatening case to the top of the duty officer's queue within seconds — each with a reason and the SOP basis — instead of being found 90 minutes deep in a FIFO queue."*

## 3. Rapid Build trail (how we got here)

- **Widen** — North-star KPI: time-to-identify the first P1 in a surge → near-zero, with ≥99% P1 recall. Key insight: this is a *triage/ranking* problem, not a chatbot problem; recall on P1 matters more than precision (bias to escalate).
- **Diagnose** — Root cause = missing danger-aware triage layer; ordering temporal not risk-based. Hypotheses: (H1) a model can classify true-urgency accurately enough to rank; (H2) the bottleneck is ordering not capacity; (H3) routine queries are safely deflectable.
- **Ideate & Converge** — 3 options scored on Impact × Feasibility × Confidence × Time-to-Value:
  - A · Process (smart intake form) — low impact, kept as a "no-regrets" framing.
  - B · Analytics/ML (urgency scoring engine) — the analytical core.
  - **C · Automation (agent swarm) — CHOSEN.** Highest impact; the only option that is literally "purely agents in GCP, deployed." B is its core; A's "Are you safe right now? Y/N" is a no-regrets add.

## 4. Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend: Next.js dashboard  → Cloud Run (or Firebase)  │
└───────────────┬─────────────────────────────────────────┘
                │  REST / SSE (streaming)
┌───────────────▼─────────────────────────────────────────┐
│  Agent backend (Python + Google ADK) → Cloud Run         │
│   ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌───────────┐   │
│   │ Intake  │→ │ Triage  │→ │Escalation│→ │ Responder │   │
│   │ Agent   │  │ Agent   │  │  Agent   │  │  Agent    │   │
│   └─────────┘  └────┬────┘  └──────────┘  └───────────┘   │
│        SOP + country feed injected into context          │
└───────────────┬─────────────────────────────────────────┘
                │  Vertex AI
        ┌───────▼────────┐      ┌──────────────┐
        │ Gemini 2.x     │      │  Firestore   │
        │ Flash (Vertex) │      │ queue + audit│
        └────────────────┘      └──────────────┘
```

**Key simplification:** the data pack is tiny (1 SOP extract + 1 country feed + ~300 messages). The SOP and feed are **injected into context** — **no vector DB / RAG infrastructure required.** This removes the most expensive and complex piece.

## 5. Components (units with one clear purpose)

Each agent has: a single responsibility, a typed input/output contract, and named dependencies.

- **Intake Agent** — *Normalize & translate.* In: raw message. Out: `{clean_text, lang, detected_location}`. Deps: Gemini Flash.
- **Triage Agent** *(the core)* — *Score true-urgency.* In: clean message + SOP + country feed (in context). Out: `{severity: P1–P4, category, confidence, reason, sop_reference}`. Deps: Gemini Flash. Bias-to-escalate on low confidence.
- **Escalation Agent** — *Rank & route.* In: scored messages. Out: queue ordered by danger; P1s with suggested action + target mission. Deps: SOP escalation thresholds.
- **Responder Agent** — *Draft safe replies for routine (P4).* In: P4 message. Out: drafted reply for one-click human confirm. Deps: Gemini Flash, SOP canned-response rules.
- **Dashboard (frontend)** — Live Triage Queue, Case Detail (reasoning trace + SOP citation + suggested action + draft + Confirm/Override), Ops scoreboard (baseline-vs-Beacon), optional Agent Trace panel.
- **Data/Eval harness** — train/holdout split of the 300 labelled messages; computes P1 recall, time-to-surface, deflection rate vs FIFO baseline. *This is the scoreboard that proves value.*

## 6. Data flow

1. **Ingest** — 300 synthetic messages stream in (simulated surge replay).
2. Intake normalizes + translates each.
3. Triage scores severity + category + confidence + reason + SOP ref.
4. Escalation ranks queue by danger; P1s float to top with action + mission.
5. Responder drafts safe replies for P4 routine queries.
6. Dashboard streams the live triage picture; officer clicks a case → reasoning, SOP basis, draft. Nothing auto-dismisses.

## 7. GCP stack & feasibility

| Layer | Service | Notes |
|---|---|---|
| Reasoning | **Gemini 2.x Flash on Vertex AI** | Fast, cheap, ideal for high-volume classification. Pro only if deeper reasoning needed. |
| Agents | **Google ADK** → **Vertex AI Agent Engine** or **Cloud Run** | Native multi-agent framework; controllable reasoning trace. |
| Orchestration/API | **Cloud Run** | Scales to zero. |
| State / queue / audit | **Firestore** (free tier) | In-memory acceptable for demo. |
| Dashboard | **Cloud Run** or **Firebase Hosting** | Streaming UI. |
| Grounding | SOP + country feed **in context** | No vector DB. |

**Cost:** ~300 messages × a few Flash calls each = a few cents per full demo run. Cloud Run + Firestore scale to zero (≈$0 idle). Build + many demo runs: **well under a few dollars**, comfortably inside a billing account / free-tier credits.

**Region:** in-region (Sensitive tier); synthetic data only; nothing leaves the boundary.

## 8. Guardrails

- Synthetic data only, in-region, no PII leaves boundary.
- **Bias-to-escalate** — false-negative (missed P1) is the catastrophic error.
- **No auto-dismiss** — system re-ranks/recommends; humans confirm.
- Every decision **logged + explainable** (reason + SOP citation must exist).
- Fallback: low model confidence → default to higher severity + flag for human.

## 9. Acceptance criteria (numeric)

- P1 recall ≥ 99% on holdout set.
- Time-to-first-P1 < 5s.
- Zero P1 auto-dismissed.
- Every P1 card shows a reason + SOP reference.

## 10. Observability

P1 recall/precision, per-message latency (SLO < 3s), confidence distribution, hallucination check (SOP citation must exist), false-negative audit log.

## 11. Build phases (detail goes to the implementation plan)

1. **GCP setup** — confirm project, enable Vertex AI + Cloud Run + Firestore APIs, set region, auth.
2. **Data layer** — load 300 labelled messages + SOP + feed; build train/holdout split (the scoreboard).
3. **Triage Agent first + prove recall** — riskiest assumption (H1); test on holdout *before* building the rest.
4. **Wrap the swarm** — Intake → Triage → Escalation → Responder as ADK agents with handoffs.
5. **Dashboard** — live queue + case detail + scoreboard, streaming.
6. **Deploy** — backend + frontend to Cloud Run; live surge replay.
7. **Measure** — baseline-vs-Beacon scoreboard. That delta is the pitch.

## 12. Risks & mitigations

- **Missed P1 (false-negative)** → bias-to-escalate, human confirm, never auto-dismiss; audit every miss.
- **Over-automation distrust** → copilot framing, visible reasoning + SOP citation.
- **2-day scope creep** → hold to 4 core agents; Vertex AI Agent Builder (managed) is the fallback if time gets tight.
- **Recall not achievable with Flash** → escalate hard cases to Gemini Pro; tune prompt with SOP examples.

## 13. Out of scope (YAGNI)

Real ministry system integration, real PII, vector DB/RAG, multilingual beyond what Gemini handles natively in-context, authentication/RBAC beyond demo, mobile apps.

## 14. Open questions

- Exact schema/format of the provided 300-message data pack, SOP extract, and country feed (resolve at Phase 2).
- ADK deployment target: Vertex AI Agent Engine vs Cloud Run (decide at Phase 1 based on trace-visibility needs).
- Which GCP project + region to use.
