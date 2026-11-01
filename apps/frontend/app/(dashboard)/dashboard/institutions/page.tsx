import { redirect } from "next/navigation";

/** Preserve old bookmarks while keeping one canonical institution directory. */
export default function Page() { redirect("/institutions"); }
