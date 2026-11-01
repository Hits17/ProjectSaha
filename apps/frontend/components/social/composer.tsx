"use client";
import { useEffect, useRef, useState } from "react";
import { api, type DisclosureCheck, type FeedPost, type PostKind, type PostVisibility, type SocialMedia } from "@/lib/api";
import { social } from "@/lib/social";
import { mentionText } from "@/lib/mentions";
import { useAuthStore } from "@/store/auth";
import { Button, Card, Dialog, ErrorBanner, Input, useToast } from "@/components/ui";
import { MemberAvatar, MentionInput } from "./content";

interface DraftMedia { key: string; file: File; alt: string; uploaded?: SocialMedia }
function Preview({ file }: { file: File }) {
  const [url,setUrl] = useState("");
  useEffect(()=>{const object=URL.createObjectURL(file);setUrl(object);return()=>URL.revokeObjectURL(object);},[file]);
  return file.type.startsWith("video/") ? <video src={url} controls preload="metadata" className="h-32 w-full rounded-lg bg-ink object-contain" /> : <img src={url} alt="Attachment preview" className="h-32 w-full rounded-lg object-cover" />;
}

export function PostComposer({ onPosted, communityId, publicOnly = false, sharedLink, onSharedClose }: {
  onPosted: (post: FeedPost)=>void; communityId?: string; publicOnly?: boolean; sharedLink?: string; onSharedClose?: ()=>void;
}) {
  const {user,accessToken:token}=useAuthStore(); const toast=useToast(); const picker=useRef<HTMLInputElement>(null);
  const [open,setOpen]=useState(false); const [body,setBody]=useState(""); const [kind,setKind]=useState<PostKind>("update");
  const [visibility,setVisibility]=useState<PostVisibility>(publicOnly?"public":"members");const [title,setTitle]=useState("");
  const [link,setLink]=useState("");const [showLink,setShowLink]=useState(false);const [media,setMedia]=useState<DraftMedia[]>([]);
  const [busy,setBusy]=useState(false);const [error,setError]=useState("");const [progress,setProgress]=useState("");
  const [warning,setWarning]=useState<DisclosureCheck|null>(null);const [acknowledged,setAcknowledged]=useState(false);
  const dialogOpen=open || !!sharedLink; const effectiveLink=sharedLink || link;
  const canPost=!!user&&(user.email_verified || user.kyc_status==="verified");
  function selectFiles(files: FileList|null) {
    if (!files)return;setError("");
    const next=[...files];const allowed=["image/jpeg","image/png","image/webp","video/mp4","video/webm"];
    if(media.length+next.length>6){setError("Choose up to six attachments.");return;}
    if([...media.map(x=>x.file),...next].filter(f=>f.type.startsWith("video/")).length>1){setError("Choose at most one video per post.");return;}
    if(next.some(f=>!allowed.includes(f.type)||f.size>(f.type.startsWith("image/")?8:40)*1024*1024)){setError("Use JPEG, PNG or WebP images up to 8 MB, or an MP4/WebM video up to 40 MB.");return;}
    setMedia(current=>[...current,...next.map(file=>({key:crypto.randomUUID(),file,alt:""}))]);
  }
  async function remove(item: DraftMedia) {
    if(busy)return;setBusy(true);
    try {if(item.uploaded&&token)await social.removeDraft(token,item.uploaded.id);setMedia(rows=>rows.filter(x=>x.key!==item.key));}
    catch(e){setError(e instanceof Error?e.message:"Could not remove attachment");}finally{setBusy(false);}
  }
  async function publish() {
    if(!token||!body.trim()||busy)return;setBusy(true);setError("");
    try {
      if(visibility==="public"&&!acknowledged){
        const check=await api.social.checkDisclosure(token,body,title||null,visibility);
        if(check.risk!=="none"&&check.warning){setWarning(check);return;}
      }
      const ids:string[]=[];
      for(let i=0;i<media.length;i++){
        const item=media[i];setProgress(`Uploading attachment ${i+1} of ${media.length}…`);
        const uploaded=item.uploaded||await social.upload(token,item.file,item.alt);
        setMedia(rows=>rows.map(row=>row.key===item.key?{...row,uploaded}:row));ids.push(uploaded.id);
      }
      setProgress("Publishing your post…");
      const post=await api.social.create(token,{body,title:title.trim()||null,kind,visibility,community_id:communityId,link_url:effectiveLink.trim()||null,media_ids:ids,acknowledged_disclosure:acknowledged});
      onPosted(post);setBody("");setTitle("");setMedia([]);setLink("");setShowLink(false);setWarning(null);setAcknowledged(false);setOpen(false);onSharedClose?.();
      toast.success(post.moderation_status==="held"?"Post submitted for review":"Your post is published");
    }catch(e){setError(e instanceof Error?e.message:"Could not publish your post");}finally{setBusy(false);setProgress("");}
  }
  if(!user||!token)return null;
  return <><Card className="p-4 sm:p-5"><div className="flex items-center gap-3"><MemberAvatar id={user.id} name={user.full_name} hasAvatar={user.has_avatar} /><button type="button" onClick={()=>setOpen(true)} className="min-h-12 flex-1 rounded-full border border-line-strong px-5 text-left text-sm font-medium text-muted transition hover:bg-surface-2">{body?"Continue your draft…":"Start a post, share what you’re building…"}</button></div><div className="mt-4 grid grid-cols-3 gap-1 border-t border-line pt-3">{[["▧","Photo","image/jpeg,image/png,image/webp"],["▷","Video","video/mp4,video/webm"],["↗","Share a link",""]].map(([symbol,label,accept])=><button key={label} type="button" onClick={()=>{setOpen(true);if(accept){requestAnimationFrame(()=>{if(picker.current){picker.current.accept=accept;picker.current.click();}});}else setShowLink(true);}} className="flex min-h-10 items-center justify-center gap-2 rounded-lg text-sm font-medium text-ink-soft hover:bg-surface-2"><span className="text-lg text-accent" aria-hidden>{symbol}</span>{label}</button>)}</div></Card>
    <Dialog open={dialogOpen} onClose={()=>{if(!busy){setOpen(false);onSharedClose?.();}}} title={sharedLink?"Share with your network":"Create a post"} className="max-w-2xl max-h-[90dvh] overflow-y-auto">
      <div className="space-y-4"><div className="flex items-center gap-3"><MemberAvatar id={user.id} name={user.full_name} hasAvatar={user.has_avatar} /><div><p className="font-semibold">{user.full_name}</p><label className="flex items-center gap-2 text-xs text-muted">Audience<select disabled={publicOnly||busy} aria-label="Post audience" value={visibility} onChange={e=>{setVisibility(e.target.value as PostVisibility);setAcknowledged(false);setWarning(null);}} className="rounded-lg border border-line bg-surface px-2 py-1 text-xs"><option value="members">Saha members</option><option value="public">Anyone · public</option></select></label></div></div>
      {!canPost&&<p className="rounded-lg bg-warning-soft p-3 text-sm">Confirm your email in account security before posting.</p>}
      <fieldset disabled={busy} className="space-y-4 disabled:opacity-70"><div className="flex flex-wrap gap-2" aria-label="Post type">{(["update","question","showcase"] as PostKind[]).map(value=><button type="button" key={value} aria-pressed={kind===value} onClick={()=>setKind(value)} className={`rounded-full px-3 py-1.5 text-xs font-medium capitalize ${kind===value?"bg-accent-soft text-accent":"bg-surface-2 text-muted"}`}>{value}</button>)}</div>
      {kind!=="update"&&<Input aria-label="Post title" value={title} maxLength={300} placeholder={kind==="question"?"What would you like to ask?":"Give your work a title"} onChange={e=>{setTitle(e.target.value);setAcknowledged(false);setWarning(null);}} />}
      <MentionInput value={body} onChange={v=>{setBody(v);setAcknowledged(false);setWarning(null);}} />
      <div className="flex justify-between gap-2 text-xs text-muted"><span>Type @ and a name to mention a member. Add #topics.</span><span>{mentionText(body).text.length.toLocaleString()}/10,000</span></div>
      {(showLink||sharedLink)&&<label className="block text-xs font-medium text-ink-soft">Link<Input type="url" value={effectiveLink} disabled={!!sharedLink} placeholder="https://" maxLength={1000} onChange={e=>setLink(e.target.value)} /></label>}
      <div className="grid gap-3 sm:grid-cols-2">{media.map(item=><div key={item.key} className="rounded-xl border border-line p-3"><Preview file={item.file} /><div className="mt-2 flex items-center justify-between gap-2"><p className="truncate text-xs text-muted">{item.file.name}</p><button type="button" aria-label={`Remove ${item.file.name}`} onClick={()=>void remove(item)} className="text-xs text-danger">Remove</button></div><label className="mt-2 block text-xs text-ink-soft">Describe this {item.file.type.startsWith("video/")?"video":"image"}<Input value={item.alt} disabled={!!item.uploaded} maxLength={500} placeholder="A short description for accessibility" onChange={e=>setMedia(rows=>rows.map(r=>r.key===item.key?{...r,alt:e.target.value}:r))} className="mt-1" /></label></div>)}</div>
      <input ref={picker} type="file" multiple accept="image/jpeg,image/png,image/webp,video/mp4,video/webm" className="hidden" aria-label="Choose post media" onChange={e=>{selectFiles(e.target.files);e.target.value="";}} />
      <div className="flex flex-wrap gap-2"><Button type="button" variant="secondary" size="sm" onClick={()=>{if(picker.current){picker.current.accept="image/jpeg,image/png,image/webp,video/mp4,video/webm";picker.current.click();}}}>＋ Add media</Button><Button type="button" variant="ghost" size="sm" onClick={()=>setShowLink(v=>!v)}>Add a link</Button></div>
      </fieldset>
      {warning&&<div className="space-y-3 rounded-xl border border-warning/30 bg-warning-soft p-4 text-sm"><p className="font-semibold">Before you post publicly</p><p>{warning.warning}</p><label className="flex items-start gap-2"><input type="checkbox" checked={acknowledged} onChange={e=>setAcknowledged(e.target.checked)} />I reviewed this warning and want to publish publicly.</label>{!publicOnly&&<button type="button" onClick={()=>{setVisibility("members");setWarning(null);setAcknowledged(false);}} className="text-accent underline">Change audience to Saha members</button>}</div>}
      {error&&<ErrorBanner>{error}</ErrorBanner>}<p role="status" className="text-xs text-muted">{progress||`${visibility==="public"?"Anyone can view this post and its media.":"Only signed-in members can view this post and its media."} Posts are not encrypted chat.`}</p>
      <div className="flex items-center justify-between border-t border-line pt-4"><span className="text-xs text-muted">{media.length}/6 attachments · 1 video maximum</span><Button onClick={()=>void publish()} loading={busy} disabled={!canPost||!body.trim()||body.length>10000||(!!warning&&!acknowledged)}>Post</Button></div></div>
    </Dialog>
  </>;
}
