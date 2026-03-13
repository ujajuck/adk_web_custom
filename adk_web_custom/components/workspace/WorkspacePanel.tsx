"use client";

import React, { useMemo, useRef, useState } from "react";
import { Rnd } from "react-rnd";
import { X, Minus, Square } from "lucide-react";
import { cn } from "@/lib/utils";
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
    checkedWidgets,
  } = useWorkspace();
  const boundsRef = useRef<HTMLDivElement | null>(null);

  // Track minimized state and saved sizes
  const [minimized, setMinimized] = useState<Record<string, boolean>>({});
  const [savedSizes, setSavedSizes] = useState<Record<string, { w: number; h: number }>>({});

  const HEADER_H = 48;
  const MINIMIZED_HEIGHT = 36;

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
      const saved = savedSizes[winId];
      if (saved) {
        updateWindow(winId, { h: saved.h });
      }
    } else {
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

    const win = windows.find((w) => w.id === winId);
    if (!win) return;

    const isMaximized = win.w >= maxW - 50 && win.h >= maxH - 50;

    if (isMaximized) {
      const saved = savedSizes[winId];
      if (saved) {
        updateWindow(winId, { w: saved.w, h: saved.h, x: 20, y: 20 });
      }
    } else {
      setSavedSizes((prev) => ({ ...prev, [winId]: { w: currentW, h: currentH } }));
      updateWindow(winId, { w: maxW, h: maxH, x: 10, y: 10 });
    }
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
            allWindows={windows}
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
      className="relative h-full min-h-dvh overflow-hidden bg-slate-100"
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
              className="rounded border bg-card shadow-md overflow-hidden"
              minWidth={200}
              minHeight={MINIMIZED_HEIGHT}
              dragHandleClassName="ws-window-handle"
              enableResizing={!isMin}
            >
              {/* window title bar */}
              <div
                className="ws-window-handle h-9 flex items-center gap-1 px-2 border-b bg-slate-50 cursor-grab select-none"
                onMouseDown={() => bringToFront(win.id)}
                onClick={(e) => handleHeaderClick(e, win)}
              >
                <span
                  className={cn(
                    "font-semibold text-xs flex-1 truncate text-slate-700",
                    "hover:text-blue-600 transition-colors",
                  )}
                  title="Ctrl+클릭으로 채팅에 참조 추가"
                >
                  {win.widget.title}
                </span>

                {/* minimize */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleMinimize(win.id, win.w, win.h);
                  }}
                  className="w-6 h-6 flex items-center justify-center rounded hover:bg-slate-200 text-slate-500 transition-colors"
                  title={isMin ? "복원" : "최소화"}
                >
                  <Minus size={12} />
                </button>

                {/* maximize */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleMaximize(win.id, win.w, win.h);
                  }}
                  className="w-6 h-6 flex items-center justify-center rounded hover:bg-slate-200 text-slate-500 transition-colors"
                  title="최대화/복원"
                >
                  <Square size={10} />
                </button>

                {/* close */}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    closeWindow(win.id);
                  }}
                  className="w-6 h-6 flex items-center justify-center rounded hover:bg-red-100 hover:text-red-600 text-slate-500 transition-colors"
                  title="닫기"
                >
                  <X size={12} />
                </button>
              </div>

              {!isMin && (
                <div className="h-[calc(100%-36px)] overflow-auto">
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
