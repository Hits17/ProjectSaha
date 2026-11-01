import { InstitutionPage } from "@/components/institutions";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <><div className="space-y-6"><InstitutionPage id={id} /></div></>;
}
