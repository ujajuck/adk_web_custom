"use client";

import React, { createContext, useContext, useMemo, useState } from "react";

export type WorkspaceWidget =
  | {
      id: string;
      type: "table";
      title: string;
      csvText: string;
    }
  | { id: string; type: "tableUrl"; title: string; src: string }
  | { id: string; type: "csvFile"; title: string; fileId: string }
  | {
      id: string;
      type: "plotly";
      title: string;
      fig: { data: any[]; layout?: any; config?: any };
    }
  | { id: string; type: "flowGraph"; title: string; sessionId: string; staticFlow?: any };

export type WorkspaceWindow = {
  id: string;
  widget: WorkspaceWidget;
  x: number;
  y: number;
  w: number;
  h: number;
  z: number;
  checked: boolean; // 플로우 그래프에 표시 여부
};

type Ctx = {
  windows: WorkspaceWindow[];
  checkedWidgets: string[]; // 체크된 위젯 ID 목록
  addTableWindow: (title: string, csvText: string) => void;
  addCsvTableWindow: (title: string, src: string) => void;
  addCsvFileWindow: (title: string, fileId: string) => string;
  addPlotlyWindow: (
    title: string,
    fig: { data: any[]; layout?: any; config?: any },
  ) => string;
  addFlowGraphWindow: (title: string, sessionId: string, staticFlow?: any) => void;
  setViewportSize: (w: number, h: number) => void;
  updateWindow: (
    id: string,
    patch: Partial<Pick<WorkspaceWindow, "x" | "y" | "w" | "h">>,
  ) => void;
  toggleWindowCheck: (id: string) => void;
  bringToFront: (id: string) => void;
  closeWindow: (id: string) => void;
  clearAllWindows: () => void;
};

const WorkspaceContext = createContext<Ctx | null>(null);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [windows, setWindows] = useState<WorkspaceWindow[]>([]);
  const [zTop, setZTop] = useState(1);
  // 워크스페이스 실제 크기 (WorkspacePanel이 ResizeObserver로 업데이트)
  const [vpW, setVpW] = useState(0);
  const [vpH, setVpH] = useState(0);

  function setViewportSize(w: number, h: number) {
    setVpW(w);
    setVpH(h);
  }

  function nextId(prefix: string) {
    return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  }

  // 새 윈도우 위치 계산 — 현재 뷰포트 기준으로 화면 안에 들어오도록 배치
  function calcNewPosition(
    existingCount: number,
    width: number,
    height: number,
  ): { x: number; y: number } {
    const vw = vpW > 0 ? vpW : 900;
    const vh = vpH > 0 ? vpH : 600;
    const margin = 20;

    // 한 행에 들어갈 수 있는 열 수
    const cols = Math.max(1, Math.floor((vw - margin) / (width + margin)));
    const col = existingCount % cols;
    const row = Math.floor(existingCount / cols);

    // 열 간격: 뷰포트 너비를 cols 등분
    const colW = Math.floor((vw - margin) / cols);
    const x = margin + col * colW;
    const y = margin + row * (height + margin) + (existingCount % 4) * 15;

    return {
      x: Math.min(x, Math.max(margin, vw - width - margin)),
      y: Math.min(y, Math.max(margin, vh - height / 2)),
    };
  }

  function addTableWindow(title: string, csvText: string) {
    const id = nextId("win");
    const widgetId = nextId("tbl");
    const z = zTop + 1;
    setZTop(z);

    const w = 560;
    const h = 380;

    setWindows((prev) => {
      const pos = calcNewPosition(prev.length, w, h);
      return [
        ...prev,
        {
          id,
          widget: { id: widgetId, type: "table", title, csvText },
          ...pos,
          w,
          h,
          z,
          checked: true,
        },
      ];
    });
  }

  function addCsvTableWindow(title: string, src: string) {
    const id = nextId("win");
    const widgetId = nextId("tblurl");
    const z = zTop + 1;
    setZTop(z);

    const w = 560;
    const h = 380;

    setWindows((prev) => {
      const pos = calcNewPosition(prev.length, w, h);
      return [
        ...prev,
        {
          id,
          widget: { id: widgetId, type: "tableUrl", title, src },
          ...pos,
          w,
          h,
          z,
          checked: true,
        },
      ];
    });
  }

  function addCsvFileWindow(title: string, fileId: string): string {
    const id = nextId("win");
    const widgetId = nextId("csvf");
    const z = zTop + 1;
    setZTop(z);

    const w = 560;
    const h = 380;

    setWindows((prev) => {
      const pos = calcNewPosition(prev.length, w, h);
      return [
        ...prev,
        {
          id,
          widget: { id: widgetId, type: "csvFile", title, fileId },
          ...pos,
          w,
          h,
          z,
          checked: true,
        },
      ];
    });
    return id;
  }

  function addPlotlyWindow(
    title: string,
    fig: { data: any[]; layout?: any; config?: any },
  ): string {
    const id = nextId("win");
    const widgetId = nextId("plt");
    const z = zTop + 1;
    setZTop(z);

    const w = 560;
    const h = 420;

    setWindows((prev) => {
      const pos = calcNewPosition(prev.length, w, h);
      return [
        ...prev,
        {
          id,
          widget: { id: widgetId, type: "plotly", title, fig },
          ...pos,
          w,
          h,
          z,
          checked: true,
        },
      ];
    });
    return id;
  }

  function addFlowGraphWindow(title: string, sessionId: string, staticFlow?: any) {
    const id = nextId("win");
    const widgetId = nextId("flow");
    const z = zTop + 1;
    setZTop(z);

    const w = 700;
    const h = 450;

    setWindows((prev) => {
      const pos = calcNewPosition(prev.length, w, h);
      return [
        ...prev,
        {
          id,
          widget: { id: widgetId, type: "flowGraph", title, sessionId, staticFlow },
          ...pos,
          w,
          h,
          z,
          checked: false,
        },
      ];
    });
  }

  function toggleWindowCheck(id: string) {
    setWindows((prev) =>
      prev.map((w) => (w.id === id ? { ...w, checked: !w.checked } : w)),
    );
  }

  function updateWindow(
    id: string,
    patch: Partial<Pick<WorkspaceWindow, "x" | "y" | "w" | "h">>,
  ) {
    setWindows((prev) =>
      prev.map((w) => (w.id === id ? { ...w, ...patch } : w)),
    );
  }

  function bringToFront(id: string) {
    setWindows((prev) => {
      const maxZ = Math.max(1, ...prev.map((w) => w.z));
      return prev.map((w) => (w.id === id ? { ...w, z: maxZ + 1 } : w));
    });
  }

  function closeWindow(id: string) {
    setWindows((prev) => prev.filter((w) => w.id !== id));
  }

  function clearAllWindows() {
    setWindows([]);
  }

  // 체크된 위젯 ID 목록 (flowGraph 제외)
  const checkedWidgets = useMemo(
    () =>
      windows
        .filter((w) => w.checked && w.widget.type !== "flowGraph")
        .map((w) => w.widget.title), // title을 사용하여 flow 노드와 매칭
    [windows],
  );

  const value = useMemo<Ctx>(
    () => ({
      windows,
      checkedWidgets,
      addTableWindow,
      addCsvTableWindow,
      addCsvFileWindow,
      addPlotlyWindow,
      addFlowGraphWindow,
      setViewportSize,
      updateWindow,
      toggleWindowCheck,
      bringToFront,
      closeWindow,
      clearAllWindows,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [windows, checkedWidgets, vpW, vpH],
  );

  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx)
    throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
}
