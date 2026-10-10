import type { ReactNode } from "react";
import BottomNav from "./BottomNav";
import TopBar from "./TopBar";

/** Page frame shared by Resumen, Login and Chat: fixed top bar, centred column, bottom navigation. */
export default function PageShell({ columnClass, children, floating, nav = true }: { columnClass: string; children: ReactNode; floating?: ReactNode; nav?: boolean }) {
  return (
    <div className="bg-surface font-body-md text-on-surface flex flex-col min-h-screen">
      <TopBar />
      <main className="flex flex-col relative w-full px-margin pt-16 pb-24 bg-surface min-h-screen">
        <div className={columnClass}>{children}</div>
      </main>
      {nav && <BottomNav />}
      {floating}
    </div>
  );
}
