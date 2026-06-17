"""Eval harness — the scoreboard that proves Beacon works.

Runs the Triage Agent over the holdout set and reports P1 recall (the gate),
precision, routine deflection rate, and latency. This is what we show the room.

Run in Cloud Shell:  python -m app.eval.score
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor

from app.agents.triage import triage_message
from app.data_loader import load_dataset

# Low default to stay under new-project Gemini quota; override with EVAL_WORKERS.
MAX_WORKERS = int(os.getenv("EVAL_WORKERS", "2"))


def evaluate(predictions: list[dict]) -> dict:
    """predictions: list of {true, pred, latency}."""
    actual_p1 = [p for p in predictions if p["true"] == "P1"]
    pred_p1 = [p for p in predictions if p["pred"] == "P1"]
    tp_p1 = [p for p in pred_p1 if p["true"] == "P1"]

    actual_p4 = [p for p in predictions if p["true"] == "P4"]
    deflected = [p for p in actual_p4 if p["pred"] == "P4"]

    # The catastrophic errors: a true P1 the model did NOT flag as P1.
    missed_p1 = [p for p in actual_p1 if p["pred"] != "P1"]

    # Where do the false P1s come from? (true label of each wrongly-flagged P1)
    false_p1 = [p for p in pred_p1 if p["true"] != "P1"]
    false_p1_by_true = {
        lab: sum(1 for p in false_p1 if p["true"] == lab) for lab in ("P2", "P3", "P4")
    }
    pred_dist = {lab: sum(1 for p in predictions if p["pred"] == lab) for lab in ("P1", "P2", "P3", "P4")}
    true_dist = {lab: sum(1 for p in predictions if p["true"] == lab) for lab in ("P1", "P2", "P3", "P4")}

    return {
        "n": len(predictions),
        "p1_recall": (len(tp_p1) / len(actual_p1)) if actual_p1 else 0.0,
        "p1_precision": (len(tp_p1) / len(pred_p1)) if pred_p1 else 0.0,
        "deflection_rate": (len(deflected) / len(actual_p4)) if actual_p4 else 0.0,
        "avg_latency": sum(p["latency"] for p in predictions) / len(predictions),
        "missed_p1": missed_p1,
        "pred_p1_count": len(pred_p1),
        "false_p1_by_true": false_p1_by_true,
        "pred_dist": pred_dist,
        "true_dist": true_dist,
    }


def _run_one(msg: dict, sop: str, feed: dict) -> dict:
    t0 = time.perf_counter()
    res = triage_message(msg["text"], sop, feed)
    return {
        "id": msg["id"],
        "text": msg["text"],
        "true": msg["true_label"],
        "pred": res.severity.value,
        "reason": res.reason,
        "sop_reference": res.sop_reference,
        "latency": time.perf_counter() - t0,
    }


def main() -> None:
    ds = load_dataset()
    print(f"Scoring {len(ds.holdout)} holdout messages with the Triage Agent...\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        preds = list(pool.map(lambda m: _run_one(m, ds.sop, ds.country_feed), ds.holdout))

    m = evaluate(preds)
    print("=" * 56)
    print("  BEACON TRIAGE — HOLDOUT SCOREBOARD")
    print("=" * 56)
    print(f"  Messages scored      : {m['n']}")
    print(f"  P1 recall (GATE ≥99%): {m['p1_recall']:.1%}")
    print(f"  P1 precision         : {m['p1_precision']:.1%}")
    print(f"  Routine deflection   : {m['deflection_rate']:.1%}")
    print(f"  Avg latency / msg    : {m['avg_latency']:.2f}s")
    print("-" * 56)
    print(f"  Predicted P1 count   : {m['pred_p1_count']}  (true P1 = {m['true_dist']['P1']})")
    print(f"  False P1 by true tier: {m['false_p1_by_true']}")
    print(f"  Predicted dist       : {m['pred_dist']}")
    print(f"  True dist            : {m['true_dist']}")
    print("=" * 56)
    if m["missed_p1"]:
        print(f"\n  ⚠️  {len(m['missed_p1'])} MISSED P1 (catastrophic) — must be zero:")
        for p in m["missed_p1"]:
            print(f"    [{p['id']}] pred={p['pred']}  «{p['text'][:70]}»")
    else:
        print("\n  ✅  Zero missed P1 cases.")

    gate = "PASS ✅" if m["p1_recall"] >= 0.99 else "FAIL ❌ — tune prompt / escalate to Pro"
    print(f"\n  GATE (P1 recall ≥ 99%): {gate}")


if __name__ == "__main__":
    main()
