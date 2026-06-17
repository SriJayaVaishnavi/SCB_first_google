import { useState } from "react";
import type { SwarmCase } from "@/lib/types";
import { SEV, SeverityChip, Panel } from "./ui";

export function CaseDetail({
  c,
  onConfirm,
  onOverride,
}: {
  c: SwarmCase | null;
  onConfirm: (id: string) => void;
  onOverride: (id: string, sev: string) => void;
}) {
  if (!c) {
    return (
      <Panel title="Case detail" className="flex-1">
        <div className="flex h-full min-h-[260px] flex-col items-center justify-center gap-2 px-6 text-center">
          <div className="font-mono text-3xl text-slate-700">⌖</div>
          <p className="text-sm text-slate-500">Select a case from the queue</p>
          <p className="max-w-xs text-[11px] text-slate-600">
            Every case shows its triage reasoning, the SOP basis, the routed action, and the
            agent handoff trace. Humans confirm — nothing is auto-dismissed.
          </p>
        </div>
      </Panel>
    );
  }

  const s = c.triage.severity;
  return (
    <Panel
      title={`Case ${c.id}`}
      right={<SeverityChip s={s} big />}
      className="flex flex-1 flex-col"
    >
      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {/* message */}
        <Block label={`Inbound · ${c.channel}`}>
          <p className="text-[13.5px] leading-relaxed text-slate-100">{c.original_text}</p>
          {c.intake.translated && (
            <p className="mt-2 border-l-2 border-beacon/40 pl-2 text-[12px] italic text-slate-400">
              {c.intake.language.toUpperCase()}→EN · {c.intake.normalized_text}
            </p>
          )}
        </Block>

        {/* triage verdict */}
        <Block label="Triage verdict">
          <div className="flex items-center gap-2 text-[12px] text-slate-300">
            <span className={`font-mono font-semibold ${SEV[s].text}`}>{s}</span>
            <span className="text-slate-500">·</span>
            <span>{c.triage.category}</span>
            <span className="text-slate-500">·</span>
            <span className="font-mono text-slate-400">
              conf {Math.round(c.triage.confidence * 100)}%
            </span>
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-slate-200">{c.triage.reason}</p>
          <p className="mt-1.5 font-mono text-[11px] text-slate-500">
            SOP basis · {c.triage.sop_reference}
          </p>
        </Block>

        {/* routed action / draft reply */}
        {c.escalation && (
          <Block label="Escalation — routed action" accent="sev-p1">
            <p className="text-[13px] text-slate-100">{c.escalation.suggested_action}</p>
            <p className="mt-1 font-mono text-[11px] text-beacon">
              → {c.escalation.target_mission}
            </p>
            <p className="mt-1 text-[11px] text-slate-500">{c.escalation.urgency_note}</p>
          </Block>
        )}
        {c.responder && (
          <Block label="Responder — draft reply (awaiting confirm)" accent="sev-p4">
            <p className="whitespace-pre-wrap text-[13px] italic leading-relaxed text-slate-300">
              “{c.responder.draft_reply}”
            </p>
          </Block>
        )}

        {/* agent trace */}
        <Block label="Agent handoff trace">
          <ol className="space-y-1.5">
            {c.trace.map((t, i) => (
              <li key={i} className="flex gap-2 font-mono text-[11px] text-slate-400">
                <span className="text-slate-600">{String(i + 1).padStart(2, "0")}</span>
                <span>{t}</span>
              </li>
            ))}
          </ol>
        </Block>
      </div>

      {/* human-in-the-loop actions */}
      <footer className="border-t border-white/[.06] px-4 py-3">
        {c.confirmed ? (
          <div className="flex items-center gap-2 font-mono text-[12px] text-sev-p4">
            <span className="h-1.5 w-1.5 rounded-full bg-sev-p4" />
            {c.overridden ? "Overridden" : "Confirmed"} by duty officer
            {c.officer_note ? ` · ${c.officer_note}` : ""}
          </div>
        ) : (
          <ConfirmBar id={c.id} sev={s} onConfirm={onConfirm} onOverride={onOverride} />
        )}
      </footer>
    </Panel>
  );
}

function ConfirmBar({
  id,
  sev,
  onConfirm,
  onOverride,
}: {
  id: string;
  sev: string;
  onConfirm: (id: string) => void;
  onOverride: (id: string, s: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        onClick={() => onConfirm(id)}
        className="rounded-md bg-sev-p4/15 px-4 py-2 font-mono text-[12px] font-semibold text-sev-p4 transition hover:bg-sev-p4/25"
      >
        ✓ Confirm
      </button>
      <button
        onClick={() => setOpen((o) => !o)}
        className="rounded-md bg-white/[.05] px-4 py-2 font-mono text-[12px] text-slate-300 transition hover:bg-white/[.1]"
      >
        Override ▾
      </button>
      {open &&
        (["P1", "P2", "P3", "P4"] as const)
          .filter((x) => x !== sev)
          .map((x) => (
            <button
              key={x}
              onClick={() => onOverride(id, x)}
              className={`rounded-md border border-white/10 px-3 py-2 font-mono text-[12px] ${SEV[x].text} hover:bg-white/[.06]`}
            >
              → {x}
            </button>
          ))}
    </div>
  );
}

function Block({
  label,
  children,
  accent,
}: {
  label: string;
  children: React.ReactNode;
  accent?: string;
}) {
  return (
    <div>
      <div
        className={`tracky mb-1.5 font-mono text-[10px] uppercase ${
          accent ? `text-${accent}` : "text-slate-500"
        }`}
      >
        {label}
      </div>
      {children}
    </div>
  );
}
