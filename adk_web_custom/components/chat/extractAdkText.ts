// components/chat/extractAdkText.ts
type AdkEvent = {
  content?: {
    role?: string;
    parts?: Array<{ text?: string; thought?: boolean }>;
  };
  partial?: boolean;
  finishReason?: string;
};

export function extractAdkAssistantText(events: unknown): string {
  if (!Array.isArray(events)) return "";

  // ✅ 마지막까지 온(=partial 아닌) 이벤트 위주로, model role의 텍스트만 뽑기
  const texts: string[] = [];

  for (const ev of events as AdkEvent[]) {
    const role = ev?.content?.role;
    const parts = ev?.content?.parts ?? [];

    if (role !== "model") continue;

    for (const p of parts) {
      const t = (p?.text ?? "").trim();
      if (!t) continue;
      if (p?.thought) continue; // ✅ thought=true 제거
      texts.push(t);
    }
  }

  // ✅ 아무것도 못 찾으면 fallback
  if (texts.length === 0) return "";

  // 여러 파트면 줄바꿈으로 합치기
  return texts.join("\n");
}
