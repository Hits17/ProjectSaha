"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/auth";
import { api, ApiError, Community, CommunityInput } from "@/lib/api";
import { TOPICS, topicMeta } from "./topics";
import {
  Avatar, TopicIcon, TopicChip, IconUsers, IconLock, IconGlobe,
  IconSearch, IconPlus, IconSparkles, IconX,
} from "./ui";

/* ------------------------------------------------------------------ card --- */
function CommunityCard({ community, onOpen, onJoin }: {
  community: Community;
  onOpen: (c: Community) => void;
  onJoin: (c: Community) => void;
}) {
  const canJoin = !community.is_member && community.visibility === "public";
  return (
    <div
      onClick={() => onOpen(community)}
      className="group cursor-pointer bg-white border border-line rounded-2xl p-5 transition-all hover:border-line-strong hover:shadow-lg hover:-translate-y-0.5"
    >
      <div className="flex items-start gap-3">
        <TopicIcon topic={community.topic} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-ink truncate group-hover:text-ink-soft">{community.name}</h3>
            {community.visibility === "private"
              ? <IconLock className="w-3.5 h-3.5 text-amber-500 shrink-0" />
              : <IconGlobe className="w-3.5 h-3.5 text-gray-300 shrink-0" />}
          </div>
          <div className="mt-1.5"><TopicChip topic={community.topic} /></div>
        </div>
      </div>

      <p className="text-sm text-muted mt-3 line-clamp-2 min-h-[2.5rem]">
        {community.description || "No description yet."}
      </p>

      <div className="flex items-center justify-between mt-4 pt-3 border-t border-line">
        <span className="inline-flex items-center gap-1.5 text-xs text-muted">
          <IconUsers className="w-3.5 h-3.5" />
          {community.member_count} {community.member_count === 1 ? "member" : "members"}
        </span>
        {community.is_member ? (
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-600">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Joined
          </span>
        ) : canJoin ? (
          <button
            onClick={(e) => { e.stopPropagation(); onJoin(community); }}
            className="text-xs font-semibold bg-accent text-white px-3.5 py-1.5 rounded-lg hover:bg-accent-hover active:scale-95 transition-all"
          >
            Join
          </button>
        ) : (
          <span className="inline-flex items-center gap-1 text-xs text-amber-600"><IconLock className="w-3 h-3" /> Invite only</span>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- modal ---- */
type FormState = { name: string; description: string; topic: string; visibility: "public" | "private" };
const EMPTY: FormState = { name: "", description: "", topic: "general", visibility: "public" };

function CreateModal({ onClose, onCreated }: { onClose: () => void; onCreated: (c: Community) => void }) {
  const { accessToken } = useAuthStore();
  const [form, setForm] = useState<FormState>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accessToken) return;
    setSaving(true); setError("");
    const body: CommunityInput = {
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      topic: form.topic,
      visibility: form.visibility,
    };
    try {
      onCreated(await api.communities.create(accessToken, body));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create community");
      setSaving(false);
    }
  };

  const input = "w-full px-3.5 py-2.5 border border-line-strong rounded-xl text-sm focus:ring-2 focus:ring-accent focus:border-transparent transition";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-accent/40 backdrop-blur-sm" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-lg bg-white rounded-2xl shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-line sticky top-0 bg-white rounded-t-2xl">
          <div className="flex items-center gap-2">
            <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-slate-700 to-slate-900 text-white flex items-center justify-center"><IconSparkles className="w-4 h-4" /></span>
            <h3 className="font-semibold text-ink">Start a community</h3>
          </div>
          <button onClick={onClose} className="text-muted hover:text-ink-soft p-1 rounded-lg hover:bg-surface-2"><IconX className="w-5 h-5" /></button>
        </div>

        <form onSubmit={submit} className="p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-ink-soft mb-1.5">Name</label>
            <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              required minLength={3} maxLength={120} autoFocus className={input}
              placeholder="e.g. Solid-state battery researchers" />
          </div>

          <div>
            <label className="block text-sm font-medium text-ink-soft mb-1.5">What's it about? <span className="text-muted font-normal">(optional)</span></label>
            <textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              rows={3} maxLength={2000} className={input}
              placeholder="Describe the focus, who should join, and what you hope to build together." />
          </div>

          <div>
            <label className="block text-sm font-medium text-ink-soft mb-2">Topic</label>
            <div className="flex flex-wrap gap-2">
              {TOPICS.map((t) => {
                const active = form.topic === t.value;
                return (
                  <button type="button" key={t.value} onClick={() => setForm((f) => ({ ...f, topic: t.value }))}
                    className={`inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border transition-all ${
                      active ? `${t.chip} ring-2 ring-offset-1 ring-line-strong scale-105` : "bg-white text-ink-soft border-line hover:border-line-strong"
                    }`}>
                    <span>{t.emoji}</span>{t.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-ink-soft mb-2">Visibility</label>
            <div className="grid grid-cols-2 gap-3">
              {([
                ["public", IconGlobe, "Public", "Anyone can find and join"],
                ["private", IconLock, "Private", "Invite-only, hidden from search"],
              ] as const).map(([val, Icon, label, desc]) => {
                const active = form.visibility === val;
                return (
                  <button type="button" key={val} onClick={() => setForm((f) => ({ ...f, visibility: val }))}
                    className={`text-left p-3 rounded-xl border-2 transition-all ${active ? "border-accent bg-canvas" : "border-line hover:border-line-strong"}`}>
                    <span className="flex items-center gap-1.5 font-medium text-sm text-ink"><Icon className="w-4 h-4" />{label}</span>
                    <span className="block text-xs text-muted mt-0.5">{desc}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {error && <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-red-700 text-sm">{error}</div>}

          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={saving} className="flex-1 bg-accent text-white px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-accent-hover disabled:opacity-40 transition-all active:scale-95">
              {saving ? "Creating…" : "Create community"}
            </button>
            <button type="button" onClick={onClose} className="px-5 py-2.5 rounded-xl text-sm font-medium text-ink-soft border border-line hover:bg-canvas transition">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------- skeletons ----- */
function CardSkeleton() {
  return (
    <div className="bg-white border border-line rounded-2xl p-5 animate-pulse">
      <div className="flex gap-3"><div className="w-11 h-11 rounded-xl bg-line" /><div className="flex-1 space-y-2"><div className="h-4 bg-line rounded w-2/3" /><div className="h-3 bg-surface-2 rounded w-1/3" /></div></div>
      <div className="h-3 bg-surface-2 rounded w-full mt-4" /><div className="h-3 bg-surface-2 rounded w-4/5 mt-2" />
    </div>
  );
}

/* --------------------------------------------------------------- page ------ */
export default function CommunityPage() {
  const router = useRouter();
  const { accessToken, user } = useAuthStore();
  const [tab, setTab] = useState<"browse" | "mine">("browse");
  const [q, setQ] = useState("");
  const [topic, setTopic] = useState("");
  const [results, setResults] = useState<Community[] | null>(null);
  const [mine, setMine] = useState<Community[] | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const runBrowse = useCallback(async (filters: { q?: string; topic?: string }) => {
    if (!accessToken) return;
    setLoading(true); setError("");
    try {
      setResults(await api.communities.browse(accessToken, { ...filters, limit: 60 }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load communities");
    } finally { setLoading(false); }
  }, [accessToken]);

  const loadMine = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true); setError("");
    try {
      setMine(await api.communities.mine(accessToken));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load your communities");
    } finally { setLoading(false); }
  }, [accessToken]);

  // Deep links (e.g. "Discuss in community" from the Open Library) pass
  // ?topic=<value>; seed the filter from the URL on first load only.
  const seededFromUrl = useRef(false);

  useEffect(() => {
    if (tab === "browse") {
      let activeTopic = topic;
      if (!seededFromUrl.current) {
        seededFromUrl.current = true;
        const urlTopic = new URLSearchParams(window.location.search).get("topic") ?? "";
        if (urlTopic && TOPICS.some((t) => t.value === urlTopic)) {
          activeTopic = urlTopic;
          setTopic(urlTopic);
        }
      }
      runBrowse({ topic: activeTopic || undefined, q: q.trim() || undefined });
    } else loadMine();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, accessToken]);

  const applyFilters = (nextTopic: string, nextQ: string) => {
    setTopic(nextTopic); setQ(nextQ);
    runBrowse({ topic: nextTopic || undefined, q: nextQ.trim() || undefined });
  };

  const handleJoin = async (c: Community) => {
    if (!accessToken) return;
    try {
      await api.communities.join(accessToken, c.id);
      router.push(`/dashboard/community/${c.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not join");
    }
  };
  const open = (c: Community) => router.push(`/dashboard/community/${c.id}`);

  const isVerified = (user?.email_verified || user?.kyc_status === "verified");
  const list = tab === "browse" ? results : mine;

  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-800 via-slate-900 to-slate-800 p-6 sm:p-8 text-white">
        <div className="absolute -right-8 -top-10 text-[140px] opacity-10 select-none">💬</div>
        <div className="relative flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold">Community</h1>
            <p className="text-slate-300 text-sm mt-1.5 max-w-xl">
              Connect with researchers and makers in topic communities — share ideas, ask questions, and advance IP research & development together.
            </p>
          </div>
          {isVerified && (
            <button onClick={() => setShowModal(true)}
              className="shrink-0 inline-flex items-center gap-1.5 bg-white text-ink px-4 py-2.5 rounded-xl text-sm font-semibold hover:bg-surface-2 active:scale-95 transition-all shadow-sm">
              <IconPlus className="w-4 h-4" /> New community
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-2 rounded-xl p-1 w-fit">
        {([["browse", "Discover"], ["mine", "My Communities"]] as const).map(([value, label]) => (
          <button key={value} onClick={() => setTab(value)}
            className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === value ? "bg-white text-ink shadow-sm" : "text-muted hover:text-ink-soft"
            }`}>
            {label}
          </button>
        ))}
      </div>

      {error && <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-red-700 text-sm">{error}</div>}
      {!isVerified && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-amber-800 text-sm">
          Confirm your email to create communities, join, and post. Financial KYC is only needed for transactions.
        </div>
      )}

      {/* Filters (Discover only) */}
      {tab === "browse" && (
        <div className="space-y-3">
          <form onSubmit={(e) => { e.preventDefault(); applyFilters(topic, q); }} className="relative max-w-md">
            <IconSearch className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-muted" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search communities…"
              className="w-full pl-10 pr-3 py-2.5 border border-line-strong rounded-xl text-sm focus:ring-2 focus:ring-accent focus:border-transparent" />
          </form>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => applyFilters("", q)}
              className={`text-xs font-medium px-3 py-1.5 rounded-full border transition-all ${topic === "" ? "bg-accent text-white border-accent" : "bg-white text-ink-soft border-line hover:border-line-strong"}`}>
              All topics
            </button>
            {TOPICS.map((t) => (
              <button key={t.value} onClick={() => applyFilters(t.value, q)}
                className={`inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border transition-all ${
                  topic === t.value ? `${t.chip} ring-2 ring-offset-1 ring-line-strong` : "bg-white text-ink-soft border-line hover:border-line-strong"
                }`}>
                <span>{t.emoji}</span>{t.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{[0, 1, 2, 3].map((i) => <CardSkeleton key={i} />)}</div>
      ) : list && list.length === 0 ? (
        <div className="bg-white border border-dashed border-line-strong rounded-2xl p-12 text-center">
          <div className="text-5xl mb-3">{tab === "browse" ? "🔍" : "👋"}</div>
          <p className="text-ink-soft font-medium">
            {tab === "browse" ? "No communities match your filters" : "You haven't joined any communities yet"}
          </p>
          <p className="text-muted text-sm mt-1">
            {tab === "browse" ? "Try a different topic — or start the first one for your field." : "Discover communities and join the conversation."}
          </p>
          {isVerified && tab === "browse" && (
            <button onClick={() => setShowModal(true)} className="mt-4 inline-flex items-center gap-1.5 bg-accent text-white px-4 py-2 rounded-xl text-sm font-semibold hover:bg-accent-hover transition">
              <IconPlus className="w-4 h-4" /> Create a community
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {list?.map((c) => <CommunityCard key={c.id} community={c} onOpen={open} onJoin={handleJoin} />)}
        </div>
      )}

      {showModal && <CreateModal onClose={() => setShowModal(false)} onCreated={(c) => router.push(`/dashboard/community/${c.id}`)} />}
    </div>
  );
}
