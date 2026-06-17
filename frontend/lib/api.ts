import type { Health, Stats, SwarmCase } from "./types";

// Production bakes NEXT_PUBLIC_API_URL at build → call the backend directly.
// Dev (incl. Cloud Shell) leaves it unset → use the same-origin "/beacon" proxy
// (see next.config rewrites), which dodges CORS and the Web Preview auth gateway.
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "/beacon";

export async function getHealth(): Promise<Health> {
  const r = await fetch(`${API_BASE}/`, { cache: "no-store" });
  return r.json();
}

export async function getQueue(): Promise<{ cases: SwarmCase[]; stats: Stats }> {
  const r = await fetch(`${API_BASE}/queue`, { cache: "no-store" });
  return r.json();
}

export async function confirmCase(
  id: string,
  body: { action: "confirm" | "override"; override_severity?: string; note?: string },
): Promise<SwarmCase> {
  const r = await fetch(`${API_BASE}/case/${id}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`confirm failed: ${r.status}`);
  return r.json();
}

export async function resetQueue(): Promise<void> {
  await fetch(`${API_BASE}/reset`, { method: "POST" });
}

type SseHandler = (event: string, data: any) => void;

/**
 * POST /simulate and parse the Server-Sent Events stream (EventSource can't POST,
 * so we read the response body and split on the SSE record delimiter ourselves).
 */
export async function simulate(
  n: number,
  onEvent: SseHandler,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}/simulate?n=${n}`, { method: "POST", signal });
  if (!res.body) throw new Error("no stream body");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const records = buf.split("\n\n");
    buf = records.pop() ?? "";
    for (const rec of records) {
      let event = "message";
      let data = "";
      for (const line of rec.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (data) {
        try {
          onEvent(event, JSON.parse(data));
        } catch {
          /* ignore malformed record */
        }
      }
    }
  }
}
