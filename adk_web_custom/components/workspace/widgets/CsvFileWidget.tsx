"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

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

  const downloadCsv = () => {
    window.open(
      `${API_URL}/api/csv/${encodeURIComponent(fileId)}/download`,
      "_blank",
    );
  };

  const totalPages = page ? Math.ceil(page.total_rows / PAGE_SIZE) : 0;
  const currentPage = page ? Math.floor(offset / PAGE_SIZE) + 1 : 0;

  if (err)
    return <div className="p-3 text-red-500 text-sm">{err}</div>;

  if (!page && loading)
    return (
      <div className="p-3 text-gray-400 flex items-center gap-2 text-sm">
        <Loader2 size={14} className="animate-spin" />
        CSV 불러오는 중…
      </div>
    );

  if (!page)
    return <div className="p-3 text-gray-400 text-sm">데이터 없음</div>;

  return (
    <div className="flex flex-col h-full p-3 gap-2">
      {/* 상단 바 */}
      <div className="flex items-center justify-between gap-3 shrink-0">
        <button
          onClick={downloadCsv}
          className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded border border-gray-300 hover:bg-gray-50 transition-colors"
        >
          <Download size={13} />
          다운로드
        </button>
        <span className="text-xs text-gray-500 bg-gray-100 rounded px-2 py-1">
          {page.total_rows}행 · {page.columns.length}열
        </span>
      </div>

      {/* 테이블 - 스크롤 하나만 */}
      <div className="flex-1 rounded border border-gray-200 overflow-auto min-h-0">
        <table className="text-[13px] border-collapse" style={{ minWidth: "100%" }}>
          <thead className="sticky top-0 bg-gray-50 z-[1]">
            <tr>
              <th className="text-center text-[11px] text-gray-400 font-normal px-2 py-1.5 border-b border-r border-gray-200 min-w-[36px]">
                #
              </th>
              {page.columns.map((c) => (
                <th
                  key={c}
                  className="text-left text-[12px] font-medium text-gray-700 px-3 py-1.5 border-b border-r border-gray-200 whitespace-nowrap"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {page.rows.map((r, i) => (
              <tr
                key={i}
                className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}
              >
                <td className="text-center text-[11px] text-gray-400 px-2 py-1 border-b border-r border-gray-100">
                  {offset + i + 1}
                </td>
                {page.columns.map((c) => (
                  <td
                    key={c}
                    className="px-3 py-1 border-b border-r border-gray-100 whitespace-nowrap text-gray-800"
                  >
                    {r?.[c] != null ? String(r[c]) : ""}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div className="shrink-0 flex items-center justify-center gap-2.5 text-xs">
          <button
            disabled={offset === 0 || loading}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            className="flex items-center gap-1 px-2.5 py-1 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft size={13} />
            이전
          </button>
          <span className="text-gray-500 tabular-nums">
            {currentPage} / {totalPages}
          </span>
          <button
            disabled={offset + PAGE_SIZE >= page.total_rows || loading}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            className="flex items-center gap-1 px-2.5 py-1 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            다음
            <ChevronRight size={13} />
          </button>
        </div>
      )}

      {loading && (
        <div className="shrink-0 text-xs text-gray-400 text-center flex items-center justify-center gap-1">
          <Loader2 size={12} className="animate-spin" />
          로딩 중…
        </div>
      )}
    </div>
  );
}
