"use client";

import { useEffect, useState } from "react";
import { api, DemandOverview } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Section, StatCard } from "@/components/ui";

export default function DemandPage() {
  const { accessToken } = useAuthStore();
  const [days, setDays] = useState(30);
  const [data, setData] = useState<DemandOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) return;
    api.demand(accessToken, days).then(setData).catch((e) => setError(e.message));
  }, [accessToken, days]);

  const BarList = ({ items }: { items: { label: string; count: number }[] }) => {
    const max = Math.max(1, ...items.map((i) => i.count));
    return (
      <div className="space-y-2">
        {items.length === 0 && <p className="text-sm text-slate-400">No data in this window.</p>}
        {items.map((i) => (
          <div key={i.label}>
            <div className="flex justify-between text-sm mb-0.5">
              <span className="text-slate-700">{i.label}</span>
              <span className="text-slate-400">{i.count}</span>
            </div>
            <div className="h-1.5 bg-slate-100 rounded-full">
              <div className="h-1.5 bg-indigo-500 rounded-full" style={{ width: `${(i.count / max) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900">Demand Intelligence</h1>
        <div className="flex gap-1">
          {[7, 30, 90].map((d) => (
            <button key={d} onClick={() => setDays(d)}
              className={`px-3 py-1 rounded-lg text-sm font-medium ${days === d ? "bg-slate-900 text-white" : "border border-slate-300 text-slate-600 hover:bg-slate-50"}`}>
              {d}d
            </button>
          ))}
        </div>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!data ? <p className="text-sm text-slate-400">Loading…</p> : (
        <>
          <div className="grid grid-cols-3 gap-3">
            <StatCard label="Total searches" value={data.total_searches} />
            <StatCard label="Unique searchers" value={data.unique_searchers} />
            <StatCard label="Unmet searches" value={data.unmet_searches} hint="zero-result queries = supply gaps" />
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <Section title="Top queries">
              <BarList items={data.top_queries.map((q) => ({ label: q.query, count: q.count }))} />
            </Section>
            <Section title="Demand gaps (unmet)">
              {data.demand_gaps.length === 0
                ? <p className="text-sm text-slate-400">No unmet searches in this window.</p>
                : <div className="flex flex-wrap gap-2">
                    {data.demand_gaps.map((g) => (
                      <span key={g.query} className="px-2.5 py-1 bg-red-50 text-red-700 border border-red-100 rounded-full text-xs">
                        {g.query} ×{g.count}
                      </span>
                    ))}
                  </div>}
            </Section>
            <Section title="Top industries"><BarList items={data.top_industries} /></Section>
            <Section title="Top product types"><BarList items={data.top_product_types} /></Section>
          </div>
        </>
      )}
    </div>
  );
}
