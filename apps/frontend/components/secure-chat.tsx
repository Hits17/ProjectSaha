"use client";

import { useCallback, useEffect, useState } from "react";
import { api, request } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Button, Card, Input } from "@/components/ui";

interface ChatStatus { configured: boolean; matrix_user_id: string | null; client_url: string | null; homeserver_url: string | null }
interface Room { room_id: string; url: string; transport: "matrix"; end_to_end_encrypted: boolean }

export function SecureChat({ scope, scopeId }: { scope: "community" | "proposal" | "transaction"; scopeId: string }) {
  const identity = useAuthStore(s => s.user?.id ?? "anonymous");
  return <SecureChatContent key={`${scope}:${scopeId}:${identity}`} scope={scope} scopeId={scopeId} />;
}

function SecureChatContent({ scope, scopeId }: { scope: "community" | "proposal" | "transaction"; scopeId: string }) {
  const token = useAuthStore(s => s.accessToken);
  const [status, setStatus] = useState<ChatStatus | null>(null);
  const [proof, setProof] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [room, setRoom] = useState<Room | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    if (!token) return;
    try { setStatus(await request<ChatStatus>("/api/v1/chat/status", { token })); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not load encrypted chat"); }
  }, [token]);
  useEffect(() => { setStatus(null); setRoom(null); setProof(""); void load(); }, [load, scopeId, scope]);
  async function link(e: React.FormEvent) {
    e.preventDefault(); if (!token) return; setBusy(true); setError("");
    const accessToken = proof; setProof("");
    try {
      const stepUp = await api.auth.stepUp(token, password, mfaCode || undefined);
      setStatus(await request<ChatStatus>("/api/v1/chat/identity", { method: "POST", token, stepUpToken: stepUp.step_up_token, body: JSON.stringify({ access_token: accessToken }) }));
    }
    catch (e) { setError(e instanceof Error ? e.message : "Could not link chat account"); } finally { setBusy(false); setPassword(""); setMfaCode(""); }
  }
  async function open() {
    if (!token) return; setBusy(true); setError(""); setRoom(null);
    try { setRoom(await request<Room>(`/api/v1/chat/rooms/${scope}/${scopeId}`, { method: "POST", token })); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not open encrypted chat"); } finally { setBusy(false); }
  }
  return <Card className="p-5 space-y-4"><div><h2 className="font-semibold text-lg">End-to-end encrypted chat</h2><p className="text-sm text-muted mt-1">Private conversations open in Element. Messages are encrypted on participants’ devices; Saha does not store message plaintext or decryption keys.</p></div>
    {error && <p role="alert" className="text-danger text-sm">{error}</p>}
    {!status ? <p role="status" className="text-sm">{error ? "Chat status unavailable." : "Checking encrypted chat…"}</p> : !status.configured ? <p className="text-sm text-muted" role="status">Encrypted chat is awaiting administrator setup. Plaintext messaging is disabled. Public posts and comments remain available for open discussion.</p> : !status.matrix_user_id ? <div className="space-y-3"><p className="text-sm">First sign in to your personal account in <a className="text-accent underline" href={status.client_url!} target="_blank" rel="noopener noreferrer">Saha’s Element client ↗</a>. Then link it to Saha.</p><details className="text-sm text-muted"><summary>How account linking works</summary><p className="mt-2">Use an access token from your Element account’s advanced settings. Saha uses it once to confirm account ownership on {status.homeserver_url}, then discards it. It is not stored. Never provide a password, recovery key or encryption key. After linking, you can revoke this access token in Element. For ongoing chat, use a separate signed-in Element session.</p></details><form className="space-y-2" onSubmit={link}><label className="text-sm grid gap-1">Matrix account access token<Input type="password" autoComplete="off" value={proof} onChange={e => setProof(e.target.value)} minLength={10} maxLength={4096} required /></label><label className="text-sm grid gap-1">Confirm your Saha password<Input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} /></label><label className="text-sm grid gap-1">Saha authenticator code (if enabled)<Input inputMode="numeric" autoComplete="one-time-code" value={mfaCode} onChange={e => setMfaCode(e.target.value)} /></label><Button type="submit" disabled={busy || proof.length < 10 || !password}>{busy ? "Confirming account…" : "Link personal chat account"}</Button></form></div> : <div className="space-y-3"><p className="text-sm text-muted">Chat account: {status.matrix_user_id}</p><Button onClick={open} disabled={busy}>{busy ? "Preparing encrypted room…" : "Prepare secure conversation"}</Button>{room && <div className="space-y-2"><a href={room.url} target="_blank" rel="noopener noreferrer" className="inline-block px-4 py-2 rounded bg-ink text-white text-sm">Open encrypted conversation in Element ↗</a><p className="text-xs text-muted">Accept the room invitation in Element. Verify your collaborators’ devices and keep your recovery key safe. Space membership controls invitations; removing a member stops future access but cannot erase messages they already received.</p></div>}</div>}
    <p className="text-xs text-muted">Older Saha chat was not end-to-end encrypted and is not copied into this room. Public institution posts and comments are public discussion, not private chat.</p>
  </Card>;
}
