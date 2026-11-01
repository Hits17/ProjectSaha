import Link from "next/link";
import { PageHeader } from "@/components/ui";
import { workspaceNavigation } from "@/lib/navigation";

export default function GuidePage() {
  return <div className="space-y-10"><PageHeader title="Find your way around Saha" description="Start with an idea. Keep useful research. Find people to build with. Here’s how the pieces fit together." />
    <section className="grid gap-4 md:grid-cols-3">{[
      ["01 · Discover", "/explore", "Explore patents & research", "Search the curated library, follow original sources and review rights evidence. Save useful resources to your private collections."],
      ["02 · Connect", "/institutions", "Meet your collaborators", "Explore institutions, join an interest group and use the community feed to share questions and progress."],
      ["03 · Contribute", "/projects", "Build together", "Start an invite-only project from your own idea or a library resource. Add collaborators, organize reference links and pick a task."],
    ].map(([step, href, title, description]) => <Link href={href} key={href} className="rounded-xl border border-line bg-surface p-6 hover:border-accent"><p className="eyebrow">{step}</p><h2 className="mt-4 text-lg font-semibold">{title}</h2><p className="mt-3 text-sm text-muted">{description}</p><span className="mt-5 inline-block text-sm text-accent">Get started →</span></Link>)}</section>
    <section><h2 className="mb-5 text-xl font-semibold">All your tools, in one place</h2><div className="grid gap-6 md:grid-cols-3">{workspaceNavigation.map(group => <div key={group.label} className="rounded-xl border border-line bg-surface p-5"><h3 className="mb-3 text-sm font-semibold">{group.label}</h3><ul className="space-y-1">{group.items.map(item => <li key={item.href}><Link className="block rounded-lg px-2 py-2 text-sm text-ink-soft hover:bg-accent-soft hover:text-accent" href={item.href}>{item.label} →</Link></li>)}</ul></div>)}</div></section>
    <section className="rounded-xl border border-line bg-surface-2 p-6"><h2 className="text-lg font-semibold">Before you contribute</h2><div className="mt-4 grid gap-5 text-sm text-ink-soft sm:grid-cols-2"><p>Confirm your email in <Link href="/dashboard/security" className="text-accent underline">account security</Link> to post, create spaces and contribute. Your research collections and notes stay private to your account.</p><p>Read the original source and its rights evidence before reusing an invention. A published patent or paper is not automatically openly licensed. Project workspaces, tasks and reference links are private to invited members. Institution updates are public.</p></div></section>
  </div>;
}
