import type { VoiceInputState } from "./useVoiceInput";

export const formatClock = (s: number): string => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/** Tap-to-talk mic: a normal toggle button (tap starts, tap again cancels). */
export default function MicButton({ state, onToggle }: { state: VoiceInputState; onToggle: () => void }) {
  const listening = state === "listening";
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={state === "transcribing"}
      aria-label="Hablar con el copiloto"
      aria-pressed={listening}
      className={`relative flex h-11 w-11 flex-shrink-0 select-none items-center justify-center rounded-full p-0 ${listening ? "bg-secondary text-white" : "bg-surface-container text-secondary"}`}
    >
      {listening && <span aria-hidden="true" className="absolute inset-0 rounded-full bg-secondary/40 motion-safe:animate-ping" />}
      <span aria-hidden="true" className="material-symbols-outlined relative text-[20px]">{state === "transcribing" ? "hourglass_top" : "mic"}</span>
    </button>
  );
}
