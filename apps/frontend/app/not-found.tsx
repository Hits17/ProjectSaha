import { Button } from "@/components/ui";
export default function NotFound() {
  return <div className="mx-auto max-w-lg py-20 text-center"><p className="eyebrow">Page not found</p><h1 className="mt-4 text-3xl font-semibold">Let’s find your next step.</h1><p className="mt-4 text-muted">This page may have moved or is no longer available. You can explore research or return to your workspace.</p><div className="mt-7 flex flex-wrap justify-center gap-3"><Button href="/explore">Explore research</Button><Button variant="secondary" href="/dashboard">My workspace</Button></div></div>;
}
