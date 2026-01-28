"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Papa from "papaparse";

export default function CsvTableFromUrlWidget({ src }: { src: string }) {
  const [csvText, setCsvText] = useState<string>("");
  const [err, setErr] = useState<string>("");

  const tableScrollRef = useRef<HTMLDivElement | null>(null); 
  const hScrollRef = useRef<HTMLDivElement | null>(null);
  const measureRef = useRef<HTMLTableElement | null>(null); 

  // 하단 스크롤바의 "스크롤 가능한 너비"를 만들기 위한 값
  const [scrollWidth, setScrollWidth] = useState<number>(0);

  useEffect(() => {
    (async () => {
      try {
        setErr("");
        const res = await fetch(src, { cache: "no-store" });
        if (!res.ok) {
          const t = await res.text().catch(() => "");
          throw new Error(`CSV fetch failed: ${res.status} ${t}`);
        }
        const text = await res.text();
        setCsvText(text);
      } catch (e: any) {
        setErr(String(e?.message ?? e));
      }
    })();
  }, [src]);

  const parsed = useMemo(() => {
    if (!csvText)
      return { columns: [] as string[], rows: [] as any[], parseErr: "" };

    const res = Papa.parse<Record<string, any>>(csvText, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: true,
    });

    const parseErr = res.errors?.[0]?.message ?? "";
    const rows = (res.data ?? []).filter(Boolean);
    const columns = rows.length
      ? Object.keys(rows[0])
      : (res.meta.fields ?? []);
    return { columns, rows, parseErr };
  }, [csvText]);

  // 테이블 렌더 후 실제 scrollWidth 측정해서 하단 스크롤바에 반영
  useEffect(() => {
    if (!csvText) return;

    const update = () => {
      const tableEl = measureRef.current;
      const containerEl = tableScrollRef.current;
      if (!tableEl || !containerEl) return;

      // 실제 테이블 전체 너비(가로 스크롤 대상)
      const w = tableEl.scrollWidth;
      setScrollWidth(w);

      // 하단 스크롤바의 scrollLeft를 현재 테이블 scrollLeft와 맞춤
      if (hScrollRef.current) {
        hScrollRef.current.scrollLeft = containerEl.scrollLeft;
      }
    };

    update();

    // 창 리사이즈 시 재측정
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [csvText, parsed.columns.length, parsed.rows.length]);

  // 테이블 스크롤 -> 하단 스크롤바로 동기화
  const onTableScroll = () => {
    const tableEl = tableScrollRef.current;
    const hEl = hScrollRef.current;
    if (!tableEl || !hEl) return;
    hEl.scrollLeft = tableEl.scrollLeft;
  };

  // 하단 스크롤바 -> 테이블로 동기화
  const onHScroll = () => {
    const tableEl = tableScrollRef.current;
    const hEl = hScrollRef.current;
    if (!tableEl || !hEl) return;
    tableEl.scrollLeft = hEl.scrollLeft;
  };

  const downloadCsv = () => {
    // CSV 텍스트를 Blob으로 만들어 다운로드
    const blob = new Blob([csvText], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = "data.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();

    URL.revokeObjectURL(url);
  };

  const onEditClick = () => {
    // TODO: 원하시는 편집 UX(모달/인라인 편집/다른 페이지 이동)에 연결
    alert("편집 기능은 아직 연결되지 않았습니다.");
  };

  if (err) return <div style={{ padding: 12, color: "#b91c1c" }}>{err}</div>;
  if (!csvText)
    return (
      <div style={{ padding: 12, color: "#6b7280" }}>CSV 불러오는 중…</div>
    );
  if (parsed.parseErr)
    return (
      <div style={{ padding: 12, color: "#b91c1c" }}>
        CSV 파싱 오류: {parsed.parseErr}
      </div>
    );

  return (
    <div style={{ padding: 12 }}>
      {/* 상단 바: 좌측 버튼 + 우측 rows/cols */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          marginBottom: 8,
        }}
      >
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            onClick={downloadCsv}
            title="CSV 다운로드"
            style={{
              fontSize: 12,
              padding: "6px 10px",
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              background: "white",
              cursor: "pointer",
            }}
          >
            ⬇ 다운로드
          </button>
          <button
            type="button"
            onClick={onEditClick}
            title="sql편집"
            style={{
              fontSize: 12,
              padding: "6px 10px",
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              background: "white",
              cursor: "pointer",
            }}
          >
            ✏️ SQL 편집
          </button>
        </div>

        <div style={{ fontSize: 12, color: "#6b7280" }}>
          rows: {parsed.rows.length} · cols: {parsed.columns.length}
        </div>
      </div>

      {/* 테이블+하단 고정 가로 스크롤을 묶는 래퍼 */}
      <div
        style={{
          border: "1px solid #e5e7eb",
          borderRadius: 10,
          overflow: "hidden", // sticky 스크롤바가 테두리 밖으로 안 나가게
        }}
      >
        {/* 실제 테이블 스크롤 영역 (세로/가로) */}
        <div
          ref={tableScrollRef}
          onScroll={onTableScroll}
          style={{
            overflow: "auto",
            maxHeight: 520, // 필요 시 조절(세로 스크롤 생기게)
          }}
        >
          <table
            ref={measureRef}
            style={{ borderCollapse: "collapse", width: "100%", fontSize: 13 }}
          >
            <thead
              style={{
                position: "sticky",
                top: 0,
                background: "white",
                zIndex: 1,
              }}
            >
              <tr>
                {parsed.columns.map((c) => (
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
              {parsed.rows.slice(0, 30).map((r, i) => (
                <tr key={i}>
                  {parsed.columns.map((c) => (
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
              ))}
            </tbody>
          </table>
        </div>

        {/* 하단에 "항상 보이는" 가로 스크롤바 (sticky) */}
        <div
          ref={hScrollRef}
          onScroll={onHScroll}
          style={{
            position: "sticky",
            bottom: 0,
            overflowX: "auto",
            overflowY: "hidden",
            background: "white",
            borderTop: "1px solid #f3f4f6",
          }}
        >
          {/* 이 div가 실제 스크롤 너비를 만든다 */}
          <div style={{ width: scrollWidth, height: 14 }} />
        </div>
      </div>

      {parsed.rows.length > 30 && (
        <div style={{ marginTop: 8, fontSize: 12, color: "#6b7280" }}>
          성능을 위해 30행까지만 표시 중
        </div>
      )}
    </div>
  );
}
