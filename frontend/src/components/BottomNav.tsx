import { NavLink } from "react-router-dom";

const ITEMS = [
  { to: "/", label: "Resumen", icon: "dashboard", end: true },
  { to: "#", label: "Pedidos", icon: "receipt_long", end: false },
  { to: "#", label: "Productos", icon: "local_cafe", end: false },
  { to: "/chat", label: "Chat", icon: "chat", end: false },
  { to: "#", label: "Ajustes", icon: "tune", end: false },
];

const base = "flex flex-col items-center justify-center min-w-[64px] min-h-[44px] px-space-sm py-1 rounded-full transition-all";
const on = "text-secondary bg-surface-container font-bold";
const off = "text-on-surface-variant hover:text-on-surface";

/** Bottom navigation of Main.dc.html and Chat.dc.html: Pedidos, Productos and Ajustes have no screen yet (href="#" as in the design). */
export default function BottomNav() {
  return (
    <nav aria-label="Navegación principal" className="fixed bottom-0 w-full z-50 pb-safe bg-surface/90 backdrop-blur-xl shadow-[0_-2px_12px_rgba(75,48,37,0.05)]">
      <div className="flex items-center justify-around h-16 px-space-xs">
        {ITEMS.map((item) => {
          const content = (
            <>
              <span aria-hidden="true" className="material-symbols-outlined text-[20px]">{item.icon}</span>
              <span className="font-label-sm text-label-sm mt-0.5">{item.label}</span>
            </>
          );
          return item.to === "#" ? (
            <a key={item.label} href="#" className={`${base} ${off}`}>{content}</a>
          ) : (
            <NavLink key={item.label} to={item.to} end={item.end} className={({ isActive }) => `${base} ${isActive ? on : off}`}>
              {content}
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
}
