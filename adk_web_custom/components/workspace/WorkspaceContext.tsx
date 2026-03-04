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
  | { id: string; type: "flowGraph"; title: string; sessionId: string };

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
  addCsvFileWindow: (title: string, fileId: string) => void;
  addPlotlyWindow: (
    title: string,
    fig: { data: any[]; layout?: any; config?: any },
  ) => void;
  addFlowGraphWindow: (title: string, sessionId: string) => void;
  updateWindow: (
    id: string,
    patch: Partial<Pick<WorkspaceWindow, "x" | "y" | "w" | "h">>,
  ) => void;
  toggleWindowCheck: (id: string) => void;
  bringToFront: (id: string) => void;
  closeWindow: (id: string) => void;
};

const WorkspaceContext = createContext<Ctx | null>(null);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [windows, setWindows] = useState<WorkspaceWindow[]>([]);
  const [zTop, setZTop] = useState(1);

  function nextId(prefix: string) {
    return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  }

  // 새 윈도우 위치 계산 (캐스케이드 + 그리드 혼합)
  function calcNewPosition(
    existingCount: number,
    width: number,
    height: number,
  ): { x: number; y: number } {
    const cols = 3; // 3열로 배치
    const baseX = 20;
    const baseY = 60;
    const gapX = width + 40; // 윈도우 폭 + 간격
    const gapY = height + 40;

    const col = existingCount % cols;
    const row = Math.floor(existingCount / cols);

    // 같은 셀에 있으면 약간씩 오프셋
    const cellCount = Math.floor(existingCount / cols);
    const offset = (existingCount % 3) * 30;

    return {
      x: baseX + col * gapX + offset,
      y: baseY + row * gapY + offset,
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

  function addCsvFileWindow(title: string, fileId: string) {
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
  }

  function addPlotlyWindow(
    title: string,
    fig: { data: any[]; layout?: any; config?: any },
  ) {
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
  }

  function addFlowGraphWindow(title: string, sessionId: string) {
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
          widget: { id: widgetId, type: "flowGraph", title, sessionId },
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
      updateWindow,
      toggleWindowCheck,
      bringToFront,
      closeWindow,
    }),
    [windows, checkedWidgets],
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
