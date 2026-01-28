"use client";

import React, { useEffect, useState } from "react";

export type ServerFileItem = { name: string; url: string };

export default function ServerFilePicker(props: {
  enabled: boolean; // windows.length === 0 일 때만 true
  onSelect: (file: ServerFileItem) => void;
}) {
  const [files, setFiles] = useState<ServerFileItem[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [filesErr, setFilesErr] = useState("");

  const loadFiles = async () => {
    try {
      setFilesErr("");
      setLoadingFiles(true);

      const res = await fetch("/api/adk/workspace/files", {
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

  // enabled 일 때만 자동 로드
  useEffect(() => {
    if (!props.enabled) return;
    void loadFiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.enabled]);

  if (!props.enabled) return null;

  return (
    <div style={{ padding: 24, color: "#6b7280" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          marginBottom: 10,
        }}
      >
        <div style={{ fontWeight: 800, color: "#111827" }}>서버 파일 목록</div>
        <div style={{ flex: 1 }} />
        <button
          onClick={loadFiles}
          style={{
            border: "1px solid #e5e7eb",
            background: "white",
            borderRadius: 10,
            padding: "8px 12px",
            cursor: "pointer",
            fontWeight: 700,
            color: "#111827",
          }}
          aria-label="파일 목록 새로고침"
          title="새로고침"
        >
          refresh
        </button>
      </div>

      {loadingFiles && <div>불러오는 중...</div>}

      {filesErr && (
        <div style={{ color: "#b91c1c", whiteSpace: "pre-wrap" }}>
          {filesErr}
        </div>
      )}

      {!loadingFiles && !filesErr && files.length === 0 && (
        <div>지정 폴더에 파일이 없습니다.</div>
      )}

      {!loadingFiles && !filesErr && files.length > 0 && (
        <div style={{ display: "grid", gap: 10, marginTop: 12, maxWidth: 720 }}>
          {files.map((f) => (
            <div
              key={f.name}
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: 12,
                background: "white",
                padding: 12,
                display: "flex",
                alignItems: "center",
                gap: 12,
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontWeight: 700,
                    color: "#111827",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                  title={f.name}
                >
                  {f.name}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    marginTop: 4,
                    color: "#6b7280",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                  title={f.url}
                >
                  {f.url}
                </div>
              </div>

              <button
                onClick={() => props.onSelect(f)}
                style={{
                  border: "1px solid #e5e7eb",
                  background: "white",
                  borderRadius: 10,
                  padding: "8px 12px",
                  cursor: "pointer",
                  fontWeight: 800,
                  letterSpacing: 0.2,
                }}
                aria-label="파일 선택"
                title="파일 선택"
              >
                SELECT
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
