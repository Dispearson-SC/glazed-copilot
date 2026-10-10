import type { PromoView } from "../../data/copilot";

/** "Activar promoción" option: the primary line, the numbers, the muted basis and the data caveat. */
export default function PromoBlock({ promo }: { promo: PromoView }) {
  return (
    <div aria-label={promo.label} className="flex flex-col gap-1 rounded-xl bg-surface-container px-3 py-2">
      <p className="m-0 flex items-center gap-1.5 text-[13px] font-semibold leading-[19px] text-primary">
        <span aria-hidden="true" className="material-symbols-outlined text-[16px] text-secondary">sell</span>
        {promo.primary}
      </p>
      {promo.details.map((d) => (
        <p key={d} className="m-0 text-[13px] leading-[19px] text-on-surface">{d}</p>
      ))}
      {promo.basis && <p className="m-0 text-[11px] leading-4 text-on-surface-variant/80">{promo.basis}</p>}
      {promo.caveat && (
        <p className="m-0 flex gap-1.5 text-[12px] leading-4 text-on-surface-variant">
          <span aria-hidden="true" className="material-symbols-outlined text-[16px] text-on-tertiary-container">info</span>
          {promo.caveat}
        </p>
      )}
    </div>
  );
}
