"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";

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
  const maxLevel = Math.max(...Array.from(levels.values()), 0);

  levelGroups.forEach((group, level) => {
    const totalHeight = group.length * nodeHeight + (group.length - 1) * verticalGap;
    let startY = 60;

    group.forEach((node, idx) => {
      layoutNodes.push({
        ...node,
        x: 40 + level * (nodeWidth + horizontalGap),
        y: startY + idx * (nodeHeight + verticalGap),
        width: nodeWidth,
        height: nodeHeight,
      });
    });
  });

  return layoutNodes;
}

interface FlowGraphWidgetProps {
  sessionId: string;
  backendUrl?: string;
}

export default function FlowGraphWidget({
  sessionId,
  backendUrl = "http://localhost:8080",
}: FlowGraphWidgetProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [flowData, setFlowData] = useState<FlowData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<LayoutNode | null>(null);
  const [layoutNodes, setLayoutNodes] = useState<LayoutNode[]>([]);

  // Fetch flow data
  const fetchFlow = useCallback(async () => {
    try {
      const res = await fetch(`${backendUrl}/api/flow/${sessionId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setFlowData(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch flow");
    } finally {
      setLoading(false);
    }
  }, [sessionId, backendUrl]);

  useEffect(() => {
    fetchFlow();
    // Poll every 5 seconds for updates
    const interval = setInterval(fetchFlow, 5000);
    return () => clearInterval(interval);
  }, [fetchFlow]);

  // Calculate layout when flow data changes
  useEffect(() => {
    if (!flowData || !containerRef.current) return;
    const width = containerRef.current.clientWidth;
    const nodes = calculateLayout(flowData.nodes, flowData.edges, width);
    setLayoutNodes(nodes);
  }, [flowData]);

  // Draw the graph
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !flowData) return;

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
    flowData.edges.forEach((edge) => {
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

      // Node background
      ctx.beginPath();
      ctx.roundRect(node.x, node.y, node.width, node.height, 8);

      // Color based on type
      if (node.node_type === "input") {
        ctx.fillStyle = isHovered ? "#3d5a80" : "#2b4162";
      } else if (node.node_type === "output") {
        ctx.fillStyle = isHovered ? "#5a8d6e" : "#3d6b52";
      } else {
        ctx.fillStyle = isHovered ? "#6b5a8d" : "#4a3d6b";
      }
      ctx.fill();

      // Border
      ctx.strokeStyle = isHovered ? "#ffffff" : "#4a90d9";
      ctx.lineWidth = isHovered ? 2 : 1;
      ctx.stroke();

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
      ctx.fillText(label, node.x + node.width / 2, node.y + node.height / 2);

      // Node type indicator
      const typeLabel =
        node.node_type === "input"
          ? "IN"
          : node.node_type === "output"
            ? "OUT"
            : "MID";
      ctx.font = "9px system-ui";
      ctx.fillStyle = "#8b9dc3";
      ctx.fillText(typeLabel, node.x + node.width / 2, node.y + node.height - 8);
    });
  }, [flowData, layoutNodes, hoveredNode]);

  // Mouse interaction
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const hovered = layoutNodes.find(
        (n) => x >= n.x && x <= n.x + n.width && y >= n.y && y <= n.y + n.height,
      );

      setHoveredNode(hovered || null);
    },
    [layoutNodes],
  );

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

  if (!flowData || flowData.nodes.length === 0) {
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
      <canvas
        ref={canvasRef}
        className="h-full w-full"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredNode(null)}
      />

      {/* Tooltip */}
      {hoveredNode && (
        <div
          className="pointer-events-none absolute z-10 max-w-xs rounded bg-slate-800 px-3 py-2 text-sm text-white shadow-lg"
          style={{
            left: hoveredNode.x + hoveredNode.width + 10,
            top: hoveredNode.y,
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
            Type:{" "}
            {hoveredNode.node_type === "input"
              ? "Input Data"
              : hoveredNode.node_type === "output"
                ? "Output Result"
                : "Intermediate"}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-2 left-2 flex gap-3 rounded bg-slate-800/80 px-2 py-1 text-xs text-slate-300">
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded bg-[#2b4162]" />
          <span>Input</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded bg-[#3d6b52]" />
          <span>Output</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="h-3 w-3 rounded bg-[#4a3d6b]" />
          <span>Intermediate</span>
        </div>
      </div>

      {/* Refresh button */}
      <button
        onClick={fetchFlow}
        className="absolute right-2 top-2 rounded bg-slate-700 p-1.5 text-slate-300 hover:bg-slate-600"
        title="Refresh"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
          />
        </svg>
      </button>
    </div>
  );
}
