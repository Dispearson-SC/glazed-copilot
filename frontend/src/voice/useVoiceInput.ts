import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "../ApiContext";
import { ApiError } from "../api";
import type { VoiceConfigState } from "./useVoiceConfig";

export type VoiceInputState = "idle" | "listening" | "transcribing";

const DEFAULT_MAX_SECONDS = 60;

export const MSG_PERMISSION = "Permite el micrófono para hablar con el copiloto";
const MSG_NO_MIC = "No se encontró un micrófono";
const MSG_NO_SPEECH = "No te escuché, intenta de nuevo";
const MSG_BAD_AUDIO = "No se pudo procesar el audio; intenta de nuevo con un mensaje más corto";
const MSG_TRANSCRIBE_FAILED = "No se pudo transcribir, intenta de nuevo";

function canRecord(): boolean {
  return typeof MediaRecorder !== "undefined" && typeof navigator !== "undefined" && typeof navigator.mediaDevices?.getUserMedia === "function";
}

const isDenied = (e: unknown) => e instanceof Error && (e.name === "NotAllowedError" || e.name === "PermissionDeniedError" || e.name === "SecurityError");

interface Opts {
  config: VoiceConfigState;
  /** Final text of a recording. `suspect`: the backend doubts the language, so the text must be reviewed before sending. */
  onTranscript: (text: string, opts?: { suspect?: boolean }) => void;
  /** User-facing notices (toast). */
  onNotice: (message: string) => void;
  /** Runs synchronously inside the mic tap (audio unlock). */
  onPress?: () => void;
}

/** Tap-to-talk: MiniMax STT only (MediaRecorder + POST /voice/transcribe). Tap the mic to start, send to transcribe, mic or X to cancel. */
export function useVoiceInput({ config: cfg, onTranscript, onNotice, onPress }: Opts) {
  const api = useApi();
  const [state, setStateRaw] = useState<VoiceInputState>("idle");
  const [seconds, setSeconds] = useState(0);
  const stateRef = useRef<VoiceInputState>("idle");
  const chunks = useRef<Blob[]>([]);
  const r = useRef({
    token: 0,
    startedAt: 0,
    stream: null as MediaStream | null,
    recorder: null as MediaRecorder | null,
    tick: 0 as unknown as ReturnType<typeof setInterval>,
    limit: 0 as unknown as ReturnType<typeof setTimeout>,
  });
  const cb = useRef({ onTranscript, onNotice, onPress });
  cb.current = { onTranscript, onNotice, onPress };

  const setState = (s: VoiceInputState) => {
    stateRef.current = s;
    setStateRaw(s);
  };

  const maxSeconds = cfg.config?.max_seconds || DEFAULT_MAX_SECONDS;
  // While the config loads the backend is assumed; once settled only an enabled stt counts.
  const available = canRecord() && (cfg.loaded ? Boolean(cfg.config?.enabled && cfg.config.stt) : true);
  const maxRef = useRef(maxSeconds);
  maxRef.current = maxSeconds;

  const stopTracks = () => {
    const s = r.current;
    s.stream?.getTracks().forEach((t) => t.stop());
    s.stream = null;
  };

  /** Drops timers, stream and recorder without producing a result. */
  const release = useCallback(() => {
    const s = r.current;
    clearInterval(s.tick);
    clearTimeout(s.limit);
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
  }, []);

  const cancel = useCallback(() => {
    r.current.token++;
    release();
    setSeconds(0);
    setState("idle");
  }, [release]);

  const deliver = (text: string, suspect = false) => {
    const clean = text.trim();
    if (clean) cb.current.onTranscript(clean, suspect ? { suspect: true } : undefined);
    else cb.current.onNotice(MSG_NO_SPEECH);
  };

  const start = () => {
    if (stateRef.current !== "idle" || !available) return;
    const s = r.current;
    cb.current.onPress?.();
    const token = ++s.token;
    setSeconds(0);
    setState("listening");
    // getUserMedia is requested synchronously, inside the tap (iOS needs the gesture).
    let pending: Promise<MediaStream>;
    try {
      pending = navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      cancel();
      cb.current.onNotice(isDenied(e) ? MSG_PERMISSION : MSG_NO_MIC);
      return;
    }
    void pending.then(
      (stream) => {
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
          s.startedAt = Date.now();
          s.tick = setInterval(() => setSeconds(Math.floor((Date.now() - s.startedAt) / 1000)), 250);
          s.limit = setTimeout(() => {
            if (s.token === token) finishRef.current();
          }, maxRef.current * 1000);
        } catch {
          stream.getTracks().forEach((t) => t.stop());
          cancel();
          cb.current.onNotice(MSG_NO_MIC);
        }
      },
      (e: unknown) => {
        if (s.token !== token) return;
        cancel();
        cb.current.onNotice(isDenied(e) ? MSG_PERMISSION : MSG_NO_MIC);
      },
    );
  };

  /** Stops the recorder and the mic, transcribes, and hands the text to onTranscript. */
  const finish = () => {
    if (stateRef.current !== "listening") return;
    const s = r.current;
    const token = s.token;
    const rec = s.recorder;
    if (!rec) return cancel(); // the mic permission was still pending
    clearInterval(s.tick);
    clearTimeout(s.limit);
    setState("transcribing");
    rec.onstop = () => {
      const type = rec.mimeType || "audio/webm";
      const blob = new Blob(chunks.current, { type });
      release(); // mic tracks are off before any reply plays (iOS routes audio to the earpiece otherwise)
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
        .catch((e: unknown) => {
          if (s.token !== token) return;
          setSeconds(0);
          setState("idle");
          // 400 = unusable audio (empty, too big); 502/503/network = try again.
          cb.current.onNotice(e instanceof ApiError && e.status === 400 ? MSG_BAD_AUDIO : MSG_TRANSCRIBE_FAILED);
        });
    };
    try {
      rec.stop();
      stopTracks();
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

  /** Mic button: start when idle, cancel when recording. */
  const toggle = () => {
    if (stateRef.current === "idle") start();
    else if (stateRef.current === "listening") cancel();
  };

  return { available, state, seconds, maxSeconds, toggle, cancel, finish };
}
