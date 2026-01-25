// components/menu/MenuPanel.tsx
"use client";

import React, { useMemo, useState } from "react";

type Props = {
  collapsed: boolean;
  onCollapse: () => void;
};

type SessionItem = {
  id: string;
  title: string;
  updatedAt: string;
};

export default function MenuPanel({ collapsed, onCollapse }: Props) {
  const [query, setQuery] = useState("");

  const sessions: SessionItem[] = useMemo(
    () => [
      { id: "s_001", title: "MLCC 분석", updatedAt: "2026-01-25" },
      { id: "s_002", title: "상관분석", updatedAt: "2026-01-24" },
      { id: "s_003", title: "AGE 그래프", updatedAt: "2026-01-22" },
    ],
    []
  );

  const filtered = sessions.filter((s) =>
    (s.title + " " + s.id).toLowerCase().includes(query.toLowerCase())
  );

  // ✅ 접힌 상태면 패널은 비워둠(펼치기 버튼은 AppShell fixed 버튼 담당)
  if (collapsed) return null;

  return (
    <div
      style={{
        height: "100%",
        position: "relative", // ✅ absolute 버튼 기준점
        display: "grid",
        gridTemplateRows: "auto auto 1fr",
      }}
    >
      {/* 헤더 */}
      <div style={{ padding: 12, display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ fontWeight: 700 }}>Menu</div>
      </div>

      {/* 검색 */}
      <div style={{ padding: "0 12px 12px" }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="세션 검색 (이름/ID)"
          style={{
            width: "100%",
            padding: 10,
            borderRadius: 10,
            border: "1px solid #e5e7eb",
            outline: "none",
          }}
        />
      </div>

      {/* 목록 */}
      <div style={{ overflow: "auto", padding: "0 8px 56px 8px" }}>
        {/* ✅ 아래 버튼과 겹치지 않도록 bottom padding 확보(56px) */}
        <div style={{ padding: "6px 8px", fontSize: 12, color: "#6b7280" }}>
          Sessions
        </div>

        {filtered.map((s) => (
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

        {filtered.length === 0 && (
          <div style={{ padding: 12, color: "#6b7280", fontSize: 14 }}>
            검색 결과가 없습니다.
          </div>
        )}
      </div>

      {/* ✅ 접기 버튼: MenuPanel 내부 오른쪽 아래 */}
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
