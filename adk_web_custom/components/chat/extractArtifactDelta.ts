export function extractArtifactDelta(events: unknown): Record<string, number> {
  if (!Array.isArray(events)) return {};
  const out: Record<string, number> = {};

  for (const ev of events as any[]) {
    const delta = ev?.actions?.artifactDelta;
    if (!delta || typeof delta !== "object") continue;

    for (const [k, v] of Object.entries(delta)) {
      const n = typeof v === "number" ? v : Number(v);
      if (!Number.isNaN(n)) out[String(k)] = n;
    }
  }
  return out;
}