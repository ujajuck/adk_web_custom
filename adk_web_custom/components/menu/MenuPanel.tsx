"use client";

import React, { useMemo, useState } from "react";
import { ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
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
  const [query, setQuery] = useState("");

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
    <div className="h-full relative grid grid-rows-[auto_1fr]">
      {/* 헤더 */}
      <div className="p-3 flex items-center gap-2">
        <span className="font-bold text-foreground">Home</span>
      </div>

      {/* 목록 */}
      <ScrollArea className="px-2 pb-14">
        <p className="px-2 py-1.5 text-xs text-muted-foreground">Notebook</p>

        {my_notebook.map((s) => (
          <button
            key={s.id}
            onClick={() => console.log("select session:", s.id)}
            className="w-full text-left p-2.5 mx-1 mb-2 rounded-xl border bg-card hover:bg-accent transition-colors cursor-pointer"
          >
            <div className="font-semibold text-sm text-card-foreground">
              {s.title}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">
              {s.id} · {s.updatedAt}
            </div>
          </button>
        ))}

        <p className="px-2 py-1.5 text-xs text-muted-foreground">
          Shared Notebook
        </p>

        {shared_notebook.map((s) => (
          <button
            key={s.id}
            onClick={() => console.log("select session:", s.id)}
            className="w-full text-left p-2.5 mx-1 mb-2 rounded-xl border bg-card hover:bg-accent transition-colors cursor-pointer"
          >
            <div className="font-semibold text-sm text-card-foreground">
              {s.title}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">
              {s.id} · {s.updatedAt}
            </div>
          </button>
        ))}
      </ScrollArea>

      {/* 접기 버튼 */}
      <Button
        variant="outline"
        size="sm"
        onClick={onCollapse}
        aria-label="메뉴 접기"
        title="메뉴 접기"
        className="absolute right-3 bottom-3 shadow-lg gap-1"
      >
        <ChevronLeft size={16} />
        접기
      </Button>
    </div>
  );
}
