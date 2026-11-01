"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { api, type FeedPost } from "@/lib/api";
import { social, type MentionMember } from "@/lib/social";
import { useAuthStore } from "@/store/auth";
import { Button, Card, EmptyState, ErrorBanner, Input, PageHeader, SkeletonList } from "@/components/ui";
import { MemberAvatar } from "./content";
import { PostComposer } from "./composer";
import { PostCard } from "./post-card";

function NetworkPanel() {
  const token=useAuthStore(s=>s.accessToken);const [query,setQuery]=useState("");const [people,setPeople]=useState<MentionMember[]>([]);const [error,setError]=useState("");
  useEffect(()=>{let active=true;setPeople([]);setError("");if(!token||query.trim().length<2)return;const timer=setTimeout(()=>{social.members(token,query.trim()).then(rows=>{if(active)setPeople(rows);}).catch(()=>{if(active)setError("Search is temporarily unavailable.");});},250);return()=>{active=false;clearTimeout(timer);};},[query,token]);
  return <aside className="hidden xl:block"><div className="sticky top-24 space-y-4"><Card className="p-5"><h2 className="text-sm font-semibold">Find your people</h2><p className="mt-2 text-xs text-muted">Connect with researchers and builders across Saha.</p><Input aria-label="Find a member by name" placeholder="Search members…" maxLength={80} value={query} onChange={e=>setQuery(e.target.value)} className="mt-4"/>{error&&<p role="status" className="mt-2 text-xs text-muted">{error}</p>}<div className="mt-3 space-y-3">{people.map(person=><Link href={`/dashboard/members/${person.user_id}`} key={person.user_id} className="flex items-center gap-2 rounded-lg hover:bg-surface-2"><MemberAvatar id={person.user_id} name={person.full_name} hasAvatar={person.has_avatar}/><div className="min-w-0"><p className="truncate text-xs font-semibold">{person.full_name}</p><p className="truncate text-[11px] text-muted">{person.headline||"Saha member"}</p></div></Link>)}</div></Card><Card className="p-5"><p className="eyebrow">Build together</p><h2 className="mt-3 text-lg font-semibold">Take the conversation further.</h2><p className="mt-2 text-xs leading-relaxed text-muted">Find a project, contribute a skill, or bring your institution into the community.</p><div className="mt-4 space-y-3 text-sm font-medium text-accent"><Link href="/projects" className="block">Find a project →</Link><Link href="/institutions" className="block">Meet institutions →</Link><Link href="/dashboard/community" className="block">Join an interest group →</Link></div></Card><p className="px-2 text-xs leading-relaxed text-muted">Share thoughtfully. Choose your audience and respect other people’s work. <Link href="/guide" className="text-accent hover:underline">Getting started</Link></p></div></aside>;
}

export function SocialFeed() {
  const identity=useAuthStore(s=>s.user?.id??"anonymous");return <FeedContent key={identity}/>;
}
function FeedContent() {
  const token=useAuthStore(s=>s.accessToken);const router=useRouter();const params=useSearchParams();const q=params.get("q")||"";
  const [query,setQuery]=useState(q);const [view,setView]=useState("all");const [sort,setSort]=useState("new");
  const [posts,setPosts]=useState<FeedPost[]>([]);const [offset,setOffset]=useState(0);const [hasMore,setHasMore]=useState(false);const [loading,setLoading]=useState(true);const [error,setError]=useState("");const [revision,setRevision]=useState(0);const [shared,setShared]=useState<string>();
  useEffect(()=>{setQuery(q);setOffset(0);},[q]);
  useEffect(()=>{
    let active=true;setLoading(true);setError("");if(offset===0)setPosts([]);
    const request=view==="saved"&&token?api.social.saved(token,offset,20):api.social.feed(token,{sort,following_only:view==="following",q,limit:20,offset});
    request.then(rows=>{if(!active)return;setPosts(prev=>offset===0?rows:[...prev,...rows.filter(p=>!prev.some(old=>old.id===p.id))]);setHasMore(rows.length===20);}).catch(e=>{if(active)setError(e.message||"Could not load your feed");}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[token,view,sort,q,offset,revision]);
  function replace(post:FeedPost){setPosts(rows=>rows.map(row=>row.id===post.id?post:row.author.user_id===post.author.user_id?{...row,is_following_author:post.is_following_author}:row));}
  function posted(){setShared(undefined);setView("all");setOffset(0);setRevision(v=>v+1);if(q)router.replace("/dashboard/feed");}
  return <div className="space-y-6"><PageHeader title="Community feed" description="Ideas, progress and conversations from people building together."/>
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_240px]"><div className="min-w-0 space-y-4"><PostComposer onPosted={posted} sharedLink={shared} onSharedClose={()=>setShared(undefined)}/>
      <div className="rounded-xl border border-line bg-surface p-3"><div className="flex flex-wrap items-center gap-2"><div role="group" aria-label="Feed selection" className="flex gap-1">{[["all","For you"],["following","Following"],["saved","Saved"]].map(([key,label])=><button key={key} type="button" aria-pressed={view===key} onClick={()=>{setView(key);setOffset(0);}} className={`rounded-lg px-3 py-2 text-sm font-medium ${view===key?"bg-accent-soft text-accent":"text-muted hover:bg-surface-2"}`}>{label}</button>)}</div>{view!=="saved"&&<label className="ml-auto text-xs text-muted">Sort <select aria-label="Sort feed" value={sort} onChange={e=>{setSort(e.target.value);setOffset(0);}} className="rounded-lg border border-line bg-surface px-2"><option value="new">Latest</option><option value="hot">Trending</option><option value="top">Top rated</option></select></label>}</div>{view!=="saved"&&<form role="search" className="mt-3 flex gap-2 border-t border-line pt-3" onSubmit={e=>{e.preventDefault();setOffset(0);router.push(`/dashboard/feed${query.trim()?`?q=${encodeURIComponent(query.trim())}`:""}`,{scroll:false});setRevision(v=>v+1);}}><Input type="search" aria-label="Search posts and hashtags" value={query} maxLength={200} onChange={e=>setQuery(e.target.value)} placeholder="Search posts or #topics"/><Button type="submit" variant="secondary" size="sm">Search</Button></form>}</div>
      {q&&view!=="saved"&&<div className="flex justify-between text-xs text-muted"><span>Results for “{q}”</span><Link href="/dashboard/feed" className="text-accent">Clear search</Link></div>}
      {error&&<ErrorBanner>{error} <button type="button" className="underline" onClick={()=>setRevision(v=>v+1)}>Try again</button></ErrorBanner>}
      {loading&&!posts.length?<SkeletonList rows={3}/>:!posts.length&&!error?<EmptyState title={view==="saved"?"Keep the ideas you want to return to":view==="following"?"Your network starts with a connection":"Start the conversation"} description={view==="saved"?"Save a post and you’ll find it here. Saved posts still follow their original visibility rules.":view==="following"?"Open a member’s profile or use Follow on a post to hear more from them.":q?"Try another topic or remove the search filter.":"Share your progress, ask a question, or introduce what you’re building."}/>:posts.map(post=><PostCard key={post.id} post={post} onChange={replace} onRemove={id=>setPosts(rows=>rows.filter(p=>p.id!==id))} onShare={setShared}/>)}
      {hasMore&&!error&&<Button variant="secondary" className="w-full" loading={loading} onClick={()=>setOffset(v=>v+20)}>Load more posts</Button>}
    </div><NetworkPanel/></div>
  </div>;
}
