
/** US dollars with two decimals (the backend reports USD). */
const usdDigits = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const usd = (n: number): string => `${n < 0 ? "-" : ""}$${usdDigits.format(Math.abs(n))}`;

/** Money with an explicit sign: "+$1,234.56", "-$22.00", and a bare "$0.00" for zero. */
export const signedUsd = (n: number): string => (n > 0 ? `+${usd(n)}` : usd(n));

const DAY_MS = 86_400_000;

export const NO_DATA = "Sin datos";

/** Shifts an ISO date (YYYY-MM-DD) by whole days, in UTC so DST never matters. */
export function shiftDate(iso: string, days: number): string {
  return new Date(Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10);
}

export const weekdayShort = (iso: string): string =>
  new Intl.DateTimeFormat("es-MX", { weekday: "short", timeZone: "UTC" }).format(new Date(`${iso.slice(0, 10)}T00:00:00Z`));

export const longDate = (iso: string): string =>
  new Intl.DateTimeFormat("es-MX", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(
    new Date(`${iso.slice(0, 10)}T00:00:00Z`),
  );

export const money = (n: number | null | undefined): string => (n == null ? NO_DATA : usd(n));

export const avgTicket = (sales: number | null | undefined, tx: number | null | undefined): string =>
  sales == null || !tx ? "—" : usd(sales / tx);

export const signedPct = (n: number): string => `${n >= 0 ? "+" : "-"}${Math.round(Math.abs(n))}%`;

/** "dd/mm" of an ISO date. */
export const dayMonth = (iso: string): string => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

/** Up to two initials from the first words that start with a letter ("50 Donut Holes" -> "DH"). */
export const initials = (name: string): string => {
  const words = name.split(/\s+/).filter((w) => /^\p{L}/u.test(w));
  return (words.length ? words : name.split(/\s+/)).slice(0, 2).map((w) => w.charAt(0).toUpperCase()).join("");
};

/** "Site · Store" -> [site, store]; without a separator the whole name is the title. */
export const splitStoreName = (name: string): [string, string | null] => {
  const i = name.indexOf(" · ");
  return i < 0 ? [name, null] : [name.slice(0, i), name.slice(i + 3)];
};

/** "mar 21": short weekday and day of month. */
export const weekdayDay = (iso: string): string => `${weekdayShort(iso).replace(".", "")} ${Number(iso.slice(8, 10))}`;

/** "14:05" in the viewer's time zone; "" for a missing or invalid timestamp. */
export const clockTime = (ts: string | undefined): string => {
  const d = ts ? new Date(ts) : null;
  return d && !Number.isNaN(d.getTime()) ? d.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit", hour12: false }) : "";
};

const usdWholeFmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
/** "$4,320" (no cents), for ranges. */
export const usdWhole = (n: number): string => `${n < 0 ? "-" : ""}$${usdWholeFmt.format(Math.abs(n))}`;

/** "Sábado 10 de octubre": weekday, day and month (no year), capitalised. */
export const dateLabel = (iso: string): string => {
  const t = new Intl.DateTimeFormat("es-MX", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" })
    .format(new Date(`${iso.slice(0, 10)}T00:00:00Z`))
    .replace(",", "");
  return t.charAt(0).toUpperCase() + t.slice(1);
};
