// components/shell/AppShell.tsx
"use client";

import React, { useEffect, useRef, useState } from "react";
import { Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import MenuPanel from "@/components/menu/MenuPanel";
import ChatPanel from "@/components/chat/ChatPanel";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [isLeftCollapsed, setIsLeftCollapsed] = useState(false);
  const [rightWidth, setRightWidth] = useState(420);

  const leftWidth = isLeftCollapsed ? 0 : 320;

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
    <div className="relative">
      {/* 메뉴 펼치기 고정 버튼 */}
      {isLeftCollapsed && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setIsLeftCollapsed(false)}
          aria-label="메뉴 펼치기"
          title="메뉴 펼치기"
          className="fixed left-3 bottom-3 z-50 shadow-lg gap-1.5"
        >
          <Menu size={16} />
          메뉴
        </Button>
      )}

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
            "overflow-hidden",
            leftWidth > 0 && "border-r",
          )}
        >
          <MenuPanel
            collapsed={isLeftCollapsed}
            onCollapse={() => setIsLeftCollapsed(true)}
          />
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
    </div>
  );
}
