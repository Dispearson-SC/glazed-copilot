import type { ReactNode } from "react";

/** One shimmering block. Decorative: the region around it carries the accessible name. */
export function Bone({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded-xl bg-surface-variant/70 ${className}`} />;
}

/** Announces a loading region to assistive tech (role=status, aria-busy). */
export function Loading({ label, className = "", children }: { label: string; className?: string; children: ReactNode }) {
  return (
    <div role="status" aria-busy="true" aria-label={label} className={className}>
      {children}
    </div>
  );
}

const card = "flex flex-col gap-2.5 rounded-[18px] border border-partition/60 bg-white p-4 shadow-card";

/** Same shape as ApprovalCard / TechDecisionCard: badge row, title, summary, figure + bar, button. */
export function DecisionCardSkeleton() {
  return (
    <div className={card}>
      <div className="flex justify-between"><Bone className="h-5 w-24 rounded-full" /><Bone className="h-4 w-16" /></div>
      <Bone className="h-5 w-4/5" />
      <Bone className="h-4 w-full" />
      <div className="flex items-center gap-3"><Bone className="h-6 w-20" /><Bone className="h-2 flex-1 rounded-full" /></div>
      <Bone className="h-12 w-full rounded-full" />
    </div>
  );
}

export function DecisionsSkeleton() {
  return (
    <Loading label="Cargando decisiones" className="flex flex-col gap-6">
      {[0, 1].map((s) => (
        <div key={s} className="flex flex-col gap-2">
          <div className="flex justify-between px-1"><Bone className="h-9 w-48" /><Bone className="h-6 w-8 rounded-full" /></div>
          <DecisionCardSkeleton />
          {s === 1 && <DecisionCardSkeleton />}
        </div>
      ))}
    </Loading>
  );
}

/** Same shape as an alert card: icon, tone pill, title, body, footer. */
export function AlertsSkeleton() {
  return (
    <Loading label="Cargando advertencias" className="flex flex-col gap-4">
      {[0, 1, 2].map((i) => (
        <div key={i} className={card}>
          <div className="flex items-start gap-3">
            <Bone className="h-9 w-9 flex-shrink-0 rounded-full" />
            <div className="flex flex-1 flex-col gap-2"><Bone className="h-4 w-24 rounded-full" /><Bone className="h-5 w-4/5" /><Bone className="h-4 w-full" /></div>
          </div>
          <div className="flex justify-between pl-12"><Bone className="h-4 w-20" /><Bone className="h-9 w-24 rounded-full" /></div>
        </div>
      ))}
    </Loading>
  );
}

/** Same shape as a memory row: tag pill, text, footer. */
export function MemoriesSkeleton() {
  return (
    <Loading label="Cargando memorias" className="flex flex-col">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="flex flex-col gap-2 border-b border-partition/70 px-1 py-3.5">
          <Bone className="h-5 w-28 rounded-full" />
          <Bone className="h-6 w-full" />
          <Bone className="h-4 w-1/2" />
        </div>
      ))}
    </Loading>
  );
}

/** The Sucursal window: hero card, two context tiles, three figures, inventory rows. */
export function BranchSkeleton() {
  return (
    <Loading label="Cargando sucursal" className="flex flex-col gap-5">
      <div className="flex flex-col gap-2 pt-3"><Bone className="h-4 w-28" /><Bone className="h-9 w-3/4" /><Bone className="h-4 w-1/2" /></div>
      <div className="flex gap-2">{[0, 1, 2].map((i) => <Bone key={i} className="h-11 flex-1 rounded-full" />)}</div>
      <Bone className="h-48 w-full rounded-[20px]" />
      <div className="grid grid-cols-2 gap-2"><Bone className="h-32 rounded-2xl" /><Bone className="h-32 rounded-2xl" /></div>
      <div className="grid grid-cols-3 gap-2">{[0, 1, 2].map((i) => <Bone key={i} className="h-16 rounded-2xl" />)}</div>
      <div className={card}>
        <Bone className="h-6 w-1/2" />
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="flex flex-col gap-1.5 border-b border-partition/70 pb-3"><Bone className="h-5 w-3/4" /><Bone className="h-3 w-full" /><Bone className="h-4 w-full" /></div>
        ))}
      </div>
    </Loading>
  );
}

/** Body of the analysis card while GET /analysis is in flight. */
export function AnalysisSkeleton() {
  return (
    <Loading label="Cargando análisis" className="flex flex-col gap-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex flex-col gap-1.5"><Bone className="h-4 w-24" /><Bone className="h-4 w-full" /><Bone className="h-4 w-4/5" /></div>
      ))}
    </Loading>
  );
}

/** Chat history while the stored turns load: a user bubble and an assistant bubble. */
export function ChatSkeleton() {
  return (
    <Loading label="Cargando conversación" className="flex flex-col gap-2.5">
      <div className="flex justify-end"><Bone className="h-12 w-3/5 rounded-[16px_16px_6px_16px]" /></div>
      <div className="flex gap-2"><Bone className="h-7 w-7 flex-shrink-0 rounded-full" /><Bone className="h-24 w-4/5 rounded-[16px_16px_16px_6px]" /></div>
    </Loading>
  );
}
