"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/auth";
import { api, ApiError } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  CardTitle,
  ErrorBanner,
  Field,
  Input,
  PageHeader,
  useToast,
} from "@/components/ui";
import * as Icon from "@/components/ui/icons";

export default function SecurityPage() {
  const { accessToken, user } = useAuthStore();
  const toast = useToast();

  const [mfaEnabled, setMfaEnabled] = useState<boolean | null>(null);
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!accessToken) return;
    api.auth.mfaStatus(accessToken).then((s) => setMfaEnabled(s.mfa_enabled)).catch(() => {});
  }, [accessToken]);

  if (!accessToken || !user) return null;

  const beginSetup = async () => {
    setError("");
    setBusy(true);
    try {
      setSetup(await api.auth.mfaSetup(accessToken));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to start MFA setup");
    } finally {
      setBusy(false);
    }
  };

  const confirmEnable = async () => {
    setError("");
    setBusy(true);
    try {
      const r = await api.auth.mfaEnable(accessToken, code);
      setMfaEnabled(r.mfa_enabled);
      setSetup(null);
      setCode("");
      toast.success("Two-factor authentication enabled.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not verify code");
    } finally {
      setBusy(false);
    }
  };

  const disable = async () => {
    setError("");
    setBusy(true);
    try {
      const r = await api.auth.mfaDisable(accessToken, code);
      setMfaEnabled(r.mfa_enabled);
      setCode("");
      toast.info("Two-factor authentication disabled.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not verify code");
    } finally {
      setBusy(false);
    }
  };

  const resendVerification = async () => {
    try {
      await api.auth.requestEmailVerification(accessToken);
      toast.success("Verification email sent — check your inbox.");
    } catch {
      toast.error("Could not send verification email.");
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <PageHeader title="Security" description="Protect your account with two-factor authentication." />

      {error && <ErrorBanner>{error}</ErrorBanner>}

      {/* Email verification */}
      <Card>
        <CardHeader>
          <CardTitle>Email verification</CardTitle>
        </CardHeader>
        <CardBody className="flex items-center justify-between gap-4">
          <p className="text-sm text-muted">
            A verified email keeps your account recoverable and secure.
          </p>
          <Button variant="secondary" size="sm" onClick={resendVerification}>
            <Icon.Bell className="w-4 h-4" />
            Resend link
          </Button>
        </CardBody>
      </Card>

      {/* MFA */}
      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>Two-factor authentication (TOTP)</CardTitle>
          {mfaEnabled !== null &&
            (mfaEnabled ? (
              <Badge tone="success" dot>
                Enabled
              </Badge>
            ) : (
              <Badge tone="neutral" dot>
                Disabled
              </Badge>
            ))}
        </CardHeader>
        <CardBody className="space-y-4">
          <p className="text-sm text-muted">
            Use an authenticator app (Google Authenticator, 1Password, Authy) to require a
            time-based code at sign-in.
          </p>

          {mfaEnabled === false && !setup && (
            <Button onClick={beginSetup} loading={busy}>
              <Icon.Lock className="w-4 h-4" />
              Set up authenticator
            </Button>
          )}

          {setup && (
            <div className="space-y-3 rounded-lg border border-line bg-surface-2 p-4">
              <p className="text-sm text-ink">
                Add this secret to your authenticator app, then enter the 6-digit code to confirm.
              </p>
              <code className="block text-sm font-mono bg-surface border border-line rounded px-3 py-2 break-all">
                {setup.secret}
              </code>
              <Field label="6-digit code">
                <Input
                  inputMode="numeric"
                  placeholder="123456"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </Field>
              <div className="flex gap-2">
                <Button onClick={confirmEnable} loading={busy}>
                  Verify & enable
                </Button>
                <Button variant="ghost" onClick={() => setSetup(null)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {mfaEnabled === true && (
            <div className="space-y-3">
              <Field label="Enter a current code to disable">
                <Input
                  inputMode="numeric"
                  placeholder="123456"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </Field>
              <Button variant="danger" onClick={disable} loading={busy}>
                Disable two-factor
              </Button>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
