"use client";

import React from "react";
import Plot from "react-plotly.js";

export default function PlotlyFigureWidget({
  fig,
}: {
  fig: { data: any[]; layout?: any; config?: any };
}) {
  return (
    <div className="p-2 h-full">
      <Plot
        data={fig.data}
        layout={{
          margin: { l: 40, r: 20, t: 30, b: 40 },
          autosize: true,
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { family: "inherit" },
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
