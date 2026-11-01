"use client";

import { useCallback, useEffect, useState } from "react";
import { api, reviewMediaBlob, type ReviewMedia, type ModerationRow } from "@/lib/api";
import { Btn, Section, Td, Th } from "@/components/ui";
import { useAuthStore } from "@/store/auth";

const CATEGORY_LABELS: Record<string, string> = {
  weapons_explosive: "Explosives",
  weapons_firearm: "Prohibited firearms",
  chem_bio_weapon: "Chem/bio weapons",
  poison: "Poisons",
  illicit_synthesis: "Illicit synthesis",
  self_harm: "Self-harm",
  malware: "Malware",
  zero_tolerance: "Zero tolerance",
  credible_threat: "Threat of violence",
};

function Since({ iso }: { iso: string | null }) {
  if (!iso) return <span className="text-slate-400">—</span>;
  const h = Math.floor((Date.now() - new Date(iso).getTime()) / 3600000);
  const overdue = h >= 24;
  return (
    <span className={overdue ? "font-medium text-red-600" : "text-slate-600"}>
      {h < 1 ? "<1h" : `${h}h`}
      {overdue && " ⚠"}
    </span>
  );
}

function Attachment({ media, token }: { media: ReviewMedia; token: string }) {
  const [url, setUrl] = useState(""); const [load, setLoad] = useState(false); const [error, setError] = useState("");
  useEffect(() => {
    if (!load) return;
    const controller = new AbortController(); let object = ""; setError("");
    reviewMediaBlob(media.url, token, controller.signal).then(blob => {
      if (!controller.signal.aborted) { object = URL.createObjectURL(blob); setUrl(object); }
    }).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => { controller.abort(); if (object) URL.revokeObjectURL(object); setUrl(""); };
  }, [media.url, token, load]);
  return <div className="mt-3 rounded border border-slate-200 p-2">{url ? media.content_type.startsWith("video/") ? <video src={url} controls className="max-h-64 w-full" /> : <img src={url} alt={media.alt_text || "Post attachment"} className="max-h-64 object-contain" /> : <button className="text-sm text-blue-700 underline" onClick={() => setLoad(v => !v)}>{load ? "Cancel / retry loading" : `Inspect ${media.content_type} (${(media.byte_size / 1048576).toFixed(1)} MB)`}</button>}{media.alt_text && <p className="text-xs mt-1">{media.alt_text}</p>}{error && <p role="alert" className="text-xs text-red-700">{error}</p>}</div>;
}

export default function ModerationPage() {
  const token = useAuthStore((s) => s.accessToken);
  const [rows, setRows] = useState<ModerationRow[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<Record<string, string>>({});

  const load = useCallback(() => {
    if (!token) return;
    setError("");
    api.moderationQueue(token)
      .then(setRows)
      .catch((e) => setError(e.message));
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const review = async (id: string, approve: boolean) => {
    if (!token) return;
    setBusy(id);
    try {
      await api.reviewPost(token, id, approve, note[id] || undefined);
      setRows((prev) => prev?.filter((r) => r.id !== id) ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Content moderation</h1>
        <p className="mt-1 text-sm text-slate-500">
          Posts held by the safety classifier or by member reports. Oldest first —
          a review queue is a FIFO, so nobody with a legitimate post waits behind
          newer arrivals. Held posts are hidden until approved; flagged posts remain visible under their audience rules pending a decision.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <Section title={`Queue${rows ? ` (${rows.length})` : ""}`}>
        {rows === null ? (
          <p className="p-4 text-sm text-slate-400">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="p-4 text-sm text-slate-500">
            Nothing awaiting review. Held posts appear here automatically.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr>
                <Th>Waiting</Th>
                <Th>Author</Th>
                <Th>Content</Th>
                <Th>Why</Th>
                <Th>Decision</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-slate-100 align-top">
                  <Td><Since iso={r.held_at ?? r.created_at} /></Td>
                  <Td>
                    <p className="font-medium text-slate-900">{r.author_name}</p>
                    <p className="text-xs text-slate-400">
                      {r.visibility}
                      {r.report_count > 0 && ` · ${r.report_count} report(s)`}
                    </p>
                  </Td>
                  <Td>
                    <div className="max-w-md">
                      {r.title && <p className="font-medium text-slate-900">{r.title}</p>}
                      <p className="whitespace-pre-wrap text-slate-700">{r.body}</p>{token && r.media?.map(media => <Attachment key={`${media.id}:${token}`} media={media} token={token} />)}
                    </div>
                  </Td>
                  <Td>
                    <div className="flex flex-wrap gap-1">
                      {r.safety_categories.map((c) => (
                        <span
                          key={c}
                          className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800"
                        >
                          {CATEGORY_LABELS[c] ?? c}
                        </span>
                      ))}
                    </div>
                    {r.safety_reason && (
                      <p className="mt-1 text-xs text-slate-400">{r.safety_reason}</p>
                    )}
                  </Td>
                  <Td>
                    <div className="space-y-2">
                      <textarea
                        value={note[r.id] ?? ""}
                        onChange={(e) => setNote({ ...note, [r.id]: e.target.value })}
                        placeholder="Note to the author (shown on rejection)"
                        rows={2}
                        className="w-56 rounded border border-slate-300 px-2 py-1 text-xs"
                      />
                      <div className="flex gap-2">
                        <Btn
                          onClick={() => review(r.id, true)}
                          disabled={busy === r.id}
                        >
                          Approve
                        </Btn>
                        <Btn
                          variant="danger"
                          onClick={() => review(r.id, false)}
                          disabled={busy === r.id}
                        >
                          Reject
                        </Btn>
                      </div>
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      <p className="text-xs text-slate-400">
        Every decision is written to the append-only audit log with your identity,
        and the author is notified either way. The classifier can hold content but
        never releases it — that always requires a person.
      </p>
    </div>
  );
}
