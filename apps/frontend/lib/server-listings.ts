import "server-only";
import type { PublicListing } from "./api";

/** Server Components cannot fetch the browser's relative /api URL. */
export async function publicListing(id: string): Promise<PublicListing | null> {
  const origin = process.env.SAHA_INTERNAL_API_URL || "http://127.0.0.1:8000";
  const response = await fetch(new URL(`/api/v1/listings/${encodeURIComponent(id)}`, origin), {
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal: AbortSignal.timeout(10_000),
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error("The listing could not be loaded. Please try again.");
  // Anonymous request only: do not forward session cookies or bearer tokens.
  return response.json();
}
