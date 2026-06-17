"""Load the synthetic crisis dataset + SOP + country feed.

Produces a deterministic train/holdout split so the eval scoreboard is reproducible.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from app.config import DATA_DIR, HOLDOUT_FRACTION, SPLIT_SEED

VALID_LABELS = {"P1", "P2", "P3", "P4"}


@dataclass
class Dataset:
    train: list[dict] = field(default_factory=list)
    holdout: list[dict] = field(default_factory=list)
    sop: str = ""
    country_feed: dict = field(default_factory=dict)

    @property
    def all_messages(self) -> list[dict]:
        return self.train + self.holdout


def load_dataset(data_dir: Path | None = None) -> Dataset:
    d = data_dir or DATA_DIR
    messages = json.loads((d / "messages.json").read_text(encoding="utf-8"))
    if not messages or any(m["true_label"] not in VALID_LABELS for m in messages):
        raise ValueError("messages.json missing or contains an invalid true_label")

    # Deterministic shuffle + split.
    rng = random.Random(SPLIT_SEED)
    shuffled = messages[:]
    rng.shuffle(shuffled)
    cut = int(len(shuffled) * (1 - HOLDOUT_FRACTION))
    train, holdout = shuffled[:cut], shuffled[cut:]

    sop = (d / "sop.md").read_text(encoding="utf-8")
    country_feed = json.loads((d / "country_feed.json").read_text(encoding="utf-8"))

    return Dataset(train=train, holdout=holdout, sop=sop, country_feed=country_feed)
