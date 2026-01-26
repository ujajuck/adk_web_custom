declare module "react-plotly.js" {
  import * as React from "react";

  interface PlotParams {
    data: any[];
    layout?: any;
    frames?: any[];
    config?: any;
    style?: React.CSSProperties;
    className?: string;
    useResizeHandler?: boolean;
    onInitialized?: (...args: any[]) => void;
    onUpdate?: (...args: any[]) => void;
    onPurge?: (...args: any[]) => void;
    onError?: (...args: any[]) => void;
  }

  const Plot: React.ComponentType<PlotParams>;
  export default Plot;
}