# voice-player

Branch: feat/voice-player (from feat/foundation b69bf29). Worktree: glazed-copilot-wt/voice-player.

## Objective
Playback controls for spoken replies, and the voice flag on push-to-talk messages.

## Constraints
- TDD off (user choice). Checks: `npx tsc -b`, `npx vitest run`, `npx vite build` in frontend/.
- No AI attribution; conventional commits; no push; deploy only through Core.
- Long-text chunking and the Mexican voice are backend work (Core).

## Tasks
- [x] P1 Player bar while a reply plays (backend audio): play/pause, seek slider, elapsed/total, speed control 0.75×/1×/1.25×/1.5×/2×, close/stop. Speed persists per viewer.
- [x] P2 speechSynthesis fallback: no seek; stop and speed (rate) only.
- [x] P3 Send `voice: true` in POST /cases/{id}/messages for push-to-talk messages only.
- [x] P4 Tests, commit.

## Route
Delegated direct (writer trigger).

## Progress / evidence
- P1/P2: voice/PlayerBar.tsx + useVoiceOutput (player state, togglePause, seek, cycleRate; rate in localStorage `glazed.voice.rate`); synthesis fallback shows speed/stop only and restarts the utterance on a speed change. AgentWindow docks the bar above the chips/composer and raises the scroller bottom to 260px while visible.
- P3: api.sendMessage(caseId, text, context?, {voice}) -> body voice:true only when set; useChat.send opts.voice (kept on retry); AgentWindow passes voice only from push-to-talk.
- P4: tests in voice/voice.test.tsx ("player bar"), api.test.ts, useChat.test.tsx.
- Verification (frontend/): `npx tsc -b`: clean; `npx vitest run`: 38 files, 471 tests passed; `npx vite build`: success.
