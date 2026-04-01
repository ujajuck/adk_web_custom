"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { RefreshCw, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getArtifactLabel } from "@/lib/artifactLabels";

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

const ART_R = 32;   // artifact 원 반지름 (slightly larger for readability)
const TOOL_W = 140; // tool 사각형 너비
const TOOL_H = 44;  // tool 사각형 높이
const COL_GAP = 90; // 컬럼 사이 간격
const ROW_GAP = 40; // 같은 컬럼 내 행 간격
const PAD_X = 60;
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

  const artColW = ART_R * 2;
  const toolColW = TOOL_W;
  const colW = artColW + COL_GAP + toolColW + COL_GAP;

  const levelRows = new Map<number, number>();
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

  const toolRowCount = new Map<number, number>();
  const toolNodeMap = new Map<string, DrawNode>();

  for (const e of data.edges) {
    const src = artNodeMap.get(e.source);
    if (!src) continue;

    const level = artLevel.get(e.source) ?? 0;
    const tIdx = toolRowCount.get(level) ?? 0;
    toolRowCount.set(level, tIdx + 1);

    const tx = src.x + ART_R + COL_GAP;
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

/** Compute bounding box of all draw nodes */
function getBounds(nodes: DrawNode[]): { minX: number; minY: number; maxX: number; maxY: number } {
  if (!nodes.length) return { minX: 0, minY: 0, maxX: 400, maxY: 300 };
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const n of nodes) {
    const left = n.kind === "artifact" ? n.x - ART_R : n.x;
    const right = n.kind === "artifact" ? n.x + ART_R : n.x + n.w;
    const top = n.kind === "artifact" ? n.y - ART_R : n.y;
    const bottom = n.kind === "artifact" ? n.y + ART_R : n.y + n.h;
    if (left < minX) minX = left;
    if (right > maxX) maxX = right;
    if (top < minY) minY = top;
    if (bottom > maxY) maxY = bottom;
  }
  return { minX, minY, maxX, maxY };
}

// ── 컴포넌트 ──────────────────────────────────────────────────────
interface WindowInfo {
  id: string;
  widget: { type: string; title: string; [key: string]: any };
  [key: string]: any;
}

interface FlowGraphWidgetProps {
  sessionId: string;
  staticFlow?: FlowData;
  checkedWidgets?: string[];
  allWindows?: WindowInfo[];
}

interface Transform {
  tx: number;
  ty: number;
  scale: number;
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
  const [clickedNode, setClickedNode] = useState<DrawNode | null>(null);
  const [layout, setLayout] = useState<{ nodes: DrawNode[]; edges: DrawEdge[] }>({
    nodes: [],
    edges: [],
  });

  // Transform state: tx/ty are canvas-space offsets, scale is zoom level
  const [transform, setTransform] = useState<Transform>({ tx: 0, ty: 0, scale: 1 });
  const transformRef = useRef<Transform>(transform);
  transformRef.current = transform;

  // Pan state
  const isPanning = useRef(false);
  const panMoved = useRef(false);
  const panStart = useRef({ x: 0, y: 0, tx: 0, ty: 0 });

  const fetchFlow = useCallback(async () => {
    if (staticFlow) return;
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
    const newLayout = buildLayout(filteredData);
    setLayout(newLayout);
    // Auto-fit on new layout
    autoFit(newLayout.nodes);
  }, [filteredData]); // eslint-disable-line react-hooks/exhaustive-deps

