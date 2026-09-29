/**
 * AnalyticsChart.tsx
 *
 * Thin Plotly wrapper pre-configured with Memora's calm, low-sensory
 * design tokens (Master Specification Section 8: Visualization —
 * Plotly; Section 9: calm, minimal, low sensory overload).
 *
 * Design choices specific to this project:
 *  - No Plotly modebar (zoom/pan/download icons) — reduces visual
 *    clutter and unpredictable interaction surface for autistic users.
 *  - No animation on load/transition — avoids sudden movement.
 *  - Muted, desaturated palette pulled directly from tailwind.config.ts
 *    rather than Plotly's default saturated colour cycle.
 *  - Fixed, generous margins and a light grid — calm and easy to read
 *    rather than dense/technical-looking.
 */
import { lazy, Suspense } from "react";
import type { Data, Layout, Config } from "plotly.js";

// Plotly.js is large (~1MB); lazy-load it so it only loads when a
// teacher actually opens the Analytics page, not on every route.
const Plot = lazy(() => import("react-plotly.js"));

// Palette pulled from tailwind.config.ts — kept in sync manually since
// Plotly consumes raw hex, not Tailwind classes.
export const CHART_COLOURS = {
  primary: "#2563EB",
  secondary: "#4F46E5",
  success: "#16A34A",
  warning: "#D97706",
  error: "#DC2626",
  muted: "#94A3B8",
} as const;

const BASE_LAYOUT: Partial<Layout> = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: {
    family: "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
    color: "#1E293B",
    size: 13,
  },
  margin: { t: 24, r: 16, b: 40, l: 48 },
  showlegend: false,
  xaxis: {
    gridcolor: "#F1F5F9",
    zeroline: false,
    fixedrange: true, // no scroll-zoom — predictable, no accidental gestures
  },
  yaxis: {
    gridcolor: "#F1F5F9",
    zeroline: false,
    fixedrange: true,
  },
};

const BASE_CONFIG: Partial<Config> = {
  displayModeBar: false, // hide zoom/pan/download toolbar — calmer UI
  responsive: true,
  staticPlot: false, // hover tooltips still work, just no drag/zoom
};

interface AnalyticsChartProps {
  data: Data[];
  layout?: Partial<Layout>;
  height?: number;
  ariaLabel: string;
}

export function AnalyticsChart({ data, layout, height = 260, ariaLabel }: AnalyticsChartProps) {
  return (
    <div role="img" aria-label={ariaLabel} className="w-full">
      <Suspense
        fallback={
          <div
            className="flex items-center justify-center text-sm text-muted-foreground"
            style={{ height }}
          >
            Loading chart...
          </div>
        }
      >
        <Plot
          data={data}
          layout={{ ...BASE_LAYOUT, ...layout, height }}
          config={BASE_CONFIG}
          style={{ width: "100%" }}
          useResizeHandler
        />
      </Suspense>
    </div>
  );
}
