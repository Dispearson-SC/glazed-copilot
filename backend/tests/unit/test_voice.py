"""Voice: speakable-text conversion, replay cache, adapter contract (fake HTTP) and the /api/v1/voice routes."""
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from glazed_backend.adapters.driven.minimax_voice import MiniMaxVoice
from glazed_backend.adapters.driving.app import Container, create_app
from glazed_backend.adapters.driven.memory import InMemoryUsers
from glazed_backend.application.auth import ManageUsers, PasswordHasher, SessionTokens
from glazed_backend.application.voice import MAX_AUDIO_BYTES, VoiceDesk, speakable_text
from glazed_backend.ports.voice import VoiceError, VoiceUnavailable
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace)


class FakeVoice:
    def __init__(self, fail=None):
        self.speaks, self.heard, self.fail = [], [], fail

    def transcribe(self, audio, mime, language="es"):
        if self.fail:
            raise self.fail
        self.heard.append((len(audio), mime, language))
        return "  cuanto pido hoy  "

    def speak(self, text):
        if self.fail:
            raise self.fail
        self.speaks.append(text)
        return b"ID3-fake-mp3"


def client(voice="default", required=False, **kw):
    users = InMemoryUsers()
    h = PasswordHasher(n=2 ** 10)
    ManageUsers(users, h).upsert("a@glazed.demo", "A", "admin", [], "correct horse battery")
    desk = VoiceDesk(FakeVoice(), "Spanish_Test", "speech-test") if voice == "default" else voice
    c = Container(metrics=FakeMetrics({date(2026, 3, 11): []}), core=FakeCore(), cases=InMemoryCases(), alerts=InMemoryAlerts(),
                  proposals=InMemoryProposals(), executions=InMemoryExecutions(), backtests=InMemoryBacktests(),
                  trace=InMemoryTrace(), clock=FakeClock(), users=users, hasher=h, auth_required=required,
                  sessions=SessionTokens(b"s"), voice=desk, **kw)
    return c, TestClient(create_app(c))


def audio(n=100):
    return {"audio": ("rec.webm", b"x" * n, "audio/webm;codecs=opus")}


# --- speakable text -------------------------------------------------------------------------------------------

def test_markdown_is_stripped():
    md = ("## Resumen\n\n- **Pedir** 12 cajas de [Concha](http://x.io/a)\n- Usar `SKU-1`\n\n"
          "| SKU | Qty |\n|---|---|\n| A | 3 |\n\n```py\nprint(1)\n```\n> nota _importante_ https://a.b/c\n")
    out = speakable_text(md)
    for bad in ("#", "*", "`", "|", "](", "http", "print", "---"):
        assert bad not in out
    assert "Pedir 12 cajas de Concha" in out and "SKU, Qty" in out and "nota importante" in out
    assert "  " not in out


def test_money_is_made_speakable_and_plain_text_is_kept():
    assert speakable_text("Ganas $1,234.50 y pierdes $40") == "Ganas 1234 dólares con 50 centavos y pierdes 40 dólares."
    assert speakable_text("Hola. ¿Qué tal?") == "Hola. ¿Qué tal?"
    assert speakable_text("") == "" and speakable_text("```x```") == ""


def test_long_text_is_capped_at_a_sentence_boundary():
    out = speakable_text("Frase corta numero uno. " * 100)
    assert len(out) <= 900 and out.endswith("uno.")
    nospace = speakable_text("palabra " * 300)
    assert len(nospace) <= 901 and nospace.endswith(".")


# --- desk: cache ---------------------------------------------------------------------------------------------

def test_replay_hits_the_cache_and_lru_evicts():
    fv = FakeVoice()
    d = VoiceDesk(fv, "v", "m", cache_size=2)
    assert d.speak("**uno**") == d.speak("uno.") == b"ID3-fake-mp3"
    assert len(fv.speaks) == 1
    d.speak("dos"); d.speak("tres")
    d.speak("uno")
    assert len(fv.speaks) == 4  # "uno" was evicted
    assert VoiceDesk(fv, "other", "m").enabled


# --- adapter contract against a fake HTTP transport -------------------------------------------------------------------

