"use client";

import {
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";
import { Send, Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
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
  const { addPlotlyWindow, addCsvFileWindow, addFlowGraphWindow } = useWorkspace();

  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");

  const [userId, setUserId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>("idle");

  const [isSending, setIsSending] = useState(false);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const creatingRef = useRef(false);

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
      const reqBody = {
        user_id: id,
        session_id: id,
        session_name: "",
      };
      console.log("[ChatPanel] Creating session:", API_URL, reqBody);

      const res = await fetch(`${API_URL}/api/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(reqBody),
      });

      const text = await res.text();
      console.log("[ChatPanel] Session response:", res.status, text);

      let json: any = null;
      try {
        json = JSON.parse(text);
      } catch {
        throw new Error(`Invalid JSON: ${text.slice(0, 200)}`);
      }

      if (!res.ok || !json?.session_id) {
        throw new Error(json?.detail ?? `HTTP ${res.status}`);
      }

      setUserId(id);
      setSessionId(id);
      setSessionStatus("ready");
      pushMsg("assistant", `세션 준비됨 · ${id}`);
    } catch (e: any) {
      console.error("[ChatPanel] Session error:", e);
      setSessionStatus("error");
      pushMsg("assistant", `세션 생성 실패: ${String(e?.message ?? e)}`);
    } finally {
      creatingRef.current = false;
    }
  }, []);

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
        const reqBody = {
          user_id: userId,
          session_id: sessionId,
          message: t,
        };
        console.log("[ChatPanel] Sending chat:", API_URL, reqBody);

        const res = await fetch(`${API_URL}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(reqBody),
        });

        const responseText = await res.text();
        console.log("[ChatPanel] Chat response:", res.status, responseText.slice(0, 500));

        let json: any = null;
        try {
          json = JSON.parse(responseText);
        } catch {
          pushMsg("assistant", `응답 파싱 실패: ${responseText.slice(0, 200)}`);
          return;
        }

        if (!res.ok) {
          pushMsg(
            "assistant",
            `요청 실패 (${res.status}): ${JSON.stringify(json?.detail ?? json)}`,
          );
          return;
        }

        // 새 응답 포맷: { status, outputs: [{ type, uri, mime_type }], text?, tool_name? }
        const outputs: Array<{ type: string; uri: string; mime_type?: string }> =
          json?.outputs ?? [];
        const toolName: string = json?.tool_name ?? "";
        const isPlottingTool = toolName.startsWith("plotting");

        for (const out of outputs) {
          if (out.type !== "resource_link") continue;

          const uri = out.uri ?? "";
          const mime = out.mime_type ?? "";

          // CSV 파일
          if (uri.endsWith(".csv") || mime === "text/csv") {
            const filename = uri.split("/").pop() ?? "data.csv";
            // URI에서 file_id 추출 (예: /files/{file_id}/... 또는 그냥 URI 사용)
            const fileId = uri;
            addCsvFileWindow(filename, fileId);
            pushMsg("assistant", `CSV를 워크스페이스에 열었어요: ${filename}`);
            continue;
          }

          // JSON 파일 - plotting 툴인 경우에만 Plotly로 처리
          if (uri.endsWith(".json") || mime === "application/json") {
            if (isPlottingTool) {
              // Plotly 데이터 fetch
              try {
                const figRes = await fetch(`${API_URL}${uri.startsWith("/") ? "" : "/"}${uri}`);
                if (figRes.ok) {
                  const fig = await figRes.json();
                  const title = uri.split("/").pop()?.replace(".json", "") ?? "Chart";
                  addPlotlyWindow(title, fig);
                  pushMsg("assistant", `그래프를 워크스페이스에 열었어요: ${title}`);
                }
              } catch (e) {
                console.error("[ChatPanel] Failed to fetch plotly data:", e);
              }
            }
            // plotting이 아닌 경우 .json은 무시 (위젯으로 표시 안함)
            continue;
          }

          // 이미지 등 다른 리소스는 메시지로만 안내
          if (mime.startsWith("image/")) {
            pushMsg("assistant", `이미지 생성됨: ${uri}`);
          }
        }

        // 백엔드에서 처리된 csv_files 처리
        const csvFiles: Array<{ file_id: string; filename: string }> =
          json?.csv_files ?? [];
        for (const csv of csvFiles) {
          if (csv.file_id && csv.filename) {
            addCsvFileWindow(csv.filename, csv.file_id);
            pushMsg("assistant", `CSV를 워크스페이스에 열었어요: ${csv.filename}`);
          }
        }

        // 백엔드에서 처리된 plotly_figs 처리 (fig 데이터 포함됨)
        const plotlyFigs: Array<{ fig_id: string; title: string; fig: any }> =
          json?.plotly_figs ?? [];
        for (const pf of plotlyFigs) {
          if (pf.fig && pf.title) {
            addPlotlyWindow(pf.title, pf.fig);
            pushMsg("assistant", `그래프를 워크스페이스에 열었어요: ${pf.title}`);
          }
        }

        // Assistant text
        const hasWidgets = csvFiles.length > 0 || plotlyFigs.length > 0 || outputs.length > 0;
        if (json?.text) {
          pushMsg("assistant", json.text);
        } else if (!hasWidgets) {
          pushMsg(
            "assistant",
            `응답 없음\n${JSON.stringify(json, null, 2)}`,
          );
        }
      } catch (e: any) {
        console.error("[ChatPanel] Chat error:", e);
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

  // Listen for flow graph request
  useEffect(() => {
    const handler = () => {
      if (sessionId) {
        addFlowGraphWindow("Artifact Flow", sessionId);
      } else {
        pushMsg("assistant", "세션이 아직 준비되지 않았습니다.");
      }
    };

    window.addEventListener("workspace:flow", handler);
    return () => window.removeEventListener("workspace:flow", handler);
  }, [sessionId, addFlowGraphWindow]);

  const canSend = sessionStatus === "ready" && !isSending;

  return (
    <div className="h-full flex flex-col bg-white">
      {/* ── 상단: 세션 상태 ── */}
      <div className="px-4 py-2.5 border-b border-gray-200 bg-gray-50 flex items-center gap-2 min-h-[44px]">
        {sessionStatus === "ready" && (
          <>
            <span className="text-xs text-gray-500">session:</span>
            <span className="font-mono text-[10px] text-gray-600 bg-white border border-gray-200 rounded px-1.5 py-0.5 truncate max-w-[160px]">
              {sessionId}
            </span>
          </>
        )}
        {sessionStatus === "creating" && (
          <span className="text-xs text-gray-500 flex items-center gap-1.5">
            <Loader2 size={12} className="animate-spin" />
            세션 연결 중…
          </span>
        )}
        {sessionStatus === "error" && (
          <span className="text-xs text-red-600 flex items-center gap-1.5">
            <AlertCircle size={12} />
            세션 오류
          </span>
        )}
        <div className="flex-1" />
        {sessionStatus === "error" && (
          <button
            className="h-7 px-2.5 text-xs text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md flex items-center gap-1 transition-colors"
            onClick={() => {
              setSessionStatus("idle");
              createSession();
            }}
          >
            <RefreshCw size={12} />
            재연결
          </button>
        )}
        {isSending && (
          <span className="text-xs text-blue-600 flex items-center gap-1.5">
            <Loader2 size={12} className="animate-spin" />
            전송 중…
          </span>
        )}
      </div>

      {/* ── 메시지 목록 ── */}
      <div ref={scrollerRef} className="flex-1 overflow-auto p-4 space-y-3 bg-gray-50">
        {messages.map((m, i) => {
          const isUser = m.role === "user";
          return (
            <div
              key={i}
              className={cn("flex", isUser ? "justify-end" : "justify-start")}
            >
              <div
                className={cn(
                  "max-w-[80%] px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap",
                  isUser
                    ? "bg-blue-500 text-white rounded-2xl rounded-br-md shadow-md"
                    : "bg-white text-gray-800 rounded-2xl rounded-bl-md shadow-sm border border-gray-200",
                )}
              >
                {m.text}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── 입력창 ── */}
      <div className="p-3 border-t border-gray-200 bg-white flex items-center gap-2">
        <input
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
          className={cn(
            "flex-1 h-11 px-4 rounded-full border text-sm transition-all",
            "bg-gray-50 border-gray-300 placeholder:text-gray-400",
            "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent focus:bg-white",
            "disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed"
          )}
        />
        <button
          onClick={send}
          disabled={!canSend || !input.trim()}
          className={cn(
            "h-11 w-11 rounded-full flex items-center justify-center transition-all shrink-0",
            "bg-blue-500 text-white shadow-md hover:bg-blue-600 hover:shadow-lg",
            "active:scale-95",
            "disabled:bg-gray-300 disabled:text-gray-500 disabled:shadow-none disabled:cursor-not-allowed"
          )}
        >
          {isSending ? (
            <Loader2 size={18} className="animate-spin" />
          ) : (
            <Send size={18} />
          )}
        </button>
      </div>
    </div>
  );
}
