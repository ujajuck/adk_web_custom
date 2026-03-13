"use client";

import React from "react";
import { RefreshCw, Workflow, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";

function TopIconButton(props: {
  label: string;
  onClick: () => void;
  icon: React.ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          onClick={props.onClick}
          aria-label={props.label}
          className="gap-2 font-bold text-[13px]"
        >
          {props.icon}
          {props.label}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{props.label}</TooltipContent>
    </Tooltip>
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
      className="sticky top-0 z-[9999] flex items-center gap-2.5 px-3 border-b bg-muted/90 backdrop-blur-sm"
      style={{ height: h }}
    >
      <TopIconButton
        label="refresh"
        onClick={props.onRefresh}
        icon={<RefreshCw size={16} />}
      />

      <div className="flex-1" />

      <TopIconButton
        label="저장"
        onClick={props.onSave}
        icon={<Save size={16} />}
      />

      <TopIconButton
        label="flow"
        onClick={props.onFlow}
        icon={<Workflow size={16} />}
      />
    </div>
  );
}
