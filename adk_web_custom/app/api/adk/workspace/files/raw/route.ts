import { NextResponse } from "next/server";
import fs from "node:fs/promises";
import path from "node:path";

const ROOT_DIR = process.env.WORKSPACE_FILES_DIR;

function guessContentType(filename: string) {
  const ext = path.extname(filename).toLowerCase();
  if (ext === ".csv") return "text/csv; charset=utf-8";
//   if (ext === ".json") return "application/json; charset=utf-8";
//   if (ext === ".txt") return "text/plain; charset=utf-8";
//   if (ext === ".html") return "text/html; charset=utf-8";
//   if (ext === ".xlsx") return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  return "application/octet-stream";
}

export async function GET(req: Request) {
  if (!ROOT_DIR) {
    return NextResponse.json(
      { ok: false, error: "WORKSPACE_FILES_DIR is not set" },
      { status: 500 },
    );
  }

  const { searchParams } = new URL(req.url);
  const name = searchParams.get("name") ?? "";

  if (!name || name.includes("/") || name.includes("\\") || name.includes("..")) {
    return NextResponse.json(
      { ok: false, error: "Invalid file name" },
      { status: 400 },
    );
  }

  const fullPath = path.resolve(path.join(ROOT_DIR, name));
  const rootResolved = path.resolve(ROOT_DIR);

  if (!fullPath.startsWith(rootResolved + path.sep) && fullPath !== rootResolved) {
    return NextResponse.json(
      { ok: false, error: "Path is out of root" },
      { status: 403 },
    );
  }

  try {
    const buf = await fs.readFile(fullPath);
    return new NextResponse(buf, {
      status: 200,
      headers: {
        "Content-Type": guessContentType(name),
        "Content-Disposition": `inline; filename="${encodeURIComponent(name)}"`,
      },
    });
  } catch (err: any) {
    return NextResponse.json(
      { ok: false, error: String(err?.message ?? err) },
      { status: 404 },
    );
  }
}
