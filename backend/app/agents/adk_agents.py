"""ADK agents for the Beacon swarm.

Starts with the Triage agent rebuilt as a real Google ADK LlmAgent. Run this module
directly as a smoke test to confirm the ADK API in the current environment before we
expand to the full swarm. Config (project, location, SA key path) comes from
backend/.env — no terminal `export` needed:

    cd backend && python -m app.agents.adk_agents
"""
from __future__ import annotations

import asyncio
import json
import os

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agents.triage import SYSTEM_INSTRUCTION
from app.config import TRIAGE_MODEL
from app.data_loader import load_dataset
from app.schemas import (
    EscalationDecision,
    IntakeResult,
    ResponderDraft,
    Severity,
    SwarmCase,
    TriageResult,
)

APP_NAME = "beacon"

# Bake the SOP + country feed into the agent instruction (they're small and static),
# so each inbound message is just the citizen's text — clean agent semantics.
_ds = load_dataset()
TRIAGE_INSTRUCTION = (
    SYSTEM_INSTRUCTION
    + "\n\n## SOP (authoritative triage rules)\n"
    + _ds.sop
    + "\n\n## Live country-conditions feed\n"
    + json.dumps(_ds.country_feed)
    + "\n\nReturn ONLY the structured triage verdict for the message you receive."
)

triage_agent = LlmAgent(
    name="triage_agent",
    model=TRIAGE_MODEL,
    description="Scores one consular message's true urgency (P1–P4) using the SOP.",
    instruction=TRIAGE_INSTRUCTION,
    output_schema=TriageResult,
    output_key="triage_result",
)

# --- Intake: normalise/translate each raw inbound message ----------------------------
INTAKE_INSTRUCTION = (
    "You are the Intake Agent for a national foreign ministry's 24/7 consular Duty Office "
    "crisis hotline. You receive ONE raw inbound citizen message (any language, possibly "
    "messy or with typos).\n\n"
    "Produce a clean ENGLISH normalisation of it. Detect the original language. If it is not "
    "English, translate it faithfully into English and set translated=true; if it is already "
    "English, return a lightly cleaned copy and set translated=false. NEVER add, drop, or infer "
    "facts — preserve every detail relevant to urgency (location, injuries, numbers, names).\n\n"
    "Return ONLY the structured intake result."
)
intake_agent = LlmAgent(
    name="intake_agent",
    model=TRIAGE_MODEL,
    description="Normalises and translates one raw inbound message into clean English.",
    instruction=INTAKE_INSTRUCTION,
    output_schema=IntakeResult,
    output_key="intake_result",
)

# --- Escalation: route urgent (P1/P2) cases to a mission with a concrete action ------
ESCALATION_INSTRUCTION = (
    "You are the Escalation Agent for a consular Duty Office during a crisis. You receive ONE "
    "triaged URGENT case (its severity, category, triage reason, SOP reference, and the citizen's "
    "message). Decide the single most appropriate NEXT ACTION for the duty officer and WHICH "
    "mission/desk to route it to. Use the live country-conditions feed below to pick the right "
    "mission. Keep the action concrete, immediate, and SOP-aligned (e.g. 'Call citizen, confirm "
    "GPS pin, task local rescue liaison'). Do NOT contact anyone yourself — you only advise; a "
    "human duty officer confirms.\n\n## Live country-conditions feed\n"
    + json.dumps(_ds.country_feed)
    + "\n\nReturn ONLY the structured escalation decision."
)
escalation_agent = LlmAgent(
    name="escalation_agent",
    model=TRIAGE_MODEL,
    description="Routes an urgent case to a mission with a concrete suggested action.",
    instruction=ESCALATION_INSTRUCTION,
    output_schema=EscalationDecision,
    output_key="escalation_decision",
)

# --- Responder: draft a safe reply for routine (P4) queries --------------------------
RESPONDER_INSTRUCTION = (
    "You are the Responder Agent for a consular Duty Office. You receive ONE ROUTINE (P4) "
    "consular query. Draft a SAFE, factual, empathetic reply the duty officer can review, confirm, "
    "and send. Use ONLY facts present in the SOP and the country-conditions feed below. NEVER "
    "promise outcomes, give medical/legal/travel-safety guarantees, or invent details; if the "
    "answer is uncertain, advise the citizen to contact the nearest mission. Keep it short and "
    "clear. This is a DRAFT pending human confirmation — nothing is sent automatically.\n\n"
    "## SOP\n" + _ds.sop + "\n\n## Live country-conditions feed\n"
    + json.dumps(_ds.country_feed)
    + "\n\nReturn ONLY the structured draft reply."
)
responder_agent = LlmAgent(
    name="responder_agent",
    model=TRIAGE_MODEL,
    description="Drafts a safe, human-confirmed reply for routine queries.",
    instruction=RESPONDER_INSTRUCTION,
    output_schema=ResponderDraft,
    output_key="responder_draft",
)


