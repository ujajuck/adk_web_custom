"use client";

import React, { useMemo, useRef, useState } from "react";
import { Rnd } from "react-rnd";
import { Check } from "lucide-react";
import { useWorkspace } from "./WorkspaceContext";
import CsvTableFromUrlWidget from "@/components/workspace/widgets/CsvTableFromUrlWidget";
import PlotlyFigureWidget from "@/components/workspace/widgets/PlotlyFigureWidget";
import WorkspaceTopBar from "@/components/workspace/WorkspaceTopBar";
import ServerFilePicker, {
  type ServerFileItem,
} from "@/components/workspace/ServerFilePicker";

export default function WorkspacePanel() {
  const { windows, updateWindow, bringToFront, closeWindow } = useWorkspace();
  const boundsRef = useRef<HTMLDivElement | null>(null);

  const HEADER_H = 48;

  const isEmpty = useMemo(() => windows.length === 0, [windows.length]);

  // 체크 상태(윈도우별)
  const [checkedById, setCheckedById] = useState<Record<string, boolean>>({});

  const requestBackendToReadFile = (file: ServerFileItem) => {
    // TODO env로 옮겨라
    const text = `C:\\MyFolder\\data\\${file.name}\n이 파일을 읽어줘`;

    window.dispatchEvent(
      new CustomEvent("adk:chat:send", {
        detail: {
          text,
          fileName: file.name,
        },
      }),
    );
  };

  const onRefresh = () => {
    // TODO 이벤트 연결
    window.dispatchEvent(new CustomEvent("workspace:refresh"));
  };

  const onFlow = () => {
    window.dispatchEvent(new CustomEvent("workspace:flow"));
  };

  const onSave = () => {
    window.dispatchEvent(new CustomEvent("workspace:save"));
  };

  const toggleCheck = (winId: string) => {
    setCheckedById((prev) => {
      const next = !prev[winId];

      // TODO(기능 추가 예정): 체크 상태 변경 시 실행할 함수 연결
      // 예: markWindowAsReviewed(winId, next)
      // 예: runFlowOnCheckedWindows(Object.entries({...}).filter(([_, v]) => v))
      // 예: persistCheckedStateToStorage(winId, next)

      return { ...prev, [winId]: next };
    });
  };

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
      {/* 침범 불가 상단 헤더 */}
      <WorkspaceTopBar
        height={HEADER_H}
        onRefresh={onRefresh}
        onFlow={onFlow}
        onSave={onSave}
      />

      {/* 헤더 아래가 "parent"가 되도록 본문 컨테이너 분리 */}
      <div
        style={{
          position: "relative",
          height: `calc(100% - ${HEADER_H}px)`,
          minHeight: `calc(100dvh - ${HEADER_H}px)`,
          overflow: "hidden",
        }}
      >
        {/* windows가 없을 때 파일 선택 UI */}
        <ServerFilePicker
          enabled={isEmpty}
          onSelect={requestBackendToReadFile}
        />

        {/* 윈도우들 */}
        {windows.map((win) => {
          const checked = Boolean(checkedById[win.id]);

          return (
            <Rnd
              key={win.id}
              bounds="parent"
              size={{ width: win.w, height: win.h }}
              position={{ x: win.x, y: win.y }}
              onDragStart={() => bringToFront(win.id)}
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
              dragHandleClassName="ws-window-handle"
            >
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

                {/* 체크 토글 버튼 */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleCheck(win.id);
                  }}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 30,
                    height: 30,
                    borderRadius: 10,
                    border: "1px solid #e5e7eb",
                    background: checked ? "white" : "#16a34a",
                    cursor: "pointer",
                    color: checked ? "#16a34a" : "#e5e7eb",
                  }}
                  aria-label={checked ? "체크 해제" : "체크"}
                  title={checked ? "체크 해제" : "체크"}
                >
                  <Check size={16} />
                </button>

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

              <div style={{ height: `calc(100% - 40px)`, overflow: "auto" }}>
                {win.widget.type === "tableUrl" ? (
                  <CsvTableFromUrlWidget src={win.widget.src} />
                ) : (
                  <PlotlyFigureWidget fig={win.widget.fig} />
                )}
              </div>
            </Rnd>
          );
        })}
      </div>
    </div>
  );
}
