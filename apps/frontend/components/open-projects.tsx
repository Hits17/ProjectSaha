"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, request, type Community } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Button, Card, Input, Textarea, SkeletonList, EmptyState } from "@/components/ui";
import { ProjectReferences } from "@/components/project-references";
import { SecureChat } from "@/components/secure-chat";

interface Project { space: Community; resource_id: string | null; resource_title: string | null; source_url: string | null; goal: string; repository_url: string | null; contribution_guide: string | null; skills_needed: string[]; stage: string }
interface Task { id: string; title: string; description: string | null; status: "todo" | "doing" | "done"; created_by: string; assigned_to: string | null; version: number }
const errorMessage = (e: unknown) => e instanceof Error ? e.message : "Please try again.";

export function ProjectDirectory({ source }: { source?: string }) {
  const token = useAuthStore(s => s.accessToken);
  const router = useRouter();
  const [rows, setRows] = useState<Project[]>([]);
  const [offset, setOffset] = useState(0);
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [create, setCreate] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true; setLoading(true); setError("");
    const params = new URLSearchParams({ q: query, offset: String(offset) }); if (source) params.set("resource_id", source);
    request<Project[]>(`/api/v1/projects?${params}`, { token: token ?? undefined }).then(data => { if (active) setRows(data); }).catch(e => { if (active) { setRows([]); setError(errorMessage(e)); } }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, query, offset, source]);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (!token) return; const form = new FormData(e.currentTarget); setBusy(true); setError("");
    try {
      const project = await request<Project>("/api/v1/projects", { method: "POST", token, body: JSON.stringify({ name: String(form.get("name")), resource_id: source || null, goal: String(form.get("goal")), repository_url: String(form.get("repository")).trim() || null, contribution_guide: String(form.get("guide")).trim() || null, skills_needed: String(form.get("skills")).split(",").map(s => s.trim()).filter(Boolean) }) });
      router.push(`/projects/${project.space.id}`);
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  return <div className="space-y-6"><div className="flex flex-wrap justify-between items-start gap-4"><div><p className="text-sm text-accent">Your collaboration spaces</p><h1 className="text-3xl font-display mt-1">Projects</h1><p className="text-muted mt-2">Build together in invite-only workspaces. Start with an idea or an optional library resource.</p></div>{token ? <Button onClick={() => setCreate(v => !v)}>{create ? "Close form" : "Start a project"}</Button> : <Button href={`/login?next=${encodeURIComponent(source ? `/projects?source=${source}` : "/projects")}`}>Sign in to start a project</Button>}</div>{source && <p className="text-sm text-muted">Showing projects linked to your selected library resource. <Link href="/projects" className="text-accent">Show all projects</Link></p>}
    {error && <p role="alert" className="text-danger">{error}</p>}
    {create && token && <Card className="p-5"><form className="grid gap-3" onSubmit={submit}><h2 className="font-semibold">Create an invite-only project</h2><label className="grid gap-1 text-sm">Project name<Input name="name" required minLength={3} maxLength={120} /></label><label className="grid gap-1 text-sm">What do you want to build?<Textarea name="goal" required minLength={10} maxLength={5000} /></label><label className="grid gap-1 text-sm">Skills needed (comma separated)<Input name="skills" placeholder="Materials testing, CAD, electronics" /></label><label className="grid gap-1 text-sm">Repository (optional)<Input name="repository" type="url" placeholder="https://" /></label><label className="grid gap-1 text-sm">How to contribute<Textarea name="guide" maxLength={5000} placeholder="Explain the first useful contribution and any contribution license or attribution rules." /></label><p className="text-xs text-muted">Only invited project members can view the workspace, tasks and references. A patent or library resource is optional. External file permissions are managed on their original platform.</p><Button disabled={busy} type="submit">{busy ? "Creating…" : "Create project"}</Button></form></Card>}
    <form className="flex gap-3 rounded-xl border border-line bg-surface p-4" onSubmit={e => { e.preventDefault(); setOffset(0); setQuery(q); }}><Input aria-label="Search projects" value={q} onChange={e => setQ(e.target.value)} maxLength={200} placeholder="Search projects and goals" /><Button type="submit">Search</Button></form>
    {loading ? <SkeletonList rows={3} /> : error ? null : rows.length === 0 ? <EmptyState title="The next project could start with you" description="Start with an idea, invite your collaborators, and bring your references together. No patent required." action={<Button onClick={() => token ? setCreate(true) : router.push("/login?next=%2Fprojects")}>Start a project</Button>} /> : <div className="grid md:grid-cols-2 gap-4">{rows.map(project => <Link href={`/projects/${project.space.id}`} key={project.space.id} className="border border-line rounded-xl bg-surface p-5 hover:border-accent"><span className="text-xs text-accent">{project.stage}</span><h2 className="text-lg font-semibold mt-1">{project.space.name}</h2><p className="text-sm text-muted mt-2 line-clamp-3">{project.goal}</p><p className="text-xs text-muted mt-3">{project.space.member_count} collaborators · {project.resource_title || "Independent project"}</p><div className="flex gap-2 flex-wrap mt-3">{project.skills_needed.map(skill => <span className="text-xs bg-surface-2 px-2 py-1 rounded" key={skill}>{skill}</span>)}</div></Link>)}</div>}
    <div className="flex items-center justify-between border-t border-line pt-5"><Button variant="secondary" disabled={!offset || loading} onClick={() => setOffset(v => Math.max(0, v - 24))}>Previous</Button><span className="text-xs text-muted" aria-live="polite">Page {Math.floor(offset / 24) + 1}</span><Button variant="secondary" disabled={rows.length < 24 || loading || !!error} onClick={() => setOffset(v => v + 24)}>Next</Button></div>
  </div>;
}

