"use client";

// Small shared UI primitives so every console page stays consistent.

export function StatCard({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold text-slate-900 mt-1">{value}</p>
      {hint && <p className="text-xs text-slate-400 mt-1">{hint}</p>}
    </div>
  );
}

const BADGE_COLORS: Record<string, string> = {
  // listing
  draft: "bg-slate-100 text-slate-600",
  ai_generating: "bg-purple-100 text-purple-700",
  review: "bg-amber-100 text-amber-700",
  published: "bg-green-100 text-green-700",
  archived: "bg-slate-200 text-slate-500",
  // proposal
  submitted: "bg-blue-100 text-blue-700",
  negotiating: "bg-amber-100 text-amber-700",
  accepted: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-600",
  withdrawn: "bg-slate-200 text-slate-500",
  // transaction
  pending_legal: "bg-slate-100 text-slate-600",
  contract_drafting: "bg-purple-100 text-purple-700",
  contract_review: "bg-amber-100 text-amber-700",
  signing_pending: "bg-blue-100 text-blue-700",
  signed: "bg-blue-100 text-blue-700",
  escrow_pending: "bg-amber-100 text-amber-700",
  escrow_funded: "bg-teal-100 text-teal-700",
  disbursement_pending: "bg-teal-100 text-teal-700",
  completed: "bg-green-100 text-green-700",
  disputed: "bg-red-100 text-red-600",
  cancelled: "bg-slate-200 text-slate-500",
  // kyc
  pending: "bg-slate-100 text-slate-600",
  in_review: "bg-amber-100 text-amber-700",
  verified: "bg-green-100 text-green-700",
  // open library
  approved: "bg-green-100 text-green-700",
  patent: "bg-indigo-100 text-indigo-700",
  research_paper: "bg-teal-100 text-teal-700",
  trademark: "bg-amber-100 text-amber-700",
  // roles
  creator: "bg-indigo-100 text-indigo-700",
  manufacturer: "bg-cyan-100 text-cyan-700",
  legal: "bg-purple-100 text-purple-700",
  admin: "bg-slate-900 text-white",
};

export function Badge({ value }: { value: string }) {
  const color = BADGE_COLORS[value] || "bg-slate-100 text-slate-600";
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${color}`}>
      {value.replace(/_/g, " ")}
    </span>
  );
}

export function Section({ title, children, actions }: {
  title: string; children: React.ReactNode; actions?: React.ReactNode;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">{title}</h2>
        {actions}
      </div>
      {children}
    </div>
  );
}

export function Th({ children }: { children?: React.ReactNode }) {
  return <th className="text-left text-xs font-semibold text-slate-400 uppercase tracking-wide px-3 py-2">{children}</th>;
}

export function Td({ children, className = "" }: { children?: React.ReactNode; className?: string }) {
  return <td className={`px-3 py-2.5 text-sm text-slate-700 border-t border-slate-100 ${className}`}>{children}</td>;
}

export function EmptyRow({ cols, text }: { cols: number; text: string }) {
  return (
    <tr><td colSpan={cols} className="px-3 py-8 text-center text-sm text-slate-400 border-t border-slate-100">{text}</td></tr>
  );
}

export function Btn({ children, onClick, variant = "default", disabled }: {
  children: React.ReactNode; onClick?: () => void;
  variant?: "default" | "danger" | "primary"; disabled?: boolean;
}) {
  const styles = {
    default: "border border-slate-300 text-slate-700 hover:bg-slate-50",
    danger: "border border-red-200 text-red-600 hover:bg-red-50",
    primary: "bg-slate-900 text-white hover:bg-slate-700",
  }[variant];
  return (
    <button onClick={onClick} disabled={disabled}
      className={`px-2.5 py-1 rounded-md text-xs font-medium disabled:opacity-40 ${styles}`}>
      {children}
    </button>
  );
}

export function fmtUsd(n: number | string | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return `$${Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export function fmtDate(s: string | null | undefined): string {
  if (!s) return "—";
  return new Date(s).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function shortId(id: string): string {
  return id.slice(0, 8);
}
