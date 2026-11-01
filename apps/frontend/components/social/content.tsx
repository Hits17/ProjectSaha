"use client";
import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { Avatar } from "@/components/profile-menu";
import { Button, Dialog } from "@/components/ui";
import { social, socialBlob, type MentionMember } from "@/lib/social";
import { editMentionText, insertMention, mentionText } from "@/lib/mentions";
import type { SocialMedia } from "@/lib/api";

export function MemberAvatar({ id, name, hasAvatar, large = false }: { id: string; name: string; hasAvatar?: boolean; large?: boolean }) {
  const token = useAuthStore(s => s.accessToken);
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    setSrc(null);
    if (!hasAvatar || !token) return;
    const controller = new AbortController(); let object: string | null = null;
    socialBlob(`/api/v1/users/${id}/avatar`, token, controller.signal).then(blob => {
      if (controller.signal.aborted) return;
      object = URL.createObjectURL(blob); setSrc(object);
    }).catch(() => {});
    return () => { controller.abort(); if (object) URL.revokeObjectURL(object); };
  }, [id, hasAvatar, token]);
  return <Avatar src={src} name={name} className={large ? "size-14 text-base" : "size-10 text-sm"} />;
}

export function RichText({ text }: { text: string }) {
  const parts: React.ReactNode[] = []; let end = 0;
  const pattern = /@\[([^\]\n]{1,255})\]\(([0-9a-fA-F-]{36})\)|(https?:\/\/[^\s<>]+)|(#[\p{L}\p{N}_]+)/gu;
  for (const match of text.matchAll(pattern)) {
    parts.push(text.slice(end, match.index));
    if (match[2]) parts.push(<Link key={match.index} href={`/dashboard/members/${match[2]}`} className="font-medium text-accent hover:underline">@{match[1]}</Link>);
    else if (match[3]) parts.push(<a key={match.index} href={match[3]} target="_blank" rel="noopener noreferrer" className="break-all text-accent hover:underline">{match[3]}</a>);
    else parts.push(<Link key={match.index} href={`/dashboard/feed?q=${encodeURIComponent(match[4])}`} className="font-medium text-accent hover:underline">{match[4]}</Link>);
    end = match.index! + match[0].length;
  }
  parts.push(text.slice(end));
  return <span className="whitespace-pre-wrap break-words">{parts}</span>;
}

export function MentionInput({ value, onChange, placeholder = "Share an idea, ask a question or mention someone with @…", maxLength = 10000, rows = 5, label = "Post text" }: {
  value: string; onChange: (value: string) => void; placeholder?: string; maxLength?: number; rows?: number; label?: string;
}) {
  const token = useAuthStore(s => s.accessToken);
  const input = useRef<HTMLTextAreaElement>(null); const listId = useId();
  const [query, setQuery] = useState<{ text: string; start: number; end: number } | null>(null);
  const [members, setMembers] = useState<MentionMember[]>([]); const [active, setActive] = useState(0);
  const plain = mentionText(value).text;
  useEffect(() => {
    let alive = true; setMembers([]); setActive(0);
    if (!query || query.text.length < 2 || !token) return;
    const timer = setTimeout(() => { social.members(token, query.text).then(result => { if (alive) setMembers(result); }).catch(() => {}); }, 200);
    return () => { alive = false; clearTimeout(timer); };
  }, [query, token]);
  function findQuery(text: string, caret: number) {
    const match = /(?:^|\s)@([^@\n]{0,50})$/.exec(text.slice(0,caret));
    setQuery(match ? { text:match[1], start:caret-match[1].length-1, end:caret } : null);
  }
  function choose(member: MentionMember) {
    if (!query) return;
    const next = insertMention(value, query.start, query.end, member); onChange(next.raw); setQuery(null); setMembers([]);
    requestAnimationFrame(() => { input.current?.focus(); input.current?.setSelectionRange(next.caret,next.caret); });
  }
  return <div className="relative"><textarea ref={input} aria-label={label} aria-autocomplete="list" aria-controls={members.length ? listId : undefined} aria-activedescendant={members.length ? `${listId}-${active}` : undefined}
    value={plain} placeholder={placeholder} rows={rows} maxLength={maxLength}
    onChange={e => { onChange(editMentionText(value,e.target.value)); findQuery(e.target.value,e.target.selectionStart); }}
    onClick={e => findQuery(plain,e.currentTarget.selectionStart)}
    onKeyDown={e => { if (e.key === "Escape") { e.stopPropagation(); setQuery(null); setMembers([]); } if (!members.length) return; if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); setActive(i => (i+(e.key === "ArrowDown" ? 1 : members.length-1))%members.length); } if (e.key === "Enter") { e.preventDefault(); choose(members[active]); } }}
    className="w-full resize-y rounded-xl border border-line bg-surface px-4 py-3 text-sm leading-relaxed placeholder:text-muted" />
    {members.length > 0 && <div id={listId} role="listbox" aria-label="Mention a member" className="absolute left-0 right-0 top-full z-20 max-h-56 overflow-y-auto rounded-xl border border-line bg-surface p-1 shadow-lg">{members.map((member,index) => <button key={member.user_id} id={`${listId}-${index}`} role="option" aria-selected={active === index} type="button" onMouseDown={e => e.preventDefault()} onClick={() => choose(member)} className={`flex w-full items-center gap-3 rounded-lg p-3 text-left ${index === active ? "bg-accent-soft" : "hover:bg-surface-2"}`}><MemberAvatar id={member.user_id} name={member.full_name} hasAvatar={member.has_avatar} /><span><span className="block text-sm font-semibold">{member.full_name}</span><span className="block text-xs text-muted">{member.headline || "Saha member"}</span></span></button>)}</div>}
  </div>;
}

