"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { Save, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8080";

// Types for flow data
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
  tool_args?: Record<string, any>;
  label?: string;
}

interface FlowData {
  session_id: string;
  nodes: FlowNode[];
  edges: FlowEdge[];
}

// Layout calculation - simple left-to-right flow
interface LayoutNode extends FlowNode {
  x: number;
  y: number;
  width: number;
  height: number;
  isWidget: boolean; // true = 원형(위젯), false = 상자(아티팩트)
}

function calculateLayout(
  nodes: FlowNode[],
  edges: FlowEdge[],
  containerWidth: number,
): LayoutNode[] {
  if (nodes.length === 0) return [];

  const nodeWidth = 120;
  const nodeHeight = 50;
  const horizontalGap = 80;
  const verticalGap = 30;

  // Build adjacency list
  const outgoing = new Map<string, string[]>();
  const incoming = new Map<string, string[]>();

  edges.forEach((edge) => {
    if (!outgoing.has(edge.source)) outgoing.set(edge.source, []);
    outgoing.get(edge.source)!.push(edge.target);

    if (!incoming.has(edge.target)) incoming.set(edge.target, []);
    incoming.get(edge.target)!.push(edge.source);
  });

  // Find root nodes (no incoming edges)
  const roots = nodes.filter(
    (n) => !incoming.has(n.id) || incoming.get(n.id)!.length === 0,
  );

  // BFS to assign levels
  const levels = new Map<string, number>();
  const queue = [...roots.map((r) => ({ id: r.id, level: 0 }))];
  const visited = new Set<string>();

  while (queue.length > 0) {
    const { id, level } = queue.shift()!;
    if (visited.has(id)) continue;
    visited.add(id);
    levels.set(id, Math.max(levels.get(id) || 0, level));

    const children = outgoing.get(id) || [];
    children.forEach((childId) => {
      if (!visited.has(childId)) {
        queue.push({ id: childId, level: level + 1 });
      }
    });
  }

  // Handle disconnected nodes
  nodes.forEach((n) => {
    if (!levels.has(n.id)) {
      levels.set(n.id, 0);
    }
  });

  // Group by level
  const levelGroups = new Map<number, FlowNode[]>();
  nodes.forEach((n) => {
    const level = levels.get(n.id) || 0;
    if (!levelGroups.has(level)) levelGroups.set(level, []);
    levelGroups.get(level)!.push(n);
  });

  // Calculate positions
  const layoutNodes: LayoutNode[] = [];

  levelGroups.forEach((group, level) => {
    let startY = 60;

    group.forEach((node, idx) => {
      // 위젯 vs 아티팩트 구분
      // 아티팩트: input 타입이거나 .csv/.json 파일명
      const isArtifact =
        node.node_type === "input" ||
        /\.(csv|json|xlsx|parquet)$/i.test(node.file_name || "") ||
        /\.(csv|json|xlsx|parquet)$/i.test(node.artifact_name || "");

      layoutNodes.push({
        ...node,
        x: 40 + level * (nodeWidth + horizontalGap),
        y: startY + idx * (nodeHeight + verticalGap),
        width: nodeWidth,
        height: nodeHeight,
        isWidget: !isArtifact,
      });
    });
  });

  return layoutNodes;
}

interface FlowGraphWidgetProps {
  sessionId: string;
  checkedWidgets?: string[]; // 체크된 위젯 title 목록
}

