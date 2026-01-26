"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useWorkspace } from "@/components/workspace/WorkspaceContext";
import { extractArtifactDelta } from "@/components/chat/extractArtifactDelta";
import type { Msg } from "@/components/chat/adkTypes";
import { extractAdkAssistantText } from "@/components/chat/adkParsers";
import { tryExtractPlotlyFig } from "@/components/chat/plotlyParsers";

export default function ChatPanel() {
  const { addPlotlyWindow, addCsvTableWindow } = useWorkspace();

  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");

  const [userId, setUserId] = useState<string>("");
  const [sessionId, setSessionId] = useState<string>("");

  const [isSending, setIsSending] = useState(false);
  const scrollerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages]);

  const hasSession = useMemo(
    () => Boolean(userId && sessionId),
    [userId, sessionId],
  );

  async function createSession() {
    const id = `user_${Date.now()}`;
    setUserId(id);
    setSessionId(id);

    setMessages((m) => [
      ...m,
      { role: "assistant", text: `세션 생성 중… (${id})` },
    ]);

    const res = await fetch("/api/adk/session", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ userId: id, sessionId: id }),
    });

    const json = await res.json().catch(() => null);

    if (json?.ok !== true) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: `세션 생성 실패: upstream=${json?.status ?? "?"} / ${json?.data?.detail ?? json?.error ?? "unknown"}`,
        },
      ]);
      return;
    }

    setMessages((m) => [
      ...m,
      { role: "assistant", text: `세션 생성됨: ${id}` },
    ]);
  }

  async function send() {
    const text = input.trim();
    if (!text) return;
    if (!hasSession) return;
    if (isSending) return;

    setIsSending(true);
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");

    try {
      const res = await fetch("/api/adk", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          userId,
          sessionId,
          newMessage: { role: "user", parts: [{ text }] },
        }),
      });

      const json = await res.json().catch(() => null);
      console.log(json);

      const events = json?.data;
      const delta = extractArtifactDelta(events);
      for (const [filename, version] of Object.entries(delta)) {
        const params = new URLSearchParams({
          userId,
          sessionId,
          filename,
          version: String(version),
        });

        const pubApp = (process.env.ADK_APP_NAME ?? "").trim();
        if (pubApp) params.set("appName", pubApp);
        const csvUrl = `/api/adk/artifacts/csv?${params.toString()}`;
        console.log("[csvUrl]", csvUrl);

        addCsvTableWindow(`CSV: ${filename} (v${version})`, csvUrl);
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            text: `📄 CSV 테이블을 워크스페이스에 열었어요: ${filename} v${version}`,
          },
        ]);
      }

      //  fig가 있으면 Workspace에 띄우기(있을 때만)
      const foundFig = tryExtractPlotlyFig(events);
      console.log("그래프 찾음 ", foundFig);
      if (foundFig) {
        addPlotlyWindow(foundFig.title, foundFig.fig);
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            text: `📈 그래프를 워크스페이스에 열었어요: ${foundFig.title}`,
          },
        ]);
      }

      //  텍스트 답변 추출(thought 제거)
      const assistantText = extractAdkAssistantText(events);

      if (assistantText) {
        setMessages((m) => [...m, { role: "assistant", text: assistantText }]);
      } else if (!foundFig) {
        // fig도 없고 텍스트도 없으면 raw 표시
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            text: `응답 파싱 실패(텍스트 없음)\n${JSON.stringify(events, null, 2)}`,
          },
        ]);
      }
    } catch (e: any) {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: `요청 실패: ${String(e?.message ?? e)}` },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  //  세션이 없으면 + 버튼만 보여주기
  if (!hasSession) {
    return (
      <div
        style={{
          height: "100%",
          display: "grid",
          placeItems: "center",
          padding: 12,
        }}
      >
        <button
          onClick={createSession}
          style={{
            padding: "12px 14px",
            borderRadius: 12,
            border: "1px solid #e5e7eb",
            background: "white",
            cursor: "pointer",
            boxShadow: "0 6px 20px rgba(0,0,0,0.08)",
          }}
          aria-label="세션 생성"
          title="세션 생성"
        >
          ＋ 세션 만들기
        </button>
      </div>
    );
  }

  return (
    <div
      style={{
        height: "100%",
        display: "grid",
        gridTemplateRows: "auto 1fr auto",
      }}
    >
      {/* 상단: 세션 표시 */}
      <div
        style={{
          padding: "10px 12px",
          borderBottom: "1px solid #e5e7eb",
          background: "#fafafa",
          fontSize: 12,
          color: "#6b7280",
          display: "flex",
          gap: 8,
          alignItems: "center",
        }}
      >
        <span>session:</span>
        <code
          style={{
            padding: "2px 6px",
            background: "white",
            border: "1px solid #e5e7eb",
            borderRadius: 8,
          }}
        >
          {sessionId}
        </code>
        <div style={{ flex: 1 }} />
        {isSending && <span>전송 중…</span>}
      </div>

      {/* 메시지 영역 */}
      <div ref={scrollerRef} style={{ padding: 12, overflow: "auto" }}>
        {messages.map((m, i) => {
          const isUser = m.role === "user";

          return (
            <div
              key={i}
              style={{
                display: "flex",
                justifyContent: isUser ? "flex-end" : "flex-start",
                marginBottom: 10,
              }}
            >
              <div
                style={{
                  maxWidth: "78%",
                  padding: "10px 14px",
                  borderRadius: 16,
                  whiteSpace: "pre-wrap",
                  lineHeight: 1.45,
                  fontSize: 14,
                  background: isUser ? "#2563eb" : "#f3f4f6",
                  color: isUser ? "white" : "#111827",
                  borderTopRightRadius: isUser ? 4 : 16,
                  borderTopLeftRadius: isUser ? 16 : 4,
                  boxShadow: "0 2px 6px rgba(0,0,0,0.06)",
                }}
              >
                {m.text}
              </div>
            </div>
          );
        })}
      </div>

      {/* 입력 영역 */}
      <div
        style={{
          padding: 12,
          borderTop: "1px solid #e5e7eb",
          display: "flex",
          gap: 8,
          background: "#fafafa",
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          style={{
            flex: 1,
            padding: "12px 14px",
            borderRadius: 14,
            border: "1px solid #e5e7eb",
            outline: "none",
            fontSize: 14,
            background: "white",
          }}
          placeholder="메시지를 입력하세요…"
          disabled={isSending}
        />
        <button
          onClick={send}
          disabled={isSending}
          style={{
            padding: "0 16px",
            borderRadius: 14,
            border: "none",
            background: isSending ? "#93c5fd" : "#2563eb",
            color: "white",
            fontWeight: 700,
            cursor: isSending ? "not-allowed" : "pointer",
          }}
        >
          전송
        </button>
      </div>
    </div>
  );
}
