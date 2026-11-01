"use client";

import { useCallback, useEffect, useState } from "react";
import { api, BASE_URL, HealthReport } from "@/lib/api";
import { Btn, Section, Td, Th } from "@/components/ui";
import { useAuthStore } from "@/store/auth";

const TOOLS = [
  { name: "API docs (Swagger)", url: `${BASE_URL}/docs`, note: "dev only" },
  { name: "Prometheus metrics", url: `${BASE_URL}/metrics/`, note: "saha_* business counters" },
  { name: "Prometheus UI", url: "http://localhost:9091", note: "scrape targets & queries" },
  { name: "Grafana", url: "http://localhost:3001", note: "dashboards" },
  { name: "MailHog", url: "http://localhost:8025", note: "dev email inbox" },
  { name: "Qdrant dashboard", url: "http://localhost:6333/dashboard", note: "vector collections" },
  { name: "MinIO console", url: "http://localhost:9001", note: "vault object storage" },
];

export default function SystemPage() {
  const [health, setHealth] = useState<HealthReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);

  const accessToken = useAuthStore((s) => s.accessToken);

  const load = useCallback(() => {
    if (!accessToken) return;
    setError(null);
    api.health(accessToken)
      .then((h) => { setHealth(h); setCheckedAt(new Date()); })
      .catch((e) => setError(e.message));
  }, [accessToken]);

  useEffect(() => { load(); }, [load]);

  const dot = (ok: boolean) => (
    <span className={`inline-block w-2 h-2 rounded-full mr-2 ${ok ? "bg-green-500" : "bg-red-500"}`} />
  );

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-slate-900">System Health</h1>
      {error && <p className="text-sm text-red-600">Health check failed: {error}</p>}

      <Section title={`Dependencies ${checkedAt ? `· checked ${checkedAt.toLocaleTimeString()}` : ""}`}
        actions={<Btn onClick={load}>Re-check</Btn>}>
        {!health ? <p className="text-sm text-slate-400">Running deep health check…</p> : (
          <>
            <p className="mb-3 text-sm">
              Overall:{" "}
              <span className={`font-semibold ${health.status === "healthy" ? "text-green-700" : "text-amber-600"}`}>
                {health.status}
              </span>
            </p>
            <table className="w-full">
              <thead><tr><Th>Component</Th><Th>Status</Th></tr></thead>
              <tbody>
                {Object.entries(health.checks).map(([name, v]) => {
                  const isObj = typeof v === "object";
                  const statusText = isObj ? `${v.status} · ${v.active} (${v.model})` : v;
                  const ok = (isObj ? v.status : v) === "healthy";
                  return (
                    <tr key={name}>
                      <Td className="font-medium text-slate-900">{name}</Td>
                      <Td>{dot(ok)}{statusText}</Td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        )}
      </Section>

      <Section title="Operational tools">
        <table className="w-full">
          <thead><tr><Th>Tool</Th><Th>URL</Th><Th>Notes</Th></tr></thead>
          <tbody>
            {TOOLS.map((t) => (
              <tr key={t.name} className="hover:bg-slate-50">
                <Td className="font-medium text-slate-900">{t.name}</Td>
                <Td><a href={t.url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline">{t.url}</a></Td>
                <Td>{t.note}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </div>
  );
}
