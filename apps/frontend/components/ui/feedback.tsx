import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "./cn";
import { Spinner } from "./icons";

/** Skeleton shimmer placeholder for loading states. */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-md bg-[linear-gradient(90deg,#e5ebe3_25%,#f4f7f2_50%,#e5ebe3_75%)]",
        "bg-[length:800px_100%] animate-[saha-shimmer_1.4s_infinite]",
        className,
      )}
      aria-hidden
      {...props}
    />
  );
}

/** A block of stacked skeleton lines — quick page/list placeholder. */
export function SkeletonList({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="bg-surface border border-line rounded-xl p-5 space-y-3">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-3 w-2/3" />
        </div>
      ))}
    </div>
  );
}

export function LoadingRow({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-muted py-8 justify-center" role="status">
      <Spinner className="w-4 h-4 animate-spin" />
      {label}
    </div>
  );
}

/** Inline error banner. */
export function ErrorBanner({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="bg-danger-soft border border-danger/30 text-danger rounded-lg px-4 py-3 text-sm"
    >
      {children}
    </div>
  );
}

/** Empty-state panel with an optional action. */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="bg-surface border border-dashed border-line-strong rounded-xl p-12 text-center">
      {icon && (
        <div className="mx-auto mb-4 w-11 h-11 rounded-full bg-accent-soft text-accent grid place-items-center text-xl">
          {icon}
        </div>
      )}
      <p className="text-ink font-medium">{title}</p>
      {description && <p className="text-sm text-muted mt-1 max-w-sm mx-auto">{description}</p>}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}
