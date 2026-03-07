"use client";

import React, { useMemo, useRef, useState } from "react";
import { Rnd } from "react-rnd";
import { Check, X, Minimize2, Maximize2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useWorkspace } from "./WorkspaceContext";
import CsvTableFromUrlWidget from "@/components/workspace/widgets/CsvTableFromUrlWidget";
import CsvFileWidget from "@/components/workspace/widgets/CsvFileWidget";
import PlotlyFigureWidget from "@/components/workspace/widgets/PlotlyFigureWidget";
import FlowGraphWidget from "@/components/workspace/widgets/FlowGraphWidget";
import WorkspaceTopBar from "@/components/workspace/WorkspaceTopBar";
import ServerFilePicker, {
  type ServerFileItem,
} from "@/components/workspace/ServerFilePicker";

export default function WorkspacePanel() {
  const {
    windows,
    updateWindow,
    bringToFront,
    closeWindow,
    toggleWindowCheck,
    checkedWidgets,
  } = useWorkspace();
  const boundsRef = useRef<HTMLDivElement | null>(null);

  // Track minimized state and saved sizes
  const [minimized, setMinimized] = useState<Record<string, boolean>>({});
  const [savedSizes, setSavedSizes] = useState<Record<string, { w: number; h: number }>>({});

  const HEADER_H = 48;
  const MINIMIZED_HEIGHT = 40;

  const isEmpty = useMemo(() => windows.length === 0, [windows.length]);

  const requestBackendToReadFile = (file: ServerFileItem) => {
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
    window.dispatchEvent(new CustomEvent("workspace:refresh"));
  };

  const onFlow = () => {
    window.dispatchEvent(new CustomEvent("workspace:flow"));
  };

  const onSave = () => {
    window.dispatchEvent(new CustomEvent("workspace:save"));
  };

  // Ctrl+click handler for widget header
  const handleHeaderClick = (e: React.MouseEvent, win: (typeof windows)[number]) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      e.stopPropagation();
      const artifactName = win.widget.title;
      // Add @artifactName to chat input
      window.dispatchEvent(
        new CustomEvent("chat:insert", {
          detail: { text: `@${artifactName} `, artifact: artifactName },
        }),
      );
    }
  };

  const toggleMinimize = (winId: string, currentW: number, currentH: number) => {
    const isMinimized = minimized[winId];
    if (isMinimized) {
      // Restore
      const saved = savedSizes[winId];
      if (saved) {
        updateWindow(winId, { h: saved.h });
      }
    } else {
      // Minimize - save current size
      setSavedSizes((prev) => ({ ...prev, [winId]: { w: currentW, h: currentH } }));
      updateWindow(winId, { h: MINIMIZED_HEIGHT });
    }
    setMinimized((prev) => ({ ...prev, [winId]: !isMinimized }));
  };

  const toggleMaximize = (winId: string, currentW: number, currentH: number) => {
    const bounds = boundsRef.current;
    if (!bounds) return;

    const maxW = bounds.clientWidth - 20;
    const maxH = bounds.clientHeight - HEADER_H - 20;

    // Check if already maximized
    const win = windows.find((w) => w.id === winId);
    if (!win) return;

    const isMaximized = win.w >= maxW - 50 && win.h >= maxH - 50;

    if (isMaximized) {
      // Restore to saved size
      const saved = savedSizes[winId];
      if (saved) {
        updateWindow(winId, { w: saved.w, h: saved.h, x: 20, y: 20 });
      }
    } else {
      // Maximize - save current size first
      setSavedSizes((prev) => ({ ...prev, [winId]: { w: currentW, h: currentH } }));
      updateWindow(winId, { w: maxW, h: maxH, x: 10, y: 10 });
    }
    // Clear minimized state
    setMinimized((prev) => ({ ...prev, [winId]: false }));
  };

  function renderWidget(win: (typeof windows)[number]) {
    const w = win.widget;
    switch (w.type) {
      case "tableUrl":
        return <CsvTableFromUrlWidget src={w.src} />;
      case "csvFile":
        return <CsvFileWidget fileId={w.fileId} artifactName={w.title} />;
      case "plotly":
        return <PlotlyFigureWidget fig={w.fig} />;
      case "flowGraph":
        return (
          <FlowGraphWidget
            sessionId={w.sessionId}
            checkedWidgets={checkedWidgets}
          />
        );
      default:
        return (
          <div className="p-3 text-muted-foreground">unknown widget</div>
        );
    }
  }

  return (
    <div
      ref={boundsRef}
      className="relative h-full min-h-dvh overflow-hidden bg-muted/30"
    >
      <WorkspaceTopBar
        height={HEADER_H}
        onRefresh={onRefresh}
        onFlow={onFlow}
        onSave={onSave}
      />

      <div
        className="relative overflow-hidden"
        style={{
          height: `calc(100% - ${HEADER_H}px)`,
          minHeight: `calc(100dvh - ${HEADER_H}px)`,
        }}
      >
        <ServerFilePicker
          enabled={isEmpty}
          onSelect={requestBackendToReadFile}
        />

        {windows.map((win) => {
          const isFlowGraph = win.widget.type === "flowGraph";
          const isMin = minimized[win.id];

          return (
            <Rnd
              key={win.id}
              bounds="parent"
              size={{ width: win.w, height: isMin ? MINIMIZED_HEIGHT : win.h }}
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
              style={{ zIndex: win.z }}
              className="rounded-xl border bg-card shadow-lg overflow-hidden"
              minWidth={200}
              minHeight={MINIMIZED_HEIGHT}
              dragHandleClassName="ws-window-handle"
              enableResizing={!isMin}
            >
              {/* window title bar */}
              <div
                className="ws-window-handle h-10 flex items-center gap-2 px-2.5 border-b bg-card cursor-grab select-none"
                onMouseDown={() => bringToFront(win.id)}
                onClick={(e) => handleHeaderClick(e, win)}
              >
                <span
                  className={cn(
                    "font-bold text-[13px] flex-1 truncate",
                    "hover:text-blue-600 transition-colors",
                  )}
                  title="Ctrl+클릭으로 채팅에 참조 추가"
                >
                  {win.widget.title}
                </span>

                {/* minimize */}
                <Button
                  variant="outline"
                  size="icon"
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleMinimize(win.id, win.w, win.h);
                  }}
                  aria-label={isMin ? "복원" : "최소화"}
                  title={isMin ? "복원" : "최소화"}
                  className="h-7 w-7 shrink-0"
                >
                  <Minimize2 size={14} />
                </Button>

                {/* maximize */}
                <Button
                  variant="outline"
                  size="icon"
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleMaximize(win.id, win.w, win.h);
                  }}
                  aria-label="최대화"
                  title="최대화/복원"
                  className="h-7 w-7 shrink-0"
                >
                  <Maximize2 size={14} />
                </Button>

                {/* check toggle - flowGraph 위젯은 표시 안함 */}
                {!isFlowGraph && (
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleWindowCheck(win.id);
                    }}
                    aria-label={win.checked ? "체크 해제" : "체크"}
                    title={win.checked ? "Flow에서 제외" : "Flow에 포함"}
                    className={cn(
                      "h-7 w-7 shrink-0",
                      win.checked
                        ? "bg-success text-success-foreground border-success hover:bg-success/90"
                        : "border-muted-foreground/50 text-muted-foreground",
                    )}
                  >
                    <Check size={14} />
                  </Button>
                )}

                {/* close */}
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => closeWindow(win.id)}
                  aria-label="창 닫기"
                  title="닫기"
                  className="h-7 w-7 shrink-0"
                >
                  <X size={14} />
                </Button>
              </div>

              {!isMin && (
                <div className="h-[calc(100%-40px)] overflow-auto">
                  {renderWidget(win)}
                </div>
              )}
            </Rnd>
          );
        })}
      </div>
    </div>
  );
}
