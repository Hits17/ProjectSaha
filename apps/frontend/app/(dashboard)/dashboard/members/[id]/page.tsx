"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { api, ApiError, BASE_URL, type MemberProfile } from "@/lib/api";
import {
  Badge, Button, Card, EmptyState, ErrorBanner, Skeleton, StatTile, useToast,
} from "@/components/ui";
import * as Icon from "@/components/ui/icons";

function timeAgo(iso: string): string {
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (d < 1) return "today";
  if (d < 30) return `${d}d ago`;
  if (d < 365) return `${Math.floor(d / 30)}mo ago`;
  return `${Math.floor(d / 365)}y ago`;
}

function Section({ title, children, action }: {
  title: string; children: React.ReactNode; action?: React.ReactNode;
}) {
  return (
    <Card className="p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold text-ink">{title}</h2>
        {action}
      </div>
      {children}
    </Card>
  );
}

export default function MemberProfilePage() {
  const { id } = useParams<{ id: string }>();
  const token = useAuthStore((s) => s.accessToken);
  const toast = useToast();
  const [profile, setProfile] = useState<MemberProfile | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);

  const load = useCallback(async () => {
    if (!token || !id) return;
    setError("");
    try {
      setProfile(await api.social.profile(token, id));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load this profile");
    }
  }, [token, id]);

  useEffect(() => { void load(); }, [load]);

  const toggleFollow = async () => {
    if (!token || !profile) return;
    try {
      if (profile.is_following) {
        await api.social.unfollow(token, profile.user_id);
        setProfile({ ...profile, is_following: false });
      } else {
        await api.social.follow(token, profile.user_id);
        setProfile({ ...profile, is_following: true });
      }
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not update");
    }
  };

  if (error) return <ErrorBanner>{error}</ErrorBanner>;
  if (!profile) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Skeleton className="h-40" />
        <Skeleton className="h-32" />
      </div>
    );
  }

  const { verified, standing, self_asserted: self } = profile;
  const initials = profile.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      {/* ── Identity ─────────────────────────────────────────────────────── */}
      <Card className="overflow-hidden">
        <div className="h-20 bg-gradient-to-r from-slate-800 to-slate-600" />
        <div className="p-5 pt-0">
          <div className="-mt-10 flex items-end justify-between gap-4">
            {profile.has_avatar ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={`${BASE_URL}/api/v1/users/${profile.user_id}/avatar`}
                alt=""
                className="h-20 w-20 rounded-full border-4 border-white bg-surface-2 object-cover"
              />
            ) : (
              <div className="grid h-20 w-20 place-items-center rounded-full border-4 border-white bg-line text-xl font-semibold text-ink-soft">
                {initials}
              </div>
            )}
            <div className="flex gap-2 pb-1">
              {profile.is_self ? (
                <Button variant="secondary" onClick={() => setEditing((v) => !v)}>
                  {editing ? "Done" : "Edit profile"}
                </Button>
              ) : (
                <Button variant={profile.is_following ? "secondary" : "primary"} onClick={toggleFollow}>
                  {profile.is_following ? "Following" : "Follow"}
                </Button>
              )}
            </div>
          </div>

          <div className="mt-3">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-xl font-bold text-ink">{profile.full_name}</h1>
              {verified.kyc_verified && (
                <Badge tone="success">
                  <Icon.Shield className="mr-1 inline h-3 w-3" />
                  Identity verified
                </Badge>
              )}
            </div>
            {self.headline && <p className="mt-1 text-ink-soft">{self.headline}</p>}
            <p className="mt-1 text-sm text-muted">
              {self.location && `${self.location} · `}
              Member since {new Date(verified.member_since).toLocaleDateString(undefined, {
                month: "long", year: "numeric",
              })}
              {self.website_url && (
                <>
                  {" · "}
                  <a
                    href={self.website_url}
                    target="_blank"
                    rel="noopener noreferrer nofollow"
                    className="text-ink-soft underline"
                  >
                    Website
                  </a>
                </>
              )}
            </p>
          </div>
        </div>
      </Card>

      {/*
        Verified block, above the fold and above anything self-reported.

        LinkedIn profiles are entirely self-asserted, which is fine when a false
        claim costs someone a wasted coffee. Here a profile informs whether to
        hand over unfiled patent claims, so "we verified" and "they claim" cannot
        look the same. That separation is the whole point of this section.
      */}
      <Card className="p-5">
        <div className="mb-3 flex items-center gap-2">
          <Icon.Shield className="h-4 w-4 text-emerald-600" />
          <h2 className="font-semibold text-ink">Verified by Saha</h2>
          <span className="text-xs text-muted">Platform records, not self-reported</span>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {/*
            Track record and standing sit side by side but are never added
            together. Standing is cheap to earn; a completed deal is not.
            Merging them would let someone farm engagement and arrive at a
            negotiation looking like a proven counterparty.
          */}
          <StatTile
            label="Track record"
            value={verified.average_rating ? `★ ${verified.average_rating}` : "—"}
            sublabel={`${verified.completed_deals} completed deal${verified.completed_deals === 1 ? "" : "s"}`}
          />
          <StatTile
            label="Standing"
            value={standing.total_standing.toLocaleString()}
            sublabel={standing.tier}
          />
          <StatTile label="Listings" value={verified.published_listings} sublabel="published" />
          <StatTile label="Library" value={verified.library_contributions} sublabel="contributions" />
        </div>

        <p className="mt-3 text-xs text-muted">
          Track record comes from completed transactions and counterparty reviews.
          Standing comes from how the community responds to posts and comments.
          They are shown separately and never combined — one is expensive to earn,
          the other is not.
        </p>

        {profile.is_self && standing.next_tier && (
          <p className="mt-2 text-xs text-muted">
            {standing.next_tier_at! - standing.total_standing} more standing to reach{" "}
            <span className="font-medium">{standing.next_tier}</span>.
            {!standing.can_downvote && " Downvoting unlocks at 50."}
          </p>
        )}
      </Card>

      {/* ── Self-asserted ─────────────────────────────────────────────────── */}
      {self.about && (
        <Section title="About">
          <p className="whitespace-pre-wrap text-sm text-ink-soft">{self.about}</p>
        </Section>
      )}

      {self.featured.length > 0 && (
        <Section title="Featured">
          <div className="grid gap-2 sm:grid-cols-2">
            {self.featured.map((f, i) => (
              <a
                key={i}
                href={f.url ?? "#"}
                target={f.url ? "_blank" : undefined}
                rel="noopener noreferrer nofollow"
                className="rounded-lg border border-line p-3 text-sm hover:bg-canvas"
              >
                <span className="text-xs uppercase tracking-wide text-muted">{f.kind}</span>
                <p className="font-medium text-ink">{f.label}</p>
              </a>
            ))}
          </div>
        </Section>
      )}

      {self.experience.length > 0 && (
        <Section
          title="Experience"
          action={<span className="text-xs text-muted">Self-reported</span>}
        >
          <div className="space-y-4">
            {self.experience.map((x, i) => (
              <div key={i} className="flex gap-3">
                <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-slate-300" />
                <div>
                  <p className="font-medium text-ink">{x.title}</p>
                  {x.organization && <p className="text-sm text-ink-soft">{x.organization}</p>}
                  {(x.start || x.end) && (
                    <p className="text-xs text-muted">{x.start} – {x.end || "Present"}</p>
                  )}
                  {x.description && (
                    <p className="mt-1 text-sm text-ink-soft">{x.description}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {self.skills.length > 0 && (
        <Section
          title="Skills"
          action={<span className="text-xs text-muted">Self-reported</span>}
        >
          <div className="flex flex-wrap gap-2">
            {self.skills.map((s) => (
              <span key={s} className="rounded-full bg-surface-2 px-3 py-1 text-sm text-ink-soft">
                {s}
              </span>
            ))}
          </div>
        </Section>
      )}

      {/* ── Activity ──────────────────────────────────────────────────────── */}
      <Section title="Recent activity">
        {profile.recent_posts.length === 0 ? (
          <EmptyState title="No posts yet" description="Nothing shared publicly so far." />
        ) : (
          <div className="space-y-3">
            {profile.recent_posts.map((p) => (
              <Link
                key={p.id}
                href={`/dashboard/feed/${p.id}`}
                className="block rounded-lg border border-line p-3 hover:bg-canvas"
              >
                {p.title && <p className="font-medium text-ink">{p.title}</p>}
                <p className="line-clamp-3 text-sm text-ink-soft">{p.body}</p>
                <p className="mt-1 text-xs text-muted">
                  {p.score} points · {p.comment_count} comments · {timeAgo(p.created_at)}
                </p>
              </Link>
            ))}
          </div>
        )}
      </Section>

      {editing && profile.is_self && (
        <EditProfile profile={profile} onSaved={(p) => { setProfile(p); setEditing(false); }} />
      )}
    </div>
  );
}

function EditProfile({ profile, onSaved }: {
  profile: MemberProfile; onSaved: (p: MemberProfile) => void;
}) {
  const token = useAuthStore((s) => s.accessToken);
  const toast = useToast();
  const s = profile.self_asserted;
  const [headline, setHeadline] = useState(s.headline ?? "");
  const [about, setAbout] = useState(s.about ?? "");
  const [location, setLocation] = useState(s.location ?? "");
  const [website, setWebsite] = useState(s.website_url ?? "");
  const [skills, setSkills] = useState(s.skills.join(", "));
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!token) return;
    setBusy(true);
    try {
      const updated = await api.social.updateProfile(token, {
        headline: headline || null,
        about: about || null,
        location: location || null,
        website_url: website || null,
        skills: skills.split(",").map((x) => x.trim()).filter(Boolean),
      });
      onSaved(updated);
      toast.success("Profile updated");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-5 space-y-3">
      <h2 className="font-semibold text-ink">Edit profile</h2>
      <p className="text-xs text-muted">
        These are your own claims and are shown as self-reported. Verified figures
        above come from platform records and can&rsquo;t be edited.
      </p>

      <label className="block">
        <span className="text-sm font-medium text-ink-soft">Headline</span>
        <input
          value={headline}
          onChange={(e) => setHeadline(e.target.value)}
          maxLength={220}
          placeholder="Materials scientist · biodegradable packaging"
          className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
        />
        <span className="text-xs text-muted">{headline.length}/220</span>
      </label>

      <label className="block">
        <span className="text-sm font-medium text-ink-soft">About</span>
        <textarea
          value={about}
          onChange={(e) => setAbout(e.target.value)}
          rows={5}
          maxLength={2600}
          className="mt-1 w-full resize-y rounded-lg border border-line-strong px-3 py-2 text-sm"
        />
        <span className="text-xs text-muted">{about.length}/2600</span>
      </label>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium text-ink-soft">Location</span>
          <input
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            maxLength={120}
            className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-ink-soft">Website</span>
          <input
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
            placeholder="https://"
            className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
          />
        </label>
      </div>

      <label className="block">
        <span className="text-sm font-medium text-ink-soft">Skills</span>
        <input
          value={skills}
          onChange={(e) => setSkills(e.target.value)}
          placeholder="polymer chemistry, extrusion, regulatory affairs"
          className="mt-1 w-full rounded-lg border border-line-strong px-3 py-2 text-sm"
        />
        <span className="text-xs text-muted">Comma-separated, up to 50</span>
      </label>

      <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save"}</Button>
    </Card>
  );
}
