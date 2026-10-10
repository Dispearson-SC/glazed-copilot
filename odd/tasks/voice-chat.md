# Feature: voice-chat

## Objective
Push-to-talk voice for the copilot chat. The backend proxies MiniMax speech so the API key never reaches the browser.

## Scope (authorized)
`backend/` and `infra/` on `feat/foundation`. Frontend is owned by another session. No push. TDD disabled by the user for the deadline (source: user, runner: `cd backend && PYTHONPATH=.deps:src python3 -m pytest -q`); focused tests still added, with fake adapters and no real network.

## Contract (verified with real calls, 2026-10-10)
- STT: `POST https://api.minimax.io/v1/speech_to_text`, multipart `model=asr-1.0`, `file`, `response_format=json`; language hint is the HTTP header `language: es`. Formats: wav, aiff, flac, m4a, mp3, aac, opus, ogg; max 500 s / 50 MB. Response `{text, duration, trace_id}`.
- TTS: `POST /v1/t2a_v2`, hex output in `data.audio`, `base_resp.status_code` 0 = ok.
- Voice: `Spanish_ConfidentWoman` (system voice, Standard Spanish; no Latin American variant is listed in `get_voice`), model `speech-2.8-turbo`, `language_boost: Spanish`.

## Tasks
- [x] T1 Port `VoiceService` + `VoiceDesk` (speakable text, LRU cache, config), MiniMax adapter, `/api/v1/voice/{config,transcribe,speak}` behind the auth guard, compose env, `python-multipart` dependency. Route: inline (parent-instructed single writer).
- [x] T2 Tests `backend/tests/unit/test_voice.py` (13): markdown stripping, money, cap, cache/LRU, adapter request shape and error mapping (MockTransport), 503/400/502, auth 401.

## Evidence
- `pytest tests/unit/test_voice.py`: 13 passed. Full backend suite: 683 passed, 3 skipped (before the money tweak; voice file re-run green).
- Real smoke (throwaway script): TTS 32 chars 1.9 s, 127 chars 2.3 s, 195 chars 3.2 s, 320 chars 5.0 s (mp3 32 kHz/128 kbps); STT 7.9 s audio 2.3 s, 22 s audio 4.0 s; STT transcribed the TTS output accurately. STT is enabled on this account.
- Not verified: browser webm/opus and Safari mp4 upload to STT (no ffmpeg here to produce a real webm); mp3 bytes labeled webm were accepted.

## Next
Parent deploys (backend rebuild picks up `python-multipart`); frontend integrates against the contract.


---

# Frontend (feat/voice-chat)

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
- Live check (2026-10-10, headless Chromium, mic stream = real speech): Chromium webm/opus → transcribe 502 "voice provider error (HTTP 400)"; audio/mp4 → 200 exact transcript, sent as a message, reply auto-spoken (orb "Hablando"). Mime order changed to ogg → mp4 → webm. Full suite 38 files / 461 tests pass; build ok.
- Pending: send the voice flag on push-to-talk messages once Core confirms the field name (planned `"voice": true`).