def adapter(handler):
    return MiniMaxVoice("secret-key", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_tts_request_shape_and_hex_decoding():
    seen = {}

    def handler(req):
        seen["auth"], seen["body"], seen["path"] = req.headers["authorization"], req.read(), req.url.path
        return httpx.Response(200, json={"base_resp": {"status_code": 0}, "data": {"audio": b"mp3!".hex()}})
    assert adapter(handler).speak("hola") == b"mp3!"
    assert seen["path"] == "/v1/t2a_v2" and seen["auth"] == "Bearer secret-key"
    assert b'"language_boost":"Spanish"' in seen["body"].replace(b" ", b"") and b"speech-2.8-turbo" in seen["body"]


def test_stt_sends_multipart_with_language_header():
    seen = {}

    def handler(req):
        seen.update(lang=req.headers.get("language"), body=req.read(), ctype=req.headers["content-type"])
        return httpx.Response(200, json={"text": "hola", "duration": 1.0})
    assert adapter(handler).transcribe(b"abc", "audio/webm;codecs=opus", "es") == "hola"
    assert seen["ctype"].startswith("multipart/form-data") and seen["lang"] == "es"
    assert b'name="file"; filename="audio.webm"' in seen["body"] and b"asr-1.0" in seen["body"]


def test_provider_failures_map_to_typed_errors_without_the_key():
    for status, exc in ((402, VoiceUnavailable), (429, VoiceUnavailable), (500, VoiceError)):
        try:
            adapter(lambda r, s=status: httpx.Response(s, json={})).speak("x")
        except VoiceError as e:
            assert type(e) is exc and "secret-key" not in str(e)
    bad = adapter(lambda r: httpx.Response(200, json={"base_resp": {"status_code": 1008}}))
    try:
        bad.speak("x")
        assert False
    except VoiceUnavailable:
        pass

    def boom(req):
        raise httpx.ReadTimeout("slow")
    try:
        adapter(boom).transcribe(b"a", "audio/webm")
        assert False
    except VoiceError as e:
        assert not isinstance(e, VoiceUnavailable)


# --- routes ---------------------------------------------------------------------------------------------------

def test_config_and_503_when_voice_is_off():
    _, cl = client(voice=None)
    assert cl.get("/api/v1/voice/config").json()["enabled"] is False
    assert cl.post("/api/v1/voice/transcribe", files=audio()).status_code == 503
    assert cl.post("/api/v1/voice/speak", json={"text": "hola"}).status_code == 503
    _, off = client(voice=VoiceDesk(None, "v", "m"))
    assert off.get("/api/v1/voice/config").json() == {"enabled": False, "stt": False, "tts": False, "voice_id": "v", "max_seconds": 60}
    _, flag = client(voice=VoiceDesk(FakeVoice(), "v", "m", enabled=False))
    assert flag.post("/api/v1/voice/speak", json={"text": "hola"}).status_code == 503


def test_config_when_enabled():
    _, cl = client()
    assert cl.get("/api/v1/voice/config").json() == {"enabled": True, "stt": True, "tts": True, "voice_id": "Spanish_Test", "max_seconds": 60}


def test_transcribe_returns_text_and_validates_input():
    c, cl = client()
    r = cl.post("/api/v1/voice/transcribe", files=audio(500))
    assert r.status_code == 200 and r.json() == {"text": "cuanto pido hoy", "language_suspect": False}
    assert c.voice.service.heard == [(500, "audio/webm;codecs=opus", "es")]
    assert cl.post("/api/v1/voice/transcribe", files=audio(0)).status_code == 400
    assert cl.post("/api/v1/voice/transcribe", files=audio(MAX_AUDIO_BYTES + 1)).status_code == 400
    assert cl.post("/api/v1/voice/transcribe", files={"other": ("a", b"x", "audio/webm")}).status_code == 400


def test_speak_returns_mp3_and_replay_uses_the_cache():
    c, cl = client()
    r = cl.post("/api/v1/voice/speak", json={"text": "## Hola\n**Pide** $1,000"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3-fake-mp3"
    assert cl.post("/api/v1/voice/speak", json={"text": "## Hola\n**Pide** $1,000"}).content == r.content
    assert c.voice.service.speaks == ["Hola. Pide 1000 dólares."]
    assert cl.post("/api/v1/voice/speak", json={"text": "```x```"}).status_code == 400


def test_provider_errors_surface_as_502_and_503():
    assert client(voice=VoiceDesk(FakeVoice(VoiceError("down")), "v", "m"))[1].post("/api/v1/voice/speak", json={"text": "a"}).status_code == 502
    assert client(voice=VoiceDesk(FakeVoice(VoiceUnavailable("quota")), "v", "m"))[1].post("/api/v1/voice/transcribe", files=audio()).status_code == 503


def test_auth_guard_applies_to_voice_routes():
    _, cl = client(required=True)
    assert cl.get("/api/v1/voice/config").status_code == 401
    assert cl.post("/api/v1/voice/speak", json={"text": "hola"}).status_code == 401
    assert cl.post("/api/v1/voice/transcribe", files=audio()).status_code == 401
    assert cl.post("/api/v1/auth/login", json={"email": "a@glazed.demo", "password": "correct horse battery"}).status_code == 200
    assert cl.get("/api/v1/voice/config").status_code == 200


# --- long text: chunking, parallel synthesis, concatenation --------------------------------------------------------------

def _long(n):
    return " ".join(f"Frase numero {i} de la respuesta." for i in range(n))


def test_long_text_is_chunked_and_concatenated_in_order():
    class Echo(FakeVoice):
        def speak(self, text):  # audio = the text itself, so the output order is observable
            import time; time.sleep(0.02 if text.startswith("Frase numero 0 ") else 0)
            self.speaks.append(text)
            return text.encode()
    fv = Echo()
    text = _long(100)  # ~3400 chars
    out = VoiceDesk(fv, "v", "m").speak(text)
    assert len(fv.speaks) > 3 and all(len(c) <= 900 for c in fv.speaks)
    assert " ".join(sorted(fv.speaks, key=text.index)) == speakable_text(text, 10 ** 9)
    assert out == "".join(sorted(fv.speaks, key=text.index)).encode()


def test_id3_tags_are_stripped_from_later_chunks():
    class V(FakeVoice):
        def speak(self, text):
            return b"ID3\x04\x00\x00\x00\x00\x00\x02XX" + text[:5].encode()
    out = VoiceDesk(V(), "v", "m").speak(_long(60))
    assert out.count(b"ID3") == 1 and out.startswith(b"ID3")


def test_long_text_hits_cache_and_key_includes_voice():
    fv = FakeVoice()
    d = VoiceDesk(fv, "v1", "m")
    d.speak(_long(60)); n = len(fv.speaks)
    d.speak(_long(60))
    assert len(fv.speaks) == n
    VoiceDesk(fv, "v2", "m").speak(_long(60))
    assert len(fv.speaks) == 2 * n
    assert ("v1", "m", speakable_text(_long(60), 10 ** 9)) in d._cache


def test_over_six_thousand_chars_gets_closing_sentence():
    fv = FakeVoice()
    VoiceDesk(fv, "v", "m").speak(_long(400))
    joined = " ".join(fv.speaks)
    assert joined.endswith("El resto está en la pantalla.") and len(joined) <= 6000
    assert all(len(c) <= 900 for c in fv.speaks)


def test_short_text_is_a_single_call_without_closing():
    fv = FakeVoice()
    VoiceDesk(fv, "v", "m").speak("Hola mundo.")
    assert fv.speaks == ["Hola mundo."]


def test_any_chunk_failure_fails_the_request():
    class V(FakeVoice):
        def speak(self, text):
            if "numero 30 " in text:
                raise VoiceError("down")
            return b"x"
    _, cl = client(voice=VoiceDesk(V(), "v", "m"))
    assert cl.post("/api/v1/voice/speak", json={"text": _long(100)}).status_code == 502


# --- ASR language guard -----------------------------------------------------------------------------------------

class SeqVoice(FakeVoice):
    def __init__(self, *texts):
        super().__init__()
        self.texts, self.calls = list(texts), 0

    def transcribe(self, audio, mime, language="es"):
        self.calls += 1
        return self.texts[min(self.calls, len(self.texts)) - 1]


PT = "O que acontece com os bagels aí?"


def test_portuguese_result_is_retried_until_spanish():
    v = SeqVoice(PT, "¿Qué pasa con los bagels hoy?")
    assert VoiceDesk(v, "v", "m").transcribe_checked(b"a", "audio/webm") == ("¿Qué pasa con los bagels hoy?", False)
    assert v.calls == 2


def test_all_portuguese_sets_the_suspect_flag_after_three_attempts():
    v = SeqVoice(PT, "Você não sabe", "Amanhã devo pedir")
    text, suspect = VoiceDesk(v, "v", "m").transcribe_checked(b"a", "audio/webm")
    assert v.calls == 3 and text == "Amanhã devo pedir" and suspect is True


def test_normal_spanish_is_not_retried():
    v = SeqVoice("¿Cuánto vendí ayer?")
    assert VoiceDesk(v, "v", "m").transcribe_checked(b"a", "audio/webm") == ("¿Cuánto vendí ayer?", False)
    assert v.calls == 1


def test_non_spanish_language_is_never_checked():
    v = SeqVoice(PT)
    assert VoiceDesk(v, "v", "m").transcribe_checked(b"a", "audio/webm", "pt") == (PT, False)
    assert v.calls == 1


@pytest.mark.parametrize("text,foreign", [
    ("Che passa con lo speck oggi?", True), ("O que acontece com os bagels hoje?", True),
    ("What should I order today?", True), ("¿Cuánto vendí ayer?", False),
    ("Cuántas donas glaseadas debo pedir para mañana", False), ("Qué pasa con los bagels hoy", False),
    ("Sí", False), ("Bagels", False), ("Donas glaseadas", False)])
def test_language_guard_flags_any_non_spanish_transcript(text, foreign):
    from glazed_backend.application.voice import looks_foreign
    assert looks_foreign(text) is foreign
