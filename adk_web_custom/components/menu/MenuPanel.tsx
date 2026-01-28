"use client";

import React, { useMemo, useState } from "react";

type Props = {
  collapsed: boolean;
  onCollapse: () => void;
};

type Notebook = {
  id: string;
  title: string;
  updatedAt: string;
};

export default function MenuPanel({ collapsed, onCollapse }: Props) {
  const [query, setQuery] = useState("");

  const my_notebook: Notebook[] = useMemo(
    () => [
      { id: "s_001", title: "개인취향과 도메인", updatedAt: "2026-01-25" },
      { id: "s_002", title: "지식이 담긴", updatedAt: "2026-01-24" },
      { id: "s_003", title: "분석결과", updatedAt: "2026-01-22" },
    ],
    [],
  );

  const shared_notebook: Notebook[] = useMemo(
    () => [
      { id: "s_001", title: "팀의 공통양식이나", updatedAt: "2026-01-25" },
      { id: "s_002", title: "공유받은 분석결과", updatedAt: "2026-01-24" },
    ],
    [],
  );

  if (collapsed) return null;

  return (
    <div
      style={{
        height: "100%",
        position: "relative",
        display: "grid",
        gridTemplateRows: "auto auto 1fr",
      }}
    >
      {/* 헤더 */}
      <div
        style={{ padding: 12, display: "flex", alignItems: "center", gap: 8 }}
      >
        <div style={{ fontWeight: 700 }}>Home</div>
      </div>

      {/* 목록 */}
      <div style={{ overflow: "auto", padding: "0 8px 56px 8px" }}>
        {/* 아래 버튼과 겹치지 않도록 bottom padding 확보(56px) */}
        <div style={{ padding: "6px 8px", fontSize: 12, color: "#6b7280" }}>
          Notebook
        </div>

        {my_notebook.map((s) => (
          <button
            key={s.id}
            onClick={() => console.log("select session:", s.id)}
            style={{
              width: "100%",
              textAlign: "left",
              padding: 10,
              margin: "0 4px 8px",
              borderRadius: 12,
              border: "1px solid #e5e7eb",
              background: "white",
              cursor: "pointer",
            }}
          >
            <div style={{ fontWeight: 600 }}>{s.title}</div>
            <div style={{ fontSize: 12, color: "#6b7280" }}>
              {s.id} · {s.updatedAt}
            </div>
          </button>
        ))}
        
        <div style={{ padding: "6px 8px", fontSize: 12, color: "#6b7280" }}>
          Shared Notebook
        </div>

        {shared_notebook.map((s) => (
          <button
            key={s.id}
            onClick={() => console.log("select session:", s.id)}
            style={{
              width: "100%",
              textAlign: "left",
              padding: 10,
              margin: "0 4px 8px",
              borderRadius: 12,
              border: "1px solid #e5e7eb",
              background: "white",
              cursor: "pointer",
            }}
          >
            <div style={{ fontWeight: 600 }}>{s.title}</div>
            <div style={{ fontSize: 12, color: "#6b7280" }}>
              {s.id} · {s.updatedAt}
            </div>
          </button>
        ))}
      </div>

      {/* 접기 버튼 */}
      <button
        onClick={onCollapse}
        aria-label="메뉴 접기"
        title="메뉴 접기"
        style={{
          position: "absolute",
          right: 12,
          bottom: 12,
          padding: "10px 12px",
          borderRadius: 12,
          border: "1px solid #e5e7eb",
          background: "white",
          boxShadow: "0 6px 20px rgba(0,0,0,0.08)",
          cursor: "pointer",
        }}
      >
        ◀ 접기
      </button>
    </div>
  );
}
