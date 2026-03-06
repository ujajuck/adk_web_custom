"use client";

import React, { useMemo } from "react";
import dynamic from "next/dynamic";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

function optimizeData(data: any[]): any[] {
  return data.map((trace) => {
    const optimized = { ...trace };

    // heatmap -> heatmapgl for large data
    if (trace.type === "heatmap" && trace.z) {
      const rows = trace.z.length;
      const cols = trace.z[0]?.length || 0;
      if (rows * cols > 10000) {
        optimized.type = "heatmapgl";
      }
    }

    // scatter -> scattergl for many points
    if (trace.type === "scatter" || !trace.type) {
      const len = trace.x?.length || trace.y?.length || 0;
      if (len > 5000) {
        optimized.type = "scattergl";
      }
    }

    return optimized;
  });
}

export default function PlotlyFigureWidget({
  fig,
}: {
  fig: { data: any[]; layout?: any; config?: any };
}) {
  const optimizedData = useMemo(() => optimizeData(fig.data || []), [fig.data]);

  return (
    <div className="p-2 h-full">
      <Plot
        data={optimizedData}
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
          plotGlPixelRatio: 1,
          ...fig.config,
        }}
        style={{ width: "100%", height: "100%" }}
        useResizeHandler
      />
    </div>
  );
}
