"use client";

import { useReturnRoute } from "@/components/use-return-route";
import { safeReturnTo } from "@/lib/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError, type UserRole } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { Button, TextField, ErrorBanner, cn } from "@/components/ui";

const schema = z.object({
  full_name: z.string().trim().max(255).min(2, "Name must be at least 2 characters"),
  email: z.string().min(1, "Email required").email("Invalid email"),
  // Matches the backend PASSWORD_MIN_LENGTH policy (12).
  password: z.string().min(12, "Password must be at least 12 characters"),
  role: z.enum(["creator", "manufacturer"] as const),
});

type FormData = z.infer<typeof schema>;

export default function RegisterPage() {
  const router = useRouter();
  const destination = useReturnRoute();
  const { setAuth } = useAuthStore();
  const [serverError, setServerError] = useState("");

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { role: "creator" },
  });

  const selectedRole = watch("role");

  const onSubmit = async (data: FormData) => {
    setServerError("");
    const revision = useAuthStore.getState().revision;
    try {
      await api.auth.register({ ...data, role: data.role as UserRole });
      const tokens = await api.auth.login({ email: data.email, password: data.password });
      const user = await api.users.me(tokens.access_token, true);
      if (useAuthStore.getState().revision !== revision) return;
      setAuth(user, tokens.access_token, tokens.refresh_token);
      router.replace(safeReturnTo(new URLSearchParams(window.location.search).get("next")));
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : "Registration failed");
    }
  };

  return (
    <>
      <h1 className="text-2xl font-semibold text-ink mb-2">Create your account</h1>
      <p className="text-sm text-muted mb-6">Discover open research, join creative communities and build with others.</p>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <TextField
          label="Full name"
          placeholder="Your full name"
          error={errors.full_name?.message}
          {...register("full_name")}
        />
        <TextField
          label="Email"
          type="email"
          placeholder="you@example.com"
          error={errors.email?.message}
          {...register("email")}
        />
        <TextField
          label="Password"
          type="password"
          placeholder="Min. 12 characters"
          hint="Use at least 12 characters."
          error={errors.password?.message}
          {...register("password")}
        />

        <div>
          <label className="block text-sm font-medium text-ink mb-2">My starting interest</label>
          <div className="grid grid-cols-2 gap-3">
            {(["creator", "manufacturer"] as const).map((role) => (
              <label key={role} className="relative cursor-pointer">
                <input {...register("role")} type="radio" value={role} className="peer sr-only" />
                <div
                  className={cn(
                    "border-2 rounded-lg p-3 text-center text-sm font-medium transition-colors",
                    selectedRole === role
                      ? "border-ink bg-accent-soft text-ink"
                      : "border-line hover:border-line-strong text-ink-soft",
                  )}
                >
                  {role === "creator" ? "Research & creation" : "Prototyping & manufacturing"}
                </div>
              </label>
            ))}
          </div>
          <p className="text-xs text-muted mt-2">
            This is only a profile preference. Every member can discover, join projects and contribute; financial KYC is only needed for transactions.
          </p>
        </div>

        {serverError && <ErrorBanner>{serverError}</ErrorBanner>}

        <Button type="submit" loading={isSubmitting} className="w-full">
          {isSubmitting ? "Creating account…" : "Create account"}
        </Button>
      </form>

      <p className="text-center text-sm text-muted mt-6">
        Already have an account?{" "}
        <Link href={`/login?next=${encodeURIComponent(destination)}`} className="text-ink font-medium hover:text-accent hover:underline">
          Sign in
        </Link>
      </p>
    </>
  );
}
