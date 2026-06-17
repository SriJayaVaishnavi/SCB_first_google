import type { SwarmCase } from "@/lib/types";
import { SEV, SeverityChip } from "./ui";

export function QueueCard({
  c,
  rank,
  selected,
  onClick,
}: {
  c: SwarmCase;
  rank: number;
  selected: boolean;
  onClick: () => void;
}) {
  const s = c.triage.severity;
  const m = SEV[s];
  const isP1 = s === "P1";

  return (
    <button
      onClick={onClick}
      className={`group relative w-full animate-rise overflow-hidden rounded-md border-l-2 ${m.border} bg-ink-800/60 px-3.5 py-3 text-left transition-all hover:bg-ink-700/60 ${
        selected ? "ring-1 ring-white/20 bg-ink-700/70" : ""
      } ${isP1 ? "animate-pulseGlow" : ""}`}
    >
      {/* scanning sweep for P1 cards */}
      {isP1 && (
        <span className="pointer-events-none absolute inset-y-0 left-0 w-1/3 animate-sweep bg-gradient-to-r from-transparent via-sev-p1/10 to-transparent" />
      )}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] text-slate-600">#{rank}</span>
          <SeverityChip s={s} />
        </div>
        <div className="flex items-center gap-2 font-mono text-[10px] text-slate-500">
          <span>{Math.round(c.triage.confidence * 100)}%</span>
          {c.confirmed && (
            <span className="rounded-sm bg-sev-p4/15 px-1.5 py-0.5 text-sev-p4">
              {c.overridden ? "OVERRIDDEN" : "CONFIRMED"}
            </span>
          )}
        </div>
      </div>

      <p className="mt-2 line-clamp-2 text-[13px] leading-snug text-slate-200">
        {c.original_text}
      </p>

      <div className="mt-2 flex items-center gap-2 font-mono text-[10px] text-slate-500">
        <span className="text-slate-400">{c.id}</span>
        <span className="opacity-40">·</span>
        <span>{c.channel}</span>
        <span className="opacity-40">·</span>
        <span className="truncate">{c.triage.category}</span>
        {c.intake.translated && (
          <>
            <span className="opacity-40">·</span>
            <span className="text-beacon">{c.intake.language.toUpperCase()}→EN</span>
          </>
        )}
      </div>
    </button>
  );
}
