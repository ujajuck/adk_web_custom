"use client";

import {
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";
import { Send, Loader2, AlertCircle, RefreshCw, Save, User, Paperclip } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/components/workspace/WorkspaceContext";
import type { Msg } from "@/components/chat/adkTypes";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8080";

type SessionStatus = "idle" | "input_user" | "creating" | "ready" | "error";

type WorkspaceSendDetail = {
  text: string;
  fileName?: string;
};

export default function ChatPanel() {
  const { addPlotlyWindow, addCsvFileWindow, addFlowGraphWindow } = useWorkspace();

  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");

  const [userIdInput, setUserIdInput] = useState("");
  const [userId, setUserId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>("input_user");

  const [isSending, setIsSending] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const creatingRef = useRef(false);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages]);

  function pushMsg(role: Msg["role"], text: string) {
    setMessages((m) => [...m, { role, text }]);
  }

  const createSession = useCallback(async (inputUserId: string) => {
    if (creatingRef.current) return;
    creatingRef.current = true;

    const sessionIdVal = `${inputUserId}_${Date.now()}`;
    setSessionStatus("creating");
    setMessages([{ role: "assistant", text: "세션 생성 중…" }]);

    try {
      const reqBody = {
        user_id: inputUserId,
        session_id: sessionIdVal,
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

      setUserId(inputUserId);
      setSessionId(sessionIdVal);
      setSessionStatus("ready");
      setMessages([{ role: "assistant", text: `세션 준비됨 · ${inputUserId}` }]);

      // Emit event to load notebooks
      window.dispatchEvent(new CustomEvent("notebook:load", { detail: { userId: inputUserId } }));
    } catch (e: any) {
      console.error("[ChatPanel] Session error:", e);
      setSessionStatus("error");
      setMessages([{ role: "assistant", text: `세션 생성 실패: ${String(e?.message ?? e)}` }]);
    } finally {
      creatingRef.current = false;
    }
  }, []);

  const handleStartSession = () => {
    const trimmed = userIdInput.trim();
    if (!trimmed) return;
    createSession(trimmed);
  };

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

          // CSV/JSON은 백엔드에서 처리 후 csv_files/plotly_figs로 전달되므로 여기서 스킵
          if (uri.endsWith(".csv") || mime === "text/csv") continue;
          if (uri.endsWith(".json") || mime === "application/json") continue;

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

  const saveNotebook = useCallback(async () => {
    if (!userId || !sessionId || messages.length === 0) return;

    setIsSaving(true);
    try {
      const title = `대화 ${new Date().toLocaleString("ko-KR")}`;
      const res = await fetch(`${API_URL}/api/notebooks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          session_id: sessionId,
          title,
          messages,
        }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const notebook = await res.json();
      pushMsg("assistant", `노트북 저장됨: ${notebook.title}`);

      // Emit event to refresh notebook list
      window.dispatchEvent(new CustomEvent("notebook:refresh", { detail: { userId } }));
    } catch (e: any) {
      console.error("[ChatPanel] Save error:", e);
      pushMsg("assistant", `저장 실패: ${String(e?.message ?? e)}`);
    } finally {
      setIsSaving(false);
    }
  }, [userId, sessionId, messages]);

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

  // Listen for notebook selection (load history)
  useEffect(() => {
    const handler = (e: Event) => {
      const ce = e as CustomEvent<{
        notebook: {
          notebook_id: string;
          user_id: string;
          session_id: string;
          title: string;
          messages: Array<{ role: string; text: string }>;
        };
      }>;
      const nb = ce.detail?.notebook;
      if (nb?.messages) {
        setMessages(nb.messages as Msg[]);
        pushMsg("assistant", `노트북 "${nb.title}" 불러옴 (읽기 전용)`);
      }
    };

    window.addEventListener("notebook:select", handler);
    return () => window.removeEventListener("notebook:select", handler);
  }, []);

  // Listen for chat:insert events (from Ctrl+click on widgets/columns)
  useEffect(() => {
    const handler = (e: Event) => {
      const ce = e as CustomEvent<{ text: string; artifact?: string; column?: string }>;
      const { text, artifact } = ce.detail || {};
      if (text) {
        setInput((prev) => prev + text);
        inputRef.current?.focus();
      }
    };

    window.addEventListener("chat:insert", handler);
    return () => window.removeEventListener("chat:insert", handler);
  }, []);

  // Click anywhere on chat area to focus input
  const handleChatAreaClick = () => {
    if (sessionStatus === "ready") {
      inputRef.current?.focus();
    }
  };

  // File attachment handling
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      setAttachedFiles(Array.from(files));
    }
    e.target.value = "";
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      setAttachedFiles(Array.from(files));
    }
  };

  const removeAttachedFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const sendWithFiles = async () => {
    const t = input.trim();
    if ((!t && attachedFiles.length === 0) || isSending) return;

    if (!userId || !sessionId) {
      pushMsg("assistant", "세션이 아직 준비되지 않았습니다.");
      return;
    }

    setIsSending(true);

    // Show user message with file info
    const fileNames = attachedFiles.map((f) => f.name).join(", ");
    const displayText = fileNames ? `${t}\n[첨부: ${fileNames}]` : t;
    pushMsg("user", displayText);
    setInput("");

    try {
      // Upload files first if any
      const uploadedPaths: string[] = [];
      for (const file of attachedFiles) {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("session_id", sessionId);

        const uploadRes = await fetch(`${API_URL}/api/files/upload`, {
          method: "POST",
          body: formData,
        });

        if (uploadRes.ok) {
          const uploadData = await uploadRes.json();
          uploadedPaths.push(uploadData.path || uploadData.filename || file.name);
        }
      }

      setAttachedFiles([]);

      // Include file paths in message
      let finalMessage = t;
      if (uploadedPaths.length > 0) {
        finalMessage = `${t}\n\n[첨부 파일: ${uploadedPaths.join(", ")}]`;
      }

      // Send to backend
      const reqBody = {
        user_id: userId,
        session_id: sessionId,
        message: finalMessage,
      };

      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(reqBody),
      });

      const responseText = await res.text();
      let json: any = null;
      try {
        json = JSON.parse(responseText);
      } catch {
        pushMsg("assistant", `응답 파싱 실패: ${responseText.slice(0, 200)}`);
        return;
      }

      if (!res.ok) {
        pushMsg("assistant", `요청 실패 (${res.status}): ${JSON.stringify(json?.detail ?? json)}`);
        return;
      }

      // Process response (same as sendTextToAdk)
      const csvFiles: Array<{ file_id: string; filename: string }> = json?.csv_files ?? [];
      for (const csv of csvFiles) {
        if (csv.file_id && csv.filename) {
          addCsvFileWindow(csv.filename, csv.file_id);
          pushMsg("assistant", `CSV를 워크스페이스에 열었어요: ${csv.filename}`);
        }
      }

      const plotlyFigs: Array<{ fig_id: string; title: string; fig: any }> = json?.plotly_figs ?? [];
      for (const pf of plotlyFigs) {
        if (pf.fig && pf.title) {
          addPlotlyWindow(pf.title, pf.fig);
          pushMsg("assistant", `그래프를 워크스페이스에 열었어요: ${pf.title}`);
        }
      }

      if (json?.text) {
        pushMsg("assistant", json.text);
      } else if (csvFiles.length === 0 && plotlyFigs.length === 0) {
        pushMsg("assistant", `응답 없음`);
      }
    } catch (e: any) {
      console.error("[ChatPanel] Send error:", e);
      pushMsg("assistant", `요청 오류: ${String(e?.message ?? e)}`);
    } finally {
      setIsSending(false);
    }
  };

  const canSend = sessionStatus === "ready" && !isSending;

  // User ID input screen
  if (sessionStatus === "input_user" || sessionStatus === "idle") {
    return (
      <div className="h-full flex flex-col bg-white">
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="w-full max-w-sm space-y-4">
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <User size={32} className="text-blue-500" />
              </div>
              <h2 className="text-lg font-semibold text-gray-800">사용자 ID 입력</h2>
              <p className="text-sm text-gray-500 mt-1">
                ID를 입력하면 저장된 노트북을 불러옵니다
              </p>
            </div>
            <div className="space-y-3">
              <input
                value={userIdInput}
                onChange={(e) => setUserIdInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleStartSession()}
                placeholder="사용자 ID (예: hong_analyst)"
                className={cn(
                  "w-full h-12 px-4 rounded-lg border text-sm transition-all",
                  "bg-gray-50 border-gray-300 placeholder:text-gray-400",
                  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent focus:bg-white"
                )}
              />
              <button
                onClick={handleStartSession}
                disabled={!userIdInput.trim()}
                className={cn(
                  "w-full h-12 rounded-lg font-medium text-sm transition-all",
                  "bg-blue-500 text-white hover:bg-blue-600",
                  "disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed"
                )}
              >
                시작하기
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-white">
      {/* ── 상단: 세션 상태 ── */}
      <div className="px-4 py-2.5 border-b border-gray-200 bg-gray-50 flex items-center gap-2 min-h-[44px]">
        {sessionStatus === "ready" && (
          <>
            <User size={12} className="text-gray-400" />
            <span className="font-mono text-xs text-gray-600 truncate max-w-[120px]">
              {userId}
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
              setSessionStatus("input_user");
            }}
          >
            <RefreshCw size={12} />
            재시작
          </button>
        )}
        {sessionStatus === "ready" && (
          <button
            className="h-7 px-2.5 text-xs text-green-600 hover:text-green-700 hover:bg-green-50 rounded-md flex items-center gap-1 transition-colors disabled:opacity-50"
            onClick={saveNotebook}
            disabled={isSaving || messages.length === 0}
          >
            {isSaving ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
            저장
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
      <div
        ref={scrollerRef}
        className="flex-1 overflow-auto p-4 space-y-3 bg-gray-50 cursor-text"
        onClick={handleChatAreaClick}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleFileDrop}
      >
        {messages.map((m, i) => {
          const isUser = m.role === "user";
          return (
            <div
              key={i}
              className={cn("flex", isUser ? "justify-end" : "justify-start")}
            >
              <div
                className={cn(
                  "max-w-[80%] px-4 py-2.5 text-sm leading-relaxed",
                  isUser
                    ? "bg-blue-500 text-white rounded-2xl rounded-br-md shadow-md whitespace-pre-wrap"
                    : "bg-white text-gray-800 rounded-2xl rounded-bl-md shadow-sm border border-gray-200",
                )}
              >
                {isUser ? (
                  m.text
                ) : (
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    className="prose prose-sm max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:my-2 prose-code:text-blue-600 prose-code:bg-blue-50 prose-code:px-1 prose-code:rounded"
                  >
                    {m.text}
                  </ReactMarkdown>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── 첨부 파일 표시 ── */}
      {attachedFiles.length > 0 && (
        <div className="px-3 py-2 border-t border-gray-200 bg-gray-50 flex flex-wrap gap-2">
          {attachedFiles.map((file, idx) => (
            <div
              key={idx}
              className="flex items-center gap-1.5 bg-blue-100 text-blue-700 px-2 py-1 rounded-full text-xs"
            >
              <Paperclip size={12} />
              <span className="max-w-[150px] truncate">{file.name}</span>
              <button
                onClick={() => removeAttachedFile(idx)}
                className="hover:text-blue-900"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ── 입력창 ── */}
      <div className="p-3 border-t border-gray-200 bg-white flex items-center gap-2">
        {/* 파일 첨부 버튼 */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileSelect}
          multiple
          className="hidden"
          accept=".csv,.json,.xlsx,.xls,.txt,.png,.jpg,.jpeg,.pdf"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={!canSend}
          className={cn(
            "h-11 w-11 rounded-full flex items-center justify-center transition-all shrink-0",
            "border border-gray-300 text-gray-500 hover:bg-gray-100 hover:text-gray-700",
            "disabled:opacity-50 disabled:cursor-not-allowed"
          )}
          title="파일 첨부"
        >
          <Paperclip size={18} />
        </button>

        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendWithFiles()}
          placeholder={
            sessionStatus === "ready"
              ? "메시지를 입력하세요… (파일 드래그 앤 드롭 가능)"
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
          onClick={sendWithFiles}
          disabled={!canSend || (!input.trim() && attachedFiles.length === 0)}
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
