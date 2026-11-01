import type { ReactNode } from "react";
import { cn } from "./cn";

/** Horizontal bar chart — good for ranked categories (top queries, demand gaps).
 *  Pure SVG/CSS, no charting dependency. Accessible via role="img" + label. */
export function BarChart({
  data,
  valueFormat = (v) => String(v),
  ariaLabel,
  emptyLabel = "No data yet.",
}: {
  data: { label: string; value: number; hint?: string }[];
  valueFormat?: (v: number) => string;
  ariaLabel: string;
  emptyLabel?: string;
}) {
  if (data.length === 0) return <p className="text-sm text-muted py-6 text-center">{emptyLabel}</p>;
  const max = Math.max(...data.map((d) => d.value), 1);

  return (
    <div className="space-y-2.5" role="img" aria-label={ariaLabel}>
      {data.map((d, i) => (
        <div key={i} className="group">
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="text-ink truncate pr-2" title={d.label}>
              {d.label}
            </span>
            <span className="text-muted tabular-nums shrink-0">{valueFormat(d.value)}</span>
          </div>
          <div className="h-2 rounded-full bg-surface-2 overflow-hidden">
            <div
              className="h-full rounded-full bg-accent transition-[width] duration-500"
              style={{ width: `${Math.max((d.value / max) * 100, 3)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Compact sparkline for trends. Values are normalized to the given height. */
export function Sparkline({
  values,
  width = 120,
  height = 32,
  className,
}: {
  values: number[];
  width?: number;
  height?: number;
  className?: string;
}) {
  if (values.length < 2) return null;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const step = width / (values.length - 1);
  const points = values
    .map((v, i) => `${(i * step).toFixed(1)},${(height - ((v - min) / span) * height).toFixed(1)}`)
    .join(" ");
  return (
    <svg width={width} height={height} className={cn("overflow-visible", className)} aria-hidden>
      <polyline points={points} fill="none" stroke="var(--color-accent)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Donut for a small set of proportions (status breakdowns). */
export function Donut({
  segments,
  size = 120,
  thickness = 14,
}: {
  segments: { label: string; value: number; color: string }[];
  size?: number;
  thickness?: number;
}) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Distribution">
      <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
        {segments.map((s, i) => {
          const frac = s.value / total;
          const dash = frac * c;
          const el = (
            <circle
              key={i}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={s.color}
              strokeWidth={thickness}
              strokeDasharray={`${dash} ${c - dash}`}
              strokeDashoffset={-offset}
            />
          );
          offset += dash;
          return el;
        })}
      </g>
    </svg>
  );
}

/** A titled panel to frame a chart with an optional right-aligned control. */
export function ChartCard({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="bg-surface border border-line rounded-xl shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-ink font-sans">{title}</h3>
        {action}
      </div>
      {children}
    </div>
  );
}
