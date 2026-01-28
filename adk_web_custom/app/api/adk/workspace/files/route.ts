import { NextResponse } from "next/server";
import fs from "node:fs/promises";
import path from "node:path";

const ROOT_DIR = process.env.WORKSPACE_FILES_DIR;

export async function GET() {
  if (!ROOT_DIR) {
    return NextResponse.json({ ok: false, error: "WORKSPACE_FILES_DIR is not set" }, { status: 500 });
  }

  try {
    const entries = await fs.readdir(ROOT_DIR, { withFileTypes: true });

    const files = entries
      .filter((e) => e.isFile())
      .map((e) => ({
        name: e.name,
        // (선택) 프론트에서 내용 미리보기 필요하면 유지
        // previewUrl: `/api/adk/workspace/files/raw?name=${encodeURIComponent(e.name)}`,
      }))
      .sort((a, b) => a.name.localeCompare(b.name));

    return NextResponse.json({ ok: true, rootDir: ROOT_DIR, files });
  } catch (err: any) {
    return NextResponse.json({ ok: false, error: String(err?.message ?? err) }, { status: 500 });
  }
}
