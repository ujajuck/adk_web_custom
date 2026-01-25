// app/api/adk/session/route.ts
export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));

  const rawBase = process.env.ADK_BASE_URL;
  const appName = process.env.ADK_APP_NAME;

  if (!rawBase) return Response.json({ ok: false, error: "ADK_BASE_URL is not set" }, { status: 500 });
  if (!appName) return Response.json({ ok: false, error: "ADK_APP_NAME is not set" }, { status: 500 });

  const adkBase =
    rawBase.startsWith("http://") || rawBase.startsWith("https://")
      ? rawBase
      : `http://${rawBase}`;

  const userId = String(body.userId ?? body.user_id ?? "");
  const sessionId = String(body.sessionId ?? body.session_id ?? "");
  if (!userId || !sessionId) {
    return Response.json({ ok: false, error: "userId/sessionId required" }, { status: 400 });
  }

  const url = `${adkBase.replace(/\/$/, "")}/apps/${encodeURIComponent(appName)}/users/${encodeURIComponent(
    userId
  )}/sessions/${encodeURIComponent(sessionId)}`;

  try {
    const upstream = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body.state ?? {}), // ✅ state 초기값(optional)
    });

    const text = await upstream.text(); // ✅ 한 번만 읽기
    let data: any;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }

    return Response.json({ ok: upstream.ok, status: upstream.status, data }, { status: 200 });
  } catch (e: any) {
    return Response.json(
      { ok: false, error: "fetch_failed", detail: String(e?.message ?? e) },
      { status: 500 }
    );
  }
}
