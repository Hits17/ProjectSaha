"use client";

import { useState } from "react";
import { useDemandOverview } from "@/lib/hooks";
import { ApiError } from "@/lib/api";
import {
  BarChart,
  Badge,
  ChartCard,
  EmptyState,
  ErrorBanner,
  PageHeader,
  SkeletonList,
  StatTile,
  cn,
} from "@/components/ui";
import * as Icon from "@/components/ui/icons";

const WINDOWS = [
  { days: 7, label: "7d" },
  { days: 30, label: "30d" },
  { days: 90, label: "90d" },
];

export default function DemandPage() {
  const [days, setDays] = useState(30);
  const { data, isLoading, error } = useDemandOverview(days);

  const windowToggle = (
    <div className="flex gap-1 bg-surface-2 rounded-lg p-1" role="tablist" aria-label="Time window">
      {WINDOWS.map((w) => (
        <button
          key={w.days}
          onClick={() => setDays(w.days)}
          role="tab"
          aria-selected={days === w.days}
          className={cn(
            "px-3 py-1 rounded-md text-sm font-medium transition-colors",
            days === w.days ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink",
          )}
        >
          {w.label}
        </button>
      ))}
    </div>
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="Demand Intelligence"
        description="What manufacturers are searching for — find gaps worth listing."
        actions={windowToggle}
      />

      {error && (
        <ErrorBanner>
          {error instanceof ApiError ? error.message : "Failed to load demand data"}
        </ErrorBanner>
      )}

      {isLoading ? (
        <SkeletonList rows={3} />
      ) : !data ? null : data.total_searches === 0 ? (
        <EmptyState
          icon={<Icon.Search className="w-5 h-5" />}
          title="No search activity yet"
          description="Demand signals are captured every time a manufacturer searches the marketplace."
        />
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <StatTile label="Total Searches" value={data.total_searches} icon={<Icon.Search />} />
            <StatTile label="Unique Searchers" value={data.unique_searchers} icon={<Icon.Users />} />
            <StatTile
              label="Unmet Searches"
              value={data.unmet_searches}
              sublabel="Zero results returned"
              icon={<Icon.TrendingUp />}
            />
          </div>

          <ChartCard title="Top Search Queries">
            <BarChart
              ariaLabel="Top search queries by volume"
              data={data.top_queries.map((q) => ({
                label: q.query,
                value: q.count,
                hint: `${q.avg_results} avg results`,
              }))}
              valueFormat={(v) => `${v} searches`}
              emptyLabel="No queries in this window."
            />
          </ChartCard>

          <div className="grid sm:grid-cols-2 gap-4">
            <ChartCard title="Top Industries">
              <BarChart
                ariaLabel="Top industries"
                data={data.top_industries.map((i) => ({ label: i.label, value: i.count }))}
                emptyLabel="No industry data yet."
              />
            </ChartCard>
            <ChartCard title="Top Product Types">
              <BarChart
                ariaLabel="Top product types"
                data={data.top_product_types.map((i) => ({ label: i.label, value: i.count }))}
                emptyLabel="No product-type data yet."
              />
            </ChartCard>
          </div>

          <ChartCard title="Demand Gaps">
            <p className="text-xs text-muted -mt-2 mb-4">
              Searches that returned nothing — unmet demand you could list IP against.
            </p>
            {data.demand_gaps.length === 0 ? (
              <p className="text-sm text-muted">No unmet searches in this window.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {data.demand_gaps.map((g) => (
                  <Badge key={g.query} tone="warning">
                    <span className="capitalize">{g.query}</span> ×{g.count}
                  </Badge>
                ))}
              </div>
            )}
          </ChartCard>
        </>
      )}
    </div>
  );
}
