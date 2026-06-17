"""Shared data contracts for the agent swarm."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    P1 = "P1"  # immediate physical danger
    P2 = "P2"  # urgent consular action
    P3 = "P3"  # assistance request
    P4 = "P4"  # routine / informational

    @property
    def rank(self) -> int:
        return {"P1": 0, "P2": 1, "P3": 2, "P4": 3}[self.value]


# Tier escalation map for the bias-to-escalate rule (round up one tier).
ESCALATE_UP = {"P4": "P3", "P3": "P2", "P2": "P1", "P1": "P1"}


class TriageResult(BaseModel):
    """The Triage Agent's structured verdict for one message."""
    severity: Severity = Field(description="P1 (life-safety) … P4 (routine)")
    category: str = Field(description="Short category, e.g. 'trapped', 'medical', 'flight-query'")
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence 0–1")
    reason: str = Field(description="One-sentence justification for the severity")
    sop_reference: str = Field(description="The SOP tier/section that applies, e.g. 'P1 §4.2'")
