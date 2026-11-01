"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { api, ApiError } from "@/lib/api";
import { AVATAR_UPDATED_EVENT, Avatar, useMyAvatar } from "@/components/profile-menu";
import * as Icon from "@/components/ui/icons";

const ROLE_LABELS: Record<string, string> = {
  creator: "Creator",
  manufacturer: "Manufacturer",
  legal: "Legal",
  admin: "Administrator",
};

const KYC_BADGE: Record<string, { label: string; cls: string }> = {
  pending: { label: "Not verified", cls: "bg-surface-2 text-ink-soft" },
  in_review: { label: "Verification in review", cls: "bg-amber-50 text-amber-700" },
  verified: { label: "Identity verified", cls: "bg-green-50 text-green-700" },
  rejected: { label: "Verification rejected", cls: "bg-red-50 text-red-600" },
};

function Note({ kind, children }: { kind: "ok" | "error"; children: React.ReactNode }) {
  return (
    <p className={`text-sm ${kind === "ok" ? "text-green-700" : "text-red-600"}`}>{children}</p>
  );
}

export default function ProfilePage() {
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const avatarUrl = useMyAvatar();
  const fileRef = useRef<HTMLInputElement>(null);

  // Identity form
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [savingIdentity, setSavingIdentity] = useState(false);
  const [identityMsg, setIdentityMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  // Password form
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [savingPw, setSavingPw] = useState(false);
  const [pwMsg, setPwMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  // Avatar
  const [uploading, setUploading] = useState(false);
  const [avatarMsg, setAvatarMsg] = useState<string | null>(null);

  // Refresh the profile from the API on mount so the page never shows stale data.
  useEffect(() => {
    if (!token) return;
    api.users.me(token).then((me) => {
      setUser(me);
      setFullName(me.full_name);
      setEmail(me.email);
    }).catch(() => { /* transient; the store copy still renders */ });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (!user) return null;

  const verified = user.kyc_status === "verified";
  const kyc = KYC_BADGE[user.kyc_status] ?? KYC_BADGE.pending;
  const identityDirty = fullName.trim() !== user.full_name || email.trim().toLowerCase() !== user.email;

  const saveIdentity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !identityDirty) return;
    setSavingIdentity(true);
    setIdentityMsg(null);
    try {
      const body: { full_name?: string; email?: string } = {};
      if (fullName.trim() !== user.full_name) body.full_name = fullName.trim();
      const emailChanged = email.trim().toLowerCase() !== user.email;
      if (emailChanged) body.email = email.trim();
      const me = await api.users.updateProfile(token, body);
      setUser(me);
      setIdentityMsg({
        kind: "ok",
        text: emailChanged
          ? "Saved. We sent a verification link to your new email address."
          : "Saved.",
      });
    } catch (err) {
      setIdentityMsg({ kind: "error", text: err instanceof ApiError ? err.message : "Save failed" });
    } finally {
      setSavingIdentity(false);
    }
  };

  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    if (newPw !== confirmPw) {
      setPwMsg({ kind: "error", text: "New passwords don't match." });
      return;
    }
    setSavingPw(true);
    setPwMsg(null);
    try {
      await api.users.changePassword(token, currentPw, newPw);
      setCurrentPw(""); setNewPw(""); setConfirmPw("");
      setPwMsg({ kind: "ok", text: "Password updated. Other signed-in sessions were logged out." });
    } catch (err) {
      setPwMsg({ kind: "error", text: err instanceof ApiError ? err.message : "Password change failed" });
    } finally {
      setSavingPw(false);
    }
  };

  const pickAvatar = () => fileRef.current?.click();

  const onAvatarFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file
    if (!file || !token) return;
    if (file.size > 2 * 1024 * 1024) {
      setAvatarMsg("Image must be 2 MB or smaller.");
      return;
    }
    setUploading(true);
    setAvatarMsg(null);
    try {
      const me = await api.users.uploadAvatar(token, file);
      setUser(me);
      window.dispatchEvent(new Event(AVATAR_UPDATED_EVENT));
    } catch (err) {
      setAvatarMsg(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const inputCls =
    "w-full border border-line-strong rounded-lg px-3 py-2 text-sm focus:border-line-strong disabled:bg-canvas disabled:text-muted";

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-ink">Profile</h1>
        <p className="text-sm text-muted mt-1">Your account details and sign-in settings.</p>
      </div>

      {/* Identity card */}
      <div className="bg-white border border-line rounded-xl p-6">
        <div className="flex items-center gap-5">
          <div className="relative shrink-0">
            <Avatar src={avatarUrl} name={user.full_name} className="w-20 h-20 text-2xl" />
            <button
              onClick={pickAvatar}
              disabled={uploading}
              className="absolute -bottom-1 -right-1 grid place-items-center w-7 h-7 rounded-full bg-accent text-white hover:bg-accent-hover disabled:opacity-50 transition-colors"
              aria-label="Change profile picture"
              title="Change profile picture"
            >
              {uploading
                ? <Icon.Spinner className="w-3.5 h-3.5 animate-spin" />
                : <Icon.Upload className="w-3.5 h-3.5" />}
            </button>
            <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp"
              className="hidden" onChange={onAvatarFile} />
          </div>
          <div className="min-w-0">
            <p className="text-lg font-semibold text-ink truncate">{user.full_name}</p>
            <p className="text-sm text-muted truncate">{user.email}</p>
            <div className="flex flex-wrap items-center gap-2 mt-2">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${kyc.cls}`}>{kyc.label}</span>
              <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-surface-2 text-ink-soft">
                {ROLE_LABELS[user.role] ?? user.role}
              </span>
              <span className="text-xs text-muted">
                Member since {new Date(user.created_at).toLocaleDateString(undefined, { year: "numeric", month: "long" })}
              </span>
            </div>
          </div>
        </div>
        {avatarMsg && <p className="text-sm text-red-600 mt-3">{avatarMsg}</p>}
        <p className="text-xs text-muted mt-4">JPEG, PNG, or WebP up to 2 MB.</p>
      </div>

      {/* Name + email */}
      <form onSubmit={saveIdentity} className="bg-white border border-line rounded-xl p-6 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="font-semibold text-ink">Name & email</h2>
            <p className="text-sm text-muted mt-0.5">
              {verified
                ? "Locked — these details were confirmed by identity verification. Contact support to change them."
                : "You can edit these until your identity is verified."}
            </p>
          </div>
          {verified && <Icon.Lock className="w-4 h-4 text-muted shrink-0 mt-1" />}
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs text-muted mb-1">Full name</label>
            <input value={fullName} onChange={(e) => setFullName(e.target.value)}
              disabled={verified} required className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">
              Email {user.email_verified
                ? <span className="text-green-700">· verified</span>
                : <span className="text-amber-600">· unverified</span>}
            </label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              disabled={verified} required className={inputCls} />
          </div>
        </div>
        {identityMsg && <Note kind={identityMsg.kind}>{identityMsg.text}</Note>}
        {!verified && (
          <button type="submit" disabled={savingIdentity || !identityDirty}
            className="bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors">
            {savingIdentity ? "Saving…" : "Save changes"}
          </button>
        )}
      </form>

      {/* Password */}
      <form onSubmit={changePassword} className="bg-white border border-line rounded-xl p-6 space-y-4">
        <div>
          <h2 className="font-semibold text-ink">Password</h2>
          <p className="text-sm text-muted mt-0.5">
            At least 12 characters with letters and numbers. Changing it signs out your other sessions.
          </p>
        </div>
        <div className="grid sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs text-muted mb-1">Current password</label>
            <input type="password" value={currentPw} onChange={(e) => setCurrentPw(e.target.value)}
              required autoComplete="current-password" className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">New password</label>
            <input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)}
              required minLength={12} autoComplete="new-password" className={inputCls} />
          </div>
          <div>
            <label className="block text-xs text-muted mb-1">Confirm new password</label>
            <input type="password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)}
              required minLength={12} autoComplete="new-password" className={inputCls} />
          </div>
        </div>
        {pwMsg && <Note kind={pwMsg.kind}>{pwMsg.text}</Note>}
        <button type="submit" disabled={savingPw || !currentPw || !newPw || !confirmPw}
          className="bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors">
          {savingPw ? "Updating…" : "Update password"}
        </button>
      </form>

      {/* Pointers to the rest of account management */}
      <div className="bg-white border border-line rounded-xl p-6 flex items-center justify-between gap-4">
        <div>
          <h2 className="font-semibold text-ink">Security settings</h2>
          <p className="text-sm text-muted mt-0.5">
            Two-factor authentication{user.mfa_enabled ? " (enabled)" : ""} and email verification.
          </p>
        </div>
        <Link href="/dashboard/security"
          className="shrink-0 text-sm font-medium border border-line px-4 py-2 rounded-lg text-ink-soft hover:border-line-strong transition-colors">
          Open Security
        </Link>
      </div>
    </div>
  );
}