  const autoFit = useCallback((nodes: DrawNode[]) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    if (!nodes.length) return;

    const dpr = window.devicePixelRatio || 1;
    const vw = canvas.getBoundingClientRect().width;
    const vh = canvas.getBoundingClientRect().height - 36; // header offset

    const bounds = getBounds(nodes);
    const contentW = bounds.maxX - bounds.minX + PAD_X * 2;
    const contentH = bounds.maxY - bounds.minY + PAD_Y * 2;

    const scaleX = vw / contentW;
    const scaleY = vh / contentH;
    const scale = Math.min(scaleX, scaleY, 2); // cap at 2x

    // Center content
    const scaledW = contentW * scale;
    const scaledH = contentH * scale;
    const tx = (vw - scaledW) / 2 - (bounds.minX - PAD_X) * scale;
    const ty = (vh - scaledH) / 2 - (bounds.minY - PAD_Y) * scale + 36;

    setTransform({ tx, ty, scale });
  }, []);

  // ── 캔버스 렌더링 ────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !filteredData) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const isSelected = (dn: DrawNode) => clickedNode?.id === dn.id;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const { tx, ty, scale } = transform;

    // 배경
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, rect.width, rect.height);

    // Apply transform
    ctx.save();
    ctx.translate(tx, ty);
    ctx.scale(scale, scale);

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
      const ar = 7;
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
      const selected = isSelected(dn);

      ctx.save();
      if (dn.kind === "artifact") {
        // selected glow ring
        if (selected) {
          ctx.beginPath();
          ctx.arc(dn.x, dn.y, ART_R + 6, 0, Math.PI * 2);
          ctx.fillStyle = "rgba(74,222,128,0.15)";
          ctx.fill();
        }
        ctx.beginPath();
        ctx.arc(dn.x, dn.y, ART_R, 0, Math.PI * 2);
        ctx.fillStyle = selected ? "#15803d" : hovered ? "#166534" : "#14532d";
        ctx.fill();
        ctx.strokeStyle = selected ? "#86efac" : hovered ? "#4ade80" : "#22c55e";
        ctx.lineWidth = selected ? 3 : hovered ? 2.5 : 1.5;
        ctx.stroke();

        ctx.font = "bold 10px system-ui";
        ctx.fillStyle = selected ? "#ffffff" : "#bbf7d0";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        const maxW = ART_R * 2 - 8;
        const displayLabel = getArtifactLabel(dn.label);
        const words = displayLabel.split(/[._\-]/);
        if (words.length > 1 && ctx.measureText(displayLabel).width > maxW) {
          const mid = Math.ceil(words.length / 2);
          ctx.fillText(words.slice(0, mid).join("."), dn.x, dn.y - 7, maxW);
          ctx.fillText(words.slice(mid).join("."), dn.x, dn.y + 7, maxW);
        } else {
          ctx.fillText(displayLabel, dn.x, dn.y, maxW);
        }
      } else {
        ctx.beginPath();
        roundRect(dn.x, dn.y, dn.w, dn.h, 7);
        ctx.fillStyle = hovered ? "#312e81" : "#1e1b4b";
        ctx.fill();
        ctx.strokeStyle = hovered ? "#818cf8" : "#4338ca";
        ctx.lineWidth = hovered ? 2.5 : 1.5;
        ctx.stroke();

        const raw = dn.label;
        const colonIdx = raw.indexOf(":");
        if (colonIdx > -1) {
          const agent = raw.slice(0, colonIdx);
          const tool = raw.slice(colonIdx + 1);
          ctx.font = "bold 9px system-ui";
          ctx.fillStyle = "#a5b4fc";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(agent, dn.x + dn.w / 2, dn.y + dn.h / 2 - 8, dn.w - 10);
          ctx.font = "10px system-ui";
          ctx.fillStyle = "#e0e7ff";
          ctx.fillText(tool, dn.x + dn.w / 2, dn.y + dn.h / 2 + 8, dn.w - 10);
        } else {
          ctx.font = "bold 10px system-ui";
          ctx.fillStyle = "#e0e7ff";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(raw, dn.x + dn.w / 2, dn.y + dn.h / 2, dn.w - 10);
        }
      }
      ctx.restore();
    }

    ctx.restore(); // restore transform
  }, [filteredData, layout, hoveredNode, clickedNode, transform]);

  // Convert screen coords to world coords
  const screenToWorld = useCallback((sx: number, sy: number) => {
    const { tx, ty, scale } = transformRef.current;
    return { x: (sx - tx) / scale, y: (sy - ty) / scale };
  }, []);

  // 마우스 인터랙션 - hover
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const screenX = e.clientX - rect.left;
      const screenY = e.clientY - rect.top;

      // Handle pan
      if (isPanning.current) {
        const dx = screenX - panStart.current.x;
        const dy = screenY - panStart.current.y;
        if (Math.abs(dx) > 4 || Math.abs(dy) > 4) panMoved.current = true;
        setTransform(t => ({ ...t, tx: panStart.current.tx + dx, ty: panStart.current.ty + dy }));
        return;
      }

      const { x: mx, y: my } = screenToWorld(screenX, screenY);

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
    [layout, screenToWorld],
  );

  // Pan start
  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (e.button === 0) {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      isPanning.current = true;
      panMoved.current = false;
      panStart.current = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
        tx: transformRef.current.tx,
        ty: transformRef.current.ty,
      };
    }
  }, []);

  const handleMouseUp = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const wasPanning = isPanning.current;
    isPanning.current = false;

    // If mouse didn't move much → treat as click
    if (wasPanning && !panMoved.current) {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      const screenX = e.clientX - rect.left;
      const screenY = e.clientY - rect.top;
      const { tx, ty, scale } = transformRef.current;
      const mx = (screenX - tx) / scale;
      const my = (screenY - ty) / scale;

      const hit = layout.nodes.find((dn) => {
        if (dn.kind === "artifact") {
          const dx = mx - dn.x;
          const dy = my - dn.y;
          return dx * dx + dy * dy <= ART_R * ART_R;
        }
        return false; // only artifact nodes are clickable
      });
      setClickedNode((prev) => (prev?.id === hit?.id ? null : hit ?? null));
    }
  }, [layout]);

  // Wheel zoom
  const handleWheel = useCallback((e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const delta = e.deltaY > 0 ? 0.85 : 1.18;
    setTransform(t => {
      const newScale = Math.max(0.1, Math.min(5, t.scale * delta));
      // Zoom towards mouse position
      const newTx = mouseX - (mouseX - t.tx) * (newScale / t.scale);
      const newTy = mouseY - (mouseY - t.ty) * (newScale / t.scale);
      return { tx: newTx, ty: newTy, scale: newScale };
    });
  }, []);

  // Fit button
  const handleFit = useCallback(() => {
    autoFit(layout.nodes);
  }, [layout.nodes, autoFit]);

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

  // Tooltip: hover takes priority, then clicked (locked)
  const tooltipNode = hoveredNode ?? clickedNode;
  const tooltipScreenX = tooltipNode
    ? (() => {
        const { tx, ty, scale } = transform;
        const worldX = tooltipNode.kind === "artifact" ? tooltipNode.x + ART_R : tooltipNode.x + tooltipNode.w;
        const worldY = tooltipNode.kind === "artifact" ? tooltipNode.y : tooltipNode.y + tooltipNode.h / 2;
        return { x: worldX * scale + tx + 8, y: worldY * scale + ty - 20 };
      })()
    : null;

  return (
    <div ref={containerRef} className="relative h-full w-full bg-slate-900 overflow-hidden">
      {/* 툴바 */}
      <div className="absolute left-2 top-2 z-10 flex items-center gap-1">
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
        <Button
          variant="secondary"
          size="sm"
          onClick={handleFit}
          className="h-7 w-7 bg-slate-800 p-0 text-slate-300 hover:bg-slate-700"
          title="화면에 맞추기"
        >
          <Maximize2 size={12} />
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setTransform(t => ({ ...t, scale: Math.min(5, t.scale * 1.25) }))}
          className="h-7 w-7 bg-slate-800 p-0 text-slate-300 hover:bg-slate-700"
          title="확대"
        >
          <ZoomIn size={12} />
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setTransform(t => ({ ...t, scale: Math.max(0.1, t.scale * 0.8) }))}
          className="h-7 w-7 bg-slate-800 p-0 text-slate-300 hover:bg-slate-700"
          title="축소"
        >
          <ZoomOut size={12} />
        </Button>
        {staticFlow && (
          <span className="text-[10px] text-slate-500 bg-slate-800 px-2 py-0.5 rounded ml-1">
            스냅샷
          </span>
        )}
        <span className="text-[10px] text-slate-600 ml-1">
          {Math.round(transform.scale * 100)}%
        </span>
      </div>

      <canvas
        ref={canvasRef}
        className="h-full w-full"
        style={{ cursor: isPanning.current ? "grabbing" : "grab" }}
        onMouseMove={handleMouseMove}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => { setHoveredNode(null); isPanning.current = false; }}
        onWheel={handleWheel}
      />

      {/* 툴팁 */}
      {tooltipNode && tooltipScreenX && (
        <div
          className={`pointer-events-none absolute z-20 rounded px-3 py-2 text-xs text-white shadow-lg max-w-[220px] ${
            clickedNode?.id === tooltipNode.id && !hoveredNode
              ? "bg-slate-700 border border-green-500/60"
              : "bg-slate-800 border border-slate-600"
          }`}
          style={{ left: tooltipScreenX.x, top: tooltipScreenX.y }}
        >
          {tooltipNode.kind === "tool" ? (
            <>
              <div className="text-[10px] text-indigo-400 font-medium mb-1">Tool</div>
              {(() => {
                const e = tooltipNode.data as FlowEdge;
                return (
                  <>
                    {e.agent_name && <div className="text-purple-400">Agent: {e.agent_name}</div>}
                    <div className="text-slate-300">Fn: {e.tool_name}</div>
                    {filteredData && (() => {
                      const tgt = filteredData.nodes.find((n) => n.id === e.target);
                      return tgt ? <div className="text-green-400 mt-1">→ {getArtifactLabel(tgt.artifact_name || tgt.label)}</div> : null;
                    })()}
                  </>
                );
              })()}
            </>
          ) : (
            <>
              <div className="text-[10px] text-green-400 font-medium mb-1">
                Artifact {clickedNode?.id === tooltipNode.id ? "· 선택됨" : ""}
              </div>
              {(() => {
                const n = tooltipNode.data as FlowNode;
                const rawName = n.artifact_name || n.label;
                const koName = getArtifactLabel(rawName);
                return (
                  <>
                    <div className="text-slate-200 font-medium">{koName}</div>
                    {koName !== rawName && <div className="text-slate-500 text-[10px]">{rawName}</div>}
                  </>
                );
              })()}
              {filteredData && (() => {
                const ce = filteredData.edges.find((e) => e.target === tooltipNode.id);
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
