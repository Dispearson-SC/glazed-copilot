import { NavLink } from "react-router-dom";

const ITEMS = [
  { to: "/", label: "Resumen", icon: "dashboard", end: true },
  { to: "/chat", label: "Chat", icon: "chat", end: false },
  { to: "/login", label: "Sucursal", icon: "storefront", end: false },
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
              `flex flex-col items-center justify-center min-w-[64px] min-h-[44px] px-space-sm py-1 rounded-full transition-all ${
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
