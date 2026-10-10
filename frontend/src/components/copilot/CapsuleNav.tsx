import type { Tab } from "../../data/copilot";

const TABS: { id: Tab; icon: string; label: string }[] = [
  { id: "agente", icon: "forum", label: "Agente" },
  { id: "decisiones", icon: "fact_check", label: "Decisiones" },
  { id: "sucursal", icon: "storefront", label: "Sucursal" },
  { id: "memorias", icon: "psychology", label: "Memorias" },
  { id: "alertas", icon: "warning", label: "Alertas" },
];

export type CapsuleBadges = Partial<Record<Tab, number>>;

/** Floating capsule with the five copilot windows. */
export default function CapsuleNav({ tab, onChange, badges }: { tab: Tab; onChange: (t: Tab) => void; badges: CapsuleBadges }) {
  return (
    <>
    {/* Solid strip behind the floating capsule so scrolled content never peeks under or around it. */}
    <div aria-hidden="true" data-testid="capsule-backdrop" className="pointer-events-none fixed inset-x-0 bottom-0 z-40 h-[88px] bg-surface" />
    <nav
      aria-label="Ventanas del copiloto"
      className="fixed inset-x-3 bottom-4 z-50 mx-auto flex h-16 max-w-[616px] items-stretch gap-0.5 rounded-full border border-partition/60 bg-white p-1.5 shadow-[0_1px_3px_rgba(75,48,37,.06),0_12px_32px_-6px_rgba(75,48,37,.16)]"
    >
      {TABS.map((t) => {
        const active = tab === t.id;
        const badge = badges[t.id] ?? 0;
        return (
          <button
            key={t.id}
            type="button"
            onClick={() => onChange(t.id)}
            aria-current={active ? "page" : undefined}
            aria-label={badge > 0 ? `${t.label}, ${badge} pendientes` : t.label}
            className={`relative flex min-h-[44px] min-w-0 flex-1 flex-col items-center justify-center gap-px rounded-full ${
              active ? "bg-surface-container text-secondary font-bold" : "bg-transparent text-on-surface-variant font-medium"
            }`}
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[21px]">{t.icon}</span>
            <span aria-hidden="true" className="text-[10.5px] leading-[13px] tracking-[0.01em]">{t.label}</span>
            {badge > 0 && (
              <span aria-hidden="true" className="absolute right-2 top-0.5 h-4 min-w-4 rounded-full bg-on-tertiary-container px-1 text-center text-[10px] font-bold leading-4 text-white">
                {badge}
              </span>
            )}
          </button>
        );
      })}
    </nav>
    </>
  );
}
