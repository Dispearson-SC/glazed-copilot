import type { ReactNode } from "react";
import BottomNav from "./BottomNav";
import TopBar from "./TopBar";

/** Page frame shared by the three screens: fixed top bar, centred column, bottom navigation. */
export default function PageShell({
  subtitle,
  columnClass,
  children,
  floating,
}: {
  subtitle: string;
  columnClass: string;
  children: ReactNode;
  floating?: ReactNode;
}) {
  return (
    <div className="bg-surface font-body-md text-on-surface flex flex-col min-h-screen">
      <TopBar subtitle={subtitle} />
      <main className="flex flex-col relative w-full px-margin pt-16 pb-24 bg-surface min-h-screen">
        <div className={columnClass}>{children}</div>
      </main>
      <BottomNav />
      {floating}
    </div>
  );
}
