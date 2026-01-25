// components/workspace/widgets/PlotlyFigureWidget.tsx
"use client";

import React from "react";
import Plot from "react-plotly.js";

export default function PlotlyFigureWidget({
  fig,
}: {
  fig: { data: any[]; layout?: any; config?: any };
}) {
  return (
    <div style={{ padding: 8, height: "100%" }}>
      <Plot
        data={fig.data}
        layout={{
          margin: { l: 40, r: 20, t: 30, b: 40 },
          autosize: true,
          ...fig.layout,
        }}
        config={{
          responsive: true,
          displaylogo: false,
          ...fig.config,
        }}
        style={{ width: "100%", height: "100%" }}
        useResizeHandler
      />
    </div>
  );
}
