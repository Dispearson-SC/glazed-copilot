# voice-chat

Branch: feat/voice-chat (from feat/foundation 22969d8). Worktree: glazed-copilot-wt/voice.

## Objective
Push-to-talk voice in the Agente composer: MiniMax STT/TTS through the backend (key server-side), browser fallbacks.

## Backend contract (from Core, not live yet — built against fakes)
- GET /api/v1/voice/config → {enabled, stt, tts, voice_id, max_seconds:60}
- POST /api/v1/voice/transcribe multipart `audio` (webm/opus or mp4, ≤60 s / ~2 MB) → {text}
- POST /api/v1/voice/speak {text} → audio/mpeg (backend strips markdown, caps ~900 chars, cached)

## Constraints
- TDD off (user choice). Ordinary checks: `npx tsc -b`, `npx vitest run`, `npx vite build`.
- No AI attribution in commits; conventional commits; no push; deploy only through Core.
- UI copy in Spanish (product language); code/comments in English.

## Tasks
- [x] V1 api + types: getVoiceConfig, transcribe (FormData, no JSON content-type), speak (returns Blob). Fake API defaults.
- [x] V2 useVoiceInput hook: hold-to-record with MediaRecorder (webm/opus → mp4 fallback), max_seconds auto-stop, cancel <0.5 s or slide-away, permission-denied message, Web Speech API (es-MX) fallback when config disabled/stt false/API error, hidden mic when neither available.
- [x] V3 useVoiceOutput: audio element unlocked on pointerdown, POST speak → blob URL → play, stop on tap, speechSynthesis (es) fallback when tts false or error.
- [x] V4 AgentWindow wiring: mic button states (Escuchando… pulse + timer, Transcribiendo…), send transcript as normal message, auto-speak only replies to voice-initiated messages, speaker button per agent bubble, orb "speaking" animation, tap to stop.
- [x] V5 tests + docs, commit.

## Route
Delegated direct (writer trigger: 4+ non-trivial files).

## Progress / evidence
- V1-V5 done in one commit. Hooks in frontend/src/voice (useVoiceConfig, useVoiceInput, useVoiceOutput, markdown, MicButton); AgentWindow/AgentOrb wired; api.ts split into fetchOk/request so multipart and Blob responses share error handling and credentials.
- Checks (frontend/): `npx tsc -b` clean; `npx vitest run` 38 files / 461 tests pass (voice.test.tsx 23 tests with fake MediaRecorder/getUserMedia/Audio/SpeechRecognition/speechSynthesis); `npx vite build` ok.
- Assumptions: mic shown while config loads (optimistic), hidden once settled with no usable backend STT or Web Speech; transcribe error switches later holds to Web Speech when present; test setup stubs MediaRecorder/mediaDevices/media play for jsdom.
- Core contract update applied: ogg>webm>mp4 with .ogg/.webm/.m4a names, language=es, 400 toast without fallback, 503/502 fallback to browser, "Preparando voz…" while speak is in flight.
