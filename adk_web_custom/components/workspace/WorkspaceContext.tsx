// components/workspace/WorkspaceContext.tsx
"use client";

import React, { createContext, useContext, useMemo, useState } from "react";

export type WorkspaceWidget =
  | {
      id: string;
      type: "table";
      title: string;
      csvText: string; // ✅ ADK 응답으로 받은 CSV 문자열(또는 base64 decode 결과)
    }
  | {
      id: string;
      type: "plotly";
      title: string;
      fig: { data: any[]; layout?: any; config?: any }; // ✅ Plotly JSON
    };

export type WorkspaceWindow = {
  id: string;
  widget: WorkspaceWidget;
  x: number;
  y: number;
  w: number;
  h: number;
  z: number;
};

type Ctx = {
  windows: WorkspaceWindow[];
  addTableWindow: (title: string, csvText: string) => void;
  addPlotlyWindow: (title: string, fig: { data: any[]; layout?: any; config?: any }) => void;
  updateWindow: (id: string, patch: Partial<Pick<WorkspaceWindow, "x" | "y" | "w" | "h">>) => void;
  bringToFront: (id: string) => void;
  closeWindow: (id: string) => void;
};

const WorkspaceContext = createContext<Ctx | null>(null);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [windows, setWindows] = useState<WorkspaceWindow[]>([]);
  const [zTop, setZTop] = useState(1);

  function nextId(prefix: string) {
    // ✅ 간단 ID 생성(충돌 확률 낮음)
    return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  }

  function addTableWindow(title: string, csvText: string) {
    const id = nextId("win");
    const widgetId = nextId("tbl");
    const z = zTop + 1;
    setZTop(z);

    setWindows((prev) => [
      ...prev,
      {
        id,
        widget: { id: widgetId, type: "table", title, csvText },
        x: 24 + prev.length * 16,
        y: 24 + prev.length * 16,
        w: 640,
        h: 420,
        z,
      },
    ]);
  }

  function addPlotlyWindow(title: string, fig: { data: any[]; layout?: any; config?: any }) {
    const id = nextId("win");
    const widgetId = nextId("plt");
    const z = zTop + 1;
    setZTop(z);

    setWindows((prev) => [
      ...prev,
      {
        id,
        widget: { id: widgetId, type: "plotly", title, fig },
        x: 40 + prev.length * 16,
        y: 40 + prev.length * 16,
        w: 720,
        h: 480,
        z,
      },
    ]);
  }

  function updateWindow(id: string, patch: Partial<Pick<WorkspaceWindow, "x" | "y" | "w" | "h">>) {
    setWindows((prev) => prev.map((w) => (w.id === id ? { ...w, ...patch } : w)));
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

  const value = useMemo<Ctx>(
    () => ({ windows, addTableWindow, addPlotlyWindow, updateWindow, bringToFront, closeWindow }),
    [windows]
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
}
