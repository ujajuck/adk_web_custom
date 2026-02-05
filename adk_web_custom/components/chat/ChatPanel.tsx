"use client";

import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { Send, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useWorkspace } from "@/components/workspace/WorkspaceContext";
import type { Msg } from "@/components/chat/adkTypes";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8080";

type WorkspaceSendDetail = {
  text: string;
  fileName?: string;
};

export default function ChatPanel() {
  const { addPlotlyWindow, addCsvFileWindow } = useWorkspace();

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

  const createSession = useCallback(async () => {
    const id = `user_${Date.now()}`;

    setUserId(id);
    setSessionId(id);
    setMessages((m) => [
      ...m,
      { role: "assistant", text: `세션 생성 중… (${id})` },
    ]);

    try {
      const res = await fetch(`${API_URL}/api/sessions`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          user_id: id,
          session_id: id,
          session_name: "",
        }),
      });

      const json = await res.json().catch(() => null);

      if (!res.ok || !json?.session_id) {
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            text: `세션 생성 실패: ${json?.detail ?? "unknown"}`,
          },
        ]);
        setUserId("");
        setSessionId("");
        throw new Error("session create failed");
      }

      setMessages((m) => [
        ...m,
        { role: "assistant", text: `세션 생성됨: ${id}` },
      ]);
      return { userId: id, sessionId: id };
    } catch (e: any) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: `세션 생성 실패: ${String(e?.message ?? e)}`,
        },
      ]);
      setUserId("");
      setSessionId("");
      throw e;
    }
  }, []);

  // 세션이 없으면 자동 생성 (최초 진입 시)
  useEffect(() => {
    if (hasSession) return;
    void createSession();
  }, [hasSession, createSession]);

  // send 전에 세션을 보장
  const ensureSession = useCallback(async () => {
    if (hasSession) return { userId, sessionId };
    return await createSession();
  }, [hasSession, userId, sessionId, createSession]);

  const sendTextToAdk = useCallback(
    async (text: string) => {
      const t = text.trim();
      if (!t) return;
      if (isSending) return;

      setIsSending(true);

      const sess = await ensureSession();

      setMessages((m) => [...m, { role: "user", text: t }]);
      setInput("");

      try {
        const res = await fetch(`${API_URL}/api/chat`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            user_id: sess.userId,
            session_id: sess.sessionId,
            message: t,
          }),
        });

        const json = await res.json().catch(() => null);
        console.log("[chat response]", json);

        if (!res.ok) {
          setMessages((m) => [
            ...m,
            {
              role: "assistant",
              text: `요청 실패 (${res.status}): ${json?.detail ?? "unknown"}`,
            },
          ]);
          return;
        }

        // CSV files
        if (json?.csv_files?.length) {
          for (const csv of json.csv_files) {
            addCsvFileWindow(
              `CSV: ${csv.filename} (${csv.total_rows} rows)`,
              csv.file_id,
            );
            setMessages((m) => [
              ...m,
              {
                role: "assistant",
                text: `CSV 테이블을 워크스페이스에 열었어요: ${csv.filename} (${csv.total_rows}행)`,
              },
            ]);
          }
        }

        // Plotly figures
        if (json?.plotly_figs?.length) {
          for (const pf of json.plotly_figs) {
            addPlotlyWindow(pf.title, pf.fig);
            setMessages((m) => [
              ...m,
              {
                role: "assistant",
                text: `그래프를 워크스페이스에 열었어요: ${pf.title}`,
              },
            ]);
          }
        }

        // Assistant text
        if (json?.text) {
          setMessages((m) => [
            ...m,
            { role: "assistant", text: json.text },
          ]);
        } else if (!json?.csv_files?.length && !json?.plotly_figs?.length) {
          setMessages((m) => [
            ...m,
            {
              role: "assistant",
              text: `응답 파싱 실패(텍스트 없음)\n${JSON.stringify(json, null, 2)}`,
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
    },
    [isSending, ensureSession, addCsvFileWindow, addPlotlyWindow],
  );

  async function send() {
    await sendTextToAdk(input);
  }

  // WorkspacePanel에서 보낸 이벤트(adk:chat:send)를 받아서 /api/chat로 전송
  useEffect(() => {
    const handler = (e: Event) => {
      const ce = e as CustomEvent<WorkspaceSendDetail>;
      const detail = ce.detail;

      const baseText = (detail?.text ?? "").trim();
      if (!baseText) return;

      const fileNameLine = detail.fileName
        ? `파일명: ${detail.fileName}\n`
        : "";
      const finalText =
        fileNameLine && !baseText.includes("파일명:")
          ? `${fileNameLine}${baseText}`
          : baseText;

      void sendTextToAdk(finalText);
    };

    window.addEventListener("adk:chat:send", handler);
    return () => window.removeEventListener("adk:chat:send", handler);
  }, [sendTextToAdk]);

  if (!hasSession) {
    return (
      <div className="h-full grid place-items-center p-3 text-muted-foreground">
        세션 준비 중…
      </div>
    );
  }

  return (
    <div className="h-full grid grid-rows-[auto_1fr_auto]">
      {/* 상단: 세션 표시 */}
      <div className="px-3 py-2.5 border-b bg-muted/50 text-xs text-muted-foreground flex items-center gap-2">
        <span>session:</span>
        <Badge variant="outline" className="font-mono text-[11px]">
          {sessionId}
        </Badge>
        <div className="flex-1" />
        {isSending && (
          <span className="flex items-center gap-1">
            <Loader2 size={12} className="animate-spin" />
            전송 중…
          </span>
        )}
      </div>

      {/* 메시지 영역 */}
      <div ref={scrollerRef} className="p-3 overflow-auto space-y-2.5">
        {messages.map((m, i) => {
          const isUser = m.role === "user";

          return (
            <div
              key={i}
              className={cn(
                "flex",
                isUser ? "justify-end" : "justify-start",
              )}
            >
              <div
                className={cn(
                  "max-w-[78%] px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap shadow-sm",
                  isUser
                    ? "bg-blue-600 text-white rounded-2xl rounded-tr-sm"
                    : "bg-muted text-foreground rounded-2xl rounded-tl-sm",
                )}
              >
                {m.text}
              </div>
            </div>
          );
        })}
      </div>

      {/* 입력 영역 */}
      <div className="p-3 border-t bg-muted/50 flex items-center gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="메시지를 입력하세요…"
          disabled={isSending}
          className="flex-1 h-10 rounded-xl bg-background"
        />
        <Button
          onClick={send}
          disabled={isSending}
          size="icon"
          className="h-10 w-10 rounded-xl bg-blue-600 hover:bg-blue-700 shrink-0"
        >
          {isSending ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Send size={16} />
          )}
        </Button>
      </div>
    </div>
  );
}
