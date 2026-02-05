"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8080";

type CsvPage = {
  file_id: string;
  filename: string;
  columns: string[];
  rows: Record<string, any>[];
  total_rows: number;
  offset: number;
  limit: number;
};

const PAGE_SIZE = 50;

export default function CsvFileWidget({ fileId }: { fileId: string }) {
  const [page, setPage] = useState<CsvPage | null>(null);
  const [offset, setOffset] = useState(0);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const tableScrollRef = useRef<HTMLDivElement | null>(null);
  const hScrollRef = useRef<HTMLDivElement | null>(null);
  const measureRef = useRef<HTMLTableElement | null>(null);
  const [scrollWidth, setScrollWidth] = useState(0);

  const fetchPage = useCallback(
    async (off: number) => {
      setLoading(true);
      try {
        const res = await fetch(
          `${API_URL}/api/csv/${encodeURIComponent(fileId)}?offset=${off}&limit=${PAGE_SIZE}`,
        );
        if (!res.ok) {
          const t = await res.text().catch(() => "");
          throw new Error(`CSV fetch failed: ${res.status} ${t}`);
        }
        const json: CsvPage = await res.json();
        setPage(json);
        setErr("");
      } catch (e: any) {
        setErr(String(e?.message ?? e));
      } finally {
        setLoading(false);
      }
    },
    [fileId],
  );

  useEffect(() => {
    fetchPage(offset);
  }, [fetchPage, offset]);

  // sync horizontal scroll width
  useEffect(() => {
    if (!page) return;
    const update = () => {
      const tableEl = measureRef.current;
      if (!tableEl) return;
      setScrollWidth(tableEl.scrollWidth);
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [page]);

  const onTableScroll = () => {
    const t = tableScrollRef.current;
    const h = hScrollRef.current;
    if (t && h) h.scrollLeft = t.scrollLeft;
  };

  const onHScroll = () => {
    const t = tableScrollRef.current;
    const h = hScrollRef.current;
    if (t && h) t.scrollLeft = h.scrollLeft;
  };

  const downloadCsv = () => {
    window.open(
      `${API_URL}/api/csv/${encodeURIComponent(fileId)}/download`,
      "_blank",
    );
  };

  const totalPages = page ? Math.ceil(page.total_rows / PAGE_SIZE) : 0;
  const currentPage = page ? Math.floor(offset / PAGE_SIZE) + 1 : 0;

  if (err)
    return <div style={{ padding: 12, color: "#b91c1c" }}>{err}</div>;

  if (!page && loading)
    return (
      <div style={{ padding: 12, color: "#6b7280" }}>CSV 불러오는 중…</div>
    );

  if (!page)
    return (
      <div style={{ padding: 12, color: "#6b7280" }}>데이터 없음</div>
    );

  return (
    <div style={{ padding: 12 }}>
      {/* 상단 바 */}
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
            다운로드
          </button>
        </div>

        <div style={{ fontSize: 12, color: "#6b7280" }}>
          rows: {page.total_rows} · cols: {page.columns.length}
        </div>
      </div>

      {/* 테이블 */}
      <div
        style={{
          border: "1px solid #e5e7eb",
          borderRadius: 10,
          overflow: "hidden",
        }}
      >
        <div
          ref={tableScrollRef}
          onScroll={onTableScroll}
          style={{ overflow: "auto", maxHeight: 420 }}
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
                <th
                  style={{
                    textAlign: "center",
                    padding: 10,
                    borderBottom: "1px solid #e5e7eb",
                    whiteSpace: "nowrap",
                    color: "#6b7280",
                    fontSize: 11,
                    minWidth: 40,
                  }}
                >
                  #
                </th>
                {page.columns.map((c) => (
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
              {page.rows.map((r, i) => (
                <tr key={i}>
                  <td
                    style={{
                      padding: 10,
                      borderBottom: "1px solid #f3f4f6",
                      textAlign: "center",
                      color: "#9ca3af",
                      fontSize: 11,
                    }}
                  >
                    {offset + i + 1}
                  </td>
                  {page.columns.map((c) => (
                    <td
                      key={c}
                      style={{
                        padding: 10,
                        borderBottom: "1px solid #f3f4f6",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {r?.[c] != null ? String(r[c]) : ""}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* 하단 가로 스크롤 */}
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
          <div style={{ width: scrollWidth, height: 14 }} />
        </div>
      </div>

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div
          style={{
            marginTop: 8,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 10,
            fontSize: 12,
          }}
        >
          <button
            disabled={offset === 0 || loading}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            style={{
              padding: "4px 10px",
              borderRadius: 6,
              border: "1px solid #e5e7eb",
              background: "white",
              cursor: offset === 0 || loading ? "not-allowed" : "pointer",
              opacity: offset === 0 || loading ? 0.4 : 1,
            }}
          >
            이전
          </button>
          <span style={{ color: "#6b7280" }}>
            {currentPage} / {totalPages}
          </span>
          <button
            disabled={offset + PAGE_SIZE >= page.total_rows || loading}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            style={{
              padding: "4px 10px",
              borderRadius: 6,
              border: "1px solid #e5e7eb",
              background: "white",
              cursor:
                offset + PAGE_SIZE >= page.total_rows || loading
                  ? "not-allowed"
                  : "pointer",
              opacity:
                offset + PAGE_SIZE >= page.total_rows || loading ? 0.4 : 1,
            }}
          >
            다음
          </button>
        </div>
      )}

      {loading && (
        <div style={{ marginTop: 6, fontSize: 12, color: "#6b7280", textAlign: "center" }}>
          로딩 중…
        </div>
      )}
    </div>
  );
}
