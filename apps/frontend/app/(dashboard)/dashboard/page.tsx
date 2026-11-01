"use client";
import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { Button, PageHeader } from "@/components/ui";
import * as Icon from "@/components/ui/icons";

export default function OpenInnovationHub() {
  const user = useAuthStore(s => s.user);
  return <div className="space-y-8">
    <PageHeader title={`Welcome${user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}. What’s next?`} description="Your place to collect ideas, meet collaborators and move shared work forward." actions={<Button href="/explore"><Icon.Search className="size-4" />Explore research</Button>} />
    {user && !user.email_verified && user.kyc_status !== "verified" && <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/20 bg-warning-soft p-4 text-sm"><p>Confirm your email to post, create spaces and contribute to projects.</p><Link href="/dashboard/security" className="font-semibold text-ink underline">Confirm email →</Link></div>}
    <section className="rounded-2xl border border-line bg-surface p-6 sm:p-8"><p className="eyebrow">Follow your curiosity</p><h2 className="mt-3 text-2xl font-semibold">A useful source can be the start of something.</h2><p className="mt-2 max-w-xl text-sm text-muted">Explore the library, save what interests you and connect that research to a project.</p><form action="/explore" className="mt-5 flex flex-col gap-3 sm:flex-row"><label className="flex-1"><span className="sr-only">Search research</span><input name="q" type="search" maxLength={255} placeholder="Search a topic, invention or patent number" className="w-full rounded-lg border border-line-strong bg-canvas px-4 py-3 text-sm" /></label><Button type="submit">Find research</Button></form></section>
    <section aria-label="Your workspace tools" className="grid gap-4 sm:grid-cols-2">{[
      { href: "/dashboard/collections", title: "My collections", text: "Return to saved sources, research notes and searches.", icon: Icon.BookOpen },
      { href: "/projects", title: "Projects", text: "Find a project and see where your skills can help.", icon: Icon.Package },
      { href: "/dashboard/feed", title: "Community feed", text: "Share progress, ask questions and join the conversation.", icon: Icon.Users },
      { href: "/institutions", title: "Institutions", text: "Connect with labs, universities and creative communities.", icon: Icon.Building },
    ].map(({ href, title, text, icon: Glyph }) => <Link key={href} href={href} className="group flex items-start gap-4 rounded-xl border border-line bg-surface p-5 hover:border-accent"><span className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent"><Glyph className="size-5" /></span><div className="flex-1"><h2 className="text-base font-semibold">{title}</h2><p className="mt-1 text-sm text-muted">{text}</p></div><Icon.ChevronRight className="mt-1 size-4 text-muted group-hover:text-accent" /></Link>)}</section>
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl bg-surface-2 p-5"><div><h2 className="text-sm font-semibold">New to Saha?</h2><p className="mt-1 text-sm text-muted">See how research, communities and projects connect.</p></div><Link href="/guide" className="text-sm font-semibold text-accent">Find your way around →</Link></div>
  </div>;
}
