// Shared IP R&D community topic catalogue + visual metadata. Kept out of the
// route page files so both pages can import it without cross-importing a page.tsx
// (Next.js restricts what route segment files may export).

export type TopicMeta = {
  value: string;
  label: string;
  emoji: string;
  gradient: string; // tailwind gradient for the icon tile
  chip: string; // tailwind classes for the small topic chip
  soft: string; // soft tinted background (banners)
};

export const TOPICS: TopicMeta[] = [
  { value: "biotech_pharma", label: "Biotech & Pharma", emoji: "🧬", gradient: "from-emerald-400 to-teal-500", chip: "bg-emerald-50 text-emerald-700 border-emerald-200", soft: "from-emerald-50 to-teal-50" },
  { value: "clean_energy", label: "Clean Energy", emoji: "⚡", gradient: "from-lime-400 to-green-500", chip: "bg-green-50 text-green-700 border-green-200", soft: "from-lime-50 to-green-50" },
  { value: "materials_science", label: "Materials Science", emoji: "🧪", gradient: "from-amber-400 to-orange-500", chip: "bg-amber-50 text-amber-700 border-amber-200", soft: "from-amber-50 to-orange-50" },
  { value: "software_ai", label: "Software & AI", emoji: "🤖", gradient: "from-violet-500 to-purple-600", chip: "bg-violet-50 text-violet-700 border-violet-200", soft: "from-violet-50 to-purple-50" },
  { value: "hardware_electronics", label: "Hardware & Electronics", emoji: "🔌", gradient: "from-sky-400 to-blue-600", chip: "bg-sky-50 text-sky-700 border-sky-200", soft: "from-sky-50 to-blue-50" },
  { value: "consumer_products", label: "Consumer Products", emoji: "🛍️", gradient: "from-pink-400 to-rose-500", chip: "bg-pink-50 text-pink-700 border-pink-200", soft: "from-pink-50 to-rose-50" },
  { value: "agritech_food", label: "Agritech & Food", emoji: "🌾", gradient: "from-lime-500 to-emerald-600", chip: "bg-lime-50 text-lime-700 border-lime-200", soft: "from-lime-50 to-emerald-50" },
  { value: "medical_devices", label: "Medical Devices", emoji: "🩺", gradient: "from-rose-400 to-red-500", chip: "bg-rose-50 text-rose-700 border-rose-200", soft: "from-rose-50 to-red-50" },
  { value: "industrial_manufacturing", label: "Industrial Manufacturing", emoji: "🏭", gradient: "from-orange-400 to-amber-600", chip: "bg-orange-50 text-orange-700 border-orange-200", soft: "from-orange-50 to-amber-50" },
  { value: "general", label: "General", emoji: "💬", gradient: "from-slate-500 to-slate-700", chip: "bg-slate-100 text-slate-600 border-slate-200", soft: "from-slate-50 to-gray-100" },
];

const FALLBACK: TopicMeta = TOPICS[TOPICS.length - 1];

export const topicMeta = (value: string): TopicMeta =>
  TOPICS.find((t) => t.value === value) ?? { ...FALLBACK, value, label: value };

export const topicLabel = (value: string) => topicMeta(value).label;
