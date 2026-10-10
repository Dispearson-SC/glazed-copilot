/** Transient confirmation above the capsule navigation. */
export default function Toast({ text }: { text: string | null }) {
  if (!text) return null;
  return (
    <div
      role="status"
      className="fixed inset-x-4 bottom-[92px] z-[60] mx-auto flex max-w-[608px] items-center gap-2.5 rounded-2xl bg-primary-container px-4 py-3 text-surface shadow-[0_12px_32px_-6px_rgba(75,48,37,.3)]"
    >
      <span aria-hidden="true" className="material-symbols-outlined text-[20px] text-tertiary-fixed-dim">task_alt</span>
      <span className="flex-1 text-[13px] leading-[18px]">{text}</span>
    </div>
  );
}
