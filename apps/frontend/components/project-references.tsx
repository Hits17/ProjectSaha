"use client";

import { useCallback, useEffect, useState } from "react";
import { request } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Button, Card, Dialog, Input, Textarea } from "@/components/ui";

const platforms: Record<string, { label: string; color: string; mark: string; hosts: string[] }> = {
  website: { label: "Website", color: "#476854", mark: "↗", hosts: [] },
  google_drive: { label: "Google Drive", color: "#1c7042", mark: "△", hosts: ["drive.google.com"] },
  google_docs: { label: "Google Docs", color: "#2459a8", mark: "D", hosts: ["docs.google.com"] },
  google_sheets: { label: "Google Sheets", color: "#1c7042", mark: "S", hosts: [] },
  google_slides: { label: "Google Slides", color: "#835d09", mark: "P", hosts: [] },
  dropbox: { label: "Dropbox", color: "#165db9", mark: "◇", hosts: ["dropbox.com"] },
  onedrive: { label: "OneDrive", color: "#155fa0", mark: "☁", hosts: ["onedrive.live.com", "1drv.ms", "sharepoint.com"] },
  github: { label: "GitHub", color: "#32363c", mark: "⌘", hosts: ["github.com", "gist.github.com"] },
  gitlab: { label: "GitLab", color: "#9e411b", mark: "G", hosts: ["gitlab.com"] },
  figma: { label: "Figma", color: "#7444ad", mark: "F", hosts: ["figma.com"] },
  notion: { label: "Notion", color: "#32363c", mark: "N", hosts: ["notion.so", "notion.site"] },
  youtube: { label: "YouTube", color: "#b52529", mark: "▶", hosts: ["youtube.com", "youtu.be"] },
  zenodo: { label: "Zenodo", color: "#19638d", mark: "Z", hosts: ["zenodo.org"] },
  osf: { label: "Open Science Framework", color: "#19638d", mark: "O", hosts: ["osf.io"] },
  other: { label: "Other platform", color: "#5b6470", mark: "↗", hosts: [] },
};
const types: Record<string, string> = { document: "Document", spreadsheet: "Spreadsheet", presentation: "Presentation", design: "Design / CAD", code: "Code", dataset: "Dataset", image: "Image", video: "Video", paper: "Research paper", folder: "Folder", other: "Other" };
interface Reference { id: string; title: string; url: string; description: string | null; platform: string; file_type: string; pinned: boolean; created_by: string; version: number }
const blank = { title: "", url: "", description: "", platform: "website", file_type: "document", pinned: false };
function domain(url: string) { try { return new URL(url).hostname; } catch { return "External platform"; } }
function suggestedPlatform(url: string) {
  try {
    const parsed = new URL(url); const host = parsed.hostname.toLowerCase();
    if (host === "docs.google.com" && parsed.pathname.startsWith("/spreadsheets/")) return "google_sheets";
    if (host === "docs.google.com" && parsed.pathname.startsWith("/presentation/")) return "google_slides";
    return Object.entries(platforms).find(([, p]) => p.hosts.some(h => host === h || host.endsWith(`.${h}`)))?.[0] ?? "website";
  } catch { return "website"; }
}
function PlatformIcon({ platform }: { platform: string }) {
  const p = platforms[platform] ?? platforms.other;
  return <svg viewBox="0 0 44 44" width="44" height="44" aria-hidden="true" className="shrink-0 rounded-xl"><rect width="44" height="44" rx="12" fill={p.color} /><text x="22" y="29" textAnchor="middle" fill="white" fontFamily="system-ui" fontWeight="700" fontSize="22">{p.mark}</text></svg>;
}

