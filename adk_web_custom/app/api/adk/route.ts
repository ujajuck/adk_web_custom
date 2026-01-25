// app/api/adk/route.ts
export async function POST(req: Request) {
  const body = await req.json();

  const rawBase = process.env.ADK_BASE_URL;
  const appName = process.env.ADK_APP_NAME;

  if (!rawBase) {
    return Response.json({ ok: false, error: "ADK_BASE_URL is not set" }, { status: 500 });
  }
  if (!appName) {
    return Response.json({ ok: false, error: "ADK_APP_NAME is not set" }, { status: 500 });
  }

  const adkBase =
    rawBase.startsWith("http://") || rawBase.startsWith("https://")
      ? rawBase
      : `http://${rawBase}`;

  const userId = body.userId ?? body.user_id;
  const sessionId = body.sessionId ?? body.session_id;
  const newMessage = body.newMessage ?? body.new_message;

  if (!userId || !sessionId || !newMessage) {
    return Response.json({ ok: false, error: "userId/sessionId/newMessage required" }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${adkBase.replace(/\/$/, "")}/run`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        appName,
        userId,
        sessionId,
        newMessage,
      }), // ✅ upstream body는 문자열로 단 1회만 전송
    });

    // ✅ 응답 body는 "한 번만" 읽는다 (json() 실패 후 text() 재시도 금지)
    const text = await upstream.text(); // ✅ 여기서 한 번 소비
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
