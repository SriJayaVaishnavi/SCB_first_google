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


class IntakeResult(BaseModel):
    """The Intake Agent's normalisation of one raw inbound message."""
    normalized_text: str = Field(description="Cleaned, English version of the message")
    language: str = Field(description="Detected language of the original, e.g. 'en', 'ta', 'th'")
    translated: bool = Field(description="True if the text was translated into English")


class EscalationDecision(BaseModel):
    """The Escalation Agent's routing for an urgent (P1/P2) case."""
    suggested_action: str = Field(description="Concrete next action for the duty officer")
    target_mission: str = Field(description="Mission/desk to route to, e.g. 'Embassy Bangkok'")
    urgency_note: str = Field(description="One-line note on why this case ranks where it does")


class ResponderDraft(BaseModel):
    """The Responder Agent's draft reply for a routine (P4) query."""
    draft_reply: str = Field(description="Safe, factual draft reply; a human confirms before send")


class SwarmCase(BaseModel):
    """One message after the full swarm pass — the dashboard's queue row."""
    id: str
    channel: str
    original_text: str
    intake: IntakeResult
    triage: TriageResult
    escalation: EscalationDecision | None = None
    responder: ResponderDraft | None = None
    requires_human_confirm: bool = True  # nothing auto-dismisses; humans always confirm
    trace: list[str] = Field(default_factory=list, description="Ordered agent-handoff log")
