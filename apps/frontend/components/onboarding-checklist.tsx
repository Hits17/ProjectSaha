"use client";

import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { useMyListings } from "@/lib/hooks";
import { Card, CardBody, CardHeader, CardTitle, cn } from "@/components/ui";
import * as Icon from "@/components/ui/icons";

type Step = { label: string; done: boolean; href: string; cta: string };

/** First-run checklist. Renders only while at least one step is incomplete, so it
 *  disappears for established users. */
export function OnboardingChecklist() {
  const user = useAuthStore((s) => s.user);
  const { data: listings } = useMyListings();

  if (!user || user.role === "admin") return null;

  const steps: Step[] = [
    {
      label: "Verify your email",
      done: user.email_verified,
      href: "/dashboard/security",
      cta: "Verify",
    },
    {
      label: "Complete identity verification (KYC)",
      done: user.kyc_status === "verified",
      href: "/dashboard/marketplace#verification",
      cta: "Start",
    },
    {
      label: "Create your first IP listing",
      done: (listings?.length ?? 0) > 0,
      href: "/dashboard/listings/new",
      cta: "Create",
    },
    {
      label: "Enable two-factor authentication",
      done: user.mfa_enabled,
      href: "/dashboard/security",
      cta: "Enable",
    },
  ];

  const remaining = steps.filter((s) => !s.done).length;
  if (remaining === 0) return null;

  const completed = steps.length - remaining;
  const pct = Math.round((completed / steps.length) * 100);

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>Get set up</CardTitle>
        <span className="text-xs text-muted tabular-nums">
          {completed} / {steps.length} complete
        </span>
      </CardHeader>
      <CardBody className="space-y-3">
        <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
          <div className="h-full bg-accent rounded-full transition-[width] duration-500" style={{ width: `${pct}%` }} />
        </div>
        <ul className="divide-y divide-line">
          {steps.map((s) => (
            <li key={s.label} className="flex items-center gap-3 py-2.5">
              <span
                className={cn(
                  "grid place-items-center w-5 h-5 rounded-full shrink-0",
                  s.done ? "bg-success text-white" : "border border-line-strong text-transparent",
                )}
              >
                <Icon.Check className="w-3 h-3" />
              </span>
              <span className={cn("text-sm flex-1", s.done ? "text-muted line-through" : "text-ink")}>
                {s.label}
              </span>
              {!s.done && (
                <Link
                  href={s.href}
                  className="text-sm font-medium text-accent hover:underline shrink-0"
                >
                  {s.cta} →
                </Link>
              )}
            </li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}
