"""Voice use cases: the speakable-text conversion, the replay cache and the public configuration.

The chat reply is markdown; reading it aloud verbatim sounds broken ("asterisk asterisk") and costs latency, so it is
reduced to plain sentences and capped at a sentence boundary before synthesis."""
from __future__ import annotations

import re
import threading
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from typing import Any

MAX_SPEAK_CHARS = 900  # one provider call
MAX_TOTAL_CHARS = 6000  # hard upper bound for the whole spoken reply
MAX_PARALLEL = 4
CLOSING = " El resto está en la pantalla."
MAX_AUDIO_BYTES = 2 * 1024 * 1024
MAX_SECONDS = 60

_FENCE = re.compile(r"```.*?```", re.S)
_INLINE_CODE = re.compile(r"`([^`]*)`")
_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_BARE_URL = re.compile(r"https?://\S+")
_EMPHASIS = re.compile(r"(\*\*|__|\*|_|~~)(?=\S)(.+?)(?<=\S)\1")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_BULLET = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+")
_QUOTE = re.compile(r"^\s*>\s?")
_RULE = re.compile(r"^\s*([-*_]\s*){3,}$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_MONEY = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?")
_END = ".!?…:;"
_PT_STRONG = re.compile(r"[ãõç]|\b(?:você|vocês|não|obrigad[oa]|também|amanhã)\b", re.I)
_PT_WEAK = re.compile(r"\b(?:o que|com os|com as|devo|acontece|aí|isso|hoje|quantos|quantas|tenho)\b", re.I)
STT_RETRIES = 2


def looks_portuguese(text: str) -> bool:
    """Cheap guard: the provider sometimes answers Portuguese for short Spanish clips."""
    t = (text or "").lower()
    return bool(_PT_STRONG.search(t)) or len(set(m.group(0) for m in _PT_WEAK.finditer(t))) >= 2


def _money(m: re.Match) -> str:
    whole, cents = m.group(1).replace(",", ""), (m.group(2) or "")[1:3].ljust(2, "0")
    return f"{whole} dólares" + (f" con {int(cents)} centavos" if m.group(2) and int(cents) else "")


def speakable_text(markdown: str, limit: int = MAX_SPEAK_CHARS) -> str:
    text = _FENCE.sub(" ", markdown or "")
    lines: list[str] = []
    for raw in text.splitlines():
        if not raw.strip() or _RULE.match(raw) or _TABLE_SEP.match(raw):
            continue
        line = raw
        if "|" in line and line.count("|") >= 2:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            line = ", ".join(c for c in cells if c)
        line = _QUOTE.sub("", _BULLET.sub("", _HEADING.sub("", line)))
        line = _IMAGE.sub(r"\1", line)
        line = _LINK.sub(r"\1", line)
        line = _BARE_URL.sub("", line)
        line = _INLINE_CODE.sub(r"\1", line)
        for _ in range(2):  # nested emphasis such as **bold _and_ italic**
            line = _EMPHASIS.sub(r"\2", line)
        line = _MONEY.sub(_money, line).strip()
        if line:
            lines.append(line if line[-1] in _END else line + ".")
    out = re.sub(r"\s+", " ", " ".join(lines)).strip()
    return _cap(out, limit)


def chunk_text(text: str, size: int = MAX_SPEAK_CHARS) -> list[str]:
    """Split at sentence boundaries into pieces of at most `size` chars, in order."""
    chunks, rest = [], text.strip()
    while rest:
        if len(rest) <= size:
            chunks.append(rest)
            break
        piece = _cap(rest, size)
        chunks.append(piece)
        rest = rest[len(piece):].strip() if rest.startswith(piece) else rest[size:].strip()
    return chunks


def _strip_id3(mp3: bytes) -> bytes:
    if mp3[:3] == b"ID3" and len(mp3) >= 10:
        size = ((mp3[6] & 0x7F) << 21) | ((mp3[7] & 0x7F) << 14) | ((mp3[8] & 0x7F) << 7) | (mp3[9] & 0x7F)
        return mp3[10 + size:]
    return mp3


def _cap(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = text[:limit]
    cut = max(head.rfind(". "), head.rfind("! "), head.rfind("? "))
    if cut >= limit * 0.4:
        return head[:cut + 1]
    space = head.rfind(" ")
    return head[:space if space > 0 else limit].rstrip(" ,;:") + "."


class VoiceDesk:
    """Wraps a VoiceService with the replay cache. `service=None` means voice is not configured."""

    def __init__(self, service: Any, voice_id: str, model: str, enabled: bool = True, cache_size: int = 64,
                 max_chars: int = MAX_SPEAK_CHARS, max_total: int = MAX_TOTAL_CHARS) -> None:
        self.service, self.voice_id, self.model = service, voice_id, model
        self.enabled = bool(enabled and service is not None)
        self.max_chars, self.max_total, self._size = max_chars, max_total, cache_size
        self._cache: OrderedDict[tuple[str, str, str], bytes] = OrderedDict()
        self._lock = threading.Lock()

    def config(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "stt": self.enabled, "tts": self.enabled, "voice_id": self.voice_id,
                "max_seconds": MAX_SECONDS}

    def transcribe(self, audio: bytes, mime: str, language: str = "es") -> str:
        return self.service.transcribe(audio, mime, language).strip()

    def transcribe_checked(self, audio: bytes, mime: str, language: str = "es") -> tuple[str, bool]:
        """Returns (text, language_suspect). For Spanish, a Portuguese-looking result is retried up to STT_RETRIES times."""
        text = self.transcribe(audio, mime, language)
        if not language.lower().startswith("es"):
            return text, False
        for _ in range(STT_RETRIES):
            if not looks_portuguese(text):
                return text, False
            text = self.transcribe(audio, mime, language)
        return text, looks_portuguese(text)

    def speak(self, text: str) -> bytes:
        spoken = speakable_text(text, 10 ** 9)
        if len(spoken) > self.max_total:
            spoken = _cap(spoken, self.max_total - len(CLOSING)) + CLOSING
        if not spoken:
            raise ValueError("nothing to speak")
        key = (self.voice_id, self.model, spoken)
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None:
                self._cache.move_to_end(key)
                return hit
        chunks = chunk_text(spoken, self.max_chars)
        if len(chunks) == 1:
            audio = self.service.speak(chunks[0])
        else:
            with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(chunks))) as pool:
                parts = list(pool.map(self.service.speak, chunks))  # in order; first failure propagates
            audio = parts[0] + b"".join(_strip_id3(p) for p in parts[1:])
        with self._lock:
            self._cache[key] = audio
            while len(self._cache) > self._size:
                self._cache.popitem(last=False)
        return audio
