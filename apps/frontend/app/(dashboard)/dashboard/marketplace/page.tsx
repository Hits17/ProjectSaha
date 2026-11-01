"use client";

import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { KYCFlow, KYCStatusBadge } from "@/components/auth/kyc-flow";
import { OnboardingChecklist } from "@/components/onboarding-checklist";
import { StatTile, PageHeader, cn } from "@/components/ui";
import * as Icon from "@/components/ui/icons";

const ROLE_LABEL: Record<string, string> = {
  creator: "IP Creator",
  manufacturer: "Manufacturer",
  legal: "Legal Partner",
  admin: "Admin",
};

// Open-roles model: every marketplace member can act as both IP creator and
// manufacturer, so creator and manufacturer get the same set of cards.
const MARKETPLACE_STEPS: {
  title: string;
  description: string;
  href: string;
  icon: (p: { className?: string }) => React.ReactNode;
}[] = [
  { title: "Create an IP Listing", description: "Use AI dialogue to document your IP and generate a Bill of Materials.", href: "/dashboard/listings", icon: Icon.FileText },
  { title: "Discover IP", description: "Search for IP using natural language — AI finds and ranks matches.", href: "/dashboard/discover", icon: Icon.Compass },
  { title: "Buy & Sell Raw Materials", description: "Source production inputs in your region, or list materials you can supply.", href: "/dashboard/materials", icon: Icon.Package },
  { title: "Join the Community", description: "Connect with researchers and makers in topic communities to advance IP R&D.", href: "/dashboard/community", icon: Icon.Users },
  { title: "Proposals", description: "Make offers on published IP, and respond to offers on your own listings.", href: "/dashboard/proposals", icon: Icon.Handshake },
  { title: "Track Transactions", description: "Follow your active deals through legal, contract signing, and escrow.", href: "/dashboard/transactions", icon: Icon.Shield },
];

export default function DashboardPage() {
  const { user } = useAuthStore();
  if (!user) return null;

  const isVerified = user.kyc_status === "verified";
  const steps = user.role === "admin" ? [] : MARKETPLACE_STEPS;

  return (
    <div className="space-y-8">
      <PageHeader
        title="IP marketplace"
        description={`${ROLE_LABEL[user.role]} · ${user.email}`}
        actions={<KYCStatusBadge status={user.kyc_status} />}
      />

      <section id="verification" className="scroll-mt-24" aria-label="Identity verification"><KYCFlow /></section>

      <OnboardingChecklist />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatTile label="Account" value={user.is_active ? "Active" : "Inactive"} icon={<Icon.Shield />} />
        <StatTile label="Role" value={ROLE_LABEL[user.role]} icon={<Icon.Users />} />
        <StatTile
          label="Member Since"
          value={new Date(user.created_at).toLocaleDateString("en-US", { month: "short", year: "numeric" })}
          icon={<Icon.TrendingUp />}
        />
      </div>

      {steps.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-muted uppercase tracking-wide mb-3 font-sans">
            What you can do
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {steps.map((step) => {
              const I = step.icon;
              const locked = !isVerified;
              const inner = (
                <div
                  className={cn(
                    "bg-surface border rounded-xl p-4 flex items-center gap-4 h-full transition-all",
                    locked
                      ? "border-line opacity-60"
                      : "border-line shadow-sm hover:border-line-strong hover:shadow-md",
                  )}
                >
                  <div
                    className={cn(
                      "w-10 h-10 rounded-lg grid place-items-center shrink-0",
                      locked ? "bg-surface-2 text-muted" : "bg-accent-soft text-accent",
                    )}
                  >
                    {locked ? <Icon.Lock className="w-5 h-5" /> : <I className="w-5 h-5" />}
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium text-ink text-sm">{step.title}</p>
                    <p className="text-xs text-muted mt-0.5">{step.description}</p>
                  </div>
                  {!locked && <Icon.ChevronRight className="w-4 h-4 text-muted ml-auto shrink-0" />}
                </div>
              );
              return isVerified ? (
                <Link key={step.title} href={step.href}>
                  {inner}
                </Link>
              ) : (
                <div key={step.title}>{inner}</div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
