import type { ComponentProps } from "react";
import type { VoiceInputState } from "./useVoiceInput";

export const formatClock = (s: number): string => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/** Hold-to-talk mic. Behaviour comes from useVoiceInput().bind; this only renders the states. */
export default function MicButton({ state, bind }: { state: VoiceInputState; bind: Omit<ComponentProps<"button">, "ref"> }) {
  const listening = state === "listening";
  return (
    <button
      type="button"
      {...bind}
      disabled={state === "transcribing"}
      aria-label="Hablar con el copiloto"
      aria-pressed={listening}
      className={`relative flex h-11 w-11 flex-shrink-0 touch-none select-none items-center justify-center rounded-full p-0 [-webkit-touch-callout:none] [-webkit-user-select:none] ${listening ? "bg-secondary text-white" : "bg-surface-container text-secondary"}`}
    >
      {listening && <span aria-hidden="true" className="absolute inset-0 rounded-full bg-secondary/40 motion-safe:animate-ping" />}
      <span aria-hidden="true" className="material-symbols-outlined relative text-[20px]">{state === "transcribing" ? "hourglass_top" : "mic"}</span>
    </button>
  );
}
