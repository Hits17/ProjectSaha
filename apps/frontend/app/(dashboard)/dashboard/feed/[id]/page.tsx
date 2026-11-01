"use client";
import { useEffect,useState } from "react";
import { useParams,useRouter } from "next/navigation";
import Link from "next/link";
import { api,type FeedPost } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Button,ErrorBanner,PageHeader,SkeletonList } from "@/components/ui";
import { PostCard } from "@/components/social/post-card";
import { PostComposer } from "@/components/social/composer";
export default function Page(){const {id}=useParams<{id:string}>();const token=useAuthStore(s=>s.accessToken);const router=useRouter();const [post,setPost]=useState<FeedPost|null>(null);const [error,setError]=useState("");const [revision,setRevision]=useState(0);const [shared,setShared]=useState<string>();
useEffect(()=>{let active=true;setPost(null);setError("");if(!token)return;api.social.post(token,id).then(value=>{if(active)setPost(value);}).catch(e=>{if(active)setError(e.message||"Post unavailable");});return()=>{active=false;};},[token,id,revision]);
return <div className="mx-auto max-w-3xl space-y-5"><PageHeader title="Conversation" description="Share a perspective and keep the discussion moving." actions={<Button href="/dashboard/feed" variant="secondary">Back to feed</Button>}/>{error?<ErrorBanner>{error} <button type="button" onClick={()=>setRevision(v=>v+1)} className="underline">Try again</button></ErrorBanner>:post?<PostCard key={post.id} post={post} onChange={setPost} onRemove={()=>router.replace("/dashboard/feed")} onShare={setShared} initialComments/>:<SkeletonList rows={2}/>} {shared&&<PostComposer sharedLink={shared} onSharedClose={()=>setShared(undefined)} onPosted={p=>router.push(`/dashboard/feed/${p.id}`)}/>}<Link href="/dashboard/feed" className="inline-block text-sm text-accent">← More from your community</Link></div>;}
