"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { request, type OpenResource } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Button, Card, Input, SkeletonList, EmptyState } from "@/components/ui";
import { research, type ResearchCollection } from "@/lib/research";

interface Resource extends OpenResource { rights_evidence_url?: string | null; rights_note?: string | null; jurisdiction?: string | null }
interface Discovery { query: string; resources: Resource[]; sources: { name: string; url: string; description: string }[]; has_more: boolean; offset: number; coverage: string }

export function OpenDiscovery({ initialQuery = "", initialType = "" }: { initialQuery?: string; initialType?: string }) {
  const identity = useAuthStore(s => s.user?.id ?? "anonymous");
  return <DiscoveryContent key={`${identity}:${initialQuery}:${initialType}`} initialQuery={initialQuery} initialType={initialType} />;
}

function DiscoveryContent({ initialQuery, initialType }: { initialQuery: string; initialType: string }) {
  const token = useAuthStore(s => s.accessToken);
  const router = useRouter();
  const pathname = usePathname();
  function updateSearch(nextQuery: string, nextType: string) {
    setOffset(0); setQuery(nextQuery); setType(nextType);
    if (pathname === "/explore") {
      const params = new URLSearchParams();
      if (nextQuery) params.set("q", nextQuery);
      if (nextType) params.set("type", nextType);
      router.push(`/explore${params.size ? `?${params}` : ""}`, { scroll: false });
    }
  }
  const [draft, setDraft] = useState(initialQuery.slice(0, 255));
  const [query, setQuery] = useState(initialQuery.slice(0, 255));
  const [type, setType] = useState(["patent", "research_paper", "trademark"].includes(initialType) ? initialType : "");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<Discovery | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [collections, setCollections] = useState<ResearchCollection[]>([]);
  const [collection, setCollection] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    let active = true;
    if (token) Promise.all([research.collections(token), research.collections(token, 50)]).then(pages => {
      if (active) { const rows = pages.flat(); setCollections(rows); setCollection(rows[0]?.id || ""); }
    }).catch(() => { if (active) setCollections([]); });
    return () => { active = false; };
  }, [token]);
  useEffect(() => {
    let active = true; setLoading(true); setError("");
    const params = new URLSearchParams({ q: query, offset: String(offset), limit: "24" });
    if (type) params.set("resource_type", type);
    request<Discovery>(`/api/v1/open-discovery?${params}`, { token: token ?? undefined })
      .then(result => { if (active) setData(result); }).catch(e => { if (active) { setData(null); setError(e instanceof Error ? e.message : "Could not search the library"); } }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, query, offset, type]);
  return <div className="space-y-6">
    {notice && <p role="status" className="text-accent text-sm">{notice}</p>}
    <form role="search" className="flex flex-wrap gap-3 rounded-xl border border-line bg-surface p-4" onSubmit={e => { e.preventDefault(); updateSearch(draft.trim(), type); }}>
      <Input className="flex-1 min-w-48" aria-label="Search open patents and research" value={draft} onChange={e => setDraft(e.target.value)} placeholder="Search inventions, patent numbers, topics or researchers" maxLength={255} />
      <select aria-label="Resource type" value={type} onChange={e => updateSearch(query, e.target.value)} className="border border-line rounded p-2 text-sm bg-surface"><option value="">All resources</option><option value="patent">Patents</option><option value="research_paper">Research papers</option><option value="trademark">Trademarks</option></select><Button type="submit">Search</Button>
    </form>
    {token && <div className="flex flex-wrap gap-3 items-center text-sm"><Link href="/dashboard/collections" className="text-accent underline">My research collections</Link>{collections.length > 0 && <label className="flex gap-2 items-center">Save resources to<select className="border border-line rounded p-2 bg-surface" value={collection} onChange={e => setCollection(e.target.value)}>{collections.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>}{query && <Button disabled={saving} onClick={async () => { setSaving(true); setError(""); try { await research.saveSearch(token, query, type); setNotice("Search saved in your private research workspace."); } catch (e) { setError(e instanceof Error ? e.message : "Could not save search"); } finally { setSaving(false); } }}>Save this search</Button>}</div>}
    {error && <p role="alert" className="text-danger">{error}</p>}
    <section className="rounded-xl border border-line bg-surface-2 p-4"><h2 className="font-semibold">Search beyond Saha</h2><p className="text-xs text-muted mt-1">These links open independent patent databases. Their results are not imported into Saha or certified as openly licensed.</p><div className="grid sm:grid-cols-3 gap-3 mt-3">{(data?.sources || [{ name: "Google Patents", url: `https://patents.google.com/?q=${encodeURIComponent(query)}`, description: "Worldwide patent publications" }, { name: "Espacenet", url: `https://worldwide.espacenet.com/patent/search?q=${encodeURIComponent(query)}`, description: "Worldwide patents and legal events" }, { name: "WIPO PATENTSCOPE", url: "https://patentscope.wipo.int/search/en/search.jsf", description: "International patent publications" }]).map(source => <a key={source.name} href={source.url} target="_blank" rel="noopener noreferrer" className="p-3 border border-line rounded-lg bg-surface hover:border-accent"><span className="text-sm text-accent font-medium">{source.name} ↗</span><span className="block text-xs text-muted mt-1">{source.description}</span></a>)}</div></section>
    <div className="flex items-center justify-between gap-3"><h2 className="text-xl font-display">Saha’s curated open library</h2><Link href={token ? "/dashboard/library" : "/login?next=%2Fdashboard%2Flibrary"} className="text-sm text-accent">Suggest a resource →</Link></div>
    <p className="text-sm text-muted">Check each source’s rights evidence and relevant jurisdiction before building. A publicly readable patent or paper is not automatically free to reuse.</p>
    {loading ? <SkeletonList rows={3} /> : data?.resources.length === 0 ? <EmptyState title="No matching resources yet" description="Try a broader topic, explore the independent databases above, or contribute a source to the library." action={<Button href="/dashboard/library" variant="secondary">Contribute a resource</Button>} /> : <div className="grid md:grid-cols-2 gap-4">{data?.resources.map(resource => <Card key={resource.id} className="p-5 flex flex-col gap-3"><div className="flex flex-wrap gap-2 text-xs"><span className="rounded bg-surface-2 px-2 py-1">{resource.resource_type.replaceAll("_", " ")}</span><span className="rounded bg-surface-2 px-2 py-1">Curated label: {resource.license.replaceAll("_", " ")}</span>{resource.jurisdiction && <span>{resource.jurisdiction}</span>}</div><h3 className="font-semibold text-lg">{resource.title}</h3><p className="text-xs text-muted">{resource.identifier}{resource.published_year ? ` · ${resource.published_year}` : ""}{resource.organization ? ` · ${resource.organization}` : ""}</p><p className="text-sm text-ink-soft line-clamp-4">{resource.summary}</p>{resource.rights_note && <p className="text-xs text-muted">Rights note: {resource.rights_note}</p>}<div className="flex flex-wrap gap-3 text-sm mt-auto pt-2"><a className="text-accent underline" href={resource.source_url} target="_blank" rel="noopener noreferrer">Read source ↗</a>{resource.rights_evidence_url && <a className="text-accent underline" href={resource.rights_evidence_url} target="_blank" rel="noopener noreferrer">Rights evidence ↗</a>}<Link className="text-accent" href={`/projects?source=${resource.id}`}>Find or start a project →</Link>{token && collection && <button disabled={saving} className="text-accent underline disabled:opacity-50" onClick={async () => { setSaving(true); setError(""); try { await research.save(token, collection, resource.id); setNotice(`Saved “${resource.title}” to your collection.`); } catch (e) { setError(e instanceof Error ? e.message : "Could not save resource"); } finally { setSaving(false); } }}>Save to collection</button>}</div></Card>)}</div>}
    <div className="flex items-center justify-between border-t border-line pt-5"><Button variant="secondary" disabled={offset === 0 || loading || !!error} onClick={() => setOffset(v => Math.max(0, v - 24))}>Previous</Button><span className="text-xs text-muted" aria-live="polite">Page {Math.floor(offset / 24) + 1}</span><Button variant="secondary" disabled={!data?.has_more || loading || !!error} onClick={() => setOffset(v => v + 24)}>Next</Button></div>
    {data && <p className="text-xs text-muted">{data.coverage}</p>}
  </div>;
}
