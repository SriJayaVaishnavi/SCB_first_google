# Beacon — Crisis Triage Agent Swarm

A GCP-native multi-agent prototype for the **MFA Singapore "AI Immersion Day"** — Challenge Card 01, *"The Crowded Hotline"* (consular crisis triage).

During a crisis, a surge of routine queries buries the citizens in immediate physical danger. Beacon is a swarm of agents that reads every inbound message, scores true-urgency, and floats life-threatening cases to the top of the duty officer's queue in seconds — each with a reason and the SOP basis — while safely deflecting routine queries. Humans confirm; nothing auto-dismisses.

## Layout
- `docs/superpowers/specs/` — design spec(s).
- `context/` — full project context for resuming work.

## Stack
Google ADK · Vertex AI (Gemini 2.x Flash) · Cloud Run · Firestore · Next.js dashboard.

## Status
Design complete. See `context/CONTEXT.md` and the latest spec in `docs/superpowers/specs/`.
