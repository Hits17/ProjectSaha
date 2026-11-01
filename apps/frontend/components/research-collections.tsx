"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { research, type ResearchCollection, type CollectionItem, type SavedSearch } from "@/lib/research";
import { useAuthStore } from "@/store/auth";
import { Button, Card, Input, Textarea } from "@/components/ui";

function CollectionResource({ item, save, remove }: { item: CollectionItem; save: (note: string | null) => Promise<void>; remove: () => Promise<void> }) {
  const [note, setNote] = useState(item.note || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  return <Card className="p-4 space-y-3"><h3 className="font-semibold">{item.resource_title || "Resource no longer publicly available"}</h3>{item.source_url && <a className="text-accent underline text-sm" href={item.source_url} target="_blank" rel="noopener noreferrer">Read source ↗</a>}<label className="grid gap-1 text-sm">Private research note<Textarea value={note} onChange={e => { setNote(e.target.value); setSaved(false); }} maxLength={3000} rows={3} /></label>{error && <p role="alert" className="text-danger text-sm">{error}</p>}{saved && <p role="status" className="text-accent text-xs">Note saved.</p>}<div className="flex gap-2"><Button disabled={busy} onClick={async () => { setBusy(true); setError(""); try { await save(note.trim() || null); setSaved(true); } catch (e) { setError(e instanceof Error ? e.message : "Could not save note"); } finally { setBusy(false); } }}>Save note</Button><Button disabled={busy} onClick={async () => { if (!window.confirm("Remove this resource and its note from the collection?")) return; setBusy(true); try { await remove(); } catch (e) { setError(e instanceof Error ? e.message : "Could not remove resource"); } finally { setBusy(false); } }}>Remove</Button></div></Card>;
}

export function ResearchCollections() {
  const identity = useAuthStore(s => s.user?.id ?? "anonymous");
  return <CollectionWorkspace key={identity} />;
}

function CollectionWorkspace() {
  const token = useAuthStore(s => s.accessToken);
  const [collections, setCollections] = useState<ResearchCollection[]>([]);
  const [searches, setSearches] = useState<SavedSearch[]>([]);
  const [items, setItems] = useState<CollectionItem[]>([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [itemOffset, setItemOffset] = useState(0);
  const [searchOffset, setSearchOffset] = useState(0);
  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try { const [folders, queries] = await Promise.all([research.collections(token, offset), research.searches(token, searchOffset)]); setCollections(folders); setSearches(queries); setSelected(current => folders.some(f => f.id === current) ? current : folders[0]?.id || ""); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load research workspace"); } finally { setLoading(false); }
  }, [token, offset, searchOffset]);
  useEffect(() => { void load(); }, [load]);
  const loadItems = useCallback(async () => { if (token && selected) setItems(await research.items(token, selected, itemOffset)); }, [token, selected, itemOffset]);
  useEffect(() => {
    let active = true; setItems([]);
    if (token && selected) research.items(token, selected, itemOffset).then(data => { if (active) setItems(data); }).catch(e => { if (active) setError(e instanceof Error ? e.message : "Could not load collection"); });
    return () => { active = false; };
  }, [token, selected, itemOffset]);
  async function create(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (!token) return; const form = e.currentTarget; const data = new FormData(form); setBusy(true); setError("");
    try { const folder = await research.create(token, String(data.get("name")), String(data.get("description")).trim() || null); form.reset(); setOffset(0); await load(); setSelected(folder.id); setItemOffset(0); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not create collection"); } finally { setBusy(false); }
  }
  const folder = collections.find(c => c.id === selected);
  return <div className="space-y-6"><div><p className="text-sm text-accent">Your private research workspace</p><h1 className="text-3xl font-display mt-1">Collections & saved searches</h1><p className="text-muted mt-2">Keep useful sources and your own research notes together. These notes are access-restricted server records, separate from end-to-end encrypted chat.</p></div>{error && <p role="alert" className="text-danger">{error}</p>}
    <Card className="p-5"><form onSubmit={create} className="grid sm:grid-cols-[1fr_1fr_auto] gap-3 items-end"><label className="grid gap-1 text-sm">New collection<Input name="name" required maxLength={120} placeholder="Battery experiments" /></label><label className="grid gap-1 text-sm">Description (optional)<Input name="description" maxLength={2000} /></label><Button type="submit" disabled={busy}>Create collection</Button></form></Card>
    {loading && <p role="status">Loading private workspace…</p>}
    <section className="space-y-3"><div className="flex items-center justify-between gap-3"><h2 className="text-xl font-semibold">Your collections</h2><Link href="/explore" className="text-sm text-accent">Find resources to save →</Link></div><div className="flex gap-2 items-center flex-wrap"><select aria-label="Choose a collection" className="border border-line rounded p-2 bg-surface" value={selected} onChange={e => { setSelected(e.target.value); setItemOffset(0); }}>{collections.length === 0 && <option value="">No collections yet</option>}{collections.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>{folder && token && <button className="text-sm text-danger" disabled={busy} onClick={async () => { if (!window.confirm(`Delete “${folder.name}” and its private notes?`)) return; setBusy(true); try { await research.remove(token, folder.id); setItems([]); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Could not delete collection"); } finally { setBusy(false); } }}>Delete collection</button>}</div>{folder?.description && <p className="text-sm text-muted">{folder.description}</p>}{selected && items.length === 0 && <p className="text-sm text-muted">No resources on this page. Save resources from Explore into this collection.</p>}<div className="grid md:grid-cols-2 gap-4">{token && items.map(item => <CollectionResource key={`${selected}:${item.resource_id}`} item={item} save={note => research.note(token, selected, item.resource_id, note)} remove={async () => { await research.removeItem(token, selected, item.resource_id); await loadItems(); }} />)}</div><div className="flex gap-3"><Button disabled={!itemOffset} onClick={() => setItemOffset(v => Math.max(0, v - 50))}>Previous resources</Button><Button disabled={items.length < 50} onClick={() => setItemOffset(v => v + 50)}>More resources</Button></div><div className="flex gap-3"><Button disabled={!offset} onClick={() => setOffset(v => Math.max(0, v - 50))}>Previous collections</Button><Button disabled={collections.length < 50} onClick={() => setOffset(v => v + 50)}>More collections</Button></div></section>
    <section className="space-y-3 border-t border-line pt-6"><h2 className="text-xl font-semibold">Saved searches</h2><p className="text-sm text-muted">Save a query in Explore to return to it here. Automatic email alerts are not enabled in this release.</p>{searches.length === 0 && <p className="text-sm text-muted">No saved searches on this page.</p>}{searches.map(search => <Card key={search.id} className="p-4 flex items-center justify-between gap-3"><Link href={`/explore?q=${encodeURIComponent(search.query)}${search.resource_type ? `&type=${encodeURIComponent(search.resource_type)}` : ""}`} className="text-accent"><strong className="text-sm">{search.label}</strong><span className="block text-xs text-muted">{search.resource_type || "All resources"}</span></Link><button className="text-danger text-sm" disabled={busy} onClick={async () => { if (!token) return; try { await research.removeSearch(token, search.id); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Could not delete search"); } }}>Remove</button></Card>)}<div className="flex gap-3"><Button disabled={!searchOffset} onClick={() => setSearchOffset(v => Math.max(0, v - 50))}>Previous searches</Button><Button disabled={searches.length < 50} onClick={() => setSearchOffset(v => v + 50)}>More searches</Button></div></section>
  </div>;
}
