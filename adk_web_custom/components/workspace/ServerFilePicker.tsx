"use client";

import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8080";

export type ServerFileItem = { name: string; url?: string; size?: number };

export default function ServerFilePicker(props: {
  enabled: boolean;
  onSelect: (file: ServerFileItem) => void;
}) {
  const [files, setFiles] = useState<ServerFileItem[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [filesErr, setFilesErr] = useState("");

  const loadFiles = async () => {
    try {
      setFilesErr("");
      setLoadingFiles(true);

      const res = await fetch(`${API_URL}/api/files`, {
        cache: "no-store",
      });
      if (!res.ok) {
        const t = await res.text().catch(() => "");
        throw new Error(`파일 목록 조회 실패: ${res.status} ${t}`);
      }
      const data = (await res.json()) as {
        ok: boolean;
        files?: ServerFileItem[];
        error?: string;
      };

      if (!data.ok) throw new Error(data.error || "파일 목록 응답이 ok=false");
      setFiles(data.files ?? []);
    } catch (e: any) {
      setFilesErr(String(e?.message ?? e));
    } finally {
      setLoadingFiles(false);
    }
  };

  useEffect(() => {
    if (!props.enabled) return;
    void loadFiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.enabled]);

  if (!props.enabled) return null;

  return (
    <div className="p-6 text-muted-foreground">
      <div className="flex items-center gap-2.5 mb-3">
        <h2 className="font-extrabold text-foreground">서버 파일 목록</h2>
      </div>

      {loadingFiles && <p>불러오는 중...</p>}

      {filesErr && (
        <p className="text-destructive whitespace-pre-wrap">{filesErr}</p>
      )}

      {!loadingFiles && !filesErr && files.length === 0 && (
        <p>지정 폴더에 파일이 없습니다.</p>
      )}

      {!loadingFiles && !filesErr && files.length > 0 && (
        <div className="grid gap-2.5 mt-3 max-w-[720px]">
          {files.map((f) => (
            <Card
              key={f.name}
              className="p-3 flex items-center gap-3"
            >
              <div className="flex-1 min-w-0">
                <div
                  className="font-bold text-sm text-card-foreground truncate"
                  title={f.name}
                >
                  {f.name}
                </div>
                {f.size != null && (
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {(f.size / 1024).toFixed(1)} KB
                  </div>
                )}
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={() => props.onSelect(f)}
                aria-label="파일 선택"
                title="파일 선택"
                className="font-extrabold tracking-wide"
              >
                SELECT
              </Button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
