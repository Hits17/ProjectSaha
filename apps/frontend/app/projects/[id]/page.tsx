import { ProjectWorkspace } from "@/components/open-projects";
export default async function Page({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <><div className="space-y-6"><ProjectWorkspace id={id} /></div></>; }
