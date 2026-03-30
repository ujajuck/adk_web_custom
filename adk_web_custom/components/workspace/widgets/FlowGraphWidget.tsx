"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8080";

// ── 타입 ──────────────────────────────────────────────────────────
interface FlowNode {
  id: string;
  label: string;
  node_type: "input" | "output" | "intermediate";
  artifact_name?: string;
  file_name?: string;
}

interface FlowEdge {
  id: string;
  source: string;
  target: string;
  tool_name: string;
  agent_name?: string;
  tool_args?: Record<string, any>;
  label?: string;
}

interface FlowData {
  session_id: string;
  nodes: FlowNode[];
  edges: FlowEdge[];
}

// ── 레이아웃 계산 ──────────────────────────────────────────────────
interface DrawNode {
  id: string;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
  kind: "artifact" | "tool";
  data: FlowNode | FlowEdge;
}

interface DrawEdge {
  from: DrawNode;
  to: DrawNode;
}

const ART_R = 26;   // artifact 원 반지름
const TOOL_W = 130; // tool 사각형 너비
const TOOL_H = 38;  // tool 사각형 높이
const COL_GAP = 80; // 컬럼 사이 간격
const ROW_GAP = 36; // 같은 컬럼 내 행 간격
const PAD_X = 50;
const PAD_Y = 60;

function buildLayout(data: FlowData): { nodes: DrawNode[]; edges: DrawEdge[] } {
  if (!data.nodes.length) return { nodes: [], edges: [] };

  // 각 artifact node의 BFS 레벨 계산 (열 위치)
  const artLevel = new Map<string, number>();
  const inEdges = new Map<string, FlowEdge[]>();
  for (const e of data.edges) {
    if (!inEdges.has(e.target)) inEdges.set(e.target, []);
    inEdges.get(e.target)!.push(e);
  }
  // BFS
  const roots = data.nodes.filter(
    (n) => !inEdges.has(n.id) || inEdges.get(n.id)!.length === 0,
  );
  const queue = roots.map((r) => ({ id: r.id, level: 0 }));
  const visited = new Set<string>();
  while (queue.length) {
    const { id, level } = queue.shift()!;
    if (visited.has(id)) continue;
    visited.add(id);
    artLevel.set(id, level);
    for (const e of data.edges) {
      if (e.source === id && !visited.has(e.target)) {
        queue.push({ id: e.target, level: level + 1 });
      }
    }
  }
  // 미방문 노드
  for (const n of data.nodes) {
    if (!artLevel.has(n.id)) artLevel.set(n.id, 0);
  }

  // artifact node의 x 좌표: 레벨 * (2컬럼 폭) → artifact | tool | artifact | tool ...
  const artColW = ART_R * 2;
  const toolColW = TOOL_W;
  const colW = artColW + COL_GAP + toolColW + COL_GAP; // 한 단계 너비

  // artifact 위치: 같은 레벨이면 행으로 분리
  const levelRows = new Map<number, number>(); // level → 현재 행 수
  const drawNodes: DrawNode[] = [];
  const artNodeMap = new Map<string, DrawNode>();

  for (const n of data.nodes) {
    const level = artLevel.get(n.id) ?? 0;
    const rowIdx = levelRows.get(level) ?? 0;
    levelRows.set(level, rowIdx + 1);

    const x = PAD_X + level * colW + ART_R;
    const y = PAD_Y + rowIdx * (ART_R * 2 + ROW_GAP) + ART_R;

    const dn: DrawNode = {
      id: n.id,
      label: n.artifact_name || n.label,
      x,
      y,
      w: ART_R * 2,
      h: ART_R * 2,
      kind: "artifact",
      data: n,
    };
    drawNodes.push(dn);
    artNodeMap.set(n.id, dn);
  }

  // tool node: 소스 artifact 오른쪽 COL_GAP에 배치
  const toolRowCount = new Map<number, number>(); // 같은 level의 tool 개수
  const toolNodeMap = new Map<string, DrawNode>();

  for (const e of data.edges) {
    const src = artNodeMap.get(e.source);
    if (!src) continue;

    const level = artLevel.get(e.source) ?? 0;
    const tIdx = toolRowCount.get(level) ?? 0;
    toolRowCount.set(level, tIdx + 1);

    // tool x: artifact 오른쪽
    const tx = src.x + ART_R + COL_GAP;
    // tool y: 소스와 타깃의 중간 (타깃 없으면 소스와 같은 높이)
    const tgt = artNodeMap.get(e.target);
    const ty = tgt
      ? (src.y + tgt.y) / 2 - TOOL_H / 2
      : src.y - TOOL_H / 2;

    const agentPart = e.agent_name || "";
    const toolPart = e.tool_name || "";
    const rawLabel = agentPart && toolPart
      ? `${agentPart}:${toolPart}`
      : toolPart || agentPart || e.label || "tool";

    const dn: DrawNode = {
      id: `tool_${e.id}`,
      label: rawLabel,
      x: tx,
      y: ty,
      w: TOOL_W,
      h: TOOL_H,
      kind: "tool",
      data: e,
    };
    drawNodes.push(dn);
    toolNodeMap.set(e.id, dn);
  }

  // 엣지: artifact→tool, tool→artifact
  const drawEdges: DrawEdge[] = [];
  for (const e of data.edges) {
    const src = artNodeMap.get(e.source);
    const tgt = artNodeMap.get(e.target);
    const tool = toolNodeMap.get(e.id);
    if (src && tool) drawEdges.push({ from: src, to: tool });
    if (tool && tgt) drawEdges.push({ from: tool, to: tgt });
  }

  return { nodes: drawNodes, edges: drawEdges };
}

