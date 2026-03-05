// components/shell/AppShell.tsx
"use client";

import React, { useEffect, useRef, useState } from "react";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import MenuPanel from "@/components/menu/MenuPanel";
import ChatPanel from "@/components/chat/ChatPanel";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [isLeftCollapsed, setIsLeftCollapsed] = useState(false);
  const [rightWidth, setRightWidth] = useState(480);

  const leftWidth = isLeftCollapsed ? 48 : 260;

  const draggingRef = useRef<null | "right">(null);

  function onRightDragStart() {
    draggingRef.current = "right";
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }

  function stopDragging() {
    draggingRef.current = null;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  }

  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (draggingRef.current !== "right") return;
      const w = window.innerWidth;
      const next = Math.max(320, Math.min(760, w - e.clientX));
      setRightWidth(next);
    }

    function onUp() {
      if (draggingRef.current) stopDragging();
    }

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  return (
    <div
      className="h-dvh"
      style={{
        display: "grid",
        gridTemplateColumns: `${leftWidth}px minmax(0, 1fr) 6px ${rightWidth}px`,
      }}
    >
      {/* 왼쪽: 메뉴 */}
      <aside
        className={cn(
          "overflow-hidden border-r bg-slate-50",
        )}
      >
        {isLeftCollapsed ? (
          <div className="h-full flex flex-col">
            <div className="px-2 py-3 border-b bg-white flex justify-center">
              <button
                onClick={() => setIsLeftCollapsed(false)}
                className="p-1.5 rounded-md hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors"
                title="메뉴 펼치기"
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </div>
        ) : (
          <MenuPanel
            collapsed={isLeftCollapsed}
            onCollapse={() => setIsLeftCollapsed(true)}
          />
        )}
      </aside>

      {/* 가운데 */}
      <main className="overflow-auto">{children}</main>

      {/* 오른쪽 리사이즈 바 */}
      <div
        onMouseDown={onRightDragStart}
        title="드래그해서 채팅 폭 조절"
        className="cursor-col-resize bg-border hover:bg-ring/30 transition-colors"
      />

      {/* 오른쪽: 채팅 */}
      <aside className="border-l overflow-hidden">
        <ChatPanel />
      </aside>
    </div>
  );
}
