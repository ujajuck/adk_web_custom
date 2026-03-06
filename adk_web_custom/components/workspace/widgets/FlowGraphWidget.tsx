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

// Layout node with position and type info
interface LayoutNode {
  id: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  isTool: boolean; // true = 사각형(tool), false = 원형(artifact)
  originalNode?: FlowNode;
  originalEdge?: FlowEdge;
}

interface LayoutEdge {
  source: string;
  target: string;
}

function calculateLayout(
  nodes: FlowNode[],
  edges: FlowEdge[],
  containerWidth: number,
): { layoutNodes: LayoutNode[]; layoutEdges: LayoutEdge[] } {
  if (nodes.length === 0) return { layoutNodes: [], layoutEdges: [] };

  const nodeWidth = 100;
  const nodeHeight = 40;
  const horizontalGap = 60;
  const verticalGap = 25;

  // 1. 노드별 incoming/outgoing 엣지 계산
  const nodeOutEdges = new Map<string, FlowEdge[]>();
  const nodeInEdges = new Map<string, FlowEdge[]>();

  edges.forEach((edge) => {
    if (!nodeOutEdges.has(edge.source)) nodeOutEdges.set(edge.source, []);
    nodeOutEdges.get(edge.source)!.push(edge);

    if (!nodeInEdges.has(edge.target)) nodeInEdges.set(edge.target, []);
    nodeInEdges.get(edge.target)!.push(edge);
  });

  // 2. 레벨 계산 (artifact -> tool -> artifact -> tool -> ...)
  // 각 엣지(tool)를 노드로 변환하여 배치
  const layoutNodes: LayoutNode[] = [];
  const layoutEdges: LayoutEdge[] = [];

  // 루트 노드 찾기 (incoming 엣지 없는 노드)
  const roots = nodes.filter(
    (n) => !nodeInEdges.has(n.id) || nodeInEdges.get(n.id)!.length === 0,
  );

  // BFS로 레벨 할당
  const nodeLevels = new Map<string, number>();
  const queue = [...roots.map((r) => ({ id: r.id, level: 0 }))];
  const visited = new Set<string>();

  while (queue.length > 0) {
    const { id, level } = queue.shift()!;
    if (visited.has(id)) continue;
    visited.add(id);
    nodeLevels.set(id, level);

    const outEdges = nodeOutEdges.get(id) || [];
    outEdges.forEach((edge) => {
      if (!visited.has(edge.target)) {
        queue.push({ id: edge.target, level: level + 2 }); // +2 to leave room for tool node
      }
    });
  }

  // 미방문 노드 처리
  nodes.forEach((n) => {
    if (!nodeLevels.has(n.id)) {
      nodeLevels.set(n.id, 0);
    }
  });

  // 3. 레이아웃 생성: artifact 노드 (원형)
  const levelCounts = new Map<number, number>();
  nodes.forEach((node) => {
    const level = nodeLevels.get(node.id) || 0;
    const idx = levelCounts.get(level) || 0;
    levelCounts.set(level, idx + 1);

    layoutNodes.push({
      id: node.id,
      label: node.label,
      x: 40 + level * (nodeWidth + horizontalGap),
      y: 60 + idx * (nodeHeight + verticalGap),
      width: nodeWidth,
      height: nodeHeight,
      isTool: false,
      originalNode: node,
    });
  });

  // 4. 엣지를 tool 노드(사각형)로 변환하고 연결
  edges.forEach((edge) => {
    const sourceLevel = nodeLevels.get(edge.source) || 0;
    const toolLevel = sourceLevel + 1;

    const idx = levelCounts.get(toolLevel) || 0;
    levelCounts.set(toolLevel, idx + 1);

    const toolNodeId = `tool_${edge.id}`;
    const toolLabel = edge.label || edge.tool_name || "tool";

    layoutNodes.push({
      id: toolNodeId,
      label: toolLabel.length > 12 ? toolLabel.slice(0, 10) + ".." : toolLabel,
      x: 40 + toolLevel * (nodeWidth + horizontalGap),
      y: 60 + idx * (nodeHeight + verticalGap),
      width: nodeWidth,
      height: nodeHeight,
      isTool: true,
      originalEdge: edge,
    });

    // source -> tool, tool -> target
    layoutEdges.push({ source: edge.source, target: toolNodeId });
    layoutEdges.push({ source: toolNodeId, target: edge.target });
  });

  return { layoutNodes, layoutEdges };
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
  const [layoutEdges, setLayoutEdges] = useState<LayoutEdge[]>([]);
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
      if (node.label && checkedWidgets.some((w) => node.label?.includes(w))) {
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
    const { layoutNodes: nodes, layoutEdges: edges } = calculateLayout(
      filteredData.nodes,
      filteredData.edges,
      width,
    );
    setLayoutNodes(nodes);
    setLayoutEdges(edges);
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

    // Draw edges
    layoutEdges.forEach((edge) => {
      const sourceNode = layoutNodes.find((n) => n.id === edge.source);
      const targetNode = layoutNodes.find((n) => n.id === edge.target);

      if (sourceNode && targetNode) {
        const startX = sourceNode.x + sourceNode.width;
        const startY = sourceNode.y + sourceNode.height / 2;
        const endX = targetNode.x;
        const endY = targetNode.y + targetNode.height / 2;

        ctx.beginPath();
        ctx.strokeStyle = "#4a90d9";
        ctx.lineWidth = 2;

        const cpX = (startX + endX) / 2;
        ctx.moveTo(startX, startY);
        ctx.bezierCurveTo(cpX, startY, cpX, endY, endX, endY);
        ctx.stroke();

        // Arrow
        const arrowSize = 6;
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
      }
    });

    // Draw nodes
    layoutNodes.forEach((node) => {
      const isHovered = hoveredNode?.id === node.id;
      const centerX = node.x + node.width / 2;
      const centerY = node.y + node.height / 2;

      if (node.isTool) {
        // Tool: 사각형
        ctx.beginPath();
        ctx.roundRect(node.x, node.y, node.width, node.height, 6);
        ctx.fillStyle = isHovered ? "#6b5a8d" : "#4a3d6b";
        ctx.fill();
        ctx.strokeStyle = isHovered ? "#ffffff" : "#9b8dc3";
        ctx.lineWidth = isHovered ? 2 : 1;
        ctx.stroke();
      } else {
        // Artifact: 원형
        const radius = Math.min(node.width, node.height) / 2 - 4;
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.fillStyle = isHovered ? "#3d6b52" : "#2b5a42";
        ctx.fill();
        ctx.strokeStyle = isHovered ? "#ffffff" : "#5a9d7e";
        ctx.lineWidth = isHovered ? 2 : 1;
        ctx.stroke();
      }

      // Label
      ctx.font = "11px system-ui";
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(node.label, centerX, centerY);
    });
  }, [filteredData, layoutNodes, layoutEdges, hoveredNode]);

  // Mouse interaction
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const hovered = layoutNodes.find((n) => {
        if (n.isTool) {
          // 사각형 히트 테스트 (tool)
          return x >= n.x && x <= n.x + n.width && y >= n.y && y <= n.y + n.height;
        } else {
          // 원형 히트 테스트 (artifact)
          const centerX = n.x + n.width / 2;
          const centerY = n.y + n.height / 2;
          const radius = Math.min(n.width, n.height) / 2 - 4;
          const dist = Math.sqrt((x - centerX) ** 2 + (y - centerY) ** 2);
          return dist <= radius;
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
          {hoveredNode.originalNode?.artifact_name && (
            <div className="text-xs text-slate-400">
              {hoveredNode.originalNode.artifact_name}
            </div>
          )}
          {hoveredNode.originalEdge?.tool_name && (
            <div className="text-xs text-slate-400">
              {hoveredNode.originalEdge.tool_name}
            </div>
          )}
          <div className="mt-1 text-xs text-slate-500">
            {hoveredNode.isTool ? "Tool" : "Artifact"}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-2 left-2 flex gap-3 rounded bg-slate-800/80 px-2 py-1 text-xs text-slate-300">
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded bg-[#4a3d6b]" />
          <span>Tool</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded-full bg-[#2b5a42]" />
          <span>Artifact</span>
        </div>
      </div>
    </div>
  );
}
