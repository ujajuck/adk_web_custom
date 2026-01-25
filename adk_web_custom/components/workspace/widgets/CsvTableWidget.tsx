// components/workspace/widgets/CsvTableWidget.tsx
"use client";

import React, { useMemo } from "react";
import Papa from "papaparse";

export default function CsvTableWidget({ csvText }: { csvText: string }) {
  const { columns, rows, error } = useMemo(() => {
    const res = Papa.parse<Record<string, any>>(csvText, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: true,
    });

    if (res.errors?.length) {
      return {
        columns: [] as string[],
        rows: [] as any[],
        error: res.errors[0].message,
      };
    }

    const data = (res.data ?? []).filter(Boolean);
    const cols = data.length ? Object.keys(data[0]) : [];
    return { columns: cols, rows: data, error: "" };
  }, [csvText]);

  if (error) {
    return (
      <div style={{ padding: 12, color: "#b91c1c" }}>
        CSV 파싱 오류: {error}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div style={{ padding: 12, color: "#6b7280" }}>
        표시할 데이터가 없습니다.
      </div>
    );
  }

  return (
    <div style={{ padding: 12 }}>
      <div
        style={{
          overflow: "auto",
          border: "1px solid #e5e7eb",
          borderRadius: 10,
        }}
      >
        <table
          style={{ borderCollapse: "collapse", width: "100%", fontSize: 13 }}
        >
          <thead style={{ position: "sticky", top: 0, background: "white" }}>
            <tr>
              {columns.map((c) => (
                <th
                  key={c}
                  style={{
                    textAlign: "left",
                    padding: 10,
                    borderBottom: "1px solid #e5e7eb",
                    whiteSpace: "nowrap",
                  }}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 500).map(
              (
                r,
                i, // ✅ 너무 큰 CSV면 우선 500행만 렌더(필요 시 페이지네이션 추가)
              ) => (
                <tr key={i}>
                  {columns.map((c) => (
                    <td
                      key={c}
                      style={{
                        padding: 10,
                        borderBottom: "1px solid #f3f4f6",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {String(r?.[c] ?? "")}
                    </td>
                  ))}
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>

      {rows.length > 500 && (
        <div style={{ marginTop: 8, fontSize: 12, color: "#6b7280" }}>
          성능을 위해 500행까지만 표시 중입니다. (페이지네이션 원하면
          추가해줄게요)
        </div>
      )}
    </div>
  );
}
