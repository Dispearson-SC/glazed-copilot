import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "../ApiContext";
import type { VoiceConfig } from "../types";
import { stripMarkdown } from "./markdown";

/** 44-byte WAV with no samples: playing it inside a gesture unlocks later programmatic play() on iOS. */
const SILENT_WAV = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";

export const RATES = [0.75, 1, 1.25, 1.5, 2] as const;
const RATE_KEY = "glazed.voice.rate";
const nextRate = (r: number) => RATES[(RATES.indexOf(r as (typeof RATES)[number]) + 1) % RATES.length];

function loadRate(): number {
  try {
    const v = Number(localStorage.getItem(RATE_KEY));
    return (RATES as readonly number[]).includes(v) ? v : 1;
  } catch {
    return 1;
  }
}

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
  /** Which engine is playing: backend audio (seekable) or speechSynthesis (no seek). Null while idle or preparing. */
  const [engine, setEngine] = useState<"audio" | "synthesis" | null>(null);
  const [paused, setPaused] = useState(false);
  const [time, setTime] = useState({ current: 0, duration: 0 });
  const [rate, setRate] = useState(loadRate);
  const rateRef = useRef(rate);
  const synth = useRef<{ text: string; u: SpeechSynthesisUtterance | null; done: () => void } | null>(null);
  const ttsRef = useRef(Boolean(config?.tts));
  ttsRef.current = Boolean(config?.tts);

  const applyRate = (a: HTMLAudioElement) => {
    a.defaultPlaybackRate = rateRef.current;
    a.playbackRate = rateRef.current;
    a.preservesPitch = true;
  };

  const getAudio = () => {
    if (audio.current) return audio.current;
    const a = new Audio();
    const sync = () => setTime({ current: a.currentTime || 0, duration: a.duration || 0 });
    for (const ev of ["timeupdate", "loadedmetadata", "durationchange", "seeked"]) a.addEventListener(ev, sync);
    a.addEventListener("play", () => setPaused(false));
    a.addEventListener("pause", () => setPaused(true));
    audio.current = a;
    return a;
  };

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
    if (synth.current?.u) {
      synth.current.u.onend = null;
      synth.current.u.onerror = null;
    }
    synth.current = null;
    if (hasSynthesis()) window.speechSynthesis.cancel();
  }, []);

  const stop = useCallback(() => {
    token.current++;
    current.current = null;
    clear();
    setPlayingId(null);
    setPreparing(false);
    setEngine(null);
    setPaused(false);
    setTime({ current: 0, duration: 0 });
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

  /** Speaks synth.current.text at the current rate (also used to restart after a speed change). */
  const speakSynthesis = useCallback(() => {
    const cur = synth.current;
    if (!cur) return;
    const u = new SpeechSynthesisUtterance(cur.text);
    u.lang = "es-MX";
    u.rate = rateRef.current;
    const voices = window.speechSynthesis.getVoices?.() ?? [];
    const v = voices.find((x) => x.lang === "es-MX") ?? voices.find((x) => x.lang.toLowerCase().startsWith("es"));
    if (v) u.voice = v;
    u.onend = cur.done;
    u.onerror = cur.done;
    cur.u = u;
    window.speechSynthesis.speak(u);
  }, []);

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
          applyRate(a);
          setTime({ current: 0, duration: 0 });
          setEngine("audio");
          await a.play();
          return;
        } catch {
          if (token.current !== mine) return;
          setPreparing(false);
          clear();
        }
      }
      if (!hasSynthesis()) return done();
      synth.current = { text: stripMarkdown(clean), u: null, done };
      setEngine("synthesis");
      speakSynthesis();
    },
    [api, stop, clear, speakSynthesis],
  );

  const togglePause = useCallback(() => {
    const a = audio.current;
    if (!a) return;
    if (a.paused) void a.play()?.catch(() => {});
    else a.pause();
  }, []);

  const seek = useCallback((seconds: number) => {
    const a = audio.current;
    if (!a) return;
    a.currentTime = seconds;
    setTime((t) => ({ ...t, current: seconds }));
  }, []);

  /** Cycles 0.75x..2x, persists it and applies it now (audio) or by restarting the utterance (synthesis). */
  const cycleRate = useCallback(() => {
    const r = nextRate(rateRef.current);
    rateRef.current = r;
    setRate(r);
    try {
      localStorage.setItem(RATE_KEY, String(r));
    } catch {
      /* persistence is best effort */
    }
    if (audio.current) applyRate(audio.current);
    const cur = synth.current;
    if (cur && hasSynthesis()) {
      if (cur.u) {
        cur.u.onend = null;
        cur.u.onerror = null;
      }
      window.speechSynthesis.cancel();
      speakSynthesis();
    }
  }, [speakSynthesis]);

  useEffect(() => () => {
    token.current++;
    clear();
    audio.current = null;
  }, [clear]);

  const player = !preparing && engine ? { engine, paused, rate, current: time.current, duration: time.duration } : null;

  return { player, togglePause, seek, cycleRate, preparing, playingId, speaking: playingId !== null, speak, stop, unlock, available: Boolean(config?.tts) || hasSynthesis() };
}