export function ProjectReferences({ projectId, manager }: { projectId: string; manager: boolean }) {
  const { accessToken: token, user } = useAuthStore();
  const [rows, setRows] = useState<Reference[]>([]); const [loading, setLoading] = useState(true);
  const [error, setError] = useState(""); const [notice, setNotice] = useState(""); const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState(""); const [type, setType] = useState("");
  const [dialog, setDialog] = useState(false); const [editing, setEditing] = useState<Reference | null>(null);
  const [form, setForm] = useState(blank); const [removing, setRemoving] = useState<Reference | null>(null);
  const base = `/api/v1/projects/${projectId}/references`;
  const load = useCallback(async () => { if (!token) return; setLoading(true); try { setRows(await request<Reference[]>(base, { token })); } catch (e) { setError(e instanceof Error ? e.message : "Could not load references."); } finally { setLoading(false); } }, [base, token]);
  useEffect(() => { void load(); }, [load]);
  function edit(row?: Reference) { setEditing(row ?? null); setForm(row ? { title: row.title, url: row.url, description: row.description ?? "", platform: row.platform, file_type: row.file_type, pinned: row.pinned } : blank); setError(""); setDialog(true); }
  async function save(e: React.FormEvent) {
    e.preventDefault(); if (!token) return; setBusy(true); setError("");
    try { await request(base + (editing ? `/${editing.id}` : ""), { method: editing ? "PATCH" : "POST", token, body: JSON.stringify({ ...form, description: form.description || null, ...(editing ? { version: editing.version } : {}) }) }); setDialog(false); setNotice(editing ? "Reference updated." : "Reference added to the project."); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not save reference."); } finally { setBusy(false); }
  }
  async function remove() { if (!token || !removing) return; setBusy(true); setError(""); try { await request(`${base}/${removing.id}`, { method: "DELETE", token }); setRemoving(null); setNotice("Reference removed. The original file is unchanged."); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Could not remove reference."); } finally { setBusy(false); } }
  const filtered = rows.filter(row => (!type || row.file_type === type) && `${row.title} ${row.description ?? ""} ${platforms[row.platform]?.label ?? ""} ${domain(row.url)}`.toLowerCase().includes(query.toLowerCase()));
  return <section id="references" className="space-y-4 scroll-mt-24"><div className="flex justify-between gap-3 items-start"><div><h2 className="text-xl font-semibold">Project references</h2><p className="text-sm text-muted mt-1">A shared shelf for documents, designs, datasets and ideas.</p></div><Button onClick={() => edit()}>Add link</Button></div>
    {error && <p role="alert" className="text-danger">{error}</p>}{notice && <p role="status" className="text-sm text-accent">{notice}</p>}
    <div className="flex flex-wrap gap-3"><Input className="flex-1 min-w-48" aria-label="Search project references" placeholder="Find a reference…" value={query} onChange={e => setQuery(e.target.value)} /><select aria-label="Filter references by type" value={type} onChange={e => setType(e.target.value)} className="rounded-lg border border-line bg-surface p-2 text-sm"><option value="">All file types</option>{Object.entries(types).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div>
    {loading ? <p role="status" className="text-sm text-muted">Loading references…</p> : !filtered.length ? <Card className="p-8 text-center"><h3 className="font-semibold">{rows.length ? "No matching references" : "Bring your team’s work together"}</h3><p className="text-sm text-muted mt-2">{rows.length ? "Try another search or file type." : "Add a link from Drive, GitHub, Figma, Notion or another public platform."}</p></Card> : <div className="grid md:grid-cols-2 gap-4">{filtered.map(row => <Card key={row.id} className="p-4 flex flex-col gap-3"><div className="flex gap-3"><PlatformIcon platform={row.platform} /><div className="min-w-0 flex-1"><div className="flex items-start gap-2"><a href={row.url} target="_blank" rel="noopener noreferrer" className="font-semibold text-accent break-words hover:underline">{row.title} ↗</a>{row.pinned && <span className="text-xs rounded bg-surface-2 px-2 py-1 ml-auto">Pinned</span>}</div><p className="text-xs text-muted mt-1">{platforms[row.platform]?.label ?? "Other platform"} · {types[row.file_type] ?? row.file_type}</p><p className="text-xs text-muted mt-1 break-all">{domain(row.url)}</p></div></div>{row.description && <p className="text-sm text-ink-soft whitespace-pre-wrap">{row.description}</p>}<div className="flex flex-wrap gap-3 mt-auto pt-2 border-t border-line"><button className="text-xs text-accent" onClick={async () => { try { await navigator.clipboard.writeText(row.url); setNotice("Reference link copied."); } catch { setError("Clipboard unavailable. Open the reference and copy its address."); } }}>Copy link</button>{(manager || row.created_by === user?.id) && <><button className="text-xs text-accent" onClick={() => edit(row)}>Edit{manager ? " / pin" : ""}</button><button className="text-xs text-danger" onClick={() => setRemoving(row)}>Remove</button></>}</div></Card>)}</div>}
    <p className="text-xs text-muted">Links are visible to project members. Files stay on their original platform; sharing permissions there still apply. Saha does not copy files or verify their contents. Icons identify the selected platform, not a verified destination.</p>
    <Dialog open={dialog} onClose={() => { if (!busy) setDialog(false); }} title={editing ? "Edit reference" : "Add a project reference"}><form onSubmit={save} className="space-y-4">{error && <p role="alert" className="text-danger text-sm">{error}</p>}<label className="grid gap-1 text-sm">Title<Input required maxLength={180} value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Prototype drawings, shared research notes…" /></label><label className="grid gap-1 text-sm">HTTPS link<Input required type="url" maxLength={2000} value={form.url} onChange={e => setForm({ ...form, url: e.target.value, platform: suggestedPlatform(e.target.value) })} placeholder="https://" /></label><div className="grid grid-cols-2 gap-3"><label className="grid gap-1 text-sm">Platform<select className="rounded-lg border border-line bg-surface p-2" value={form.platform} onChange={e => setForm({ ...form, platform: e.target.value })}>{Object.entries(platforms).map(([key, p]) => <option key={key} value={key}>{p.label}</option>)}</select></label><label className="grid gap-1 text-sm">File type<select className="rounded-lg border border-line bg-surface p-2" value={form.file_type} onChange={e => setForm({ ...form, file_type: e.target.value })}>{Object.entries(types).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label></div><label className="grid gap-1 text-sm">Notes (optional)<Textarea maxLength={2000} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="What should collaborators look at first?" /></label>{manager && <label className="flex gap-2 text-sm"><input type="checkbox" checked={form.pinned} onChange={e => setForm({ ...form, pinned: e.target.checked })} />Pin this reference to the top</label>}<p className="text-xs text-muted">Check the destination’s sharing settings so your collaborators can open it. Avoid links containing passwords or secret access tokens.</p><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save reference"}</Button></form></Dialog>
    <Dialog open={!!removing} onClose={() => { if (!busy) setRemoving(null); }} title="Remove reference?"><p className="text-sm mb-4">Remove “{removing?.title}” from this project? The original file will stay on its platform.</p>{error && <p role="alert" className="text-danger">{error}</p>}<Button onClick={() => void remove()} disabled={busy}>Remove reference</Button></Dialog>
  </section>;
}
