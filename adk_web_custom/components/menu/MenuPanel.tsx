"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  ChevronLeft,
  FileText,
  Users,
  Plus,
  Share2,
  Trash2,
  Loader2,
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8080";

type Props = {
  collapsed: boolean;
  onCollapse: () => void;
};

type Notebook = {
  notebook_id: string;
  user_id: string;
  session_id: string;
  title: string;
  messages: Array<{ role: string; text: string }>;
  is_shared: boolean;
  created_at: string;
  updated_at: string;
};

export default function MenuPanel({ collapsed, onCollapse }: Props) {
  const [userId, setUserId] = useState("");
  const [myNotebooks, setMyNotebooks] = useState<Notebook[]>([]);
  const [sharedNotebooks, setSharedNotebooks] = useState<Notebook[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedNotebook, setSelectedNotebook] = useState<Notebook | null>(null);

  const fetchMyNotebooks = useCallback(async (uid: string) => {
    if (!uid) return;
    try {
      const res = await fetch(`${API_URL}/api/notebooks/user/${uid}`);
      if (res.ok) {
        const data = await res.json();
        setMyNotebooks(data);
      }
    } catch (e) {
      console.error("Failed to fetch notebooks:", e);
    }
  }, []);

  const fetchSharedNotebooks = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/notebooks/shared`);
      if (res.ok) {
        const data = await res.json();
        setSharedNotebooks(data);
      }
    } catch (e) {
      console.error("Failed to fetch shared notebooks:", e);
    }
  }, []);

  const refreshAll = useCallback(
    async (uid: string) => {
      setLoading(true);
      await Promise.all([fetchMyNotebooks(uid), fetchSharedNotebooks()]);
      setLoading(false);
    },
    [fetchMyNotebooks, fetchSharedNotebooks],
  );

  // Listen for notebook events
  useEffect(() => {
    const handleLoad = (e: Event) => {
      const ce = e as CustomEvent<{ userId: string }>;
      const uid = ce.detail?.userId || "";
      setUserId(uid);
      if (uid) {
        refreshAll(uid);
      }
    };

    const handleRefresh = (e: Event) => {
      const ce = e as CustomEvent<{ userId: string }>;
      const uid = ce.detail?.userId || userId;
      if (uid) {
        refreshAll(uid);
      }
    };

    window.addEventListener("notebook:load", handleLoad);
    window.addEventListener("notebook:refresh", handleRefresh);
    return () => {
      window.removeEventListener("notebook:load", handleLoad);
      window.removeEventListener("notebook:refresh", handleRefresh);
    };
  }, [userId, refreshAll]);

  const handleShare = async (notebook: Notebook, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const res = await fetch(`${API_URL}/api/notebooks/${notebook.notebook_id}/share`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_shared: !notebook.is_shared }),
      });
      if (res.ok) {
        refreshAll(userId);
      }
    } catch (err) {
      console.error("Failed to share notebook:", err);
    }
  };

  const handleDelete = async (notebookId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("정말 삭제하시겠습니까?")) return;
    try {
      const res = await fetch(`${API_URL}/api/notebooks/${notebookId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        refreshAll(userId);
        if (selectedNotebook?.notebook_id === notebookId) {
          setSelectedNotebook(null);
        }
      }
    } catch (err) {
      console.error("Failed to delete notebook:", err);
    }
  };

  const handleSelectNotebook = (notebook: Notebook) => {
    setSelectedNotebook(notebook);
    // Emit event to load chat history
    window.dispatchEvent(
      new CustomEvent("notebook:select", { detail: { notebook } }),
    );
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString("ko-KR");
    } catch {
      return dateStr;
    }
  };

  if (collapsed) return null;

  return (
    <div className="h-full flex flex-col bg-slate-50">
      {/* 헤더 */}
      <div className="px-4 py-3 flex items-center justify-between border-b bg-white">
        <span className="font-semibold text-slate-800">노트북</span>
        <div className="flex items-center gap-1">
          {loading && <Loader2 size={14} className="animate-spin text-slate-400" />}
          <button
            onClick={onCollapse}
            className="p-1.5 rounded-md hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors"
            title="메뉴 접기"
          >
            <ChevronLeft size={18} />
          </button>
        </div>
      </div>

      {/* 사용자 정보 */}
      {userId && (
        <div className="px-4 py-2 border-b bg-slate-100 text-xs text-slate-600">
          사용자: <span className="font-medium">{userId}</span>
        </div>
      )}

      {/* 새 노트북 버튼 */}
      <div className="px-3 py-2">
        <button
          onClick={() =>
            window.dispatchEvent(new CustomEvent("chat:new-session"))
          }
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          새 대화
        </button>
      </div>

      {/* 목록 */}
      <ScrollArea className="flex-1 px-3">
        <div className="flex items-center gap-1.5 px-1 py-2 text-xs font-medium text-slate-500 uppercase tracking-wide">
          <FileText size={12} />
          내 노트북 ({myNotebooks.length})
        </div>

        {myNotebooks.length === 0 && (
          <div className="text-xs text-slate-400 px-3 py-2">저장된 노트북이 없습니다</div>
        )}

        {myNotebooks.map((nb) => (
          <div
            key={nb.notebook_id}
            onClick={() => handleSelectNotebook(nb)}
            className={`w-full text-left px-3 py-2.5 mb-1 rounded-lg hover:bg-white hover:shadow-sm border transition-all group cursor-pointer ${
              selectedNotebook?.notebook_id === nb.notebook_id
                ? "bg-white border-blue-200 shadow-sm"
                : "border-transparent hover:border-slate-200"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm text-slate-700 group-hover:text-slate-900 truncate">
                  {nb.title}
                </div>
                <div className="text-xs text-slate-400 mt-0.5 flex items-center gap-2">
                  {formatDate(nb.updated_at)}
                  {nb.is_shared && (
                    <span className="text-blue-500 flex items-center gap-0.5">
                      <Share2 size={10} /> 공유중
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={(e) => handleShare(nb, e)}
                  className={`p-1 rounded hover:bg-slate-100 opacity-0 group-hover:opacity-100 transition-opacity ${
                    nb.is_shared ? "text-blue-500" : "text-slate-400"
                  }`}
                  title={nb.is_shared ? "공유 해제" : "공유하기"}
                >
                  <Share2 size={14} />
                </button>
                <button
                  onClick={(e) => handleDelete(nb.notebook_id, e)}
                  className="p-1 rounded hover:bg-red-50 text-slate-400 hover:text-red-500"
                  title="삭제"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          </div>
        ))}

        <div className="flex items-center gap-1.5 px-1 py-2 mt-2 text-xs font-medium text-slate-500 uppercase tracking-wide">
          <Users size={12} />
          공유된 노트북 ({sharedNotebooks.length})
        </div>

        {sharedNotebooks.length === 0 && (
          <div className="text-xs text-slate-400 px-3 py-2">공유된 노트북이 없습니다</div>
        )}

        {sharedNotebooks.map((nb) => (
          <div
            key={`shared_${nb.notebook_id}`}
            onClick={() => handleSelectNotebook(nb)}
            className={`w-full text-left px-3 py-2.5 mb-1 rounded-lg hover:bg-white hover:shadow-sm border transition-all group cursor-pointer ${
              selectedNotebook?.notebook_id === nb.notebook_id
                ? "bg-white border-blue-200 shadow-sm"
                : "border-transparent hover:border-slate-200"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm text-slate-700 group-hover:text-slate-900 truncate">
                  {nb.title}
                </div>
                <div className="text-xs text-slate-400 mt-0.5">
                  {nb.user_id} · {formatDate(nb.updated_at)}
                </div>
              </div>
              <div className="flex items-center gap-1">
                {nb.user_id === userId && (
                  <button
                    onClick={(e) => handleShare(nb, e)}
                    className="p-1 rounded hover:bg-slate-100 text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="공유 해제"
                  >
                    <Share2 size={14} />
                  </button>
                )}
                <button
                  onClick={(e) => handleDelete(nb.notebook_id, e)}
                  className="p-1 rounded hover:bg-red-50 text-slate-400 hover:text-red-500"
                  title="삭제"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          </div>
        ))}
      </ScrollArea>
    </div>
  );
}
