import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { useApi } from "../ApiContext";
import { ApiError } from "../api";
import type { VoiceConfigState } from "./useVoiceConfig";

export type VoiceInputState = "idle" | "listening" | "transcribing";

export const MIN_RECORDING_MS = 500;
const DEFAULT_MAX_SECONDS = 60;
/** How far outside the button the pointer may drift before the recording is cancelled. */
const SLIDE_MARGIN_PX = 12;
/** Max wait for recognition.onend after stop(). */
const STOP_GUARD_MS = 4000;

export const MSG_PERMISSION = "Permite el micrófono para hablar con el copiloto";
export const MSG_HINT = "Mantén presionado el micrófono para hablar";
const MSG_NO_MIC = "No se encontró un micrófono";
const MSG_NO_SPEECH = "No te escuché, intenta de nuevo";
const MSG_BAD_AUDIO = "No se pudo procesar el audio; intenta de nuevo con un mensaje más corto";
const MSG_SPEECH_FAILED = "El dictado del navegador falló; mantén presionado de nuevo para intentarlo";
const MSG_SPEECH_DOWN = "El dictado del navegador no está disponible; intenta de nuevo";

/** Minimal Web Speech typings (not part of lib.dom). */
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: { results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function speechCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: SpeechRecognitionCtor; webkitSpeechRecognition?: SpeechRecognitionCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

function canRecord(): boolean {
  return typeof MediaRecorder !== "undefined" && typeof navigator !== "undefined" && typeof navigator.mediaDevices?.getUserMedia === "function";
}

const isDenied = (e: unknown) => e instanceof Error && (e.name === "NotAllowedError" || e.name === "PermissionDeniedError" || e.name === "SecurityError");

interface Opts {
  config: VoiceConfigState;
  /** Final text of a hold. `suspect`: the backend doubts the language, so the text must be reviewed before sending. */
  onTranscript: (text: string, opts?: { suspect?: boolean }) => void;
  /** User-facing notices (toast). */
  onNotice: (message: string) => void;
  /** Runs synchronously inside the pointerdown gesture (audio unlock). */
  onPress?: () => void;
}

/** Hold-to-talk. Web Speech API first; backend STT (MediaRecorder + POST /voice/transcribe) as fallback. */
export function useVoiceInput({ config: cfg, onTranscript, onNotice, onPress }: Opts) {
  const api = useApi();
  const [state, setStateRaw] = useState<VoiceInputState>("idle");
  const [seconds, setSeconds] = useState(0);
  /** Live interim+final text of the current Web Speech hold. */
  const [preview, setPreview] = useState("");
  const stateRef = useRef<VoiceInputState>("idle");
  const r = useRef({
    token: 0,
    startedAt: 0,
    stream: null as MediaStream | null,
    recorder: null as MediaRecorder | null,
    recognition: null as SpeechRecognitionLike | null,
    tick: 0 as unknown as ReturnType<typeof setInterval>,
    limit: 0 as unknown as ReturnType<typeof setTimeout>,
    speechFailed: false,
    speechStop: null as (() => void) | null,
    stopGuard: 0 as unknown as ReturnType<typeof setTimeout>,
  });
  const cb = useRef({ onTranscript, onNotice, onPress });
  cb.current = { onTranscript, onNotice, onPress };

  const setState = (s: VoiceInputState) => {
    stateRef.current = s;
    setStateRaw(s);
  };

  const maxSeconds = cfg.config?.max_seconds || DEFAULT_MAX_SECONDS;
  // While the config loads the backend is assumed; once settled only an enabled stt counts.
  const backendOk = canRecord() && (cfg.loaded ? Boolean(cfg.config?.enabled && cfg.config.stt) : true);
  // Web Speech is primary and works even when the backend stt is off.
  const speechOk = speechCtor() !== null;
  const available = backendOk || speechOk;
  const maxRef = useRef(maxSeconds);
  maxRef.current = maxSeconds;

  /** Drops timers, stream, recorder and recognition without producing a result. */
  const release = useCallback(() => {
    const s = r.current;
    clearInterval(s.tick);
    clearTimeout(s.limit);
    clearTimeout(s.stopGuard);
    s.speechStop = null;
    if (s.recorder) {
      s.recorder.ondataavailable = null;
      s.recorder.onstop = null;
      try {
        if (s.recorder.state !== "inactive") s.recorder.stop();
      } catch {
        /* already stopped */
      }
      s.recorder = null;
    }
    s.stream?.getTracks().forEach((t) => t.stop());
    s.stream = null;
    if (s.recognition) {
      s.recognition.onresult = s.recognition.onerror = s.recognition.onend = null;
      try {
        s.recognition.abort();
      } catch {
        /* not started */
      }
      s.recognition = null;
    }
  }, []);

  const cancel = useCallback(() => {
    r.current.token++;
    release();
    setSeconds(0);
    setPreview("");
    setState("idle");
  }, [release]);

  const deliver = (text: string, suspect = false) => {
    const clean = text.trim();
    if (clean) cb.current.onTranscript(clean, suspect ? { suspect: true } : undefined);
    else cb.current.onNotice(MSG_NO_SPEECH);
  };

  const startTimers = (token: number) => {
    const s = r.current;
    s.startedAt = Date.now();
    s.tick = setInterval(() => setSeconds(Math.floor((Date.now() - s.startedAt) / 1000)), 250);
    s.limit = setTimeout(() => {
      if (r.current.token === token) finishRef.current();
    }, maxRef.current * 1000);
  };

  const startBackend = async (token: number) => {
    const s = r.current;
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      if (s.token !== token) return;
      cancel();
      cb.current.onNotice(isDenied(e) ? MSG_PERMISSION : MSG_NO_MIC);
      return;
    }
    if (s.token !== token) {
      stream.getTracks().forEach((t) => t.stop());
      return;
    }
    // The provider accepts ogg/opus and m4a but rejects Chromium's webm, so webm is the last resort.
    const mime = ["audio/ogg;codecs=opus", "audio/mp4", "audio/webm;codecs=opus"].find((m) => MediaRecorder.isTypeSupported?.(m));
    try {
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      s.stream = stream;
      s.recorder = rec;
      chunks.current = [];
      rec.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunks.current.push(e.data);
      };
      rec.start();
      startTimers(token);
    } catch {
      stream.getTracks().forEach((t) => t.stop());
      cancel();
      cb.current.onNotice(MSG_NO_MIC);
    }
  };
  const chunks = useRef<Blob[]>([]);

  /** Web Speech (primary). Runs synchronously inside the pointerdown gesture: no await before start(). */
  const startSpeech = (token: number) => {
    const Ctor = speechCtor();
    const s = r.current;
    if (!Ctor) return cancel();
    const join = (...parts: string[]) => parts.join(" ").replace(/\s+/g, " ").trim();
    let acc = ""; // text of recognition sessions Chrome ended on its own while the button was held
    let finals = "";
    let interim = "";
    let settled = false;
    const live = () => s.token === token && s.recognition !== null;
    const finalize = () => {
      if (settled || s.token !== token) return;
      settled = true;
      const text = join(acc, finals) || join(acc, interim);
      release();
      setSeconds(0);
      setPreview("");
      setState("idle");
      deliver(text);
    };
    const fail = (message: string) => {
      if (s.token !== token) return;
      settled = true;
      cancel();
      cb.current.onNotice(message);
    };
    try {
      const rec = new Ctor();
      rec.lang = "es-MX";
      rec.continuous = true;
      rec.interimResults = true;
      rec.onresult = (e) => {
        if (!live()) return;
        const fin: string[] = [];
        const int: string[] = [];
        for (let i = 0; i < e.results.length; i++) (e.results[i].isFinal ? fin : int).push(e.results[i][0].transcript);
        finals = join(...fin);
        interim = join(...int);
        setPreview(join(acc, finals, interim));
      };
      rec.onerror = (e) => {
        if (!live()) return;
        if (e.error === "not-allowed") fail(MSG_PERMISSION);
        else if (e.error === "network" || e.error === "service-not-allowed") {
          // The audio of this hold is gone: later holds use the backend (when there is one).
          if (backendOk) s.speechFailed = true;
          fail(backendOk ? MSG_SPEECH_FAILED : MSG_SPEECH_DOWN);
        }
        // no-speech / aborted: nothing to do; onend decides (empty, or restart while held).
      };
      rec.onend = () => {
        if (!live()) return;
        if (stateRef.current !== "listening") return finalize();
        // Chrome ends recognition on long pauses: keep the text and restart while the button is held.
        acc = join(acc, finals || interim);
        finals = interim = "";
        try {
          rec.start();
        } catch {
          finalize();
        }
      };
      s.recognition = rec;
      s.speechStop = finalize;
      rec.start();
      startTimers(token);
    } catch {
      fail(MSG_NO_MIC);
    }
  };

  const start = () => {
    if (stateRef.current !== "idle") return;
    cb.current.onPress?.();
    const token = ++r.current.token;
    setSeconds(0);
    setState("listening");
    setPreview("");
    // Web Speech first (synchronously, inside the gesture); the backend only when it is missing or failed.
    if (speechOk && !(r.current.speechFailed && backendOk)) startSpeech(token);
    else if (backendOk) void startBackend(token);
    else cancel();
  };

  const finish = () => {
    if (stateRef.current !== "listening") return;
    const s = r.current;
    const token = s.token;
    const live = s.recorder ?? s.recognition;
    if (!live || Date.now() - s.startedAt < MIN_RECORDING_MS) {
      cancel();
      cb.current.onNotice(MSG_HINT);
      return;
    }
    clearInterval(s.tick);
    clearTimeout(s.limit);
    setState("transcribing");
    if (s.recognition) {
      // Wait for onend; the guard covers browsers that never fire it.
      const done = s.speechStop;
      s.stopGuard = setTimeout(() => done?.(), STOP_GUARD_MS);
      try {
        s.recognition.stop();
      } catch {
        done?.();
      }
      return;
    }
    const rec = s.recorder!;
    rec.onstop = () => {
      const type = rec.mimeType || "audio/webm";
      const blob = new Blob(chunks.current, { type });
      release();
      if (s.token !== token) return;
      const name = type.includes("mp4") ? "voice.m4a" : type.includes("ogg") ? "voice.ogg" : "voice.webm";
      api
        .transcribe(blob, name)
        .then(({ text, language_suspect }) => {
          if (s.token !== token) return;
          setSeconds(0);
          setState("idle");
          deliver(text ?? "", language_suspect === true);
        })
        .catch((e: Error) => {
          if (s.token !== token) return;
          setSeconds(0);
          setState("idle");
          // 400 = unusable audio (empty, too big).
          cb.current.onNotice(e instanceof ApiError && e.status === 400 ? MSG_BAD_AUDIO : e.message || "No se pudo transcribir el audio");
        });
    };
    try {
      rec.stop();
    } catch {
      cancel();
    }
  };
  const finishRef = useRef(finish);
  finishRef.current = finish;

  useEffect(() => () => {
    r.current.token++;
    release();
  }, [release]);

  const outside = (e: PointerEvent<HTMLElement>) => {
    const b = e.currentTarget.getBoundingClientRect();
    return e.clientX < b.left - SLIDE_MARGIN_PX || e.clientX > b.right + SLIDE_MARGIN_PX || e.clientY < b.top - SLIDE_MARGIN_PX || e.clientY > b.bottom + SLIDE_MARGIN_PX;
  };
  const isHoldKey = (e: KeyboardEvent) => e.key === " " || e.key === "Enter";

  /** Spread on the mic button. No pointer capture, so sliding away is observable. */
  const bind = {
    onPointerDown: (e: PointerEvent<HTMLElement>) => {
      if (e.button > 0) return;
      start();
    },
    onPointerUp: () => finishRef.current(),
    onPointerMove: (e: PointerEvent<HTMLElement>) => {
      if (stateRef.current === "listening" && outside(e)) cancel();
    },
    onPointerLeave: () => {
      if (stateRef.current === "listening") cancel();
    },
    onPointerCancel: () => {
      if (stateRef.current === "listening") cancel();
    },
    onContextMenu: (e: { preventDefault: () => void }) => e.preventDefault(),
    onKeyDown: (e: KeyboardEvent<HTMLElement>) => {
      if (isHoldKey(e)) {
        e.preventDefault();
        if (!e.repeat) start();
      }
    },
    onKeyUp: (e: KeyboardEvent<HTMLElement>) => {
      if (isHoldKey(e)) finishRef.current();
    },
  };

  return { available, state, seconds, maxSeconds, preview, bind };
}
