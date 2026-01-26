// app/api/adk/artifacts/csv/route.ts
import fs from "node:fs/promises";
import path from "node:path";

function safe(s: string) {
  return s.replace(/[\\/]/g, "_").replace(/\.\./g, "_").trim();
}

export async function GET(req: Request) {
  const url = new URL(req.url);

  const userId = safe((url.searchParams.get("userId") ?? "").trim());
  const sessionId = safe((url.searchParams.get("sessionId") ?? "").trim());
  const filename = safe((url.searchParams.get("filename") ?? "").trim());
  const version = safe((url.searchParams.get("version") ?? "0").trim());

  if (!userId || !sessionId || !filename) {
    return Response.json(
      { ok: false, error: "userId/sessionId/filename required" },
      { status: 400 }
    );
  }

  const adkRoot =
    process.env.ADK_ARTIFACT_ROOT ??
    path.join(process.cwd(), ".adk", "artifacts");

  const filePath = path.join(
    adkRoot,
    "users",
    userId,
    "sessions",
    sessionId,
    "artifacts",
    filename,
    "versions",
    version,
    filename
  );

  try {
    const buf = await fs.readFile(filePath);
    return new Response(buf, {
      status: 200,
      headers: {
        "content-type": "text/csv; charset=utf-8",
        "cache-control": "no-store",
      },
    });
  } catch (e: any) {
    return Response.json(
      {
        ok: false,
        error: "artifact_read_failed",
        filePath,
        detail: String(e?.message ?? e),
      },
      { status: 404 }
    );
  }
}
