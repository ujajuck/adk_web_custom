// components/chat/ChatPanel.tsx
"use client";

import { useEffect, useRef, useState } from "react";

type Msg = { role: "user" | "assistant"; text: string };

export default function ChatPanel() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");

  const [userId, setUserId] = useState<string>(""); // ✅ user_{timestamp}
  const [sessionId, setSessionId] = useState<string>(""); // ✅ user_{timestamp}

  const scrollerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages]);

  // ✅ + 버튼: 세션 먼저 만들기
  async function createSession() {
    const id = `user_${Date.now()}`; // ✅ 요청하신 규칙
    setUserId(id);
    setSessionId(id);

    // ✅ 서버에 “세션 초기화” 호출
    const res = await fetch("/api/adk/session", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ user_id: id, session_id: id }),
    });

    const json = await res.json().catch(() => null);
    if (!res.ok || json?.ok === false) {
      // 실패해도 UI는 세션을 들고 있지만, 실제 ADK가 세션을 안 만들었을 수 있음
      // 필요하면 여기서 롤백(setUserId(""), setSessionId("")) 처리 가능
    if (json?.ok !== true) {
        setMessages((m) => [
        ...m,
        {
            role: "assistant",
            text: `세션 생성 실패: upstream=${json?.status ?? "?"} (${json?.data?.detail ?? json?.error ?? "unknown"})`,
        },
        ]);
        // 필요하면 롤백
        // setUserId(""); setSessionId("");
        return;
    }

    setMessages((m) => [...m, { role: "assistant", text: `세션 생성됨: ${id}` }]);
    
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
    if (!userId || !sessionId) return; // ✅ 세션 없으면 전송 불가

    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");

    const res = await fetch("/api/adk", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        user_id: userId,
        session_id: sessionId,
        new_message: { role: "user", parts: [{ text }] },
      }),
    });

    const json = await res.json().catch(() => null);

    // ✅ 여기서 json.data 안에 fig/csv가 있으면 Workspace로 띄우는 로직을 붙이면 됨
    const assistantText =
      json?.data?.message ??
      json?.data?.output ??
      (json ? JSON.stringify(json.data ?? json) : "응답 파싱 실패");

    setMessages((m) => [
      ...m,
      { role: "assistant", text: String(assistantText) },
    ]);
  }

  // ✅ 세션이 없으면: + 버튼만 보여주기
  if (!sessionId) {
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
          }}
          aria-label="세션 생성"
          title="세션 생성"
        >
          ＋ 세션 만들기
        </button>
      </div>
    );
  }

  // ✅ 세션이 있으면: 채팅 UI
  return (
    <div
      style={{ height: "100%", display: "grid", gridTemplateRows: "1fr auto" }}
    >
      <div
        style={{
          padding: 10,
          borderBottom: "1px solid #e5e7eb",
          fontSize: 12,
          color: "#6b7280",
        }}
      >
        session: {sessionId}
      </div>

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

                // 🎨 색상/정렬
                background: isUser ? "#2563eb" : "#f3f4f6",
                color: isUser ? "white" : "#111827",

                // 말풍선 꼬리 느낌
                borderTopRightRadius: isUser ? 4 : 16,
                borderTopLeftRadius: isUser ? 16 : 4,

                // 살짝 띄우는 느낌
                boxShadow: "0 2px 6px rgba(0,0,0,0.06)",
            }}
            >
            {m.text}
            </div>
        </div>
        );
    })}
    </div>


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
        placeholder="메시지를 입력하세요…"
        style={{
        flex: 1,
        padding: "12px 14px",
        borderRadius: 14,
        border: "1px solid #e5e7eb",
        outline: "none",
        fontSize: 14,
        }}
    />
    <button
        onClick={send}
        style={{
        padding: "0 16px",
        borderRadius: 14,
        border: "none",
        background: "#2563eb",
        color: "white",
        fontWeight: 600,
        cursor: "pointer",
        }}
    >
        전송
    </button>
    </div>

    </div>
  );
}
