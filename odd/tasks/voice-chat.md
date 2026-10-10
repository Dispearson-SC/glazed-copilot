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
