import { Suspense } from "react";
import { SocialFeed } from "@/components/social/feed";
import { LoadingRow } from "@/components/ui";
export default function FeedPage(){return <Suspense fallback={<LoadingRow label="Opening the community feed…"/>}><SocialFeed/></Suspense>;}
