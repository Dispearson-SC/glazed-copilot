# voice-webspeech

Objective: browser Web Speech API is the primary STT for push-to-talk; MiniMax `/voice/transcribe` is the fallback only. TTS, PlayerBar and auto-speak unchanged. TDD: off (user choice); runner: vitest.

Route: delegated direct, single writer.

## Tasks
- [x] T1 Web Speech primary in `frontend/src/voice/useVoiceInput.ts` (es-MX, continuous, interim; start synchronous in pointerdown; no getUserMedia; restart on browser-ended recognition while held; stop + wait onend with 4 s guard; <0.5 s or slide-away aborts). Evidence: tsc clean, new tests pass.
- [x] T2 Fallback to MediaRecorder + transcribe when SpeechRecognition is missing, or on `network` / `service-not-allowed` (sticky for the session, "hold again" notice); `not-allowed` shows the permission message; `no-speech` / `aborted` are empty; `language_suspect` review kept on MiniMax. Evidence: tests "error 'network'", "language_suspect still reviews".
- [x] T3 Live interim+final preview inside the "Escuchando…" indicator (`AgentWindow.tsx`, 2-line clamp). Evidence: test "shows interim text".
- [x] T4 Empty transcript toast "No te escuché, intenta de nuevo". Evidence: tests.

## Verification
- `npx tsc -b`: clean
- `npx vitest run`: 38 files, 484 tests passed
- `npx vite build`: succeeded
