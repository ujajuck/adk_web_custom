"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Download, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";

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
    return <div className="p-3 text-destructive text-sm">{err}</div>;

  if (!page && loading)
    return (
      <div className="p-3 text-muted-foreground flex items-center gap-2">
        <Loader2 size={14} className="animate-spin" />
        CSV 불러오는 중…
      </div>
    );

  if (!page)
    return <div className="p-3 text-muted-foreground">데이터 없음</div>;

  return (
    <div className="p-3">
      {/* 상단 바 */}
      <div className="flex items-center justify-between gap-3 mb-2">
        <Button variant="outline" size="sm" onClick={downloadCsv} title="CSV 다운로드">
          <Download size={14} />
          다운로드
        </Button>

        <Badge variant="secondary" className="text-xs font-normal">
          rows: {page.total_rows} · cols: {page.columns.length}
        </Badge>
      </div>

      {/* 테이블 */}
      <div className="rounded-lg border overflow-hidden">
        <div
          ref={tableScrollRef}
          onScroll={onTableScroll}
          className="overflow-auto max-h-[420px]"
        >
          <table ref={measureRef} className="w-full text-[13px] border-collapse">
            <thead className="sticky top-0 bg-card z-[1]">
              <tr>
                <TableHead className="text-center text-[11px] text-muted-foreground min-w-[40px]">
                  #
                </TableHead>
                {page.columns.map((c) => (
                  <TableHead key={c} className="whitespace-nowrap">
                    {c}
                  </TableHead>
                ))}
              </tr>
            </thead>
            <tbody>
              {page.rows.map((r, i) => (
                <TableRow key={i}>
                  <TableCell className="text-center text-[11px] text-muted-foreground">
                    {offset + i + 1}
                  </TableCell>
                  {page.columns.map((c) => (
                    <TableCell key={c} className="whitespace-nowrap">
                      {r?.[c] != null ? String(r[c]) : ""}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </tbody>
          </table>
        </div>

        {/* 하단 가로 스크롤 */}
        <div
          ref={hScrollRef}
          onScroll={onHScroll}
          className="sticky bottom-0 overflow-x-auto overflow-y-hidden bg-card border-t"
        >
          <div style={{ width: scrollWidth, height: 14 }} />
        </div>
      </div>

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div className="mt-2 flex items-center justify-center gap-2.5 text-xs">
          <Button
            variant="outline"
            size="sm"
            disabled={offset === 0 || loading}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            className="h-7 px-2.5"
          >
            <ChevronLeft size={14} />
            이전
          </Button>
          <span className="text-muted-foreground tabular-nums">
            {currentPage} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={offset + PAGE_SIZE >= page.total_rows || loading}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            className="h-7 px-2.5"
          >
            다음
            <ChevronRight size={14} />
          </Button>
        </div>
      )}

      {loading && (
        <div className="mt-1.5 text-xs text-muted-foreground text-center flex items-center justify-center gap-1">
          <Loader2 size={12} className="animate-spin" />
          로딩 중…
        </div>
      )}
    </div>
  );
}
