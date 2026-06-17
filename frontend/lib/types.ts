export type Severity = "P1" | "P2" | "P3" | "P4";

export interface TriageResult {
  severity: Severity;
  category: string;
  confidence: number;
  reason: string;
  sop_reference: string;
}

export interface IntakeResult {
  normalized_text: string;
  language: string;
  translated: boolean;
}

export interface EscalationDecision {
  suggested_action: string;
  target_mission: string;
  urgency_note: string;
}

export interface ResponderDraft {
  draft_reply: string;
}

export interface SwarmCase {
  id: string;
  channel: string;
  original_text: string;
  intake: IntakeResult;
  triage: TriageResult;
  escalation: EscalationDecision | null;
  responder: ResponderDraft | null;
  requires_human_confirm: boolean;
  trace: string[];
  arrival_offset_sec?: number;
  true_label?: Severity;
  confirmed?: boolean;
  officer_action?: string;
  overridden?: boolean;
  officer_note?: string;
}

export interface Stats {
  total: number;
  predicted: Record<Severity, number>;
  p1_count: number;
  confirmed: number;
  fifo_first_p1_position: number | null;
  fifo_first_p1_wait_min: number;
  beacon_first_p1: string;
  api_calls: number;
}

export interface Health {
  status: string;
  mode: string;
  model: string;
  queued: number;
}
