# voice-tap-to-talk

Objective: replace hold-to-talk with tap-to-talk, make MiniMax `/voice/transcribe` the only STT (Web Speech removed), and make reply audio play reliably on iOS (shared primed audio element, mic released before playback, Spanish-only speechSynthesis fallback). TDD: off (user choice); runner: vitest. Route: delegated direct, single writer.

## Tasks
- [x] T1 Shared audio element primed synchronously in the mic tap (`unlock`), the send tap (`prime`, typed or voice) and the speaker button (`speak`); silent ~0.1 s WAV data URI; playback reuses the same element. Evidence: tests "requests the mic and primes...", "primes the shared element on the mic tap and the send tap...", "a typed send and the speaker button prime...".
- [x] T2 Mic tracks stopped as soon as recording stops (after `rec.stop()` and in `onstop`), before transcribe and any playback. Evidence: test "send transcribes... tracks already stopped" (call order).
- [x] T3 speechSynthesis fallback: lang es-MX, voice es-MX > es-US > es-*, wait once for `voiceschanged` (1.5 s timeout), never the default voice; one `console.info("[voice] tts path:", path, reason)` per playback. Evidence: "speechSynthesis fallback voice" tests.
- [x] T4 STT is MiniMax only; Web Speech code and tests removed; mic shown only with MediaRecorder + getUserMedia and `stt` true (or config loading). Evidence: "mic availability" tests.
- [x] T5 Tap interaction: mic toggles, "Escuchando… m:ss" with cancel X, send button enabled while recording ("Enviar mensaje de voz"), "Transcribiendo…" with send disabled, auto-stop at `max_seconds`, empty/400/502/network/permission messages, `language_suspect` review kept. Hold, slide-away, <0.5 s and keyboard-hold logic removed. Evidence: "tap-to-talk (MiniMax STT)" tests.

## Verification (in frontend/)
- `npx tsc -b`: clean
- `npx vitest run`: 38 files, 486 tests passed
- `npx vite build`: succeeded

## Notes
- The prime is skipped while a reply is already playing (the element is already unlocked).
- Not verified on a real iPad; needs a device check.
