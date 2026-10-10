"""VoiceService: speech to text and text to speech for the copilot chat (push-to-talk).

Keys stay on the server; the browser only ever talks to our /api/v1/voice routes."""
from __future__ import annotations

from typing import Protocol


class VoiceError(RuntimeError):
    """The provider failed or answered something unusable (maps to 502)."""


class VoiceUnavailable(VoiceError):
    """Voice is not configured, or the provider account cannot serve it right now: quota, auth, rate limit (maps to 503)."""


class VoiceService(Protocol):
    def transcribe(self, audio: bytes, mime: str, language: str = "es") -> str: ...

    def speak(self, text: str) -> bytes:
        """Synthesize `text` and return mp3 bytes."""
        ...
