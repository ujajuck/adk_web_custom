export type Msg = { role: "user" | "assistant"; text: string; windowId?: string };

export type AdkEvent = {
  content?: {
    role?: string;
    parts?: Array<{ text?: string; thought?: boolean }>;
  };
  partial?: boolean;
  finishReason?: string;
  actions?: any;
};

export type PlotlyFig = { data: any[]; layout?: any; config?: any; frames?: any[] };
