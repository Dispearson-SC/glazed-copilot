import { usd } from "../issues";

const DAY_MS = 86_400_000;

export const NO_DATA = "Sin datos";

/** Shifts an ISO date (YYYY-MM-DD) by whole days, in UTC so DST never matters. */
export function shiftDate(iso: string, days: number): string {
  return new Date(Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10);
}

/** The 7 days ending at `end` (inclusive), oldest first. */
export const lastSevenDays = (end: string): string[] => Array.from({ length: 7 }, (_, i) => shiftDate(end, i - 6));

export const weekdayShort = (iso: string): string =>
  new Intl.DateTimeFormat("es-MX", { weekday: "short", timeZone: "UTC" }).format(new Date(`${iso.slice(0, 10)}T00:00:00Z`));

export const longDate = (iso: string): string =>
  new Intl.DateTimeFormat("es-MX", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" }).format(
    new Date(`${iso.slice(0, 10)}T00:00:00Z`),
  );

export const money = (n: number | null | undefined): string => (n == null ? NO_DATA : usd(n));

export const avgTicket = (sales: number | null | undefined, tx: number | null | undefined): string =>
  sales == null || !tx ? "—" : usd(sales / tx);

export const signedPct = (n: number): string => `${n >= 0 ? "+" : "-"}${Math.abs(n).toFixed(1)}%`;
