"use client";

import React, { useRef } from "react";
import { Rnd } from "react-rnd";
import { useWorkspace } from "./WorkspaceContext";
import CsvTableFromUrlWidget from "@/components/workspace/widgets/CsvTableFromUrlWidget";
import PlotlyFigureWidget from "@/components/workspace/widgets/PlotlyFigureWidget";

export default function WorkspacePanel() {
  const { windows, updateWindow, bringToFront, closeWindow } = useWorkspace();
  const boundsRef = useRef<HTMLDivElement | null>(null);

  return (
    <div
      ref={boundsRef}
      style={{
        position: "relative",
        height: "100%",
        minHeight: "100dvh",
        overflow: "hidden",
        background: "#fafafa",
      }}
    >
      {windows.length === 0 && (
        <div style={{ padding: 24, color: "#6b7280" }}>
          채팅에서 CSV/그래프 응답을 받으면 여기에 창으로 열립니다.
        </div>
      )}

      {windows.map((win) => (
        <Rnd
          key={win.id}
          bounds="parent"
          size={{ width: win.w, height: win.h }}
          position={{ x: win.x, y: win.y }}
          onDragStart={() => bringToFront(win.id)} // ✅ 클릭하면 앞으로
          onResizeStart={() => bringToFront(win.id)}
          onDragStop={(_, d) => updateWindow(win.id, { x: d.x, y: d.y })}
          onResizeStop={(_, __, ref, ___, pos) => {
            updateWindow(win.id, {
              w: ref.offsetWidth,
              h: ref.offsetHeight,
              x: pos.x,
              y: pos.y,
            });
          }}
          style={{
            zIndex: win.z,
            border: "1px solid #e5e7eb",
            borderRadius: 12,
            background: "white",
            boxShadow: "0 10px 30px rgba(0,0,0,0.08)",
            overflow: "hidden",
          }}
          minWidth={360}
          minHeight={240}
          dragHandleClassName="ws-window-handle" // ✅ 헤더만 드래그 핸들
        >
          {/* 윈도우 헤더 */}
          <div
            className="ws-window-handle"
            style={{
              height: 40,
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "0 10px",
              borderBottom: "1px solid #e5e7eb",
              cursor: "grab",
              userSelect: "none",
              background: "#fff",
            }}
            onMouseDown={() => bringToFront(win.id)}
          >
            <div
              style={{
                fontWeight: 700,
                fontSize: 13,
                flex: 1,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {win.widget.title}
            </div>

            <button
              onClick={() => closeWindow(win.id)}
              style={{
                border: "1px solid #e5e7eb",
                background: "white",
                borderRadius: 10,
                padding: "6px 10px",
                cursor: "pointer",
              }}
              aria-label="창 닫기"
              title="닫기"
            >
              ✕
            </button>
          </div>

          {/* 윈도우 바디 */}
          <div style={{ height: `calc(100% - 40px)`, overflow: "auto" }}>
            {
            win.widget.type === "tableUrl" ? (
              <CsvTableFromUrlWidget src={win.widget.src} /> // ✅ 추가
            ) : (
              <PlotlyFigureWidget fig={win.widget.fig} />
            )}
          </div>
        </Rnd>
      ))}
    </div>
  );
}
