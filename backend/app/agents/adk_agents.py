"""ADK agents for the Beacon swarm.

A real Google ADK swarm (Intake → Triage → Escalation/Responder). Runs in two modes,
selected by GOOGLE_GENAI_USE_VERTEXAI in backend/.env (see app/config.py):
  • aistudio — Gemini Developer API via GOOGLE_API_KEY (active now; Vertex quota drained)
  • vertex   — Gemini on Vertex AI via the beacon-vertex SA (tomorrow; flip the one flag)
Both paths stay live — switching is a one-line .env edit, no code changes, no exports.

    cd backend && python -m app.agents.adk_agents          # full swarm demo
    cd backend && python -m app.agents.adk_agents smoke     # triage-only smoke test
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

from pydantic import BaseModel

from app.agents.triage import SYSTEM_INSTRUCTION
from app.config import GROQ_MODEL, MODE, TRIAGE_MODEL
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


def _build_model():
    """The model object every agent runs on, per MODE.

    Gemini (vertex/aistudio) takes a plain model-id string; ADK routes Vertex vs the
    Developer API from env. Groq (a temporary off-GCP dev backend) goes through ADK's
    LiteLLM bridge — imported lazily so litellm is only needed in groq mode.
    """
    if MODE == "groq":
        from google.adk.models.lite_llm import LiteLlm

        return LiteLlm(model=GROQ_MODEL)
    return TRIAGE_MODEL


_MODEL = _build_model()
# Gemini enforces output_schema natively (controlled generation); Llama-via-LiteLLM does
# not, so in groq mode we drop output_schema, inject the JSON shape into the prompt, and
# parse tolerantly (_extract_json). Keeps one agent definition working across all modes.
_NATIVE_SCHEMA = MODE != "groq"


def _schema_hint(model_cls: type[BaseModel]) -> str:
    """A prompt instruction telling a non-Gemini model exactly what JSON to emit."""
    fields = ", ".join(
        f'"{name}": <{(f.annotation.__name__ if hasattr(f.annotation, "__name__") else f.annotation)}>'
        f"  // {f.description or ''}".rstrip()
        for name, f in model_cls.model_fields.items()
    )
    return (
        "Respond with ONLY a single JSON object (no markdown fences, no prose) of the form:\n"
        f"{{{fields}}}"
    )


def _mk_agent(name: str, description: str, instruction: str,
              schema: type[BaseModel], output_key: str) -> LlmAgent:
    kwargs = dict(name=name, model=_MODEL, description=description, output_key=output_key)
    if _NATIVE_SCHEMA:
        kwargs["instruction"] = instruction
        kwargs["output_schema"] = schema
    else:
        kwargs["instruction"] = instruction + "\n\n" + _schema_hint(schema)
    return LlmAgent(**kwargs)

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

triage_agent = _mk_agent(
    name="triage_agent",
    description="Scores one consular message's true urgency (P1–P4) using the SOP.",
    instruction=TRIAGE_INSTRUCTION,
    schema=TriageResult,
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
intake_agent = _mk_agent(
    name="intake_agent",
    description="Normalises and translates one raw inbound message into clean English.",
    instruction=INTAKE_INSTRUCTION,
    schema=IntakeResult,
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
escalation_agent = _mk_agent(
    name="escalation_agent",
    description="Routes an urgent case to a mission with a concrete suggested action.",
    instruction=ESCALATION_INSTRUCTION,
    schema=EscalationDecision,
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
responder_agent = _mk_agent(
    name="responder_agent",
    description="Drafts a safe, human-confirmed reply for routine queries.",
    instruction=RESPONDER_INSTRUCTION,
    schema=ResponderDraft,
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
    """True for 429s — surfaced either as genai ClientError or ADK's wrapper."""
    blob = f"{type(exc).__name__}: {exc}"
    return "429" in blob or "RESOURCE_EXHAUSTED" in blob or "ResourceExhausted" in blob


def _is_overloaded(exc: Exception) -> bool:
    """True for transient backend overload (503 UNAVAILABLE / 'high demand') — retry it."""
    blob = f"{type(exc).__name__}: {exc}"
    return "503" in blob or "UNAVAILABLE" in blob or "high demand" in blob or "overloaded" in blob


