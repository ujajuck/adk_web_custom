"use client";

import {
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";
import { Send, Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useWorkspace } from "@/components/workspace/WorkspaceContext";
import type { Msg } from "@/components/chat/adkTypes";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8080";

type SessionStatus = "idle" | "creating" | "ready" | "error";

type WorkspaceSendDetail = {
  text: string;
  fileName?: string;
};

export default function ChatPanel() {
  const { addPlotlyWindow, addCsvFileWindow } = useWorkspace();

  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");

  const [userId, setUserId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>("idle");

  const [isSending, setIsSending] = useState(false);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const creatingRef = useRef(false); // 중복 생성 방지

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages]);

  function pushMsg(role: Msg["role"], text: string) {
    setMessages((m) => [...m, { role, text }]);
  }

  const createSession = useCallback(async () => {
    if (creatingRef.current) return;
    creatingRef.current = true;

    const id = `user_${Date.now()}`;
    setSessionStatus("creating");
    pushMsg("assistant", "세션 생성 중…");

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
        throw new Error(json?.detail ?? `HTTP ${res.status}`);
      }

      setUserId(id);
      setSessionId(id);
      setSessionStatus("ready");
      pushMsg("assistant", `세션 준비됨 · ${id}`);
    } catch (e: any) {
      setSessionStatus("error");
      pushMsg("assistant", `세션 생성 실패: ${String(e?.message ?? e)}`);
    } finally {
      creatingRef.current = false;
    }
  }, []);

  // 최초 마운트 시 1회만 세션 생성
  useEffect(() => {
    createSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sendTextToAdk = useCallback(
    async (text: string) => {
      const t = text.trim();
      if (!t || isSending) return;

      if (!userId || !sessionId) {
        pushMsg("assistant", "세션이 아직 준비되지 않았습니다. 잠시 후 다시 시도하세요.");
        return;
      }

      setIsSending(true);
      pushMsg("user", t);
      setInput("");

      try {
        const res = await fetch(`${API_URL}/api/chat`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            user_id: userId,
            session_id: sessionId,
            message: t,
          }),
        });

        const json = await res.json().catch(() => null);

        if (!res.ok) {
          pushMsg(
            "assistant",
            `요청 실패 (${res.status}): ${json?.detail ?? "unknown"}`,
          );
          return;
        }

        // CSV files
        for (const csv of json?.csv_files ?? []) {
          addCsvFileWindow(
            `${csv.filename} (${csv.total_rows} rows)`,
            csv.file_id,
          );
          pushMsg(
            "assistant",
            `CSV를 워크스페이스에 열었어요: ${csv.filename} (${csv.total_rows}행, ${csv.total_cols}열)`,
          );
        }

        // Plotly figures
        for (const pf of json?.plotly_figs ?? []) {
          addPlotlyWindow(pf.title, pf.fig);
          pushMsg("assistant", `그래프를 워크스페이스에 열었어요: ${pf.title}`);
        }

        // Assistant text (항상 마지막에 표시)
        if (json?.text) {
          pushMsg("assistant", json.text);
        } else if (!json?.csv_files?.length && !json?.plotly_figs?.length) {
          pushMsg(
            "assistant",
            `응답 없음\n${JSON.stringify(json, null, 2)}`,
          );
        }
      } catch (e: any) {
        pushMsg("assistant", `요청 오류: ${String(e?.message ?? e)}`);
      } finally {
        setIsSending(false);
      }
    },
    [isSending, userId, sessionId, addCsvFileWindow, addPlotlyWindow],
  );

  function send() {
    void sendTextToAdk(input);
  }

  // WorkspacePanel → ChatPanel 이벤트 수신
  useEffect(() => {
    const handler = (e: Event) => {
      const ce = e as CustomEvent<WorkspaceSendDetail>;
      const detail = ce.detail;
      const baseText = (detail?.text ?? "").trim();
      if (!baseText) return;

      const fileNameLine = detail.fileName ? `파일명: ${detail.fileName}\n` : "";
      const finalText =
        fileNameLine && !baseText.includes("파일명:")
          ? `${fileNameLine}${baseText}`
          : baseText;

      void sendTextToAdk(finalText);
    };

    window.addEventListener("adk:chat:send", handler);
    return () => window.removeEventListener("adk:chat:send", handler);
  }, [sendTextToAdk]);

  const canSend = sessionStatus === "ready" && !isSending;

  return (
    <div className="h-full grid grid-rows-[auto_1fr_auto]">
      {/* ── 상단: 세션 상태 ── */}
      <div className="px-3 py-2 border-b bg-muted/50 flex items-center gap-2 min-h-[40px]">
        {sessionStatus === "ready" && (
          <>
            <span className="text-xs text-muted-foreground">session:</span>
            <Badge variant="outline" className="font-mono text-[10px] truncate max-w-[160px]">
              {sessionId}
            </Badge>
          </>
        )}
        {sessionStatus === "creating" && (
          <span className="text-xs text-muted-foreground flex items-center gap-1.5">
            <Loader2 size={11} className="animate-spin" />
            세션 연결 중…
          </span>
        )}
        {sessionStatus === "error" && (
          <span className="text-xs text-destructive flex items-center gap-1.5">
            <AlertCircle size={11} />
            세션 오류
          </span>
        )}
        <div className="flex-1" />
        {sessionStatus === "error" && (
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-xs gap-1"
            onClick={() => {
              setSessionStatus("idle");
              createSession();
            }}
          >
            <RefreshCw size={11} />
            재연결
          </Button>
        )}
        {isSending && (
          <span className="text-xs text-muted-foreground flex items-center gap-1.5">
            <Loader2 size={11} className="animate-spin" />
            전송 중…
          </span>
        )}
      </div>

      {/* ── 메시지 목록 ── */}
      <div ref={scrollerRef} className="overflow-auto p-3 space-y-2.5">
        {messages.map((m, i) => {
          const isUser = m.role === "user";
          return (
            <div
              key={i}
              className={cn("flex", isUser ? "justify-end" : "justify-start")}
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

      {/* ── 입력창 ── */}
      <div className="p-3 border-t bg-muted/50 flex items-center gap-2">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          placeholder={
            sessionStatus === "ready"
              ? "메시지를 입력하세요…"
              : sessionStatus === "creating"
              ? "세션 연결 중…"
              : "세션 오류 – 재연결 후 입력하세요"
          }
          disabled={!canSend}
          className="flex-1 h-10 rounded-xl bg-background"
        />
        <Button
          onClick={send}
          disabled={!canSend || !input.trim()}
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
