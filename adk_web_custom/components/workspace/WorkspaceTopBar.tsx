"use client";

import React from "react";
import { RefreshCw, Workflow, Save } from "lucide-react";

function TopIconButton(props: {
  label: string;
  onClick: () => void;
  icon: React.ReactNode;
}) {
  return (
    <button
      onClick={props.onClick}
      title={props.label}
      aria-label={props.label}
      style={{
        height: 34,
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "0 12px",
        borderRadius: 12,
        border: "1px solid #e5e7eb",
        background: "white",
        cursor: "pointer",
        fontWeight: 700,
        fontSize: 13,
        color: "#111827",
      }}
    >
      {props.icon}
      {props.label}
    </button>
  );
}

export default function WorkspaceTopBar(props: {
  height?: number;
  onRefresh: () => void;
  onFlow: () => void;
  onSave: () => void;
}) {
  const h = props.height ?? 48;

  return (
    <div
      style={{
        position: "sticky",
        top: 0,
        height: h,
        zIndex: 9999, 
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "0 12px",
        borderBottom: "1px solid #e5e7eb",
        background: "rgba(250,250,250,0.92)",
        backdropFilter: "blur(6px)",
      }}
    >
      <TopIconButton
        label="refresh"
        onClick={props.onRefresh}
        icon={<RefreshCw size={16} />}
      />

      <div style={{ flex: 1 }} />

      <TopIconButton
        label="flow"
        onClick={props.onFlow}
        icon={<Workflow size={16} />}
      />
      <TopIconButton
        label="save"
        onClick={props.onSave}
        icon={<Save size={16} />}
      />
    </div>
  );
}
