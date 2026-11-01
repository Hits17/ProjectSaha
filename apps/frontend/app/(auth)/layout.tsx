import { GuestOnly } from "@/components/guest-only";
import Link from "next/link";
import { BookOpen, Users, Package } from "@/components/ui/icons";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return <GuestOnly><div className="mx-auto grid max-w-5xl items-center gap-10 py-6 sm:py-12 lg:grid-cols-2 lg:gap-20">
    <section className="hidden lg:block"><p className="eyebrow mb-5">A little curiosity goes a long way</p><h1 className="font-display text-5xl leading-tight">Your next idea.<br /><span className="text-accent italic">Our shared future.</span></h1><p className="mt-5 text-ink-soft">A home for people who discover, share and build together.</p><div className="mt-9 space-y-5">{[{ Icon: BookOpen, text: "Keep your research in one place" }, { Icon: Users, text: "Connect with people and institutions" }, { Icon: Package, text: "Contribute to projects that matter to you" }].map(({ Icon, text }) => <div key={text} className="flex items-center gap-3 text-sm text-ink-soft"><span className="grid size-9 place-items-center rounded-lg bg-accent-soft text-accent"><Icon className="size-4" /></span>{text}</div>)}</div><Link href="/explore" className="mt-9 inline-block text-sm font-medium text-accent hover:underline">Keep exploring without an account →</Link></section>
    <div className="mx-auto w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-sm sm:p-8">{children}</div>
  </div></GuestOnly>;
}
