export interface PlayerState {
  engine: "audio" | "synthesis";
  paused: boolean;
  rate: number;
  current: number;
  duration: number;
}

/** m:ss for a position in seconds; non-finite values read as 0:00. */
export const formatTime = (s: number): string => {
  const t = Number.isFinite(s) && s > 0 ? Math.floor(s) : 0;
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
};

const BTN = "flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full p-0 text-secondary";

/** Compact player for the reply being read: pause, seek, time, speed and close. Backend audio only seeks; speech synthesis gets speed and stop. */
export default function PlayerBar({ player, onToggle, onSeek, onRate, onClose }: { player: PlayerState; onToggle: () => void; onSeek: (s: number) => void; onRate: () => void; onClose: () => void }) {
  const seekable = player.engine === "audio";
  const known = Number.isFinite(player.duration) && player.duration > 0;
  return (
    <div role="group" aria-label="Reproductor de voz" className="flex min-h-[48px] items-center gap-1 rounded-full border border-surface-container-high bg-white pl-1 pr-1 shadow-card">
      {seekable && (
        <button type="button" onClick={onToggle} aria-label={player.paused ? "Reanudar" : "Pausar"} className={BTN}>
          <span aria-hidden="true" className="material-symbols-outlined text-[22px]">{player.paused ? "play_arrow" : "pause"}</span>
        </button>
      )}
      {seekable ? (
        <>
          <input
            type="range"
            aria-label="Posición del audio"
            min={0}
            max={known ? player.duration : 0}
            step={0.1}
            value={known ? Math.min(player.current, player.duration) : 0}
            disabled={!known}
            onChange={(e) => onSeek(Number(e.target.value))}
            className="min-w-0 flex-1 accent-secondary"
          />
          <span className="flex-shrink-0 font-label-sm text-label-sm text-on-surface-variant" aria-label="Tiempo">
            {formatTime(player.current)} / {known ? formatTime(player.duration) : "--:--"}
          </span>
        </>
      ) : (
        <span className="min-w-0 flex-1 truncate pl-3 font-label-sm text-label-sm text-on-surface-variant">Leyendo con la voz del dispositivo</span>
      )}
      <button type="button" onClick={onRate} aria-label="Velocidad de reproducción" className="h-11 min-w-[44px] flex-shrink-0 rounded-full bg-surface-container px-2 font-label-md text-label-md normal-case tracking-normal text-secondary">
        {player.rate}×
      </button>
      <button type="button" onClick={onClose} aria-label="Cerrar reproductor" className={BTN}>
        <span aria-hidden="true" className="material-symbols-outlined text-[20px]">close</span>
      </button>
    </div>
  );
}
