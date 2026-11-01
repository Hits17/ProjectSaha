import { HomeSessionActions } from "@/components/home-session-actions";
import Link from "next/link";
import { Button } from "@/components/ui";
import * as Icon from "@/components/ui/icons";

const journeys = [
  { number: "01", title: "Find your starting point", description: "Explore patents and research. Follow the original sources and understand what you can build on.", href: "/explore", action: "Explore research", icon: Icon.Search },
  { number: "02", title: "Find your people", description: "Meet research groups, universities and makerspaces with interests that connect with yours.", href: "/institutions", action: "Meet institutions", icon: Icon.Users },
  { number: "03", title: "Make something together", description: "Start an invite-only project, bring your collaborators and references, and turn an idea into a working prototype.", href: "/projects", action: "Start collaborating", icon: Icon.Package },
];

export default function RootPage() {
  return <div className="space-y-16 sm:space-y-20">
    <section className="grid items-center gap-10 py-5 lg:grid-cols-[1.15fr_1fr] lg:gap-14 lg:py-10">
      <div>
        <p className="eyebrow mb-5 flex items-center gap-2"><span className="size-2 rounded-full bg-accent" />An open space for shared progress</p>
        <h1 className="font-display text-5xl leading-[1.08] tracking-tight sm:text-6xl lg:text-[4.25rem]">Good ideas grow<br />better <span className="text-accent italic">together.</span></h1>
        <p className="mt-6 max-w-lg text-base leading-relaxed text-ink-soft sm:text-lg">Discover research worth exploring. Find people who share your curiosity. Build something that others can build on.</p>
        <div className="mt-8 flex flex-wrap gap-3"><Button href="/explore" size="lg">Explore ideas <Icon.ChevronRight className="size-4" /></Button><Button href="/projects" variant="secondary" size="lg">Find a project</Button></div>
        <p className="mt-5"><HomeSessionActions hint /></p>
      </div>
      <div className="hero-grid relative rounded-3xl border border-line bg-[#edf3eb] p-5 sm:p-8">
        <div className="mb-7 flex items-center justify-between"><span className="eyebrow">From curiosity to contribution</span><Icon.Sparkles className="size-5 text-accent" /></div>
        <div className="space-y-3">
          {journeys.map(({ number, title, href, icon: Glyph }, index) => <Link key={href} href={href} className={`group flex items-center gap-4 rounded-2xl border border-line bg-surface p-5 shadow-xs transition-shadow hover:shadow-md ${index === 1 ? "sm:ml-6" : index === 2 ? "sm:ml-12" : ""}`}>
            <span className={`grid size-11 shrink-0 place-items-center rounded-xl ${index === 1 ? "bg-[#f6eedb] text-[#816027]" : "bg-accent-soft text-accent"}`}><Glyph className="size-5" /></span>
            <div className="flex-1"><p className="text-[10px] font-semibold uppercase tracking-widest text-muted">Step {number}</p><p className="mt-1 text-sm font-semibold text-ink">{title}</p></div><Icon.ChevronRight className="size-4 text-muted group-hover:text-accent" />
          </Link>)}
        </div>
        <div className="mt-7 flex items-center gap-2 border-t border-accent/15 pt-5 text-xs text-ink-soft"><Icon.BookOpen className="size-4 text-accent" />Built around sources, people and shared work.</div>
      </div>
    </section>

    <section aria-labelledby="search-heading" className="rounded-2xl border border-line bg-surface p-5 sm:p-7">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2"><h2 id="search-heading" className="text-lg font-semibold">What are you curious about?</h2><span className="text-xs text-muted">Search Saha’s curated research library</span></div>
      <form action="/explore" className="flex flex-col gap-3 sm:flex-row"><label className="relative flex-1"><span className="sr-only">Search patents, research and topics</span><Icon.Search className="pointer-events-none absolute left-4 top-4 size-5 text-muted" /><input name="q" maxLength={255} type="search" placeholder="Try solar energy, water filtration, open hardware…" className="w-full min-w-0 rounded-xl border border-line-strong bg-canvas py-3 pl-12 pr-4 text-sm" /></label><Button type="submit" size="lg">Search research</Button></form>
      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs"><span className="mr-1 text-muted">Start exploring</span>{["Clean energy", "Open hardware", "Water", "Materials"].map(topic => <Link key={topic} href={`/explore?q=${encodeURIComponent(topic)}`} className="rounded-full border border-line px-3 py-1.5 text-ink-soft hover:border-accent hover:text-accent">{topic}</Link>)}</div>
    </section>

    <section aria-labelledby="journey-heading">
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow mb-2">A place for every kind of curious</p><h2 id="journey-heading" className="text-3xl font-semibold tracking-tight">Your next step starts here.</h2></div><Link href="/guide" className="text-sm font-medium text-accent hover:underline">How Saha works →</Link></div>
      <div className="grid gap-4 md:grid-cols-3">{journeys.map(({ number, title, description, href, action, icon: Glyph }) => <Link key={href} href={href} className="group flex flex-col rounded-2xl border border-line bg-surface p-6 transition-shadow hover:border-line-strong hover:shadow-md"><div className="mb-8 flex items-center justify-between"><Glyph className="size-6 text-accent" /><span className="text-xs text-muted">{number}</span></div><h3 className="text-lg font-semibold">{title}</h3><p className="mt-3 text-sm leading-relaxed text-muted">{description}</p><span className="mt-auto pt-7 text-sm font-semibold text-accent">{action} <span aria-hidden="true">→</span></span></Link>)}</div>
    </section>

    <section className="flex flex-col justify-between gap-7 rounded-2xl bg-ink p-7 text-white sm:flex-row sm:items-center sm:p-10"><div className="max-w-xl"><p className="text-xs font-semibold uppercase tracking-widest text-[#b8d9bb]">Keep your curiosity moving</p><h2 className="mt-3 text-2xl font-semibold sm:text-3xl">A shared idea is just the beginning.</h2><p className="mt-3 text-sm leading-relaxed text-white/75">Save your research, connect with a community and take the first step toward a collaborative project.</p></div><HomeSessionActions /></section>
  </div>;
}
