import { Link } from "react-router-dom";
import StoreSwitcher from "./StoreSwitcher";
import { useStores } from "../components";
import { useSession } from "../SessionContext";
import { storeLabel } from "../types";

/** Header shared by Resumen, Login and Chat (Main.dc.html): logo, store name, "Resumen", notifications and sign-in. */
export default function TopBar() {
  const { stores, storeId: firstId } = useStores();
  const session = useSession();
  const active = stores.find((s) => s.store_id === (session.storeId || firstId));
  const name = active ? storeLabel(active) : "Glazed Copilot";
  return (
    <header className="fixed top-0 w-full z-50 bg-surface/85 backdrop-blur-xl pt-safe shadow-[0_1px_8px_rgba(75,48,37,0.04)]">
      <div className="h-16 px-margin flex items-center justify-between">
        <div className="flex items-center gap-space-sm min-w-0">
          <img alt="Logo Glazed" className="h-8 w-8 rounded-full object-contain" src="/Logo.png" />
          <StoreSwitcher className="min-h-[44px]">
            <div className="flex flex-col min-w-0">
              <span title={name} className="font-headline-sm text-headline-sm text-primary tracking-tight truncate">{name}</span>
              <span className="font-label-sm text-label-sm text-on-surface-variant font-normal truncate">Resumen</span>
            </div>
          </StoreSwitcher>
        </div>
        <div className="flex items-center gap-space-xs">
          <button type="button" aria-label="Notificaciones" className="w-11 h-11 flex items-center justify-center bg-transparent p-0 text-secondary">
            <span aria-hidden="true" className="material-symbols-outlined text-[22px]">notifications</span>
          </button>
          <Link to="/login" aria-label="Iniciar sesión" className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
            <span aria-hidden="true" className="material-symbols-outlined text-white text-[18px]">person</span>
          </Link>
        </div>
      </div>
    </header>
  );
}
