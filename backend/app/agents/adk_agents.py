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

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

from app.agents.triage import SYSTEM_INSTRUCTION
from app.config import TRIAGE_MODEL
from app.data_loader import load_dataset
from app.schemas import TriageResult

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


def triage_via_adk(text: str) -> TriageResult:
    raw = asyncio.run(_invoke(triage_agent, text))
    return TriageResult.model_validate_json(raw)


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
    _smoke_test()
