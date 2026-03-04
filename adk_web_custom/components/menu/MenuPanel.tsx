"use client";

import React, { useMemo } from "react";
import { ChevronLeft, FileText, Users, Plus } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";

type Props = {
  collapsed: boolean;
  onCollapse: () => void;
};

type Notebook = {
  id: string;
  title: string;
  updatedAt: string;
};

export default function MenuPanel({ collapsed, onCollapse }: Props) {
  const my_notebook: Notebook[] = useMemo(
    () => [
      { id: "s_001", title: "개인취향과 도메인", updatedAt: "2026-01-25" },
      { id: "s_002", title: "지식이 담긴", updatedAt: "2026-01-24" },
      { id: "s_003", title: "분석결과", updatedAt: "2026-01-22" },
    ],
    [],
  );

  const shared_notebook: Notebook[] = useMemo(
    () => [
      { id: "s_001", title: "팀의 공통양식이나", updatedAt: "2026-01-25" },
      { id: "s_002", title: "공유받은 분석결과", updatedAt: "2026-01-24" },
    ],
    [],
  );

  if (collapsed) return null;

  return (
    <div className="h-full flex flex-col bg-slate-50">
      {/* 헤더 */}
      <div className="px-4 py-3 flex items-center justify-between border-b bg-white">
        <span className="font-semibold text-slate-800">노트북</span>
        <button
          onClick={onCollapse}
          className="p-1.5 rounded-md hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors"
          title="메뉴 접기"
        >
          <ChevronLeft size={18} />
        </button>
      </div>

      {/* 새 노트북 버튼 */}
      <div className="px-3 py-2">
        <button className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-500 hover:bg-blue-600 text-white text-sm font-medium transition-colors">
          <Plus size={16} />
          새 노트북
        </button>
      </div>

      {/* 목록 */}
      <ScrollArea className="flex-1 px-3">
        <div className="flex items-center gap-1.5 px-1 py-2 text-xs font-medium text-slate-500 uppercase tracking-wide">
          <FileText size={12} />
          내 노트북
        </div>

        {my_notebook.map((s) => (
          <button
            key={s.id}
            onClick={() => console.log("select session:", s.id)}
            className="w-full text-left px-3 py-2.5 mb-1 rounded-lg hover:bg-white hover:shadow-sm border border-transparent hover:border-slate-200 transition-all group"
          >
            <div className="font-medium text-sm text-slate-700 group-hover:text-slate-900 truncate">
              {s.title}
            </div>
            <div className="text-xs text-slate-400 mt-0.5">
              {s.updatedAt}
            </div>
          </button>
        ))}

        <div className="flex items-center gap-1.5 px-1 py-2 mt-2 text-xs font-medium text-slate-500 uppercase tracking-wide">
          <Users size={12} />
          공유된 노트북
        </div>

        {shared_notebook.map((s) => (
          <button
            key={`shared_${s.id}`}
            onClick={() => console.log("select session:", s.id)}
            className="w-full text-left px-3 py-2.5 mb-1 rounded-lg hover:bg-white hover:shadow-sm border border-transparent hover:border-slate-200 transition-all group"
          >
            <div className="font-medium text-sm text-slate-700 group-hover:text-slate-900 truncate">
              {s.title}
            </div>
            <div className="text-xs text-slate-400 mt-0.5">
              {s.updatedAt}
            </div>
          </button>
        ))}
      </ScrollArea>
    </div>
  );
}
