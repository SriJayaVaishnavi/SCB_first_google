# Beacon — Project Context

This file preserves the full context behind the Beacon prototype so any future session can resume.

## The engagement
**TCS × Singapore MFA "AI Immersion Day"** — a Rapid Build, one-day hands-on session where an MFA delegation pairs with TCS AI-native engineers to build working AI prototypes against the ministry's real pain points, live.

**Who's in the room:** a build/transform/service-delivery delegation — Solutions Architect, Info Tech lead, DG Information Management, Deputy DG + Designer from Central Transformation & Strategy, and the triple-hatted 2nd PS (Development) who owns the whole-of-government digital pipeline (MFA + MDDI + Smart Nation/PMO). The immersion feeds national digital capability, not just one ministry.

## The chosen challenge — Card 01 "The Crowded Hotline"
- **Domain:** Consular · Triage · Pod P1 (Consular & Crisis). Pod P1's *primary* build.
- **Statement:** "During a crisis, a surge of *routine* queries buries the citizens who are in immediate physical danger."
- **What's happening:** When a disaster/geopolitical shock hits, the 24/7 Duty Office is flooded with repetitive transit/travel-status questions; that volume delays identifying who needs urgent evacuation or medical help — the hardest cases are the easiest to miss in a full queue.
- **Why it matters now:** Hat Yai floods, Middle-East travel disruptions show the tempo. Rising travel + overlapping incidents strain a finite team; minutes matter most when the queue is longest.
- **Synthetic data pack (Restricted/Sensitive · Normal tier):** ~300 mixed inbound messages (true-urgency labelled) · 1 duty-officer SOP extract · 1 live country-conditions feed.
- **Who feels the pain:** Consular Duty Officer · citizens in high-risk situations.

## Goal set by user
Build a prototype for this challenge **purely by creating agents in GCP**, and it must be **deployed** (not a mockup). User has a GCP project with billing + Vertex AI access.

## Method
We are running the **TCS Rapid Build Squad methodology** (from `Stockland-RapidBuild.pptx` — that deck is the methodology template; the Stockland cards are just example payload). Steps: Learn → Widen → Diagnose → Ideate & Converge → Brief → Build.

### Rapid Build outputs
- **Step 0 Learn** — the consolidated dossier serves as the pre-generated deep research.
- **Step 1 Widen** — North-star KPI: time-to-identify first P1 in a surge → near-zero with ≥99% P1 recall. Top pain chosen: **"P1 cases drown in routine volume."**
- **Step 2 Diagnose** — Root cause: no danger-aware triage layer between intake and the human queue; ordering is temporal, not risk-based. Hypotheses H1 (model can classify true-urgency), H2 (bottleneck is ordering not capacity), H3 (routine deflectable).
- **Step 3 Ideate & Converge** — 3 options (Process / Analytics-ML / Automation). Chosen: **Option C — Triage Agent Swarm** (highest impact; the literal "agents in GCP, deployed" story).
- **Step 4 Brief** — see the design spec.

## Decisions locked
- Product: **Beacon — Crisis Triage Agent Swarm** (name changeable).
- Stack: **Google ADK + Cloud Run + Vertex AI Gemini 2.x Flash + Firestore**; Next.js dashboard.
- SOP + country feed injected into context — **no vector DB / RAG**.
- Cost: a few cents per demo run; well under a few dollars total.
- 4 core agents: Intake → Triage → Escalation → Responder, + dashboard + eval harness.

## Source files (on user's Desktop)
- `MFA_SG_AI_Immersion_Consolidated_Dossier 2.md` — the dossier / deep research.
- `MFA-Singapore-AI-Immersion-Day 2.html` — 22-slide deck with the 9 challenge cards.
- `demo1.png` — screenshot of Card 01 "The Crowded Hotline".
- `Stockland-RapidBuild.pptx` — the TCS Rapid Build Squad methodology deck (prompt framework).

## Status
Design spec written: `docs/superpowers/specs/2026-06-17-beacon-crisis-triage-design.md`.
Next: user reviews spec → writing-plans skill → implementation.
