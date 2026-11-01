"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { api, ApiError, OpenResource, ParsedIntent, SearchResult } from "@/lib/api";

const SUGGESTIONS = [
  "biodegradable wound dressing formulation",
  "plant-based protein concentrate for food manufacturing",
  "low-viscosity epoxy resin for electronics",
  "antimicrobial textile coating process",
];

function IntentChip({ intent }: { intent: ParsedIntent }) {
  const chips = [
    intent.product_type && { label: "Product", value: intent.product_type },
    intent.industry && { label: "Industry", value: intent.industry },
    ...intent.keywords.slice(0, 3).map((k) => ({ label: "Tag", value: k })),
  ].filter(Boolean) as { label: string; value: string }[];

  if (chips.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 mt-3">
      {chips.map((c, i) => (
        <span key={i} className="text-xs bg-blue-50 text-blue-700 border border-blue-100 px-2.5 py-1 rounded-full">
          <span className="font-medium">{c.label}:</span> {c.value}
        </span>
      ))}
    </div>
  );
}

function ResultCard({ result }: { result: SearchResult }) {
  const { listing, score } = result;
  return (
    <Link
      href={`/listings/${listing.id}`}
      target="_blank"
      className="block bg-white border border-line rounded-xl p-5 hover:border-line-strong hover:shadow-sm transition-all"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          {listing.product_category && (
            <p className="text-xs text-muted uppercase tracking-wide mb-1">{listing.product_category}</p>
          )}
          <p className="font-semibold text-ink truncate">{listing.title}</p>
          {listing.public_description && (
            <p className="text-sm text-muted mt-1 line-clamp-2">{listing.public_description}</p>
          )}
        </div>
        <div className="shrink-0 text-right">
          <span className="text-xs font-medium text-green-700 bg-green-50 px-2 py-1 rounded-full">
            {Math.round(score * 100)}% match
          </span>
        </div>
      </div>

      {listing.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {listing.tags.slice(0, 5).map((t) => (
            <span key={t} className="text-xs bg-surface-2 text-muted px-2 py-0.5 rounded-full">{t}</span>
          ))}
        </div>
      )}

      {/* The BOM summary that used to sit here leaked how many materials a
          listing needs and how many are critical — a fingerprint of the
          manufacturing process, shown to every searcher including anonymous
          ones (security/AUDIT.md SAHA-003). Search results now carry the teaser
          tier only; material detail is disclosed inside a deal. */}
      {listing.product_category && (
        <p className="text-xs text-muted mt-3">{listing.product_category.replace(/_/g, " ")}</p>
      )}
    </Link>
  );
}

const OPEN_RESOURCE_KIND: Record<string, string> = {
  patent: "Open patent",
  research_paper: "Open research",
  trademark: "Open trademark",
};

function OpenResourceSuggestionCard({ resource }: { resource: OpenResource }) {
  const kind = OPEN_RESOURCE_KIND[resource.resource_type] ?? "Open resource";
  return (
    <div className="bg-white border border-emerald-200 rounded-xl p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-emerald-700 font-medium mb-1">
            {kind} · free to build on
          </p>
          <p className="font-semibold text-ink truncate">{resource.title}</p>
          {resource.summary && (
            <p className="text-sm text-muted mt-1 line-clamp-2">{resource.summary}</p>
          )}
        </div>
        <a
          href={resource.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 text-xs font-medium bg-emerald-600 text-white px-3 py-1.5 rounded-lg hover:bg-emerald-500 transition-colors"
        >
          Source ↗
        </a>
      </div>
    </div>
  );
}

export default function DiscoverPage() {
  const { accessToken } = useAuthStore();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [intent, setIntent] = useState<ParsedIntent | null>(null);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [suggestions, setSuggestions] = useState<OpenResource[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const runSearch = async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setError("");
    setIntent(null);
    setResults(null);
    setSuggestions([]);
    try {
      const resp = await api.search.query(q.trim(), 10, accessToken ?? undefined);
      setIntent(resp.intent);
      setResults(resp.results);
      setSuggestions(resp.open_resource_suggestions ?? []);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    runSearch(query);
  };

  const useSuggestion = (s: string) => {
    setQuery(s);
    runSearch(s);
    inputRef.current?.focus();
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Discover IP</h1>
        <p className="text-sm text-muted mt-0.5">Describe what you're looking for in plain language — AI finds and ranks matching IP listings.</p>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 px-4 py-3 border border-line-strong rounded-xl text-sm focus:ring-2 focus:ring-accent focus:border-transparent"
          placeholder="e.g. biodegradable packaging adhesive for food-grade applications"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="bg-accent text-white px-5 py-3 rounded-xl text-sm font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors"
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {!results && !loading && (
        <div>
          <p className="text-xs text-muted uppercase tracking-wide mb-2">Try searching for</p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => useSuggestion(s)}
                className="text-sm text-ink-soft bg-white border border-line px-3 py-1.5 rounded-lg hover:border-line-strong transition-colors text-left"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{error}</div>
      )}

      {intent && (
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-4">
          <p className="text-xs font-semibold text-blue-600 uppercase tracking-wide mb-1">AI understood your query as</p>
          <p className="text-sm text-blue-900 font-medium">"{intent.refined_query}"</p>
          <IntentChip intent={intent} />
        </div>
      )}

      {results !== null && (
        <div className="space-y-3">
          <p className="text-sm text-muted">
            {results.length === 0
              ? "No published listings matched your query yet."
              : `${results.length} listing${results.length !== 1 ? "s" : ""} found`}
          </p>
          {results.map((r) => (
            <ResultCard key={r.listing.id} result={r} />
          ))}
        </div>
      )}

      {results !== null && suggestions.length > 0 && (
        <div className="space-y-3">
          <div>
            <p className="text-sm font-semibold text-ink">
              {results.length === 0 ? "No listings yet — build it yourself" : "Or build it yourself"}
            </p>
            <p className="text-xs text-muted mt-0.5">
              These open-source patents and papers from the{" "}
              <Link href="/dashboard/library" className="text-emerald-700 font-medium hover:underline">
                Open Innovation Library
              </Link>{" "}
              match your search — free to develop and license on Saha.
            </p>
          </div>
          {suggestions.map((s) => (
            <OpenResourceSuggestionCard key={s.id} resource={s} />
          ))}
        </div>
      )}
    </div>
  );
}