// ── 컴포넌트 ──────────────────────────────────────────────────────
interface WindowInfo {
  id: string;
  widget: { type: string; title: string; [key: string]: any };
  [key: string]: any;
}

interface FlowGraphWidgetProps {
  sessionId: string;
  staticFlow?: FlowData; // 노트북에서 로드된 정적 스냅샷
  checkedWidgets?: string[];
  allWindows?: WindowInfo[];
}

export default function FlowGraphWidget({
  sessionId,
  staticFlow,
  checkedWidgets = [],
  allWindows = [],
}: FlowGraphWidgetProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [flowData, setFlowData] = useState<FlowData | null>(staticFlow ?? null);
  const [loading, setLoading] = useState(!staticFlow);
  const [error, setError] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<DrawNode | null>(null);
  const [layout, setLayout] = useState<{ nodes: DrawNode[]; edges: DrawEdge[] }>({
    nodes: [],
    edges: [],
  });

  // staticFlow가 있으면 API 폴링 없이 바로 사용
  const fetchFlow = useCallback(async () => {
    if (staticFlow) return; // 정적 모드에서는 API 호출 불요
    try {
      const res = await fetch(`${API_URL}/api/flow/${sessionId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setFlowData(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch flow");
    } finally {
      setLoading(false);
    }
  }, [sessionId, staticFlow]);

  useEffect(() => {
    if (staticFlow) {
      setFlowData(staticFlow);
      setLoading(false);
      return;
    }
    fetchFlow();
    const interval = setInterval(fetchFlow, 5000);
    return () => clearInterval(interval);
  }, [fetchFlow, staticFlow]);

  // checkedWidgets 필터링
  const filteredData = React.useMemo<FlowData | null>(() => {
    if (!flowData) return null;
    if (checkedWidgets.length === 0) return flowData;

    const relevantNodeIds = new Set<string>();
    const relevantEdgeIds = new Set<string>();

    for (const e of flowData.edges) {
      const label = e.label || e.tool_name || "";
      if (checkedWidgets.some((w) => label.includes(w))) {
        relevantEdgeIds.add(e.id);
        relevantNodeIds.add(e.source);
        relevantNodeIds.add(e.target);
      }
    }
    for (const n of flowData.nodes) {
      if (checkedWidgets.some((w) => (n.label || "").includes(w)))
        relevantNodeIds.add(n.id);
    }
    for (const e of flowData.edges) {
      if (relevantNodeIds.has(e.source) || relevantNodeIds.has(e.target)) {
        relevantEdgeIds.add(e.id);
        relevantNodeIds.add(e.source);
        relevantNodeIds.add(e.target);
      }
    }

    const fn = flowData.nodes.filter((n) => relevantNodeIds.has(n.id));
    const fe = flowData.edges.filter((e) => relevantEdgeIds.has(e.id));
    return {
      ...flowData,
      nodes: fn.length ? fn : flowData.nodes,
      edges: fe.length ? fe : flowData.edges,
    };
  }, [flowData, checkedWidgets]);

  // 레이아웃 계산
  useEffect(() => {
    if (!filteredData) return;
    setLayout(buildLayout(filteredData));
  }, [filteredData]);

  // ── 캔버스 렌더링 ────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !filteredData) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    // 배경
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, rect.width, rect.height);

    // roundRect 폴백
    const roundRect = (x: number, y: number, w: number, h: number, r: number) => {
      if (typeof ctx.roundRect === "function") {
        ctx.roundRect(x, y, w, h, r);
      } else {
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w - r, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + r);
        ctx.lineTo(x + w, y + h - r);
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
        ctx.lineTo(x + r, y + h);
        ctx.quadraticCurveTo(x, y + h, x, y + h - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();
      }
    };

    // 엣지 그리기
    for (const edge of layout.edges) {
      const { from, to } = edge;
      // from → to 연결점 계산
      const sx = from.kind === "artifact" ? from.x + ART_R : from.x + from.w;
      const sy = from.kind === "artifact" ? from.y : from.y + from.h / 2;
      const ex = to.kind === "artifact" ? to.x - ART_R : to.x;
      const ey = to.kind === "artifact" ? to.y : to.y + to.h / 2;

      const cpX = (sx + ex) / 2;
      ctx.beginPath();
      ctx.strokeStyle = "#475569";
      ctx.lineWidth = 1.5;
      ctx.moveTo(sx, sy);
      ctx.bezierCurveTo(cpX, sy, cpX, ey, ex, ey);
      ctx.stroke();

      // 화살표
      const angle = Math.atan2(ey - sy, ex - cpX);
      const ar = 6;
      ctx.beginPath();
      ctx.fillStyle = "#475569";
      ctx.moveTo(ex, ey);
      ctx.lineTo(ex - ar * Math.cos(angle - Math.PI / 6), ey - ar * Math.sin(angle - Math.PI / 6));
      ctx.lineTo(ex - ar * Math.cos(angle + Math.PI / 6), ey - ar * Math.sin(angle + Math.PI / 6));
      ctx.closePath();
      ctx.fill();
    }

    // 노드 그리기
    for (const dn of layout.nodes) {
      const hovered = hoveredNode?.id === dn.id;

      ctx.save();
      if (dn.kind === "artifact") {
        // 원형 (artifact)
        ctx.beginPath();
        ctx.arc(dn.x, dn.y, ART_R, 0, Math.PI * 2);
        ctx.fillStyle = hovered ? "#166534" : "#14532d";
        ctx.fill();
        ctx.strokeStyle = hovered ? "#4ade80" : "#22c55e";
        ctx.lineWidth = hovered ? 2 : 1.5;
        ctx.stroke();

        // 라벨 (원 안)
        ctx.font = "bold 9px system-ui";
        ctx.fillStyle = "#bbf7d0";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        const maxW = ART_R * 2 - 6;
        // 두 줄 분할
        const words = dn.label.split(/[._\-]/);
        if (words.length > 1 && ctx.measureText(dn.label).width > maxW) {
          const mid = Math.ceil(words.length / 2);
          ctx.fillText(words.slice(0, mid).join("."), dn.x, dn.y - 6, maxW);
          ctx.fillText(words.slice(mid).join("."), dn.x, dn.y + 6, maxW);
        } else {
          ctx.fillText(dn.label, dn.x, dn.y, maxW);
        }
      } else {
        // 사각형 (tool)
        ctx.beginPath();
        roundRect(dn.x, dn.y, dn.w, dn.h, 6);
        ctx.fillStyle = hovered ? "#312e81" : "#1e1b4b";
        ctx.fill();
        ctx.strokeStyle = hovered ? "#818cf8" : "#4338ca";
        ctx.lineWidth = hovered ? 2 : 1.5;
        ctx.stroke();

        // 라벨 분리: agent / tool
        const raw = dn.label;
        const colonIdx = raw.indexOf(":");
        if (colonIdx > -1) {
          const agent = raw.slice(0, colonIdx);
          const tool = raw.slice(colonIdx + 1);
          ctx.font = "bold 8px system-ui";
          ctx.fillStyle = "#a5b4fc";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(agent, dn.x + dn.w / 2, dn.y + dn.h / 2 - 7, dn.w - 8);
          ctx.font = "9px system-ui";
          ctx.fillStyle = "#e0e7ff";
          ctx.fillText(tool, dn.x + dn.w / 2, dn.y + dn.h / 2 + 7, dn.w - 8);
        } else {
          ctx.font = "bold 9px system-ui";
          ctx.fillStyle = "#e0e7ff";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(raw, dn.x + dn.w / 2, dn.y + dn.h / 2, dn.w - 8);
        }
      }
      ctx.restore();
    }
  }, [filteredData, layout, hoveredNode]);

  // 마우스 인터랙션
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      const hit = layout.nodes.find((dn) => {
        if (dn.kind === "artifact") {
          const dx = mx - dn.x;
          const dy = my - dn.y;
          return dx * dx + dy * dy <= ART_R * ART_R;
        } else {
          return mx >= dn.x && mx <= dn.x + dn.w && my >= dn.y && my <= dn.y + dn.h;
        }
      });
      setHoveredNode(hit ?? null);
    },
    [layout],
  );

  // ── 렌더 ──────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex h-full items-center justify-center bg-slate-900 text-slate-400 text-sm">
        플로우 로딩 중…
      </div>
    );
  }
  if (error) {
    return (
      <div className="flex h-full items-center justify-center bg-slate-900 text-red-400 text-sm">
        오류: {error}
      </div>
    );
  }
  if (!filteredData || filteredData.nodes.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-slate-900 text-slate-500 text-sm gap-1">
        <span className="text-2xl opacity-40">⬡</span>
        <p>플로우 데이터 없음</p>
        {!staticFlow && (
          <p className="text-xs text-slate-600">툴을 사용하면 데이터 흐름이 표시됩니다</p>
        )}
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative h-full w-full bg-slate-900">
      {/* 툴바 */}
      <div className="absolute left-2 top-2 z-10 flex items-center gap-2">
        {!staticFlow && (
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchFlow}
            className="h-7 w-7 bg-slate-800 p-0 text-slate-300 hover:bg-slate-700"
            title="새로고침"
          >
            <RefreshCw size={12} />
          </Button>
        )}
        {staticFlow && (
          <span className="text-[10px] text-slate-500 bg-slate-800 px-2 py-0.5 rounded">
            스냅샷
          </span>
        )}
      </div>

      <canvas
        ref={canvasRef}
        className="h-full w-full"
        style={{ paddingTop: 36 }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredNode(null)}
      />

      {/* 툴팁 */}
      {hoveredNode && (
        <div
          className="pointer-events-none absolute z-20 rounded bg-slate-800 border border-slate-600 px-3 py-2 text-xs text-white shadow-lg max-w-[200px]"
          style={{ left: hoveredNode.x + (hoveredNode.kind === "tool" ? hoveredNode.w : ART_R) + 10, top: hoveredNode.y }}
        >
          {hoveredNode.kind === "tool" ? (
            <>
              <div className="text-[10px] text-indigo-400 font-medium mb-1">Tool</div>
              {(() => {
                const e = hoveredNode.data as FlowEdge;
                return (
                  <>
                    {e.agent_name && <div className="text-purple-400">Agent: {e.agent_name}</div>}
                    <div className="text-slate-300">Fn: {e.tool_name}</div>
                    {filteredData && (() => {
                      const tgt = filteredData.nodes.find((n) => n.id === e.target);
                      return tgt ? <div className="text-green-400 mt-1">→ {tgt.artifact_name || tgt.label}</div> : null;
                    })()}
                  </>
                );
              })()}
            </>
          ) : (
            <>
              <div className="text-[10px] text-green-400 font-medium mb-1">Artifact</div>
              {(() => {
                const n = hoveredNode.data as FlowNode;
                return <div className="text-slate-300">{n.artifact_name || n.label}</div>;
              })()}
              {filteredData && (() => {
                const ce = filteredData.edges.find((e) => e.target === hoveredNode.id);
                return ce ? (
                  <div className="text-purple-400 mt-1">← {ce.agent_name ? `${ce.agent_name}:` : ""}{ce.tool_name}</div>
                ) : null;
              })()}
            </>
          )}
        </div>
      )}

      {/* 범례 */}
      <div className="absolute bottom-2 right-2 flex gap-3 rounded bg-slate-800/80 px-2 py-1 text-[10px] text-slate-400">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-full bg-[#14532d] border border-[#22c55e]" />
          (아티팩트)
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-2.5 rounded-sm bg-[#1e1b4b] border border-[#4338ca]" />
          [agent:tool]
        </span>
      </div>
    </div>
  );
}
