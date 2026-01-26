export type PlotlyFig = { data: any[]; layout?: any; config?: any; frames?: any[] };

/**
 * ADK 이벤트 전체를 DFS로 훑어 FastMCP 툴의 고정 스키마(outputs[0].graph)를 찾아
 * Plotly Figure JSON 문자열을 객체로 파싱해 반환합니다.
 *
 * FastMCP 툴 출력 예:
 * return { "status":"success", "outputs":[ { "graph":"<plotly_json_string>" } ] }
 */
export function tryExtractPlotlyFig(
  events: unknown,
): { title: string; fig: PlotlyFig } | null {
  if (!Array.isArray(events)) return null;

  const visited = new Set<any>();

  const findGraphJson = (
    node: any,
  ): { graph: string; title?: string } | null => {
    if (!node || typeof node !== "object") return null;
    if (visited.has(node)) return null;
    visited.add(node);

    // { status:"success", outputs:[{ graph:"<json>" }] }
    const graph = node?.outputs?.[0]?.graph;
    if (typeof graph === "string" && graph.trim().length > 0) {
      const title =
        node?.title ??
        (typeof node?.layout?.title === "string"
          ? node.layout.title
          : node?.layout?.title?.text);
      return { graph, title };
    }

    // 배열이면 각 원소 DFS
    if (Array.isArray(node)) {
      for (const it of node) {
        const r = findGraphJson(it);
        if (r) return r;
      }
      return null;
    }

    // 객체이면 키 전부 DFS
    for (const k of Object.keys(node)) {
      const r = findGraphJson((node as any)[k]);
      if (r) return r;
    }
    return null;
  };

  // 이벤트들 각각에서 graphJson을 찾아서 PlotlyFig로 파싱
  for (const ev of events as any[]) {
    const found = findGraphJson(ev);
    if (!found) continue;

    try {
      const figObj: any = JSON.parse(found.graph);
      if (!figObj || !Array.isArray(figObj.data)) continue;

      const titleFromLayout =
        typeof figObj?.layout?.title === "string"
          ? figObj.layout.title
          : figObj?.layout?.title?.text;

      return {
        title: found.title ?? titleFromLayout ?? "그래프",
        fig: {
          data: figObj.data,
          layout: figObj.layout ?? {},
          config: figObj.config ?? {},
          frames: Array.isArray(figObj.frames) ? figObj.frames : undefined,
        },
      };
    } catch {
      // graph 문자열은 찾았는데 JSON이 아니면 다음 이벤트로
      continue;
    }
  }

  return null;
}