def _is_retryable(exc: Exception) -> bool:
    """Retry both rate-limits (429) and transient overload (503)."""
    return _is_rate_limit(exc) or _is_overloaded(exc)


# Live API-call meter — every _invoke attempt (incl. retries) hits Vertex once and burns
# quota. Surfaced in the demo so we always see how many LLM calls a run actually made.
_api_calls = {"total": 0, "by_agent": {}}


def _count_call(agent_name: str) -> None:
    _api_calls["total"] += 1
    _api_calls["by_agent"][agent_name] = _api_calls["by_agent"].get(agent_name, 0) + 1


# Workflow-tunable knobs, read from backend/.env (no terminal export needed):
#   CALL_INTERVAL_SEC — min gap between API calls; paces a tight per-MINUTE quota so the
#                       swarm grinds through like the patient Phase-3 eval did.
#   MAX_RETRIES       — backoff attempts per call; set low (e.g. 2) when a per-DAY cap is
#                       drained so we stop wasting requests on doomed retries.
_CALL_INTERVAL = float(os.getenv("CALL_INTERVAL_SEC", "0"))
_MAX_RETRIES = int(os.getenv("MAX_RETRIES", "6"))
_last_call = {"t": 0.0}


class QuotaExhausted(RuntimeError):
    """A Vertex 429 that survived full backoff — points to a per-DAY cap, not per-minute."""


async def _throttle() -> None:
    """Enforce CALL_INTERVAL between API calls (process-wide, single-loop)."""
    if _CALL_INTERVAL <= 0:
        return
    wait = _CALL_INTERVAL - (time.monotonic() - _last_call["t"])
    if wait > 0:
        await asyncio.sleep(wait)
    _last_call["t"] = time.monotonic()


async def _run_async(agent: LlmAgent, text: str, *, max_retries: int | None = None) -> str:
    """Invoke an ADK agent with pacing + exponential backoff on Vertex 429s.

    Mirrors the direct-genai eval path's resilience. Async so the whole swarm shares one
    event loop (per-call asyncio.run() orphaned the genai HTTP client cleanup → "Event
    loop is closed" noise, and would break the async FastAPI handlers in Phase 5).

    On a 429 we back off (4→60s). If it survives every retry, we raise QuotaExhausted:
    a per-minute limit would have reset inside that window, so a hard failure means the
    per-DAY cap is drained — the caller stops the run fast instead of grinding on.
    """
    retries = max_retries if max_retries is not None else _MAX_RETRIES
    delay = 4.0
    for attempt in range(retries):
        await _throttle()
        try:
            _count_call(agent.name)
            return await _invoke(agent, text)
        except Exception as exc:  # noqa: BLE001 — narrowed via _is_retryable below
            if not _is_retryable(exc):
                raise
            if attempt < retries - 1:
                kind = "429 quota" if _is_rate_limit(exc) else "503 overloaded"
                print(f"    [{kind} on {agent.name}; retry in {delay:.0f}s "
                      f"({attempt + 1}/{retries})]")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            if _is_rate_limit(exc):
                raise QuotaExhausted(
                    f"{agent.name}: 429 survived {retries} retries (~120s of backoff). "
                    "Per-minute quota would reset within that window, so this is most likely "
                    "a per-DAY cap drained by today's runs. Check Console → Quotas; it "
                    "resets ~midnight US-Pacific, or request a bump. (Tune MAX_RETRIES / "
                    "CALL_INTERVAL_SEC in .env.)"
                ) from exc
            raise RuntimeError(
                f"{agent.name}: backend overloaded (503) after {retries} retries — the model "
                "is busy (transient). Wait a minute and rerun; pacing via CALL_INTERVAL_SEC helps."
            ) from exc
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


def _extract_json(raw: str) -> str:
    """Pull the JSON object out of a model reply. Gemini returns clean JSON, but Llama
    (groq) may wrap it in ```json fences or stray prose — strip those before validating."""
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()
    i, j = s.find("{"), s.rfind("}")
    return s[i:j + 1] if i != -1 and j > i else s


def _parse(model_cls, raw: str):
    return model_cls.model_validate_json(_extract_json(raw))


