import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "../ApiContext";
import type { VoiceConfig } from "../types";
import { stripMarkdown } from "./markdown";

/** 44-byte WAV with no samples: playing it inside a gesture unlocks later programmatic play() on iOS. */
const SILENT_WAV = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";

const hasSynthesis = () => typeof window !== "undefined" && "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined";

/** Plays replies: backend TTS through one reused audio element, browser speech synthesis as fallback. */
export function useVoiceOutput(config: VoiceConfig | null) {
  const api = useApi();
  const audio = useRef<HTMLAudioElement | null>(null);
  const url = useRef<string | null>(null);
  const token = useRef(0);
  const current = useRef<string | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  /** The speak request is in flight (about 2 s plus 10 ms per character). */
  const [preparing, setPreparing] = useState(false);
  const ttsRef = useRef(Boolean(config?.tts));
  ttsRef.current = Boolean(config?.tts);

  const getAudio = () => (audio.current ??= new Audio());

  const clear = useCallback(() => {
    const a = audio.current;
    if (a) {
      a.onended = null;
      a.onerror = null;
      a.pause();
    }
    if (url.current) {
      URL.revokeObjectURL(url.current);
      url.current = null;
    }
    if (hasSynthesis()) window.speechSynthesis.cancel();
  }, []);

  const stop = useCallback(() => {
    token.current++;
    current.current = null;
    clear();
    setPlayingId(null);
    setPreparing(false);
  }, [clear]);

  /** Call inside a user gesture (pointerdown): makes later play() calls on the shared element allowed. */
  const unlock = useCallback(() => {
    stop();
    try {
      const a = getAudio();
      a.src = SILENT_WAV;
      void a.play()?.catch(() => {});
    } catch {
      /* unlock is best effort */
    }
  }, [stop]);

  const speak = useCallback(
    async (text: string, id: string) => {
      if (current.current === id) return stop(); // second press stops
      stop();
      const clean = text.trim();
      if (!clean) return;
      const mine = token.current;
      current.current = id;
      setPlayingId(id);
      const done = () => {
        if (token.current !== mine) return;
        stop();
      };
      if (ttsRef.current) {
        try {
          setPreparing(true);
          const blob = await api.speak(clean);
          if (token.current !== mine) return;
          setPreparing(false);
          const a = getAudio();
          url.current = URL.createObjectURL(blob);
          a.onended = done;
          a.onerror = done;
          a.src = url.current;
          await a.play();
          return;
        } catch {
          if (token.current !== mine) return;
          setPreparing(false);
          clear();
        }
      }
      if (!hasSynthesis()) return done();
      const u = new SpeechSynthesisUtterance(stripMarkdown(clean));
      u.lang = "es-MX";
      const voices = window.speechSynthesis.getVoices?.() ?? [];
      const v = voices.find((x) => x.lang === "es-MX") ?? voices.find((x) => x.lang.toLowerCase().startsWith("es"));
      if (v) u.voice = v;
      u.onend = done;
      u.onerror = done;
      window.speechSynthesis.speak(u);
    },
    [api, stop, clear],
  );

  useEffect(() => () => {
    token.current++;
    clear();
    audio.current = null;
  }, [clear]);

  return { preparing, playingId, speaking: playingId !== null, speak, stop, unlock, available: Boolean(config?.tts) || hasSynthesis() };
}