export default function FlowGraphWidget({
  sessionId,
  checkedWidgets = [],
}: FlowGraphWidgetProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [flowData, setFlowData] = useState<FlowData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<LayoutNode | null>(null);
  const [layoutNodes, setLayoutNodes] = useState<LayoutNode[]>([]);
  const [saving, setSaving] = useState(false);

  // Fetch flow data
  const fetchFlow = useCallback(async () => {
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
  }, [sessionId]);

  useEffect(() => {
    fetchFlow();
    // Poll every 5 seconds for updates
    const interval = setInterval(fetchFlow, 5000);
    return () => clearInterval(interval);
  }, [fetchFlow]);

  // Filter nodes/edges based on checked widgets
  const filteredData = React.useMemo(() => {
    if (!flowData) return null;

    // 체크된 위젯이 없으면 전체 표시
    if (checkedWidgets.length === 0) {
      return flowData;
    }

    // 체크된 위젯과 관련된 노드만 필터링
    const relevantEdgeIds = new Set<string>();
    const relevantNodeIds = new Set<string>();

    flowData.edges.forEach((edge) => {
      // 엣지의 label이 체크된 위젯과 일치하면 포함
      if (edge.label && checkedWidgets.some((w) => edge.label?.includes(w))) {
        relevantEdgeIds.add(edge.id);
        relevantNodeIds.add(edge.source);
        relevantNodeIds.add(edge.target);
      }
    });

    // 노드의 label이 체크된 위젯과 일치하면 포함
    flowData.nodes.forEach((node) => {
      if (checkedWidgets.some((w) => node.label.includes(w))) {
        relevantNodeIds.add(node.id);
      }
    });

    // 관련 노드에 연결된 엣지도 포함
    flowData.edges.forEach((edge) => {
      if (relevantNodeIds.has(edge.source) || relevantNodeIds.has(edge.target)) {
        relevantEdgeIds.add(edge.id);
        relevantNodeIds.add(edge.source);
        relevantNodeIds.add(edge.target);
      }
    });

    const filteredNodes = flowData.nodes.filter((n) => relevantNodeIds.has(n.id));
    const filteredEdges = flowData.edges.filter((e) => relevantEdgeIds.has(e.id));

    return {
      ...flowData,
      nodes: filteredNodes.length > 0 ? filteredNodes : flowData.nodes,
      edges: filteredEdges.length > 0 ? filteredEdges : flowData.edges,
    };
  }, [flowData, checkedWidgets]);

  // Calculate layout when flow data changes
  useEffect(() => {
    if (!filteredData || !containerRef.current) return;
    const width = containerRef.current.clientWidth;
    const nodes = calculateLayout(filteredData.nodes, filteredData.edges, width);
    setLayoutNodes(nodes);
  }, [filteredData]);

  // Draw the graph
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

    // Clear
    ctx.fillStyle = "#1a1a2e";
    ctx.fillRect(0, 0, rect.width, rect.height);

    // Draw edges first
    filteredData.edges.forEach((edge) => {
      const sourceNode = layoutNodes.find((n) => n.id === edge.source);
      const targetNode = layoutNodes.find((n) => n.id === edge.target);

      if (sourceNode && targetNode) {
        const startX = sourceNode.x + sourceNode.width;
        const startY = sourceNode.y + sourceNode.height / 2;
        const endX = targetNode.x;
        const endY = targetNode.y + targetNode.height / 2;

        // Draw bezier curve
        ctx.beginPath();
        ctx.strokeStyle = "#4a90d9";
        ctx.lineWidth = 2;

        const cpX = (startX + endX) / 2;
        ctx.moveTo(startX, startY);
        ctx.bezierCurveTo(cpX, startY, cpX, endY, endX, endY);
        ctx.stroke();

        // Draw arrow
        const arrowSize = 8;
        const angle = Math.atan2(endY - startY, endX - cpX);
        ctx.beginPath();
        ctx.fillStyle = "#4a90d9";
        ctx.moveTo(endX, endY);
        ctx.lineTo(
          endX - arrowSize * Math.cos(angle - Math.PI / 6),
          endY - arrowSize * Math.sin(angle - Math.PI / 6),
        );
        ctx.lineTo(
          endX - arrowSize * Math.cos(angle + Math.PI / 6),
          endY - arrowSize * Math.sin(angle + Math.PI / 6),
        );
        ctx.closePath();
        ctx.fill();

        // Draw edge label (tool name)
        if (edge.label) {
          const labelX = (startX + endX) / 2;
          const labelY = (startY + endY) / 2 - 8;

          ctx.font = "11px system-ui";
          ctx.fillStyle = "#8b9dc3";
          ctx.textAlign = "center";
          ctx.fillText(edge.label, labelX, labelY);
        }
      }
    });

    // Draw nodes
    layoutNodes.forEach((node) => {
      const isHovered = hoveredNode?.id === node.id;
      const centerX = node.x + node.width / 2;
      const centerY = node.y + node.height / 2;

      if (node.isWidget) {
        // 위젯: 원형으로 그리기
        const radius = Math.min(node.width, node.height) / 2 - 5;

        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);

        // 색상: output(초록), intermediate(보라)
        if (node.node_type === "output") {
          ctx.fillStyle = isHovered ? "#5a8d6e" : "#3d6b52";
        } else {
          ctx.fillStyle = isHovered ? "#6b5a8d" : "#4a3d6b";
        }
        ctx.fill();

        // Border
        ctx.strokeStyle = isHovered ? "#ffffff" : "#4a90d9";
        ctx.lineWidth = isHovered ? 2 : 1;
        ctx.stroke();
      } else {
        // 아티팩트: 상자로 그리기
        ctx.beginPath();
        ctx.roundRect(node.x, node.y, node.width, node.height, 8);

        // 색상: input(파랑)
        ctx.fillStyle = isHovered ? "#3d5a80" : "#2b4162";
        ctx.fill();

        // Border
        ctx.strokeStyle = isHovered ? "#ffffff" : "#4a90d9";
        ctx.lineWidth = isHovered ? 2 : 1;
        ctx.stroke();
      }

      // Node label
      ctx.font = "12px system-ui";
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      // Truncate long labels
      let label = node.label;
      if (label.length > 14) {
        label = label.substring(0, 12) + "...";
      }
      ctx.fillText(label, centerX, centerY);
    });
  }, [filteredData, layoutNodes, hoveredNode]);

  // Mouse interaction
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const hovered = layoutNodes.find((n) => {
        if (n.isWidget) {
          // 원형 히트 테스트
          const centerX = n.x + n.width / 2;
          const centerY = n.y + n.height / 2;
          const radius = Math.min(n.width, n.height) / 2 - 5;
          const dist = Math.sqrt((x - centerX) ** 2 + (y - centerY) ** 2);
          return dist <= radius;
        } else {
          // 사각형 히트 테스트
          return x >= n.x && x <= n.x + n.width && y >= n.y && y <= n.y + n.height;
        }
      });

      setHoveredNode(hovered || null);
    },
    [layoutNodes],
  );

  // Save to notebook
  const handleSave = useCallback(async () => {
    if (!filteredData) return;

    setSaving(true);
    try {
      // 노트북에 저장 이벤트 발생
      window.dispatchEvent(
        new CustomEvent("notebook:add", {
          detail: {
            type: "flow",
            sessionId,
            data: filteredData,
            title: `Flow Graph - ${new Date().toLocaleString()}`,
          },
        }),
      );
    } catch (err) {
      console.error("Failed to save to notebook:", err);
    } finally {
      setSaving(false);
    }
  }, [filteredData, sessionId]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center bg-slate-900 text-slate-400">
        Loading flow...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center bg-slate-900 text-red-400">
        Error: {error}
      </div>
    );
  }

  if (!filteredData || filteredData.nodes.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-slate-900 text-slate-400">
        <svg
          className="mb-2 h-12 w-12 opacity-50"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M13 10V3L4 14h7v7l9-11h-7z"
          />
        </svg>
        <p>No artifact flow yet</p>
        <p className="mt-1 text-xs text-slate-500">
          Use tools to see the data flow graph
        </p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative h-full w-full bg-slate-900">
      {/* Top toolbar */}
      <div className="absolute left-2 right-2 top-2 z-10 flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={handleSave}
          disabled={saving}
          className="h-8 gap-1.5 bg-slate-700 text-slate-200 hover:bg-slate-600"
        >
          <Save size={14} />
          {saving ? "저장 중..." : "노트북에 저장"}
        </Button>

        <Button
          variant="secondary"
          size="sm"
          onClick={fetchFlow}
          className="h-8 w-8 bg-slate-700 p-0 text-slate-200 hover:bg-slate-600"
          title="새로고침"
        >
          <RefreshCw size={14} />
        </Button>

        {checkedWidgets.length > 0 && (
          <span className="ml-auto text-xs text-slate-400">
            {checkedWidgets.length}개 위젯 선택됨
          </span>
        )}
      </div>

      <canvas
        ref={canvasRef}
        className="h-full w-full"
        style={{ paddingTop: 40 }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredNode(null)}
      />

      {/* Tooltip */}
      {hoveredNode && (
        <div
          className="pointer-events-none absolute z-10 max-w-xs rounded bg-slate-800 px-3 py-2 text-sm text-white shadow-lg"
          style={{
            left: hoveredNode.x + hoveredNode.width + 10,
            top: hoveredNode.y + 40,
          }}
        >
          <div className="font-medium">{hoveredNode.label}</div>
          {hoveredNode.artifact_name && (
            <div className="text-xs text-slate-400">
              Artifact: {hoveredNode.artifact_name}
            </div>
          )}
          {hoveredNode.file_name && (
            <div className="text-xs text-slate-400">
              File: {hoveredNode.file_name}
            </div>
          )}
          <div className="mt-1 text-xs text-slate-500">
            {hoveredNode.isWidget ? "위젯 (결과)" : "아티팩트 (데이터)"}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-2 left-2 flex gap-3 rounded bg-slate-800/80 px-2 py-1 text-xs text-slate-300">
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded bg-[#2b4162]" />
          <span>아티팩트</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded-full bg-[#3d6b52]" />
          <span>위젯(결과)</span>
        </div>
      </div>
    </div>
  );
}
