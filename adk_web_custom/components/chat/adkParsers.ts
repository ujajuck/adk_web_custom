import type { AdkEvent } from "@/components/chat/adkTypes";

export function extractAdkAssistantText(events: unknown): string {
  if (!Array.isArray(events)) return "";

  const texts: string[] = [];

  for (const ev of events as AdkEvent[]) {
    const role = ev?.content?.role;
    if (role !== "model") continue;

    const parts = ev?.content?.parts ?? [];
    for (const p of parts) {
      const t = (p?.text ?? "").trim();
      if (!t) continue;
      if (p?.thought) continue;
      texts.push(t);
    }
  }

  return texts.join("\n").trim();
}
