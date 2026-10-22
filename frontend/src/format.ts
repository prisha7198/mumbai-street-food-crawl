export const rupees = (n: number) => `₹${n.toLocaleString("en-IN")}`;

export function minutes(n: number): string {
  const m = Math.max(1, Math.round(n));
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const r = m % 60;
  return r ? `${h} hr ${r} min` : `${h} hr`;
}

export function distance(m: number): string {
  return m < 1000 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`;
}

export function time12(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  const suffix = h < 12 ? "AM" : "PM";
  const h12 = h % 12 || 12;
  return m ? `${h12}:${String(m).padStart(2, "0")} ${suffix}` : `${h12} ${suffix}`;
}

export const WHEN_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "Now" },
  { value: "08:30", label: "Breakfast" },
  { value: "13:00", label: "Lunch" },
  { value: "17:00", label: "Evening snack" },
  { value: "20:00", label: "Dinner" },
  { value: "23:30", label: "Late night" },
];

export function whenLabel(t: string | null): string {
  if (!t) return "Now";
  return WHEN_OPTIONS.find((o) => o.value === t)?.label ?? time12(t);
}

export const DIET_OPTIONS = [
  { value: "any", label: "Any" },
  { value: "veg", label: "Veg" },
  { value: "jain", label: "Jain" },
  { value: "non_veg", label: "Non-veg" },
] as const;
