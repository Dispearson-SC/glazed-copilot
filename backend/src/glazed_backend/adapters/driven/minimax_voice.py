"""VoiceService over MiniMax: asr-1.0 speech to text and speech-2.8 text to speech. The key is never logged or put in
an error message."""
from __future__ import annotations

from typing import Any

import httpx

from ...ports.voice import VoiceError, VoiceUnavailable

BASE = "https://api.minimax.io/v1"
DEFAULT_VOICE = "Spanish_RationalMan"
DEFAULT_TTS_MODEL = "speech-2.8-turbo"
DEFAULT_STT_MODEL = "asr-1.0"
# Formats the provider documents: wav, aiff, flac, m4a (alac), mp3, aac, opus, ogg. Browsers send webm/opus or mp4/aac.
_EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/aac": "aac",
        "audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/wav": "wav", "audio/x-wav": "wav", "audio/wave": "wav",
        "audio/flac": "flac", "audio/opus": "opus"}


class MiniMaxVoice:
    def __init__(self, api_key: str, voice_id: str = DEFAULT_VOICE, tts_model: str = DEFAULT_TTS_MODEL,
                 stt_model: str = DEFAULT_STT_MODEL, base_url: str = BASE, client: Any = None,
                 stt_timeout: float = 20.0, tts_timeout: float = 20.0) -> None:
        self._key, self.voice_id, self.tts_model, self.stt_model = api_key, voice_id, tts_model, stt_model
        self._base = base_url.rstrip("/")
        self._client = client or httpx.Client()
        self._stt_timeout, self._tts_timeout = stt_timeout, tts_timeout

    def _post(self, path: str, timeout: float, **kw: Any) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._key}", **kw.pop("headers", {})}
        try:
            r = self._client.post(f"{self._base}{path}", headers=headers, timeout=timeout, **kw)
        except httpx.TimeoutException:
            raise VoiceError("voice provider timed out") from None
        except httpx.HTTPError as e:
            raise VoiceError(f"voice provider unreachable ({type(e).__name__})") from None
        if r.status_code in (401, 402, 403, 429):
            raise VoiceUnavailable(f"voice provider refused the request (HTTP {r.status_code})")
        if r.status_code >= 400:
            raise VoiceError(f"voice provider error (HTTP {r.status_code})")
        return r

    def transcribe(self, audio: bytes, mime: str, language: str = "es") -> str:
        base = (mime or "").split(";")[0].strip().lower()
        name = f"audio.{_EXT.get(base, 'webm')}"
        headers = {"language": language} if language else {}
        r = self._post("/speech_to_text", self._stt_timeout, headers=headers,
                       data={"model": self.stt_model, "response_format": "json"},
                       files={"file": (name, audio, base or "application/octet-stream")})
        try:
            return str(r.json()["text"])
        except (ValueError, KeyError, TypeError):
            raise VoiceError("voice provider returned an unusable transcription") from None

    def speak(self, text: str) -> bytes:
        body = {"model": self.tts_model, "text": text, "stream": False,
                "voice_setting": {"voice_id": self.voice_id, "speed": 1.0, "vol": 1.0, "pitch": 0},
                "audio_setting": {"format": "mp3", "sample_rate": 32000, "bitrate": 128000, "channel": 1},
                "language_boost": "Spanish", "output_format": "hex"}
        r = self._post("/t2a_v2", self._tts_timeout, json=body)
        try:
            j = r.json()
            code = (j.get("base_resp") or {}).get("status_code", 0)
            if code in (1004, 1008, 1002):  # auth, insufficient balance, rate limit
                raise VoiceUnavailable(f"voice provider refused the request (code {code})")
            if code != 0:
                raise VoiceError(f"voice provider error (code {code})")
            return bytes.fromhex(j["data"]["audio"])
        except (ValueError, KeyError, TypeError, AttributeError):
            raise VoiceError("voice provider returned unusable audio") from None
