"""Voice routes /api/v1/voice/*: push-to-talk transcription and spoken replies. Same auth guard as the public API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ...application.voice import MAX_AUDIO_BYTES
from ...ports.voice import VoiceError, VoiceUnavailable
from .auth_api import AuthGuard


class SpeakBody(BaseModel):
    text: str


def build_voice_router(c: Any, guard: AuthGuard) -> APIRouter:
    r = APIRouter(prefix="/api/v1/voice", dependencies=[Depends(guard)])

    def desk() -> Any:
        v = c.voice
        if v is None or not v.enabled:
            raise HTTPException(503, "voice is not configured")
        return v

    def provider(call):
        try:
            return call()
        except VoiceUnavailable as e:
            raise HTTPException(503, str(e)) from None
        except VoiceError as e:
            raise HTTPException(502, str(e)) from None

    @r.get("/config")
    def config() -> dict[str, Any]:
        v = c.voice
        return v.config() if v is not None else {"enabled": False, "stt": False, "tts": False, "voice_id": "",
                                                 "max_seconds": 60}

    @r.post("/transcribe")
    async def transcribe(request: Request) -> dict[str, str]:
        v = desk()
        form = await request.form(max_part_size=MAX_AUDIO_BYTES + 1024)
        up = form.get("audio")
        if up is None or not hasattr(up, "read"):
            raise HTTPException(400, "multipart field 'audio' is required")
        audio = await up.read(MAX_AUDIO_BYTES + 1)
        if not audio:
            raise HTTPException(400, "audio is empty")
        if len(audio) > MAX_AUDIO_BYTES:
            raise HTTPException(400, f"audio is too big (max {MAX_AUDIO_BYTES // 1024} KB)")
        lang = str(form.get("language") or "es")
        from starlette.concurrency import run_in_threadpool
        text = await run_in_threadpool(provider, lambda: v.transcribe(audio, up.content_type or "", lang))
        return {"text": text}

    @r.post("/speak")
    def speak(b: SpeakBody) -> Response:
        v = desk()
        try:
            audio = provider(lambda: v.speak(b.text))
        except ValueError:
            raise HTTPException(400, "text has nothing to speak") from None
        return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=3600"})

    return r
