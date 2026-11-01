import Link from "next/link";

export function Brand() {
  return <Link href="/" aria-label="Saha home" className="inline-flex shrink-0 items-center gap-2.5">
    <span className="grid size-9 place-items-center rounded-xl bg-accent text-white" aria-hidden="true">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M7 5h7a4 4 0 0 1 0 8H9a3 3 0 0 0 0 6h8M17 5 7 19" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
    </span>
    <span className="text-2xl font-semibold tracking-tight text-ink">saha<span className="text-accent">.</span></span>
  </Link>;
}
