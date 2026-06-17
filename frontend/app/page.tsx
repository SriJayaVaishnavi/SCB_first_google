"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Health, Severity, Stats, SwarmCase } from "@/lib/types";
import { confirmCase, getHealth, getQueue, resetQueue, simulate } from "@/lib/api";
import { QueueCard } from "@/components/QueueCard";
import { CaseDetail } from "@/components/CaseDetail";
import { Scoreboard } from "@/components/Scoreboard";
import { Panel } from "@/components/ui";

const RANK: Record<Severity, number> = { P1: 0, P2: 1, P3: 2, P4: 3 };

export default function Dashboard() {
  const [cases, setCases] = useState<Record<string, SwarmCase>>({});
  const [stats, setStats] = useState<Stats | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [n, setN] = useState(12);
  const [error, setError] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
    getQueue()
      .then((d) => {
        setCases(Object.fromEntries(d.cases.map((c) => [c.id, c])));
        setStats(d.stats);
      })
      .catch(() => {});
  }, []);

  const ranked = useMemo(
    () =>
      Object.values(cases).sort(
        (a, b) =>
          RANK[a.triage.severity] - RANK[b.triage.severity] ||
          b.triage.confidence - a.triage.confidence,
      ),
    [cases],
  );

  const runSimulation = useCallback(async () => {
    setError(null);
    setRunning(true);
    setCases({});
    setStats(null);
    setSelected(null);
    abort.current = new AbortController();
    try {
      await simulate(
        n,
        (event, data) => {
          if (event === "case") {
            setCases((prev) => ({ ...prev, [data.id]: data }));
          } else if (event === "done") {
            setStats(data);
          } else if (event === "error") {
            setError(data.message ?? "stream error");
          }
        },
        abort.current.signal,
      );
    } catch (e: any) {
      if (e?.name !== "AbortError") setError(String(e?.message ?? e));
    } finally {
      setRunning(false);
    }
  }, [n]);

  const doConfirm = async (id: string) => {
    const updated = await confirmCase(id, { action: "confirm" });
    setCases((p) => ({ ...p, [id]: updated }));
  };
  const doOverride = async (id: string, sev: string) => {
    const updated = await confirmCase(id, { action: "override", override_severity: sev });
    setCases((p) => ({ ...p, [id]: updated }));
  };

  const reset = async () => {
    abort.current?.abort();
    await resetQueue();
    setCases({});
    setStats(null);
    setSelected(null);
  };

  const p1Live = ranked.filter((c) => c.triage.severity === "P1" && !c.confirmed).length;
  const estCalls = `~${n * 2}–${n * 3}`;

  return (
    <main className="mx-auto max-w-[1400px] px-5 py-6">
      {/* ── Masthead ─────────────────────────────────────────────────── */}
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <Beacon />
          <div>
            <h1 className="font-sans text-[22px] font-bold leading-none tracking-tight text-slate-50">
              BEACON
            </h1>
            <p className="mt-1 font-mono text-[11px] text-slate-500">
              Consular crisis triage · Duty Office
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {health && (
            <span className="flex items-center gap-2 rounded-md border border-white/[.07] bg-ink-850/70 px-3 py-1.5 font-mono text-[11px] text-slate-400">
              <span className="h-1.5 w-1.5 rounded-full bg-sev-p4" />
              {health.mode.toUpperCase()} · {health.model}
            </span>
          )}
          <div className="flex items-center overflow-hidden rounded-md border border-white/[.07] font-mono text-[11px]">
            <button
              onClick={() => setN((v) => Math.max(4, v - 4))}
              className="bg-ink-850/70 px-2.5 py-1.5 text-slate-400 hover:bg-white/[.06]"
            >
              −
            </button>
            <span className="bg-ink-800/70 px-2 py-1.5 text-slate-300">{n} msgs</span>
            <button
              onClick={() => setN((v) => Math.min(40, v + 4))}
              className="bg-ink-850/70 px-2.5 py-1.5 text-slate-400 hover:bg-white/[.06]"
            >
              +
            </button>
          </div>
          <button
            onClick={runSimulation}
            disabled={running}
            className="group relative overflow-hidden rounded-md bg-beacon px-4 py-2 font-mono text-[12px] font-semibold text-ink-950 transition hover:brightness-110 disabled:opacity-50"
          >
            {running ? "● Streaming surge…" : "▶ Simulate surge"}
            <span className="ml-1.5 opacity-60">{estCalls} calls</span>
          </button>
          <button
            onClick={reset}
            className="rounded-md border border-white/[.07] bg-ink-850/70 px-3 py-2 font-mono text-[12px] text-slate-400 hover:bg-white/[.06]"
          >
            Reset
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-md border border-sev-p1/40 bg-sev-p1/10 px-4 py-2.5 font-mono text-[12px] text-sev-p1">
          Stream halted — {error}
        </div>
      )}

      {/* ── Console grid ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.05fr_1.25fr]">
        {/* live queue */}
        <Panel
          title="Live triage queue"
          right={
            <span className="flex items-center gap-2 font-mono text-[11px]">
              {p1Live > 0 && (
                <span className="flex items-center gap-1.5 text-sev-p1">
                  <span className="h-1.5 w-1.5 animate-blink rounded-full bg-sev-p1" />
                  {p1Live} P1 awaiting
                </span>
              )}
              <span className="text-slate-500">{ranked.length} in queue</span>
            </span>
          }
        >
          <div className="max-h-[72vh] space-y-2 overflow-y-auto p-3">
            {ranked.length === 0 && (
              <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
                <p className="text-sm text-slate-500">Queue empty</p>
                <p className="max-w-xs text-[11px] text-slate-600">
                  Run a surge to stream inbound messages through the agent swarm. Life-threatening
                  cases rise to the top in seconds.
                </p>
              </div>
            )}
            {ranked.map((c, i) => (
              <QueueCard
                key={c.id}
                c={c}
                rank={i + 1}
                selected={selected === c.id}
                onClick={() => setSelected(c.id)}
              />
            ))}
          </div>
        </Panel>

        {/* right column */}
        <div className="flex flex-col gap-5">
          <Scoreboard stats={stats} />
          <CaseDetail
            c={selected ? cases[selected] ?? null : null}
            onConfirm={doConfirm}
            onOverride={doOverride}
          />
        </div>
      </div>

      <footer className="mt-6 text-center font-mono text-[10px] text-slate-700">
        MFA Singapore · AI Immersion Day — Challenge 01 “The Crowded Hotline” · prototype
      </footer>
    </main>
  );
}

/* Lighthouse beacon mark — a pulsing signal. */
function Beacon() {
  return (
    <div className="relative grid h-10 w-10 place-items-center">
      <span className="absolute inset-0 animate-pulseGlow rounded-full" />
      <span className="absolute h-10 w-10 rounded-full bg-beacon/10" />
      <span className="absolute h-6 w-6 rounded-full bg-beacon/20" />
      <span className="h-2.5 w-2.5 rounded-full bg-beacon shadow-[0_0_12px_2px_rgba(255,176,46,.8)]" />
    </div>
  );
}
