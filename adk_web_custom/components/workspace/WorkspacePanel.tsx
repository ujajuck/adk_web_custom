"use client";

import React, { useMemo, useRef } from "react";
import { Rnd } from "react-rnd";
import { Check, X } from "lucide-react";
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

  const HEADER_H = 48;

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

  function renderWidget(win: (typeof windows)[number]) {
    const w = win.widget;
    switch (w.type) {
      case "tableUrl":
        return <CsvTableFromUrlWidget src={w.src} />;
      case "csvFile":
        return <CsvFileWidget fileId={w.fileId} />;
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
              style={{ zIndex: win.z }}
              className="rounded-xl border bg-card shadow-lg overflow-hidden"
              minWidth={360}
              minHeight={240}
              dragHandleClassName="ws-window-handle"
            >
              {/* window title bar */}
              <div
                className="ws-window-handle h-10 flex items-center gap-2 px-2.5 border-b bg-card cursor-grab select-none"
                onMouseDown={() => bringToFront(win.id)}
              >
                <span className="font-bold text-[13px] flex-1 truncate">
                  {win.widget.title}
                </span>

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

              <div className="h-[calc(100%-40px)] overflow-auto">
                {renderWidget(win)}
              </div>
            </Rnd>
          );
        })}
      </div>
    </div>
  );
}
