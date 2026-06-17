"""Beacon API — serves the duty-officer dashboard (Phase 5).

Endpoints:
  GET  /                  — health + active mode.
  POST /simulate?n=12     — replay a surge of n messages through the swarm; Server-Sent
                            Events stream each triaged case as it lands (the dashboard
                            watches the queue fill and P1s jump to the top live).
  GET  /queue             — current ranked queue (P1 first) + ops scoreboard stats.
  POST /case/{id}/confirm — duty officer confirms or overrides a case (human-in-the-loop;
                            nothing is auto-dismissed).
  POST /reset             — clear the in-memory queue.

Run (Cloud Shell, config from backend/.env — no exports):
    cd backend && uvicorn app.api:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents.adk_agents import _api_calls, stream_swarm
from app.config import MODE, TRIAGE_MODEL
from app.data_loader import load_dataset

app = FastAPI(title="Beacon — Crisis Triage API")
# Open CORS for the dev dashboard (Next.js on :3000). Tighten before any public deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_ds = load_dataset()
_RANK = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}

# In-memory queue: id -> case dict (+ confirmed / officer fields). Resets on each /simulate.
QUEUE: dict[str, dict] = {}

# Illustrative FIFO handling time per message, for the baseline-vs-Beacon scoreboard.
FIFO_MIN_PER_MSG = 1.5


class ConfirmRequest(BaseModel):
    action: str = "confirm"           # "confirm" | "override"
    override_severity: str | None = None  # e.g. "P1" when action == "override"
    note: str | None = None


def _simulate_batch(n: int) -> list[dict]:
    """A realistic surge slice: a few real emergencies buried in routine volume,
    emitted in arrival order so the dashboard shows P1s surfacing out of the noise."""
    by: dict[str, list[dict]] = {"P1": [], "P2": [], "P3": [], "P4": []}
    for m in _ds.all_messages:
        by[m["true_label"]].append(m)
    picked = by["P1"][:2] + by["P2"][:1] + by["P3"][:2] + by["P4"][: max(0, n - 5)]
    picked = picked[:n]
    picked.sort(key=lambda m: m.get("arrival_offset_sec", 0.0))  # surge = temporal order
    return picked


def _ranked() -> list[dict]:
    return sorted(
        QUEUE.values(),
        key=lambda c: (_RANK.get(c["triage"]["severity"], 9), -c["triage"]["confidence"]),
    )


def _stats() -> dict:
    cases = list(QUEUE.values())
    pred = {s: 0 for s in ("P1", "P2", "P3", "P4")}
    for c in cases:
        pred[c["triage"]["severity"]] = pred.get(c["triage"]["severity"], 0) + 1

    # FIFO: how many messages a duty officer clears (in arrival order) before reaching the
    # first true emergency — vs Beacon, which floats it to the top immediately.
    arrival = sorted(cases, key=lambda c: c.get("arrival_offset_sec", 0.0))
    fifo_pos = next((i for i, c in enumerate(arrival) if c["triage"]["severity"] == "P1"), None)
    return {
        "total": len(cases),
        "predicted": pred,
        "p1_count": pred["P1"],
        "confirmed": sum(1 for c in cases if c.get("confirmed")),
        "fifo_first_p1_position": fifo_pos,
        "fifo_first_p1_wait_min": round((fifo_pos or 0) * FIFO_MIN_PER_MSG, 1),
        "beacon_first_p1": "top of queue, seconds",
        "api_calls": _api_calls["total"],
    }


@app.get("/")
def health() -> dict:
    return {"status": "ok", "mode": MODE, "model": TRIAGE_MODEL, "queued": len(QUEUE)}


@app.get("/queue")
def get_queue() -> dict:
    return {"cases": _ranked(), "stats": _stats()}


@app.post("/reset")
def reset() -> dict:
    QUEUE.clear()
    return {"status": "cleared"}


@app.post("/simulate")
async def simulate(n: int = 12, pace_sec: float = 0.0):
    """Stream a surge of n messages through the swarm as Server-Sent Events."""
    QUEUE.clear()
    batch = _simulate_batch(n)

    async def gen():
        yield _sse("start", {"count": len(batch), "mode": MODE, "model": TRIAGE_MODEL})
        idx = 0
        try:
            async for case in stream_swarm(batch, pace_sec=pace_sec):
                d = case.model_dump(mode="json")
                d["arrival_offset_sec"] = batch[idx].get("arrival_offset_sec", 0.0)
                d["true_label"] = batch[idx].get("true_label")  # for the demo scoreboard
                d["confirmed"] = False
                QUEUE[d["id"]] = d
                idx += 1
                yield _sse("case", d)
        except Exception as exc:  # surface a quota/overload stall to the UI, don't 500 mid-stream
            yield _sse("error", {"message": str(exc), "api_calls": _api_calls["total"]})
            return
        yield _sse("done", _stats())

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.post("/case/{case_id}/confirm")
def confirm_case(case_id: str, req: ConfirmRequest) -> dict:
    case = QUEUE.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"case {case_id} not in queue")
    case["confirmed"] = True
    case["officer_action"] = req.action
    if req.action == "override" and req.override_severity:
        case["triage"]["severity"] = req.override_severity
        case["overridden"] = True
    if req.note:
        case["officer_note"] = req.note
    return case


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
