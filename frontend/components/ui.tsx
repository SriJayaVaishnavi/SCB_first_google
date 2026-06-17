import type { Severity } from "@/lib/types";

export const SEV: Record<
  Severity,
  { label: string; word: string; text: string; border: string; chipBg: string; dot: string }
> = {
  P1: {
    label: "P1",
    word: "LIFE-SAFETY",
    text: "text-sev-p1",
    border: "border-sev-p1/70",
    chipBg: "bg-sev-p1/15",
    dot: "bg-sev-p1",
  },
  P2: {
    label: "P2",
    word: "URGENT",
    text: "text-sev-p2",
    border: "border-sev-p2/60",
    chipBg: "bg-sev-p2/15",
    dot: "bg-sev-p2",
  },
  P3: {
    label: "P3",
    word: "ASSIST",
    text: "text-sev-p3",
    border: "border-sev-p3/50",
    chipBg: "bg-sev-p3/15",
    dot: "bg-sev-p3",
  },
  P4: {
    label: "P4",
    word: "ROUTINE",
    text: "text-sev-p4",
    border: "border-sev-p4/40",
    chipBg: "bg-sev-p4/10",
    dot: "bg-sev-p4",
  },
};

export function SeverityChip({ s, big = false }: { s: Severity; big?: boolean }) {
  const m = SEV[s];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-sm font-mono font-semibold ${m.chipBg} ${m.text} ${
        big ? "px-2.5 py-1 text-sm" : "px-1.5 py-0.5 text-[11px]"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${m.dot} ${s === "P1" ? "animate-blink" : ""}`} />
      {m.label}
      <span className="tracky text-[9px] opacity-70">{m.word}</span>
    </span>
  );
}

export function Panel({
  title,
  right,
  children,
  className = "",
}: {
  title?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-lg border border-white/[.06] bg-ink-850/60 shadow-panel backdrop-blur-sm ${className}`}
    >
      {title && (
        <header className="flex items-center justify-between border-b border-white/[.06] px-4 py-2.5">
          <h2 className="tracky font-mono text-[11px] font-semibold uppercase text-slate-400">
            {title}
          </h2>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}
