// components/shell/AppShell.tsx
"use client";

import React, { useEffect, useRef, useState } from "react";
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
    <div style={{ position: "relative" }}>
      {/* ✅ 왼쪽 접힘 상태에서도 항상 보이는 “펼치기” 고정 버튼 */}
      {isLeftCollapsed && (
        <button
          onClick={() => setIsLeftCollapsed(false)}
          aria-label="메뉴 펼치기"
          title="메뉴 펼치기"
          style={{
            position: "fixed",
            left: 12,
            bottom: 12,
            zIndex: 50,
            padding: "10px 12px",
            borderRadius: 12,
            border: "1px solid #e5e7eb",
            background: "white",
            boxShadow: "0 6px 20px rgba(0,0,0,0.08)",
            cursor: "pointer",
          }}
        >
          ☰ 메뉴
        </button>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: `${leftWidth}px minmax(0, 1fr) 6px ${rightWidth}px`,
          height: "100dvh",
        }}
      >
        {/* 왼쪽: 메뉴 */}
        <aside
          style={{
            borderRight: leftWidth ? "1px solid #e5e7eb" : "none",
            overflow: "hidden",
          }}
        >
          <MenuPanel
            collapsed={isLeftCollapsed}
            onCollapse={() => setIsLeftCollapsed(true)}
          />
        </aside>

        {/* 가운데 */}
        <main style={{ overflow: "auto" }}>{children}</main>

        {/* 오른쪽 리사이즈 바 */}
        <div
          onMouseDown={onRightDragStart}
          title="드래그해서 채팅 폭 조절"
          style={{ cursor: "col-resize", background: "#e5e7eb" }}
        />

        {/* 오른쪽: 채팅 */}
        <aside style={{ borderLeft: "1px solid #e5e7eb", overflow: "hidden" }}>
          <ChatPanel />
        </aside>
      </div>
    </div>
  );
}
