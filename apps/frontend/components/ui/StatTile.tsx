import type { ReactNode } from "react";
import { cn } from "./cn";

/** A KPI tile for dashboards: label, large value, optional delta + icon. */
export function StatTile({
  label,
  value,
  sublabel,
  icon,
  delta,
  className,
}: {
  label: string;
  value: ReactNode;
  sublabel?: string;
  icon?: ReactNode;
  delta?: { value: string; positive?: boolean };
  className?: string;
}) {
  return (
    <div className={cn("bg-surface border border-line rounded-xl shadow-sm p-5", className)}>
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
        {icon && <span className="text-accent text-lg leading-none">{icon}</span>}
      </div>
      <p className="mt-2 text-2xl font-semibold text-ink font-display tabular-nums">{value}</p>
      <div className="mt-1 flex items-center gap-2">
        {sublabel && <span className="text-xs text-muted">{sublabel}</span>}
        {delta && (
          <span
            className={cn(
              "text-xs font-medium",
              delta.positive ? "text-success" : "text-danger",
            )}
          >
            {delta.positive ? "▲" : "▼"} {delta.value}
          </span>
        )}
      </div>
    </div>
  );
}
