"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Download, Pencil } from "lucide-react";
import Papa from "papaparse";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TableHead, TableRow, TableCell } from "@/components/ui/table";

export default function CsvTableFromUrlWidget({ src }: { src: string }) {
  const [csvText, setCsvText] = useState<string>("");
  const [err, setErr] = useState<string>("");

  const tableScrollRef = useRef<HTMLDivElement | null>(null);
  const hScrollRef = useRef<HTMLDivElement | null>(null);
  const measureRef = useRef<HTMLTableElement | null>(null);

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

  useEffect(() => {
    if (!csvText) return;

    const update = () => {
      const tableEl = measureRef.current;
      const containerEl = tableScrollRef.current;
      if (!tableEl || !containerEl) return;

      const w = tableEl.scrollWidth;
      setScrollWidth(w);

      if (hScrollRef.current) {
        hScrollRef.current.scrollLeft = containerEl.scrollLeft;
      }
    };

    update();

    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [csvText, parsed.columns.length, parsed.rows.length]);

  const onTableScroll = () => {
    const tableEl = tableScrollRef.current;
    const hEl = hScrollRef.current;
    if (!tableEl || !hEl) return;
    hEl.scrollLeft = tableEl.scrollLeft;
  };

  const onHScroll = () => {
    const tableEl = tableScrollRef.current;
    const hEl = hScrollRef.current;
    if (!tableEl || !hEl) return;
    tableEl.scrollLeft = hEl.scrollLeft;
  };

  const downloadCsv = () => {
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
    alert("편집 기능은 아직 연결되지 않았습니다.");
  };

  if (err)
    return <div className="p-3 text-destructive text-sm">{err}</div>;
  if (!csvText)
    return <div className="p-3 text-muted-foreground">CSV 불러오는 중…</div>;
  if (parsed.parseErr)
    return (
      <div className="p-3 text-destructive text-sm">
        CSV 파싱 오류: {parsed.parseErr}
      </div>
    );

  return (
    <div className="p-3">
      {/* 상단 바 */}
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={downloadCsv} title="CSV 다운로드">
            <Download size={14} />
            다운로드
          </Button>
          <Button variant="outline" size="sm" onClick={onEditClick} title="SQL 편집">
            <Pencil size={14} />
            SQL 편집
          </Button>
        </div>

        <Badge variant="secondary" className="text-xs font-normal">
          rows: {parsed.rows.length} · cols: {parsed.columns.length}
        </Badge>
      </div>

      {/* 테이블 */}
      <div className="rounded-lg border overflow-hidden">
        <div
          ref={tableScrollRef}
          onScroll={onTableScroll}
          className="overflow-auto max-h-[520px]"
        >
          <table ref={measureRef} className="w-full text-[13px] border-collapse">
            <thead className="sticky top-0 bg-card z-[1]">
              <tr>
                {parsed.columns.map((c) => (
                  <TableHead key={c} className="whitespace-nowrap">
                    {c}
                  </TableHead>
                ))}
              </tr>
            </thead>
            <tbody>
              {parsed.rows.slice(0, 30).map((r, i) => (
                <TableRow key={i}>
                  {parsed.columns.map((c) => (
                    <TableCell key={c} className="whitespace-nowrap">
                      {String(r?.[c] ?? "")}
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

      {parsed.rows.length > 30 && (
        <p className="mt-2 text-xs text-muted-foreground">
          성능을 위해 30행까지만 표시 중
        </p>
      )}
    </div>
  );
}
