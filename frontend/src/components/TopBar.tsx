import { Link } from "react-router-dom";
import { useStores } from "../components";
import { useSession } from "../SessionContext";
import { splitStoreName } from "../format";
import { storeLabel } from "../types";

export default function TopBar({ subtitle = "Resumen" }: { subtitle?: string }) {
  const { stores, storeId: firstId } = useStores();
  const session = useSession();
  const active = stores.find((s) => s.store_id === (session.storeId || firstId));
  const fullName = active ? storeLabel(active) : "Glazed Copilot";
  const [storeName, branch] = splitStoreName(fullName);
  return (
    <header className="fixed top-0 w-full z-50 bg-surface/85 backdrop-blur-xl pt-safe shadow-[0_1px_8px_rgba(75,48,37,0.04)]">
      <div className="h-16 px-margin flex items-center justify-between">
        <div className="flex items-center gap-space-sm min-w-0">
          <img alt="Logo Glazed" className="h-8 w-auto object-contain" src="/Logo.png" />
          <div className="flex flex-col min-w-0">
            <span title={fullName} className="font-headline-sm text-headline-sm text-primary tracking-tight truncate">{storeName}</span>
            <span className="font-label-sm text-label-sm text-on-surface-variant font-normal truncate">{branch ?? subtitle}</span>
          </div>
        </div>
        <div className="flex items-center gap-space-xs">
          <Link
            to="/login"
            aria-label="Cambiar sucursal"
            className="w-8 h-8 rounded-full bg-primary flex items-center justify-center"
          >
            <span aria-hidden="true" className="material-symbols-outlined text-on-primary text-[18px]">person</span>
          </Link>
        </div>
      </div>
    </header>
  );
}
