import { useLayoutEffect, useRef, useState } from "react";
import { useAuth } from "../../AuthContext";
import DaySwitcher from "../DaySwitcher";
import ConversationBar from "./ConversationBar";
import StoreSwitcher from "../StoreSwitcher";

/** Fixed 64px top bar: logo, brand, store code and the settings button. */
export default function CopilotTopBar({ storeCode, onSettings }: { storeCode: string; onSettings: () => void }) {
  const { user, logout } = useAuth();
  const [menu, setMenu] = useState(false);
  const bar = useRef<HTMLElement>(null);
  // Publish the real header height (safe area, day switcher and its wrapping note included) so content starts below it.
  useLayoutEffect(() => {
    const el = bar.current;
    if (!el) return;
    const publish = () => document.documentElement.style.setProperty("--copilot-header-h", `${Math.ceil(el.getBoundingClientRect().height)}px`);
    publish();
    const ro = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(publish);
    ro?.observe(el);
    return () => {
      ro?.disconnect();
      document.documentElement.style.removeProperty("--copilot-header-h");
    };
  }, []);
  return (
    <header ref={bar} className="fixed inset-x-0 top-0 z-40 bg-surface/[.88] pt-safe backdrop-blur-xl shadow-[0_1px_8px_rgba(75,48,37,.04)]">
      <div className="mx-auto flex h-16 max-w-[640px] items-center justify-between px-4">
        <div className="flex min-w-0 items-center gap-2">
          <img alt="Logo Glazed Co." src="/Logo.png" className="h-8 w-8 flex-shrink-0 rounded-full object-contain" />
          <StoreSwitcher className="min-h-[44px]">
            <div className="flex min-w-0 flex-col">
              <span className="font-headline-sm text-headline-sm tracking-tight text-primary">Glazed Co.</span>
              <span className="flex items-center gap-1 truncate font-label-sm text-label-sm font-normal text-on-surface-variant">
                <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full bg-on-tertiary-container" />
                <span className="truncate">Copiloto · Sucursal {storeCode}</span>
              </span>
            </div>
          </StoreSwitcher>
        </div>
        <div className="relative flex-shrink-0">
        <button
          type="button"
          onClick={user ? () => setMenu((v) => !v) : onSettings}
          aria-label="Ajustes del copiloto"
          aria-haspopup={user ? "menu" : undefined}
          aria-expanded={user ? menu : undefined}
          className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full border border-partition/60 bg-white p-0 text-secondary shadow-card"
        >
          <span aria-hidden="true" className="material-symbols-outlined text-[22px]">tune</span>
        </button>
        {user && menu && (
          <>
            <div className="fixed inset-0 z-[-1]" onClick={() => setMenu(false)} data-testid="user-menu-backdrop" />
            <div role="menu" aria-label="Sesión" className="absolute right-0 top-[52px] w-[220px] rounded-[16px] border border-partition/60 bg-elevation p-2 shadow-card">
              <p className="m-0 truncate px-3 py-2 font-body-md text-body-md font-semibold text-primary" title={user.name}>{user.name}</p>
              <button
                type="button"
                role="menuitem"
                onClick={() => void logout()}
                className="flex min-h-[44px] w-full items-center gap-2 rounded-[12px] border-0 bg-transparent px-3 text-left font-body-md text-body-md text-on-surface"
              >
                <span aria-hidden="true" className="material-symbols-outlined text-[20px]">logout</span>
                Cerrar sesión
              </button>
            </div>
          </>
        )}
        </div>
      </div>
      <ConversationBar storeId={storeCode} className="pb-1">
        <DaySwitcher storeId={storeCode} />
      </ConversationBar>
    </header>
  );
}
