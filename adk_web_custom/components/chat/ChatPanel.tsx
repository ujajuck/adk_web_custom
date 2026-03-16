"use client";

import React, {
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";
import { Send, Loader2, AlertCircle, RefreshCw, Save, User, Bot, ChevronDown } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/components/workspace/WorkspaceContext";
import type { Msg } from "@/components/chat/adkTypes";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8080";

/* ── 마크다운 커스텀 컴포넌트 ── */
const markdownComponents: React.ComponentProps<typeof ReactMarkdown>["components"] = {
  // 표: 가로 스크롤 래퍼 + 테두리/줄무늬
  table: ({ children, ...props }) => (
    <div className="overflow-x-auto my-3 rounded-lg border border-gray-200">
      <table
        className="min-w-full border-collapse text-xs"
        {...props}
      >
        {children}
      </table>
    </div>
  ),
  thead: ({ children, ...props }) => (
    <thead className="bg-gray-100 text-gray-700" {...props}>
      {children}
    </thead>
  ),
  tbody: ({ children, ...props }) => (
    <tbody className="divide-y divide-gray-100" {...props}>
      {children}
    </tbody>
  ),
  tr: ({ children, ...props }) => (
    <tr className="even:bg-gray-50 hover:bg-blue-50 transition-colors" {...props}>
      {children}
    </tr>
  ),
  th: ({ children, ...props }) => (
    <th
      className="px-3 py-2 text-left font-semibold text-gray-700 border-b border-gray-300 whitespace-nowrap"
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td
      className="px-3 py-2 text-gray-700 border-r border-gray-100 last:border-r-0 whitespace-nowrap"
      {...props}
    >
      {children}
    </td>
  ),
  // 코드 블록 / 인라인 코드
  code: ({ className, children, ...props }) => {
    const isBlock = className?.startsWith("language-");
    if (isBlock) {
      return (
        <code
          className="block bg-gray-900 text-gray-100 p-3 rounded text-xs font-mono overflow-x-auto"
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code
        className="text-blue-600 bg-blue-50 px-1 py-0.5 rounded text-xs font-mono"
        {...props}
      >
        {children}
      </code>
    );
  },
  pre: ({ children, ...props }) => (
    <pre className="bg-gray-900 rounded my-2 overflow-x-auto text-xs" {...props}>
      {children}
    </pre>
  ),
  // 헤딩
  h1: ({ children, ...props }) => (
    <h1 className="text-base font-bold text-gray-900 mt-4 mb-2 pb-1 border-b border-gray-200" {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2 className="text-sm font-semibold text-gray-900 mt-3 mb-1.5" {...props}>
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3 className="text-sm font-medium text-gray-800 mt-2 mb-1" {...props}>
      {children}
    </h3>
  ),
  // 단락
  p: ({ children, ...props }) => (
    <p className="my-1 leading-relaxed text-gray-800" {...props}>
      {children}
    </p>
  ),
  // 리스트
  ul: ({ children, ...props }) => (
    <ul className="my-1 pl-5 list-disc space-y-0.5" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="my-1 pl-5 list-decimal space-y-0.5" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => (
    <li className="text-gray-700 leading-relaxed" {...props}>
      {children}
    </li>
  ),
  // 인용구
  blockquote: ({ children, ...props }) => (
    <blockquote
      className="border-l-4 border-blue-400 pl-3 my-2 text-gray-600 italic bg-blue-50 py-1 rounded-r"
      {...props}
    >
      {children}
    </blockquote>
  ),
  // 수평선
  hr: () => <hr className="my-3 border-gray-200" />,
  // 링크
  a: ({ children, ...props }) => (
    <a className="text-blue-500 hover:text-blue-700 underline" {...props}>
      {children}
    </a>
  ),
  // 강조
  strong: ({ children, ...props }) => (
    <strong className="font-semibold text-gray-900" {...props}>
      {children}
    </strong>
  ),
};

type SessionStatus = "idle" | "input_user" | "creating" | "ready" | "error";

/* ── Frontend Form types (from ADK stateDelta.frontend_data) ── */
interface FormFieldOption { label: string; value: string }
interface FormField {
  name: string;
  label: string;
  type: "text" | "select" | "number";
  default?: string | number;
  placeholder?: string;
  required?: boolean;
  options?: FormFieldOption[];
  min?: number;
  max?: number;
  step?: number;
}
interface FrontendFormData {
  type: "input_form";
  title?: string;
  description?: string;
  submit_label?: string;
  fields: FormField[];
}

type WorkspaceSendDetail = {
  text: string;
  fileName?: string;
};

type WidgetMeta =
  | { type: "csvFile"; title: string; fileId: string }
  | { type: "plotly"; title: string; fig: any };

const STORAGE_KEY = "chatUserId";

export default function ChatPanel() {
  const { addPlotlyWindow, addCsvFileWindow, addFlowGraphWindow, clearAllWindows } = useWorkspace();

  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [widgetsMeta, setWidgetsMeta] = useState<WidgetMeta[]>([]);

  // 동적 폼 상태 (frontend_trigger)
  const [pendingForm, setPendingForm] = useState<FrontendFormData | null>(null);
  const [formValues, setFormValues] = useState<Record<string, string | number>>({});

  // 에이전트 관련 상태
  const [agents, setAgents] = useState<string[]>(["root_agent"]);
  const [selectedAgent, setSelectedAgent] = useState<string>("root_agent");
  const [currentAgent, setCurrentAgent] = useState<string>("root_agent");
  const [agentDropdownOpen, setAgentDropdownOpen] = useState(false);
  const agentDropdownRef = useRef<HTMLDivElement | null>(null);

  const [userIdInput, setUserIdInput] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem(STORAGE_KEY) ?? "";
    }
    return "";
  });
  const [userId, setUserId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>("input_user");

  const [isSending, setIsSending] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const creatingRef = useRef(false);

  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, pendingForm]);

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
      localStorage.setItem(STORAGE_KEY, inputUserId);

      // 에이전트 목록 로드
      fetch(`${API_URL}/api/agents`)
        .then((r) => r.json())
        .then((data) => {
          const list: string[] = data?.agents ?? [];
          if (list.length > 0) setAgents(list);
        })
        .catch(() => {});

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
        const reqBody: Record<string, string> = {
          user_id: userId,
          session_id: sessionId,
          message: t,
        };
        if (selectedAgent && selectedAgent !== "root_agent") {
          reqBody.agent_name = selectedAgent;
        }
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

        // 새 응답 포맷: { status, outputs, text?, tool_name?, responding_agent? }
        const outputs: Array<{ type: string; uri: string; mime_type?: string }> =
          json?.outputs ?? [];
        const toolName: string = json?.tool_name ?? "";
        if (json?.responding_agent) {
          setCurrentAgent(json.responding_agent);
        }
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
            const widgetTitle = toolName ? `${toolName}_${csv.filename}` : csv.filename;
            addCsvFileWindow(widgetTitle, csv.file_id);
            setWidgetsMeta((prev) => [
              ...prev,
              { type: "csvFile", title: widgetTitle, fileId: csv.file_id },
            ]);
            pushMsg("assistant", `CSV를 워크스페이스에 열었어요: ${widgetTitle}`);
          }
        }

        // 백엔드에서 처리된 plotly_figs 처리 (fig 데이터 포함됨)
        const plotlyFigs: Array<{ fig_id: string; title: string; fig: any }> =
          json?.plotly_figs ?? [];
        for (const pf of plotlyFigs) {
          if (pf.fig && pf.title) {
            const widgetTitle = toolName ? `${toolName}_${pf.title}` : pf.title;
            addPlotlyWindow(widgetTitle, pf.fig);
            setWidgetsMeta((prev) => [
              ...prev,
              { type: "plotly", title: widgetTitle, fig: pf.fig },
            ]);
            pushMsg("assistant", `그래프를 워크스페이스에 열었어요: ${widgetTitle}`);
          }
        }

        // Assistant text
        const hasWidgets = csvFiles.length > 0 || plotlyFigs.length > 0 || outputs.length > 0;
        if (json?.text) {
          pushMsg("assistant", json.text);
        } else if (!hasWidgets && !json?.frontend_data) {
          pushMsg(
            "assistant",
            `응답 없음\n${JSON.stringify(json, null, 2)}`,
          );
        }

        // 동적 폼 트리거
        if (json?.frontend_data?.type === "input_form") {
          const formData = json.frontend_data as FrontendFormData;
          // 각 필드의 default 값으로 초기화
          const initValues: Record<string, string | number> = {};
          for (const f of formData.fields) {
            initValues[f.name] = f.default ?? (f.type === "number" ? 0 : "");
          }
          setFormValues(initValues);
          setPendingForm(formData);
        }
      } catch (e: any) {
        console.error("[ChatPanel] Chat error:", e);
        pushMsg("assistant", `요청 오류: ${String(e?.message ?? e)}`);
      } finally {
        setIsSending(false);
        // 응답 후 입력창 자동 포커스
        setTimeout(() => inputRef.current?.focus(), 0);
      }
    },
    [isSending, userId, sessionId, selectedAgent, addCsvFileWindow, addPlotlyWindow, setWidgetsMeta],
  );

  function send() {
    void sendTextToAdk(input);
  }

  function submitForm(e: React.FormEvent) {
    e.preventDefault();
    if (!pendingForm) return;
    const payload = JSON.stringify(formValues, null, 2);
    setPendingForm(null);
    setFormValues({});
    void sendTextToAdk(payload);
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
          metadata: { widgets: widgetsMeta },
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
  }, [userId, sessionId, messages, widgetsMeta]);

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

  // Listen for workspace:save (워크스페이스 TopBar 저장 버튼)
  useEffect(() => {
    const handler = () => void saveNotebook();
    window.addEventListener("workspace:save", handler);
    return () => window.removeEventListener("workspace:save", handler);
  }, [saveNotebook]);

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
          metadata?: { widgets?: WidgetMeta[] };
        };
      }>;
      const nb = ce.detail?.notebook;
      if (nb?.messages) {
        setMessages(nb.messages as Msg[]);

        // 저장된 위젯 복원 (채팅 메시지 표시 없이)
        const savedWidgets = nb.metadata?.widgets ?? [];
        clearAllWindows();
        for (const w of savedWidgets) {
          if (w.type === "csvFile") {
            addCsvFileWindow(w.title, w.fileId);
          } else if (w.type === "plotly") {
            addPlotlyWindow(w.title, w.fig);
          }
        }
        setWidgetsMeta(savedWidgets);
      }
    };

    window.addEventListener("notebook:select", handler);
    return () => window.removeEventListener("notebook:select", handler);
  }, [clearAllWindows, addCsvFileWindow, addPlotlyWindow]);

  // Listen for notebook:add events (from FlowWidget save)
  useEffect(() => {
    const handler = async (e: Event) => {
      const ce = e as CustomEvent<{
        type: string;
        sessionId: string;
        data: any;
        selectedArtifacts: string[];
        title: string;
      }>;
      const { selectedArtifacts, title } = ce.detail || {};

      if (!userId || !sessionId) {
        pushMsg("assistant", "세션이 아직 준비되지 않았습니다.");
        return;
      }

      // Filter messages to only include those related to selected artifacts
      let filteredMessages = messages;
      if (selectedArtifacts && selectedArtifacts.length > 0) {
        filteredMessages = messages.filter((msg) =>
          selectedArtifacts.some((artifact) =>
            msg.text.toLowerCase().includes(artifact.toLowerCase())
          )
        );
        // If no messages match, include all
        if (filteredMessages.length === 0) {
          filteredMessages = messages;
        }
      }

      try {
        const notebookTitle = title || `Flow ${new Date().toLocaleString("ko-KR")}`;
        const res = await fetch(`${API_URL}/api/notebooks`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId,
            session_id: sessionId,
            title: notebookTitle,
            messages: filteredMessages,
          }),
        });

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }

        const notebook = await res.json();
        pushMsg("assistant", `노트북 저장됨: ${notebook.title} (${selectedArtifacts?.length || 0}개 아티팩트)`);
        window.dispatchEvent(new CustomEvent("notebook:refresh", { detail: { userId } }));
      } catch (e: any) {
        console.error("[ChatPanel] Notebook add error:", e);
        pushMsg("assistant", `저장 실패: ${String(e?.message ?? e)}`);
      }
    };

    window.addEventListener("notebook:add", handler);
    return () => window.removeEventListener("notebook:add", handler);
  }, [userId, sessionId, messages]);

  // Listen for chat:insert events (from Ctrl+click on widgets/columns)
  useEffect(() => {
    const handler = (e: Event) => {
      const ce = e as CustomEvent<{ text: string; artifact?: string; column?: string }>;
      const { text } = ce.detail || {};
      if (text) {
        setInput((prev) => prev + text);
        inputRef.current?.focus();
      }
    };

    window.addEventListener("chat:insert", handler);
    return () => window.removeEventListener("chat:insert", handler);
  }, []);

  // Listen for chat:new-session (새 대화 - userId 유지, 세션만 초기화)
  useEffect(() => {
    const handler = () => {
      const savedId = localStorage.getItem(STORAGE_KEY) ?? "";
      setMessages([]);
      setInput("");
      setWidgetsMeta([]);
      setSessionId("");
      setSessionStatus("creating");
      clearAllWindows();
      creatingRef.current = false;
      if (savedId) {
        createSession(savedId);
      } else {
        setSessionStatus("input_user");
      }
    };

    window.addEventListener("chat:new-session", handler);
    return () => window.removeEventListener("chat:new-session", handler);
  }, [createSession, clearAllWindows]);

  // 에이전트 드롭다운 외부 클릭 시 닫기
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (agentDropdownRef.current && !agentDropdownRef.current.contains(e.target as Node)) {
        setAgentDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // 채팅 배경(컨테이너 자체)을 클릭할 때만 입력창 포커스
  // 메시지 텍스트 선택/복사 시에는 포커스 이동하지 않음
  const handleChatAreaClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget && sessionStatus === "ready") {
      inputRef.current?.focus();
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
            {/* 현재 응답 에이전트 + 선택 드롭다운 */}
            <div ref={agentDropdownRef} className="relative ml-1">
              <button
                className={cn(
                  "h-6 px-2 text-xs rounded-full flex items-center gap-1 transition-colors border",
                  selectedAgent === "root_agent"
                    ? "bg-purple-50 border-purple-200 text-purple-700 hover:bg-purple-100"
                    : "bg-blue-50 border-blue-200 text-blue-700 hover:bg-blue-100"
                )}
                onClick={() => setAgentDropdownOpen((v) => !v)}
                title="에이전트 선택"
              >
                <Bot size={10} />
                <span className="max-w-[80px] truncate">{selectedAgent}</span>
                <ChevronDown size={10} />
              </button>
              {agentDropdownOpen && (
                <div className="absolute top-full left-0 mt-1 z-50 bg-white border border-gray-200 rounded-lg shadow-lg min-w-[160px] py-1">
                  <div className="px-3 py-1.5 text-xs text-gray-400 font-medium border-b border-gray-100">
                    에이전트 선택
                  </div>
                  {agents.map((ag) => (
                    <button
                      key={ag}
                      className={cn(
                        "w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 flex items-center gap-2 transition-colors",
                        selectedAgent === ag ? "text-purple-700 font-medium" : "text-gray-700"
                      )}
                      onClick={() => {
                        setSelectedAgent(ag);
                        setAgentDropdownOpen(false);
                      }}
                    >
                      <Bot size={10} className={selectedAgent === ag ? "text-purple-500" : "text-gray-400"} />
                      <span className="truncate">{ag}</span>
                      {currentAgent === ag && (
                        <span className="ml-auto text-[10px] text-green-600 bg-green-50 px-1 rounded">
                          응답중
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {/* 현재 실제 응답한 에이전트 표시 (선택과 다를 때) */}
            {currentAgent !== selectedAgent && (
              <span className="text-[10px] text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded-full border border-amber-200">
                실제: {currentAgent}
              </span>
            )}
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
                  "max-w-[90%] px-4 py-2.5 text-sm leading-relaxed",
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
                    components={markdownComponents}
                    className="max-w-none text-sm"
                  >
                    {m.text}
                  </ReactMarkdown>
                )}
              </div>
            </div>
          );
        })}

        {/* ── 동적 입력 폼 (frontend_trigger) ── */}
        {pendingForm && (
          <div className="flex justify-start">
            <div className="max-w-[95%] w-full bg-white rounded-2xl rounded-bl-md shadow-sm border border-blue-200 overflow-hidden">
              {/* 폼 헤더 */}
              <div className="px-4 py-3 bg-blue-50 border-b border-blue-100 flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-blue-400" />
                <span className="text-sm font-semibold text-blue-800">
                  {pendingForm.title ?? "입력 필요"}
                </span>
              </div>
              <form onSubmit={submitForm} className="px-4 py-3 space-y-3">
                {pendingForm.description && (
                  <p className="text-xs text-gray-500">{pendingForm.description}</p>
                )}
                {pendingForm.fields.map((field) => (
                  <div key={field.name} className="space-y-1">
                    <label className="block text-xs font-medium text-gray-700">
                      {field.label}
                      {field.required && <span className="text-red-500 ml-0.5">*</span>}
                    </label>
                    {field.type === "select" ? (
                      <select
                        className="w-full h-9 px-3 rounded-lg border border-gray-300 text-sm bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white"
                        value={String(formValues[field.name] ?? field.default ?? "")}
                        required={field.required}
                        onChange={(e) =>
                          setFormValues((v) => ({ ...v, [field.name]: e.target.value }))
                        }
                      >
                        {(field.options ?? []).map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    ) : field.type === "number" ? (
                      <input
                        type="number"
                        className="w-full h-9 px-3 rounded-lg border border-gray-300 text-sm bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white"
                        value={formValues[field.name] ?? field.default ?? ""}
                        required={field.required}
                        min={field.min}
                        max={field.max}
                        step={field.step}
                        placeholder={field.placeholder}
                        onChange={(e) =>
                          setFormValues((v) => ({
                            ...v,
                            [field.name]: e.target.valueAsNumber,
                          }))
                        }
                      />
                    ) : (
                      <input
                        type="text"
                        className="w-full h-9 px-3 rounded-lg border border-gray-300 text-sm bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white"
                        value={String(formValues[field.name] ?? field.default ?? "")}
                        required={field.required}
                        placeholder={field.placeholder}
                        onChange={(e) =>
                          setFormValues((v) => ({ ...v, [field.name]: e.target.value }))
                        }
                      />
                    )}
                  </div>
                ))}
                <div className="flex gap-2 pt-1">
                  <button
                    type="submit"
                    disabled={!canSend}
                    className={cn(
                      "flex-1 h-9 rounded-lg text-sm font-medium transition-all",
                      "bg-blue-500 text-white hover:bg-blue-600",
                      "disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed"
                    )}
                  >
                    {pendingForm.submit_label ?? "실행"}
                  </button>
                  <button
                    type="button"
                    className="h-9 px-3 rounded-lg text-sm text-gray-500 hover:bg-gray-100 transition-colors"
                    onClick={() => setPendingForm(null)}
                  >
                    취소
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>

      {/* ── 입력창 ── */}
      <div className="p-3 border-t border-gray-200 bg-white flex items-center gap-2">
        <input
          ref={inputRef}
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