# Async agent calls (the swarm's building blocks).
async def _intake(text: str) -> IntakeResult:
    # Translation is the only thing Intake adds, so skip the LLM for already-English text:
    # plain-ASCII ⇒ English/Latin (no call); non-ASCII (Thai/Tamil/Arabic/…) ⇒ translate.
    # Saves one call per English message — most of the surge — without losing the step.
    if text.isascii():
        return IntakeResult(normalized_text=text.strip(), language="en", translated=False)
    return _parse(IntakeResult, await _run_async(intake_agent, text))


async def _triage(text: str) -> TriageResult:
    return _parse(TriageResult, await _run_async(triage_agent, text))


async def _escalation(text: str, triage: TriageResult) -> EscalationDecision:
    raw = await _run_async(escalation_agent, _escalation_prompt(text, triage))
    return _parse(EscalationDecision, raw)


async def _responder(text: str, triage: TriageResult) -> ResponderDraft:
    raw = await _run_async(responder_agent, _responder_prompt(text, triage))
    return _parse(ResponderDraft, raw)


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


async def stream_swarm(messages: list[dict], *, pace_sec: float = 0.0):
    """Async generator: yield each SwarmCase the moment it's triaged (for SSE).

    Unsorted — emit order is arrival order; the dashboard ranks the live queue by danger.
    Lets the UI watch the surge stream in and P1s jump to the top in real time.
    """
    for i, m in enumerate(messages):
        if i and pace_sec:
            await asyncio.sleep(pace_sec)
        yield await _swarm_case(m)


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

    # Order so a small slice (batch_size) still shows all 3 handoffs with the fewest
    # calls: P1→Escalation, P4→Responder, non-EN→translation, then P2, P3 to fill out.
    take(lambda m: m.get("true_label") == "P1")
    take(lambda m: m.get("true_label") == "P4")
    before = len(batch)
    take(lambda m: m.get("lang") != "en")  # real non-English message if the data has one…
    if len(batch) == before:
        batch.append(_DEMO_NON_EN)          # …else the synthetic Thai one
    take(lambda m: m.get("true_label") == "P2")
    take(lambda m: m.get("true_label") == "P3")
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

    print(f"google-adk version: {getattr(google.adk, '__version__', 'unknown')}  "
          f"| mode: {MODE.upper()} | model: {TRIAGE_MODEL}\n")
    batch = _pick_demo_batch(_ds.all_messages)
    if batch_size is None:
        batch_size = int(os.getenv("DEMO_BATCH_SIZE", str(len(batch))))
    batch = batch[:batch_size]
    pace = float(os.getenv("DEMO_PACE_SEC", "0"))
    # Call budget so we know the cost before we spend it: Triage (1) + a handoff (1, none
    # for P3) + Intake only for non-English text (English is a free local pass-through).
    est = sum(
        1
        + (0 if m.get("true_label") == "P3" else 1)
        + (0 if m.get("text", "").isascii() else 1)
        for m in batch
    )
    print(f"Running the Beacon swarm over {len(batch)} sample messages "
          f"(pace {pace:.0f}s). Estimated API calls (no retries): ~{est}…")

    try:
        queue = run_swarm(batch, pace_sec=pace)
    except QuotaExhausted as exc:
        print(f"\n[!] Stopped after {_api_calls['total']} API calls — {exc}")
        print(f"    API calls by agent: {_api_calls['by_agent']}")
        print("    To stay on Vertex: wait for the daily reset or bump the quota. To grind")
        print("    through a per-minute limit, pace calls via .env, e.g. CALL_INTERVAL_SEC=7.")
        return
    except Exception as exc:  # noqa: BLE001
        if _is_retryable(exc):
            print(f"\n[!] Stopped after {_api_calls['total']} API calls: {exc}")
            print(f"    API calls by agent: {_api_calls['by_agent']}")
            return
        raise

    _print_queue(queue)
    print("Swarm demo OK — Intake→Triage→Escalation/Responder, ranked queue + trace.")
    print(f"API calls made: {_api_calls['total']} (by agent: {_api_calls['by_agent']})")


def _smoke_test() -> None:
    import google.adk

    print(f"google-adk version: {getattr(google.adk, '__version__', 'unknown')}  "
          f"| mode: {MODE.upper()} | model: {TRIAGE_MODEL}\n")
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
