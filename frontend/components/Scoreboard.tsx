import type { Severity, Stats } from "@/lib/types";
import { SEV, Panel } from "./ui";

const ORDER: Severity[] = ["P1", "P2", "P3", "P4"];

export function Scoreboard({ stats }: { stats: Stats | null }) {
  const fifoMin = stats?.fifo_first_p1_wait_min ?? 0;
  const total = stats?.total ?? 0;

  return (
    <Panel title="Ops scoreboard — Beacon vs FIFO">
      <div className="grid grid-cols-2 gap-px bg-white/[.06]">
        <Stat
          label="First P1 — Beacon"
          value="seconds"
          sub="floated to top on arrival"
          accent="text-sev-p4"
        />
        <Stat
          label="First P1 — FIFO queue"
          value={fifoMin > 0 ? `~${fifoMin} min` : "—"}
          sub={
            stats?.fifo_first_p1_position != null
              ? `behind ${stats.fifo_first_p1_position} routine msgs`
              : "no P1 yet"
          }
          accent="text-sev-p1"
        />
      </div>

      <div className="px-4 py-3.5">
        <div className="mb-2 flex items-center justify-between">
          <span className="tracky font-mono text-[10px] uppercase text-slate-500">
            Triage distribution
          </span>
          <span className="font-mono text-[11px] text-slate-400">
            {total} triaged · {stats?.api_calls ?? 0} LLM calls
          </span>
        </div>
        <div className="space-y-1.5">
          {ORDER.map((s) => {
            const count = stats?.predicted?.[s] ?? 0;
            const pct = total ? (count / total) * 100 : 0;
            return (
              <div key={s} className="flex items-center gap-2.5">
                <span className={`w-6 font-mono text-[11px] font-semibold ${SEV[s].text}`}>{s}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/[.05]">
                  <div
                    className={`h-full rounded-full ${SEV[s].dot} transition-all duration-500`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="w-6 text-right font-mono text-[11px] text-slate-400">{count}</span>
              </div>
            );
          })}
        </div>
      </div>
    </Panel>
  );
}

function Stat({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub: string;
  accent: string;
}) {
  return (
    <div className="bg-ink-850/60 px-4 py-3.5">
      <div className="tracky font-mono text-[10px] uppercase text-slate-500">{label}</div>
      <div className={`mt-1 font-sans text-2xl font-bold tabular-nums ${accent}`}>{value}</div>
      <div className="mt-0.5 text-[11px] text-slate-500">{sub}</div>
    </div>
  );
}
