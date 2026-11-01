"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type FeedPost } from "@/lib/api";
import { institutions, type Institution, type PrivateSpaceRecord } from "@/lib/institutions";
import { useAuthStore } from "@/store/auth";
import { Button, Card, Input, Textarea, SkeletonList, EmptyState } from "@/components/ui";

import { PostComposer } from "@/components/social/composer";
import { PostCard } from "@/components/social/post-card";

const domains = ["general", "biotech_pharma", "clean_energy", "materials_science", "software_ai", "hardware_electronics", "consumer_products", "agritech_food", "medical_devices", "industrial_manufacturing"];
const message = (error: unknown) => error instanceof Error ? error.message : "Something went wrong. Please try again.";

export function InstitutionDirectory() {
  const token = useAuthStore(s => s.accessToken);
  const router = useRouter();
  const [rows, setRows] = useState<Institution[]>([]);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true; setLoading(true); setError("");
    institutions.browse(token, search, offset).then(data => { if (active) setRows(data); })
      .catch(e => { if (active) { setRows([]); setError(message(e)); } }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, search, offset]);
  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!token) return;
    const data = new FormData(event.currentTarget); setBusy(true); setError("");
    try {
      const row = await institutions.create(token, { name: String(data.get("name")), description: String(data.get("description")), topic: String(data.get("topic")), website_url: String(data.get("website")).trim() || null });
      router.push(`/institutions/${row.id}`);
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  return <div className="space-y-6">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-sm text-accent font-medium">Build together</p><h1 className="text-3xl font-display mt-1">Institutions</h1><p className="text-muted mt-2 max-w-2xl">Find research groups, universities, makerspaces and community labs. Share progress, discuss ideas and meet collaborators.</p></div>
      {token ? <Button onClick={() => setCreating(v => !v)}>{creating ? "Close form" : "Create institution"}</Button> : <Link className="text-accent underline" href="/login?next=%2Finstitutions">Sign in to create a page</Link>}</div>
    {error && <p role="alert" className="text-danger">{error}</p>}
    {creating && token && <Card className="p-5"><form onSubmit={create} className="grid gap-4 max-w-2xl">
      <h2 className="text-lg font-semibold">Create a public institution page</h2>
      <label className="grid gap-1 text-sm">Institution name<Input name="name" required minLength={3} maxLength={120} /></label>
      <label className="grid gap-1 text-sm">About<Textarea name="description" maxLength={2000} rows={3} /></label>
      <label className="grid gap-1 text-sm">Official website (optional)<Input name="website" type="url" placeholder="https://" maxLength={1000} /></label>
      <label className="grid gap-1 text-sm">Research domain<select name="topic" className="rounded border border-line p-2">{domains.map(d => <option key={d} value={d}>{d.replaceAll("_", " ")}</option>)}</select></label>
      <p className="text-xs text-muted">Create a page only if you are authorized to represent the institution. A page does not receive a verification badge automatically.</p>
      <Button type="submit" disabled={busy}>{busy ? "Creating…" : "Create page"}</Button>
    </form></Card>}
    <form onSubmit={e => { e.preventDefault(); setOffset(0); setSearch(query.trim()); }} className="flex gap-3 rounded-xl border border-line bg-surface p-4"><Input aria-label="Search institutions" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search institutions" maxLength={200} /><Button type="submit">Search</Button></form>
    {loading ? <SkeletonList rows={3} /> : error ? null : rows.length === 0 ? <EmptyState title="Find a home for your research community" description="Try another search, or create a public page for your lab, university or makerspace." action={token ? <Button onClick={() => setCreating(true)}>Create institution</Button> : <Button href="/login?next=%2Finstitutions">Sign in to create a page</Button>} /> : <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">{rows.map(row => <Link key={row.id} href={`/institutions/${row.id}`} className="rounded-xl border border-line bg-surface p-5 hover:border-accent focus-visible:outline-accent"><div className="flex gap-2 items-start"><h2 className="font-semibold text-lg">{row.name}</h2>{row.verification_status === "verified" && <span className="text-xs text-accent" aria-label="Institution verified by Saha">Verified</span>}</div><p className="text-sm text-muted mt-2 line-clamp-3">{row.description || "An open innovation institution on Saha."}</p><p className="text-xs text-muted mt-4">{row.topic.replaceAll("_", " ")} · {row.member_count} members</p></Link>)}</div>}
    <div className="flex items-center justify-between border-t border-line pt-5"><Button variant="secondary" disabled={offset === 0 || loading} onClick={() => setOffset(v => Math.max(0, v - 24))}>Previous</Button><span className="text-xs text-muted" aria-live="polite">Page {Math.floor(offset / 24) + 1}</span><Button variant="secondary" disabled={rows.length < 24 || loading || !!error} onClick={() => setOffset(v => v + 24)}>Next</Button></div>
  </div>;
}

export function InstitutionPage({ id }: { id: string }) {
  const identity = useAuthStore(s => s.user?.id ?? "anonymous");
  return <InstitutionPageContent key={`${id}:${identity}`} id={id} />;
}

function InstitutionPageContent({ id }: { id: string }) {
  const { accessToken: token, user } = useAuthStore();
  const [space, setSpace] = useState<Institution | null>(null);
  const [posts, setPosts] = useState<FeedPost[]>([]);
  const [privateRecord, setPrivateRecord] = useState<PrivateSpaceRecord | null>(null);
  const [policy, setPolicy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState(false);
  const load = useCallback(async () => {
    try { const [page, feed] = await Promise.all([institutions.get(token, id), institutions.posts(token, id, offset)]); setSpace(page); setPosts(feed); }
    catch (e) { setError(message(e)); }
  }, [token, id, offset]);
  useEffect(() => { setSpace(null); setPosts([]); setPrivateRecord(null); void load(); institutions.policy().then(p => setPolicy(p.institution_verification_enabled)).catch(() => setPolicy(false)); }, [load]);
  async function join() {
    if (!token) return; setBusy(true); setError("");
    try { await api.communities.join(token, id); await load(); } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  async function verify(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (!token) return; const form = new FormData(e.currentTarget); setBusy(true); setError("");
    try { setPrivateRecord(await institutions.verify(token, id, String(form.get("note")), String(form.get("evidence")).trim() || null)); await load(); setNotice("Verification request submitted to Saha administrators."); } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  async function update(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (!token) return;
    const form = new FormData(e.currentTarget); setBusy(true); setError("");
    try {
      setSpace(await institutions.update(token, id, { name: String(form.get("name")), description: String(form.get("description")), topic: String(form.get("topic")), website_url: String(form.get("website")).trim() || null }));
      setEditing(false); setNotice("Institution page updated. Name or website changes require a new verification review.");
    } catch (e) { setError(message(e)); } finally { setBusy(false); }
  }
  const isOwner = space?.created_by === user?.id;
  return <div className="space-y-6"><Link href="/institutions" className="text-sm text-accent">← Institutions</Link>{error && <p role="alert" className="text-danger">{error}</p>}{notice && <p role="status" className="text-accent">{notice}</p>}
    {!space ? <p role="status">{error ? "Unable to load this institution." : "Loading institution…"}</p> : <>
      <Card className="p-6"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-sm text-muted">Institution · {space.topic.replaceAll("_", " ")}</p><h1 className="text-3xl font-display mt-1">{space.name}</h1>{space.verification_status === "verified" && <p className="text-accent text-sm mt-2">Identity reviewed by Saha</p>}</div>{token && !space.is_member && <Button disabled={busy} onClick={join}>Join institution</Button>}</div><p className="mt-4 text-ink-soft whitespace-pre-wrap">{space.description}</p><div className="flex flex-wrap gap-4 text-sm mt-4 text-muted"><span>{space.member_count} members</span>{space.website_url && <a href={space.website_url} target="_blank" rel="noopener noreferrer" className="text-accent underline">Official website ↗</a>}<Link href={`/dashboard/community/${id}`} className="text-accent">Members & secure chat</Link></div></Card>
      {(isOwner || user?.role === "admin") && token && <Card className="p-5 space-y-3"><h2 className="font-semibold">Space administration</h2><p className="text-sm text-muted">Internal references and verification evidence are private to the page owner and Saha administrators.</p>{isOwner && <Button onClick={() => setEditing(v => !v)}>{editing ? "Cancel editing" : "Edit institution page"}</Button>}{editing && isOwner && <form onSubmit={update} className="grid gap-3"><label className="grid gap-1 text-sm">Name<Input name="name" required minLength={3} maxLength={120} defaultValue={space.name} /></label><label className="grid gap-1 text-sm">About<Textarea name="description" maxLength={2000} defaultValue={space.description || ""} /></label><label className="grid gap-1 text-sm">Official website<Input type="url" name="website" defaultValue={space.website_url || ""} maxLength={1000} /></label><label className="grid gap-1 text-sm">Domain<select name="topic" defaultValue={space.topic} className="border border-line rounded p-2">{domains.map(d => <option key={d} value={d}>{d.replaceAll("_", " ")}</option>)}</select></label><p className="text-xs text-muted">Changing the name or official website removes an existing verification badge until reviewed again.</p><Button disabled={busy} type="submit">Save page</Button></form>}<Button onClick={async () => { try { setPrivateRecord(await institutions.private(token, id)); } catch (e) { setError(message(e)); } }}>Show private space reference</Button>{privateRecord && <div className="rounded bg-surface-2 p-3 text-sm"><p>Internal reference: <code>{privateRecord.reference}</code></p>{privateRecord.review_note && <p className="mt-2">Review: {privateRecord.review_note}</p>}</div>}
        {isOwner && policy && space.verification_status !== "verified" && <form onSubmit={verify} className="grid gap-3 max-w-xl"><h3 className="text-sm font-semibold">Request institution verification</h3><label className="text-sm grid gap-1">How can we confirm you represent this institution?<Textarea name="note" required minLength={10} maxLength={2000} /></label><label className="text-sm grid gap-1">Public evidence link (optional)<Input type="url" name="evidence" placeholder="https://institution.example/team" /></label><Button disabled={busy || space.verification_status === "pending"} type="submit">{space.verification_status === "pending" ? "Review pending" : "Request verification"}</Button></form>}
      </Card>}
      {token && space.is_member ? <PostComposer communityId={id} publicOnly onPosted={() => { setOffset(0); void load(); }} /> : <p className="text-sm text-muted">{token ? "Join this institution to publish updates." : <Link href={`/login?next=${encodeURIComponent(`/institutions/${id}`)}`} className="text-accent">Sign in to join and collaborate.</Link>}</p>}
      <section aria-label="Institution updates" className="space-y-4"><h2 className="text-xl font-semibold">Updates & discussion</h2>{posts.length === 0 && <p className="text-muted">No public updates yet.</p>}{posts.map(post => <PostCard key={post.id} post={post} onChange={updated => setPosts(rows => rows.map(row => row.id === updated.id ? updated : row))} onRemove={removed => setPosts(rows => rows.filter(row => row.id !== removed))} />)}</section>
      <div className="flex items-center justify-between border-t border-line pt-5"><Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(v => Math.max(0, v - 20))}>Previous</Button><Button disabled={posts.length < 20} onClick={() => setOffset(v => v + 20)}>Next</Button></div>
    </>}
  </div>;
}