async def _invoke(agent: LlmAgent, text: str) -> str:
    """Run an ADK agent on one message; return the final response text."""
    runner = InMemoryRunner(agent=agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(app_name=APP_NAME, user_id="duty")
    content = types.Content(role="user", parts=[types.Part.from_text(text=text)])
    final = ""
    async for event in runner.run_async(
        user_id="duty", session_id=session.id, new_message=content
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text or ""
    return final


def _is_rate_limit(exc: Exception) -> bool:
    """True for Vertex 429s — surfaced either as genai ClientError or ADK's wrapper."""
    blob = f"{type(exc).__name__}: {exc}"
    return "429" in blob or "RESOURCE_EXHAUSTED" in blob or "ResourceExhausted" in blob


async def _run_async(agent: LlmAgent, text: str, *, max_retries: int = 6) -> str:
    """Invoke an ADK agent with exponential backoff on Vertex 429s.

    ADK does its own brief retries then raises; new-project Gemini quota is low, so we
    back off and retry here (mirrors the direct-genai path's _generate_with_backoff).
    Async so the whole swarm shares one event loop (per-call asyncio.run() left the
    genai HTTP client's cleanup orphaned → "Event loop is closed" noise, and would
    break the async FastAPI handlers in Phase 5).
    """
    delay = 4.0
    for attempt in range(max_retries):
        try:
            return await _invoke(agent, text)
        except Exception as exc:  # noqa: BLE001 — narrowed via _is_rate_limit below
            if _is_rate_limit(exc) and attempt < max_retries - 1:
                print(f"    [429 rate-limited on {agent.name}; retrying in {delay:.0f}s…]")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise
    raise RuntimeError("unreachable")  # pragma: no cover


def _escalation_prompt(text: str, triage: TriageResult) -> str:
    return (
        f"Severity: {triage.severity.value}\n"
        f"Category: {triage.category}\n"
        f"Triage reason: {triage.reason}\n"
        f"SOP reference: {triage.sop_reference}\n"
        f'Citizen message: """{text}"""'
    )


def _responder_prompt(text: str, triage: TriageResult) -> str:
    return f'Routine query (category {triage.category}):\n"""{text}"""'


# Async agent calls (the swarm's building blocks).
async def _intake(text: str) -> IntakeResult:
    return IntakeResult.model_validate_json(await _run_async(intake_agent, text))


async def _triage(text: str) -> TriageResult:
    return TriageResult.model_validate_json(await _run_async(triage_agent, text))


async def _escalation(text: str, triage: TriageResult) -> EscalationDecision:
    raw = await _run_async(escalation_agent, _escalation_prompt(text, triage))
    return EscalationDecision.model_validate_json(raw)


async def _responder(text: str, triage: TriageResult) -> ResponderDraft:
    raw = await _run_async(responder_agent, _responder_prompt(text, triage))
    return ResponderDraft.model_validate_json(raw)


# Sync one-shot wrappers (smoke test / external callers running outside a loop).
def triage_via_adk(text: str) -> TriageResult:
    return asyncio.run(_triage(text))


def intake_via_adk(text: str) -> IntakeResult:
    return asyncio.run(_intake(text))


def escalation_via_adk(text: str, triage: TriageResult) -> EscalationDecision:
    return asyncio.run(_escalation(text, triage))


def responder_via_adk(text: str, triage: TriageResult) -> ResponderDraft:
    return asyncio.run(_responder(text, triage))


async def _swarm_case(m: dict) -> SwarmCase:
    text = m.get("text", "")
    trace: list[str] = []

    intake = await _intake(text)
    trace.append(f"Intake → lang={intake.language}, translated={intake.translated}")

    triage = await _triage(intake.normalized_text)
    trace.append(
        f"Triage → {triage.severity.value} {triage.category} "
        f"(conf {triage.confidence:.2f}, {triage.sop_reference})"
    )

    escalation: EscalationDecision | None = None
    responder: ResponderDraft | None = None
    if triage.severity in (Severity.P1, Severity.P2):
        escalation = await _escalation(text, triage)
        trace.append(f"Escalation → {escalation.target_mission}: {escalation.suggested_action}")
    elif triage.severity is Severity.P4:
        responder = await _responder(text, triage)
        trace.append("Responder → drafted reply (awaiting human confirm)")
    else:  # P3
        trace.append("Hold → P3 queued for officer assistance")

    return SwarmCase(
        id=m.get("id", ""),
        channel=m.get("channel", ""),
        original_text=text,
        intake=intake,
        triage=triage,
        escalation=escalation,
        responder=responder,
        trace=trace,
    )


async def run_swarm_async(messages: list[dict], *, pace_sec: float = 0.0) -> list[SwarmCase]:
    """Run the full Beacon swarm over a batch of inbound messages (one event loop).

    Per message: Intake → Triage, then a danger-aware handoff —
      • P1/P2 → Escalation (route to a mission with a suggested action)
      • P3    → held for officer assistance
      • P4    → Responder (drafts a safe reply for human confirmation)
    Returns the cases ranked by danger (P1 first, ties broken by confidence), each
    carrying an ordered agent-handoff trace. Nothing is auto-dismissed.

    pace_sec inserts a gap between messages to stay under a tight per-minute quota.
    """
    cases: list[SwarmCase] = []
    for i, m in enumerate(messages):
        if i and pace_sec:
            await asyncio.sleep(pace_sec)
        cases.append(await _swarm_case(m))
    cases.sort(key=lambda c: (c.triage.severity.rank, -c.triage.confidence))
    return cases


def run_swarm(messages: list[dict], *, pace_sec: float = 0.0) -> list[SwarmCase]:
    """Sync entrypoint: run the swarm in a single event loop."""
    return asyncio.run(run_swarm_async(messages, pace_sec=pace_sec))


# The synthetic dataset is English-only, so inject one non-English message to exercise
# the Intake translation path in the demo. Thai P1 (medical emergency in Hat Yai):
# "My mother can't breathe and we're trapped by the flood in Hat Yai — please help now."
_DEMO_NON_EN = {
    "id": "MSG-DEMO-TH",
    "text": "แม่หายใจไม่ออก เราติดอยู่กับน้ำท่วมที่หาดใหญ่ ช่วยด้วยเดี๋ยวนี้",
    "channel": "whatsapp",
    "lang": "th",
    "true_label": "P1",
}


def _pick_demo_batch(messages: list[dict]) -> list[dict]:
    """A small, representative batch: one of each P1–P4 plus a non-English message."""
    batch: list[dict] = []
    seen: set[str] = set()

    def take(predicate) -> None:
        for m in messages:
            if m["id"] not in seen and predicate(m):
                batch.append(m)
                seen.add(m["id"])
                return

    for label in ("P1", "P2", "P3", "P4"):
        take(lambda m, lbl=label: m.get("true_label") == lbl)
    # Show Intake translation: a real non-English message if the data has one, else the synthetic one.
    before = len(batch)
    take(lambda m: m.get("lang") != "en")
    if len(batch) == before:
        batch.append(_DEMO_NON_EN)
    return batch


def _print_queue(queue: list[SwarmCase]) -> None:
    print(f"\n=== Beacon swarm — ranked queue ({len(queue)} cases) ===\n")
    for i, c in enumerate(queue, 1):
        print(f"#{i}  [{c.triage.severity.value}] conf={c.triage.confidence:.2f}  "
              f"{c.id} ({c.channel})  cat={c.triage.category}")
        print(f"    msg : {c.original_text}")
        if c.escalation:
            print(f"    act : {c.escalation.target_mission} — {c.escalation.suggested_action}")
        if c.responder:
            print(f"    draft: {c.responder.draft_reply}")
        print(f"    trace: {' | '.join(c.trace)}\n")


def _swarm_demo(batch_size: int | None = None) -> None:
    """Run the swarm over a small batch and print the ranked queue.

    DEMO_BATCH_SIZE caps the message count (handy under a tight quota); DEMO_PACE_SEC
    inserts a gap between messages. Degrades gracefully: on a quota exhaustion it prints
    what completed and a clear next step instead of a raw traceback.
    """
    import google.adk

    print(f"google-adk version: {getattr(google.adk, '__version__', 'unknown')}\n")
    batch = _pick_demo_batch(_ds.all_messages)
    if batch_size is None:
        batch_size = int(os.getenv("DEMO_BATCH_SIZE", str(len(batch))))
    batch = batch[:batch_size]
    pace = float(os.getenv("DEMO_PACE_SEC", "0"))
    print(f"Running the Beacon swarm over {len(batch)} sample messages "
          f"(pace {pace:.0f}s)…")

    try:
        queue = run_swarm(batch, pace_sec=pace)
    except Exception as exc:  # noqa: BLE001
        if _is_rate_limit(exc):
            print("\n[!] Vertex quota (429) exhausted before the batch finished.")
            print("    The swarm logic is fine — this is a quota wall. Options:")
            print("    • request a gemini-2.5-flash quota bump in us-central1, or")
            print("    • retry with a smaller/paced batch, e.g.:")
            print("        DEMO_BATCH_SIZE=2 DEMO_PACE_SEC=20 python -m app.agents.adk_agents")
            return
        raise

    _print_queue(queue)
    print("Swarm demo OK — Intake→Triage→Escalation/Responder with ranked queue + trace.")


def _smoke_test() -> None:
    import google.adk

    print(f"google-adk version: {getattr(google.adk, '__version__', 'unknown')}\n")
    samples = [
        "We are trapped on the roof, water is rising and my child can't swim. Help now!",
        "Is Hat Yai airport open today? Just planning my trip.",
    ]
    for s in samples:
        r = triage_via_adk(s)
        print(f"[{r.severity.value}] conf={r.confidence:.2f} sop={r.sop_reference}")
        print(f"   msg: {s}")
        print(f"   why: {r.reason}\n")
    print("ADK smoke test OK — ready to build the full swarm.")


if __name__ == "__main__":
    # `python -m app.agents.adk_agents`        → full swarm demo on a small batch
    # `python -m app.agents.adk_agents 2`      → swarm demo capped to 2 messages
    # `python -m app.agents.adk_agents smoke`  → just the Triage smoke test
    import sys

    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "smoke":
        _smoke_test()
    else:
        _swarm_demo(batch_size=int(arg) if arg.isdigit() else None)
