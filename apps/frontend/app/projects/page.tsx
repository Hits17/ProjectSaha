import { ProjectDirectory } from "@/components/open-projects";
export default async function Page({ searchParams }: { searchParams: Promise<{ source?: string }> }) { const { source } = await searchParams; return <><div className="space-y-6"><ProjectDirectory source={source} /></div></>; }