function MediaItem({ media }: { media: SocialMedia }) {
  const token = useAuthStore(s => s.accessToken);
  const host = useRef<HTMLDivElement>(null); const video = media.content_type.startsWith("video/");
  const [requested, setRequested] = useState(false); const [src,setSrc] = useState<string | null>(null);
  const [error,setError] = useState(false); const [zoom,setZoom] = useState(false); const [attempt,setAttempt] = useState(0);
  useEffect(() => {
    if (video || !host.current) return;
    const observer = new IntersectionObserver(entries => { if (entries.some(e=>e.isIntersecting)) { setRequested(true); observer.disconnect(); } },{rootMargin:"200px"});
    observer.observe(host.current); return ()=>observer.disconnect();
  },[video]);
  useEffect(() => {
    if (!requested) return;
    const controller = new AbortController(); let object: string | null = null; setSrc(null); setError(false);
    socialBlob(`/api/v1/social/media/${media.id}`,token,controller.signal).then(blob=> { if (controller.signal.aborted) return; object=URL.createObjectURL(blob); setSrc(object); }).catch(()=>{if (!controller.signal.aborted)setError(true);});
    return ()=>{controller.abort(); if(object)URL.revokeObjectURL(object);};
  },[media.id, token, requested, attempt]);
  return <div ref={host} className="grid min-h-48 place-items-center overflow-hidden rounded-xl bg-surface-2">
    {src ? video ? <video src={src} controls playsInline preload="metadata" aria-label={media.alt_text || "Video attachment"} className="max-h-[520px] w-full" /> : <><button type="button" className="w-full" aria-label="Expand image" onClick={()=>setZoom(true)}><img src={src} alt={media.alt_text || "Image shared with this post"} className="max-h-[540px] w-full object-contain" /></button><Dialog open={zoom} onClose={()=>setZoom(false)} title="Post image" className="max-w-4xl"><img src={src} alt={media.alt_text || "Image shared with this post"} className="max-h-[70dvh] w-full object-contain" /></Dialog></> : <div className="p-5 text-center text-sm text-muted">{error ? <><p>Media couldn’t be loaded.</p><Button variant="ghost" onClick={()=>setAttempt(v=>v+1)}>Try again</Button></> : video && !requested ? <><Button variant="secondary" onClick={()=>setRequested(true)}>▶ Load video</Button><p className="mt-2 text-xs">{(media.byte_size/1024/1024).toFixed(1)} MB · {media.alt_text || "Video"}</p></> : <p role="status">Loading image or video…</p>}</div>}
  </div>;
}
export function MediaGallery({ media }: { media: SocialMedia[] }) { return media.length ? <div className={`grid gap-2 ${media.length > 1 ? "sm:grid-cols-2" : ""}`}>{media.map(item=><MediaItem key={item.id} media={item} />)}</div> : null; }

export function LinkAttachment({ url }: { url: string }) {
  let parsed: URL; try { parsed = new URL(url); if (!['http:','https:'].includes(parsed.protocol)) return null; } catch { return null; }
  return <a href={url} target="_blank" rel="noopener noreferrer" className="block overflow-hidden rounded-xl border border-line bg-surface-2 p-4 hover:border-accent"><p className="text-xs font-medium uppercase tracking-wide text-muted">Shared link · {parsed.hostname}</p><p className="mt-1 truncate text-sm font-medium text-accent">{parsed.pathname === "/" ? parsed.hostname : parsed.pathname} ↗</p></a>;
}
