import { topicMeta } from "./topics";

// Deterministic avatar gradient from a seed (user id or name).
const AVATAR_GRADIENTS = [
  "from-rose-400 to-pink-600",
  "from-orange-400 to-amber-600",
  "from-emerald-400 to-teal-600",
  "from-sky-400 to-blue-600",
  "from-violet-400 to-purple-600",
  "from-fuchsia-400 to-pink-600",
  "from-cyan-400 to-sky-600",
  "from-lime-400 to-green-600",
];

function hash(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return h;
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function Avatar({ name, seed, size = 36 }: { name: string; seed?: string; size?: number }) {
  const grad = AVATAR_GRADIENTS[hash(seed || name) % AVATAR_GRADIENTS.length];
  return (
    <div
      className={`shrink-0 rounded-full bg-gradient-to-br ${grad} text-white font-semibold flex items-center justify-center shadow-sm ring-2 ring-white`}
      style={{ width: size, height: size, fontSize: size * 0.38 }}
      title={name}
    >
      {initials(name)}
    </div>
  );
}

export function TopicIcon({ topic, size = 44 }: { topic: string; size?: number }) {
  const m = topicMeta(topic);
  return (
    <div
      className={`shrink-0 rounded-xl bg-gradient-to-br ${m.gradient} flex items-center justify-center shadow-sm`}
      style={{ width: size, height: size, fontSize: size * 0.5 }}
      aria-hidden
    >
      <span>{m.emoji}</span>
    </div>
  );
}

export function TopicChip({ topic }: { topic: string }) {
  const m = topicMeta(topic);
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full border ${m.chip}`}>
      <span>{m.emoji}</span>
      {m.label}
    </span>
  );
}

/* ---- Inline SVG icons (no icon dependency) ---- */
type IconProps = { className?: string };
const base = "w-4 h-4";

export const IconUsers = ({ className = base }: IconProps) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></svg>
);
export const IconLock = ({ className = base }: IconProps) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>
);
export const IconGlobe = ({ className = base }: IconProps) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" /></svg>
);
export const IconSearch = ({ className = base }: IconProps) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></svg>
);
export const IconSend = ({ className = base }: IconProps) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></svg>
);
export const IconPlus = ({ className = base }: IconProps) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12h14" /></svg>
);
export const IconArrowLeft = ({ className = base }: IconProps) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 19-7-7 7-7M19 12H5" /></svg>
);
export const IconCrown = ({ className = base }: IconProps) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor"><path d="M5 16 3 7l5.5 4L12 5l3.5 6L21 7l-2 9H5Zm0 2h14v2H5v-2Z" /></svg>
);
export const IconX = ({ className = base }: IconProps) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
);
export const IconChat = ({ className = base }: IconProps) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
);
export const IconSparkles = ({ className = base }: IconProps) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.8 4.7L18 8.5l-4.2 1.8L12 15l-1.8-4.7L6 8.5l4.2-1.8L12 2Zm6 11 .9 2.3L21 16l-2.1.9L18 19l-.9-2.1L15 16l2.1-.7L18 13ZM5 14l.9 2.3L8 17l-2.1.9L5 20l-.9-2.1L2 17l2.1-.7L5 14Z" /></svg>
);