export function ProjectWorkspace({ id }: { id: string }) {
  const identity = useAuthStore(s => s.user?.id ?? "anonymous");
  return <ProjectWorkspaceContent key={`${id}:${identity}`} id={id} />;
}

function ProjectWorkspaceContent({ id }: { id: string }) {
  const { accessToken: token, user } = useAuthStore();
  const [project, setProject] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [offset, setOffset] = useState(0);
  const load = useCallback(async () => {
    try { const [page, board] = await Promise.all([request<Project>(`/api/v1/projects/${id}`, { token: token ?? undefined }), request<Task[]>(`/api/v1/projects/${id}/tasks?offset=${offset}`, { token: token ?? undefined })]); setProject(page); setTasks(board); }
    catch (e) { setError(errorMessage(e)); }
  }, [id, token, offset]);
  useEffect(() => { setProject(null); setTasks([]); setError(""); void load(); }, [load]);
  async function action(run: () => Promise<unknown>) { setBusy(true); setError(""); try { await run(); await load(); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); } }
  async function task(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (!token) return; const element = e.currentTarget; const data = new FormData(element);
    await action(async () => { await request(`/api/v1/projects/${id}/tasks`, { method: "POST", token, body: JSON.stringify({ title: String(data.get("title")), description: String(data.get("description")) || null, assigned_to: data.get("self") ? user?.id : null }) }); element.reset(); });
  }
  return <div className="space-y-6"><Link href="/projects" className="text-accent text-sm">← Projects</Link>{error && <p role="alert" className="text-danger">{error}</p>}{!project ? <p role="status">{error ? "Project unavailable." : "Loading project…"}</p> : <>
    <Card className="p-6 space-y-3"><p className="text-sm text-accent">Invite-only project · {project.stage}</p><h1 className="text-3xl font-display">{project.space.name}</h1><p className="whitespace-pre-wrap text-ink-soft">{project.goal}</p><div className="flex flex-wrap gap-3 text-sm">{project.source_url && <a href={project.source_url} target="_blank" rel="noopener noreferrer" className="text-accent underline">Source: {project.resource_title} ↗</a>}{project.repository_url && <a href={project.repository_url} target="_blank" rel="noopener noreferrer" className="text-accent underline">Repository ↗</a>}<Link href={`/dashboard/community/${id}`} className="text-accent">Members & space settings</Link></div><p className="text-sm text-muted">{project.space.member_count} collaborators</p>{token && user?.id === project.space.created_by && <label className="text-sm grid gap-1 max-w-xs">Project stage<select value={project.stage} disabled={busy} onChange={e => void action(() => request(`/api/v1/projects/${id}/stage`, { method: "PATCH", token, body: JSON.stringify({ stage: e.target.value }) }))} className="border border-line rounded p-2 bg-surface">{["idea", "research", "prototype", "testing", "released"].map(stage => <option key={stage}>{stage}</option>)}</select></label>}{!token && <Link href={`/login?next=${encodeURIComponent(`/projects/${id}`)}`} className="text-accent">Sign in to collaborate</Link>}</Card>
    <nav aria-label="Project sections" className="flex flex-wrap gap-2 text-sm">{[["#references", "References"], ["#tasks", "Tasks"], ["#chat", "Encrypted chat"]].map(([href, label]) => <a key={href} href={href} className="rounded-full border border-line bg-surface px-4 py-2 hover:border-accent">{label}</a>)}<Link href={`/dashboard/community/${id}`} className="rounded-full border border-line bg-surface px-4 py-2 hover:border-accent">Members & invitations</Link></nav>
    {project.space.is_member && <ProjectReferences projectId={id} manager={project.space.my_role === "owner" || project.space.my_role === "moderator"} />}
    {project.contribution_guide && <Card className="p-5"><h2 className="font-semibold">How to contribute</h2><p className="text-sm whitespace-pre-wrap mt-2">{project.contribution_guide}</p></Card>}
    <section id="tasks" className="space-y-4 scroll-mt-24"><h2 className="text-xl font-semibold">Team task board</h2>{token && project.space.is_member && <Card className="p-4"><form onSubmit={task} className="grid gap-3"><label className="grid gap-1 text-sm">Task title<Input name="title" required minLength={3} maxLength={240} /></label><label className="grid gap-1 text-sm">Description<Textarea name="description" maxLength={5000} /></label><label className="flex gap-2 text-sm"><input name="self" type="checkbox" />Assign to me</label><Button type="submit" disabled={busy}>Add task</Button></form></Card>}
      <div className="grid md:grid-cols-3 gap-4">{(["todo", "doing", "done"] as const).map(status => <div key={status} className="rounded-xl bg-surface-2 p-3 space-y-3"><h3 className="font-semibold text-sm">{status === "todo" ? "To do" : status === "doing" ? "In progress" : "Done"}</h3>{tasks.filter(t => t.status === status).map(item => <Card className="p-3 space-y-2" key={item.id}><h4 className="text-sm font-medium">{item.title}</h4><p className="text-xs text-muted whitespace-pre-wrap">{item.description}</p>{project.space.is_member && user && token && [item.created_by, item.assigned_to, project.space.created_by].includes(user.id) && <select aria-label={`Status for ${item.title}`} disabled={busy} value={item.status} onChange={e => void action(() => request(`/api/v1/projects/${id}/tasks/${item.id}`, { method: "PATCH", token, body: JSON.stringify({ status: e.target.value, version: item.version }) }))} className="border border-line rounded p-1 text-xs bg-surface"><option value="todo">To do</option><option value="doing">In progress</option><option value="done">Done</option></select>}</Card>)}</div>)}</div><div className="flex items-center justify-between border-t border-line pt-5"><Button variant="secondary" disabled={!offset || busy} onClick={() => setOffset(v => Math.max(0, v - 50))}>Previous tasks</Button><Button disabled={tasks.length < 50 || busy} onClick={() => setOffset(v => v + 50)}>More tasks</Button></div>
    </section>{project.space.is_member && <section id="chat" className="scroll-mt-24"><SecureChat scope="community" scopeId={id} /></section>}
  </>}
  </div>;
}
