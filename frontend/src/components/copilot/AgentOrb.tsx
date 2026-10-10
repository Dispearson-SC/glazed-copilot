const ORGANIC = "rounded-[48%_52%_45%_55%/54%_46%_54%_46%]";

/** Caramel orb with an organic border. `size` >= 100 renders the big hero orb with its ring and dots; smaller sizes the chat avatar. */
export default function AgentOrb({ size = 116, speaking = false }: { size?: number; speaking?: boolean }) {
  const pulse = speaking ? "motion-safe:animate-pulse" : "";
  if (size < 100) {
    return (
      <div
        aria-hidden="true"
        style={{ width: size, height: size }}
        className={`${pulse} ${ORGANIC} flex-shrink-0 bg-[radial-gradient(circle_at_34%_30%,#ffdcc0_0%,#f6bb87_35%,#cb9564_70%,#7a5649_100%)]`}
      />
    );
  }
  return (
    <div aria-hidden="true" className="relative flex h-[148px] w-[148px] items-center justify-center">
      <div className={`absolute inset-0 rounded-full border ${speaking ? "border-secondary/60 motion-safe:animate-ping" : "border-on-tertiary-container/25"}`} />
      <div
        style={{ width: size, height: size }}
        className={`${pulse} ${ORGANIC} bg-[radial-gradient(circle_at_34%_30%,#ffdcc0_0%,#f6bb87_30%,#cb9564_62%,#7a5649_100%)] shadow-[0_18px_40px_-10px_rgba(75,48,37,.35),inset_-10px_-14px_24px_rgba(75,48,37,.25)]`}
      />
      <div className="absolute right-1.5 top-[26px] h-2.5 w-2.5 rounded-full bg-tertiary-fixed-dim" />
      <div className="absolute bottom-[30px] left-2.5 h-1.5 w-1.5 rounded-full bg-secondary-fixed-dim" />
    </div>
  );
}
