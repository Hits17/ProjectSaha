"use client";

import { useReturnRoute } from "@/components/use-return-route";
import { safeReturnTo } from "@/lib/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Button, TextField, ErrorBanner } from "@/components/ui";

const schema = z.object({
  email: z.string().min(1, "Email required").email("Invalid email"),
  password: z.string().min(1, "Password required"),
  mfa_code: z.string().optional(),
});

type FormData = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const destination = useReturnRoute();
  const { setAuth } = useAuthStore();
  const [serverError, setServerError] = useState("");
  const [mfaRequired, setMfaRequired] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    setServerError("");
    const revision = useAuthStore.getState().revision;
    try {
      const tokens = await api.auth.login(data);
      const user = await api.users.me(tokens.access_token, true);
      if (useAuthStore.getState().revision !== revision) return;
      setAuth(user, tokens.access_token, tokens.refresh_token);
      router.replace(safeReturnTo(new URLSearchParams(window.location.search).get("next")));
    } catch (e) {
      if (e instanceof ApiError && e.message === "MFA code required") {
        setMfaRequired(true);
        setServerError("Enter the 6-digit code from your authenticator app.");
        return;
      }
      setServerError(e instanceof ApiError ? e.message : "Login failed");
    }
  };

  return (
    <>
      <h1 className="text-2xl font-semibold text-ink mb-2">Sign in to your account</h1>
      <p className="text-sm text-muted mb-6">Welcome back to Saha.</p>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          error={errors.email?.message}
          {...register("email")}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          placeholder="••••••••"
          error={errors.password?.message}
          {...register("password")}
        />

        {mfaRequired && (
          <TextField
            label="Authenticator code"
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="123456"
            hint="6-digit code from your authenticator app."
            error={errors.mfa_code?.message}
            {...register("mfa_code")}
          />
        )}

        {serverError && <ErrorBanner>{serverError}</ErrorBanner>}

        <Button type="submit" loading={isSubmitting} className="w-full">
          {isSubmitting ? "Signing in…" : mfaRequired ? "Verify & sign in" : "Sign in"}
        </Button>
      </form>

      <p className="text-center text-sm text-muted mt-6">
        No account?{" "}
        <Link href={`/register?next=${encodeURIComponent(destination)}`} className="text-ink font-medium hover:text-accent hover:underline">
          Create one
        </Link>
      </p>
    </>
  );
}
