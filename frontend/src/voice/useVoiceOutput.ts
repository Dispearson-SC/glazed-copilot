import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "../ApiContext";
import type { VoiceConfig } from "../types";
import { stripMarkdown } from "./markdown";

/** About 0.1 s of silent 8-bit mono WAV: playing it inside a gesture unlocks later programmatic play() on iOS. */
const SILENT_WAV = (() => {
  const n = 800;
  const b = new Uint8Array(44 + n);
  const dv = new DataView(b.buffer);
  const tag = (o: number, t: string) => [...t].forEach((c, i) => b.set([c.charCodeAt(0)], o + i));
  tag(0, "RIFF");
  dv.setUint32(4, 36 + n, true);
  tag(8, "WAVEfmt ");
  dv.setUint32(16, 16, true);
  dv.setUint16(20, 1, true);
  dv.setUint16(22, 1, true);
  dv.setUint32(24, 8000, true);
  dv.setUint32(28, 8000, true);
  dv.setUint16(32, 1, true);
  dv.setUint16(34, 8, true);
  tag(36, "data");
  dv.setUint32(40, n, true);
  b.fill(0x80, 44);
  return `data:audio/wav;base64,${btoa(String.fromCharCode(...b))}`;
})();

const VOICES_WAIT_MS = 1500;
const normLang = (l: string) => l.toLowerCase().replace("_", "-");
/** es-MX first, then es-US, then any es-*; undefined when the device has no Spanish voice. */
export function pickSpanishVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | undefined {
  return voices.find((v) => normLang(v.lang) === "es-mx") ?? voices.find((v) => normLang(v.lang) === "es-us") ?? voices.find((v) => normLang(v.lang).startsWith("es"));
}

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
  const voicesWaited = useRef(false);
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

  /**
   * Call synchronously inside a user gesture: plays a silent clip on the shared element so later
   * programmatic play() calls are allowed (iOS). Skipped while a reply is already playing.
   */
  const prime = useCallback(() => {
    if (current.current !== null) return;
    try {
      const a = getAudio();
      a.src = SILENT_WAV;
      void a.play()?.catch(() => {});
      a.pause();
    } catch {
      /* priming is best effort */
    }
  }, []);

  /** Mic tap: stops any reading and primes the element. */
  const unlock = useCallback(() => {
    stop();
    prime();
  }, [stop, prime]);

  /** Speaks synth.current.text at the current rate (also used to restart after a speed change). */
  const speakSynthesis = useCallback(() => {
    const cur = synth.current;
    if (!cur) return;
    const u = new SpeechSynthesisUtterance(cur.text);
    u.lang = "es-MX";
    u.rate = rateRef.current;
    const go = (voices: SpeechSynthesisVoice[]) => {
      if (synth.current !== cur) return; // stopped while waiting for voices
      const v = pickSpanishVoice(voices);
      if (v) u.voice = v; // never the default voice when a Spanish one exists; lang es-MX is set either way
      u.onend = cur.done;
      u.onerror = cur.done;
      cur.u = u;
      window.speechSynthesis.speak(u);
    };
    const ss = window.speechSynthesis;
    const voices = ss.getVoices?.() ?? [];
    if (voices.length || voicesWaited.current || typeof ss.addEventListener !== "function") return go(voices);
    // iOS/Chrome load voices lazily: wait once for voiceschanged.
    voicesWaited.current = true;
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      ss.removeEventListener?.("voiceschanged", finish);
      go(ss.getVoices?.() ?? []);
    };
    const timer = setTimeout(finish, VOICES_WAIT_MS);
    ss.addEventListener("voiceschanged", finish);
  }, []);

  const speak = useCallback(
    async (text: string, id: string) => {
      if (current.current === id) return stop(); // second press stops
      stop();
      prime(); // synchronous, inside the tap that led here (speaker button / auto-speak after a voice send)
      const clean = text.trim();
      if (!clean) return;
      const mine = token.current;
      current.current = id;
      setPlayingId(id);
      const done = () => {
        if (token.current !== mine) return;
        stop();
      };
      let reason = "tts-off";
      if (ttsRef.current) {
        try {
          reason = "speak-error";
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
          reason = "play-rejected";
          await a.play();
          console.info("[voice] tts path:", "minimax", "ok");
          return;
        } catch {
          if (token.current !== mine) return;
          setPreparing(false);
          clear();
        }
      }
      if (!hasSynthesis()) return done();
      console.info("[voice] tts path:", "speechSynthesis", reason);
      synth.current = { text: stripMarkdown(clean), u: null, done };
      setEngine("synthesis");
      speakSynthesis();
    },
    [api, stop, clear, prime, speakSynthesis],
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

  return { player, togglePause, seek, cycleRate, preparing, playingId, speaking: playingId !== null, speak, stop, unlock, prime, available: Boolean(config?.tts) || hasSynthesis() };
}
