import type { Option, Range3, Tier } from "./types";

/** Highest net_usd_mid among options with tier != N0; do_nothing competes too. */
export function bestOption(options: Option[]): Option | null {
  const eligible = options.filter((o) => o.tier !== "N0");
  if (eligible.length === 0) return null;
  return eligible.reduce((best, o) => (o.net_usd_mid > best.net_usd_mid ? o : best));
}

const TIERS: Record<Tier, { label: string; className: string }> = {
  N0: { label: "N0 no actuar", className: "tier-n0" },
  N1: { label: "N1 automático", className: "tier-n1" },
  N2: { label: "N2 propuesta", className: "tier-n2" },
  N3: { label: "N3 diálogo", className: "tier-n3" },
};
export const tierInfo = (t: Tier) => TIERS[t];

export type DeadlineUrgency = "overdue" | "today" | "tomorrow" | null;

const dayNumber = (iso: string) => Math.floor(Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) / 86_400_000);

/** Compares against the simulated date, not the wall clock. */
export function deadlineUrgency(deadline: string | null | undefined, simToday: string): DeadlineUrgency {
  if (!deadline) return null;
  const d = dayNumber(deadline) - dayNumber(simToday);
  if (d < 0) return "overdue";
  if (d === 0) return "today";
  if (d === 1) return "tomorrow";
  return null;
}

export const isLowConfidence = (score: number) => score < 0.5;

export const usd = (n: number) => `${n < 0 ? "-" : ""}$${Math.abs(n).toFixed(2)}`;
export const rangeText = (r: Range3) => `${usd(r.low)} – ${usd(r.high)}`;
export const wasteMid = (w: number | Range3) => (typeof w === "number" ? w : w.mid);
