"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type Community, type CommunityMember } from "@/lib/api";
import { institutions, type PrivateSpaceRecord } from "@/lib/institutions";
import { useAuthStore } from "@/store/auth";
import { SecureChat } from "@/components/secure-chat";
import { Button, Card, Input } from "@/components/ui";

export default function CommunityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const identity = useAuthStore(s => s.user?.id ?? "anonymous");
  return <CommunityDetails key={`${id}:${identity}`} />;
}

function CommunityDetails() {
  const { id } = useParams<{ id: string }>();
  const { accessToken: token, user } = useAuthStore();
  const [space, setSpace] = useState<(Community & { is_institution?: boolean }) | null>(null);
  const [members, setMembers] = useState<CommunityMember[]>([]);
  const [record, setRecord] = useState<PrivateSpaceRecord | null>(null);
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    if (!token) return;
    try {
      const result = await api.communities.get(token, id); setSpace(result);
      setMembers(await api.communities.members(token, id));
    } catch (e) { setError(e instanceof Error ? e.message : "Could not load space"); }
  }, [token, id]);
  useEffect(() => { setSpace(null); setMembers([]); setRecord(null); setError(""); void load(); }, [load]);
  async function action(run: () => Promise<unknown>) {
    setBusy(true); setError(""); try { await run(); await load(); } catch (e) { setError(e instanceof Error ? e.message : "Could not update space"); } finally { setBusy(false); }
  }
  const owner = space?.created_by === user?.id;
  const manager = owner || space?.my_role === "moderator";
  return <div className="space-y-5"><Link href="/dashboard/community" className="text-accent text-sm">← Communities</Link>{error && <p role="alert" className="text-danger">{error}</p>}
    {!space ? <p role="status">{error ? "Space unavailable." : "Loading space…"}</p> : <>
      <Card className="p-6"><p className="text-xs text-muted">{space.visibility} · {space.topic.replaceAll("_", " ")}</p><h1 className="text-3xl font-display mt-2">{space.name}</h1><p className="text-ink-soft whitespace-pre-wrap mt-3">{space.description}</p><div className="flex flex-wrap items-center gap-3 mt-4 text-sm"><span>{space.member_count} members</span>{space.is_institution && <Link href={`/institutions/${id}`} className="text-accent underline">Institution page & discussion</Link>}{!space.is_member && space.visibility === "public" && token && <Button disabled={busy} onClick={() => action(() => api.communities.join(token, id))}>Join space</Button>}{space.is_member && !owner && token && <Button disabled={busy} onClick={() => { if (window.confirm("Leave this space? Future encrypted chat access will be revoked.")) void action(() => api.communities.leave(token, id)); }}>Leave space</Button>}</div></Card>
      {space.is_member ? <SecureChat scope="community" scopeId={id} /> : <Card className="p-5 text-muted">Join this space to participate in its private encrypted chat. Public institution discussion is available on its page.</Card>}
      {(owner || user?.role === "admin") && token && <Card className="p-5 space-y-2"><h2 className="font-semibold">Private space reference</h2><p className="text-xs text-muted">Visible only to this space’s owner and Saha administrators.</p><Button onClick={async () => { try { setRecord(await institutions.private(token, id)); } catch (e) { setError(e instanceof Error ? e.message : "Access denied"); } }}>Show internal reference</Button>{record && <p className="text-sm"><code>{record.reference}</code></p>}</Card>}
      <Card className="p-5 space-y-4"><h2 className="font-semibold">Members</h2>{manager && token && <form className="flex gap-2" onSubmit={e => { e.preventDefault(); void action(async () => { await api.communities.addMember(token, id, email); setEmail(""); }); }}><Input type="email" aria-label="Member email" value={email} onChange={e => setEmail(e.target.value)} placeholder="Invite an existing member by email" required /><Button disabled={busy} type="submit">Add member</Button></form>}<ul className="divide-y divide-line">{members.map(member => <li key={member.user_id} className="py-3 flex justify-between gap-3"><div><span className="font-medium text-sm">{member.full_name}</span><span className="text-xs text-muted ml-2">{member.role}</span>{member.email && <p className="text-xs text-muted">{member.email}</p>}</div>{manager && member.role !== "owner" && member.user_id !== user?.id && token && <button className="text-danger text-xs" disabled={busy} onClick={() => { if (window.confirm(`Remove ${member.full_name}? Future encrypted chat access will be revoked.`)) void action(() => api.communities.removeMember(token, id, member.user_id)); }}>Remove</button>}</li>)}</ul></Card>
    </>}
  </div>;
}
