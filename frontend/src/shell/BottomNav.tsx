import { NavLink } from "react-router-dom";

const ITEMS = [
  { to: "/", label: "Inicio", icon: "home", end: true },
  { to: "/purchases", label: "Compras", icon: "shopping_cart", end: false },
  { to: "/decisions", label: "Decisiones", icon: "fact_check", end: false },
  { to: "/alerts", label: "Alertas", icon: "notifications_active", end: false },
  { to: "/cases", label: "Casos", icon: "forum", end: false },
  { to: "/chat", label: "Chat", icon: "smart_toy", end: false },
  { to: "/trace", label: "Inspector", icon: "account_tree", end: false },
];

export default function BottomNav() {
  return (
    <nav
      aria-label="Navegación principal"
      className="fixed bottom-0 w-full z-50 pb-safe bg-surface/90 backdrop-blur-xl shadow-[0_-2px_12px_rgba(75,48,37,0.05)]"
    >
      <div className="flex items-center justify-around h-16 px-space-xs">
        {ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `flex flex-col items-center justify-center min-w-[56px] min-h-[44px] px-space-sm py-1 rounded-full transition-all ${
                isActive ? "text-secondary bg-surface-container font-bold" : "text-on-surface-variant hover:text-on-surface"
              }`
            }
          >
            <span aria-hidden="true" className="material-symbols-outlined text-[20px]">{item.icon}</span>
            <span className="font-label-sm text-label-sm mt-0.5">{item.label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
