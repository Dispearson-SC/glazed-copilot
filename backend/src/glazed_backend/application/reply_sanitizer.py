"""Clean-up of the model's final reply before the manager sees it.

Conservative on purpose: only things that are certainly noise are removed (leaked reasoning, garbled token runs,
stray non-Latin scripts, glued words), numbers are never touched, and `contamination` says when what is left still
looks like a leaked draft so the caller can ask for one rewrite."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_FOREIGN = ("Ѐ-ԯ԰-֏֐-׿؀-ۿݐ-ݿऀ-ॿ฀-๿"
            "ᄀ-ᇿ぀-ヿ㐀-䶿一-鿿가-힯")
_FOREIGN_RUN = re.compile(f"[{_FOREIGN}]+(?:[ ]+[{_FOREIGN}]+)*")

_TAG = r"(?:mm:)?(?:think|thinking|reasoning)"
_ESCAPED_TAG = re.compile(rf"&lt;\s*(/?)\s*({_TAG})\s*&gt;", re.I)
_THINK_BLOCK = re.compile(rf"<\s*({_TAG})\s*>.*?<\s*/\s*\1\s*>", re.I | re.S)
_CLOSE_TAG = re.compile(rf"<\s*/\s*{_TAG}\s*>", re.I)
_OPEN_TAG = re.compile(rf"<\s*{_TAG}\s*>", re.I)

_GARBLE = re.compile(r"\w*([^\W\d_])\1{4,}\w*", re.I)
_GLUE = re.compile(r"\b([a-záéíóúñ]{2,})([A-Z][a-záéíóúñ]+)\b")
_ENGLISH = frozenset("help the and with for you can will this that please sure here just also".split())
_CODE = re.compile(r"(`[^`\n]*`|https?://\S+|\S+@\S+)")

_META = re.compile(
    r"no tengo acceso a (?:los|las|el|la)\b|necesito que me (?:pases|pase|proporciones|compartas|des)\b"
    r"|como (?:modelo de lenguaje|una? ia\b|asistente de ia)|\bthe user (?:is|wants|asks|said)\b|\blet me (?:think|draft|rewrite)\b"
    r"|\bborrador\b|\bdraft (?:answer|reply|response)\b", re.I)
_GREETING = re.compile(r"^\s*(?:¡\s*)?(?:hola|buen(?:os|as)? (?:d[ií]as?|tardes|noches))\b", re.I | re.M)
_HEADING = re.compile(r"^\s{0,3}#{1,3}\s+(.+?)\s*$", re.M)


@dataclass
class ReplyCleaning:
    text: str
    removed: list[str] = field(default_factory=list)
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    @property
    def contaminated(self) -> bool:
        return self.score >= 2


def _strip_think(text: str, removed: list[str]) -> str:
    text = _ESCAPED_TAG.sub(lambda m: f"<{m.group(1)}{m.group(2)}>", text)
    for m in _THINK_BLOCK.finditer(text):
        removed.append(m.group(0))
    text = _THINK_BLOCK.sub("", text)
    closers = list(_CLOSE_TAG.finditer(text))
    if closers:  # the opening tag was swallowed: everything before the last closer is reasoning
        last = closers[-1]
        before, after = text[:last.start()], text[last.end():]
        if after.strip():
            removed.append(before + last.group(0))
            text = after
        text = _CLOSE_TAG.sub("", text)
    opener = _OPEN_TAG.search(text)
    if opener:  # unfinished reasoning until the end
        if text[:opener.start()].strip():
            removed.append(text[opener.start():])
            text = text[:opener.start()]
        else:
            text = _OPEN_TAG.sub("", text)
    return text


def _glue(segment: str, hits: list[str]) -> str:
    def fix(m: re.Match[str]) -> str:
        hits.append(m.group(0))
        return m.group(1) if m.group(2).lower() in _ENGLISH else f"{m.group(1)} {m.group(2)}"
    return _GLUE.sub(fix, segment)


def _fix_glue(text: str, hits: list[str]) -> str:
    parts = _CODE.split(text)  # odd indexes are code/urls/emails: never touched
    return "".join(p if i % 2 else _glue(p, hits) for i, p in enumerate(parts))


def _tidy(text: str) -> str:
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"(?<=\S)[ ]{2,}", " ", text)
    text = re.sub(r"[ ]+([,;:.!?])(?![.\d])", r"\1", text)
    text = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", text)
    text = re.sub(r"([,;])\s*\.", ".", text)
    text = re.sub(r"[ ]+$", "", text, flags=re.M)
    text = re.sub(r"(?<=\S)[ ]{2,}", " ", text)
    return text.strip()


def clean_reply(text: str) -> ReplyCleaning:
    original, removed = text, []
    text = _strip_think(text, removed)
    think_removed = bool(removed)
    foreign = _FOREIGN_RUN.findall(text)
    text = _FOREIGN_RUN.sub("", text)
    removed += foreign
    garbage = [m.group(0) for m in _GARBLE.finditer(text)]
    text = _GARBLE.sub("", text)
    removed += garbage
    glued: list[str] = []
    text = _fix_glue(text, glued)
    if text != original:  # untouched replies come back byte-identical
        text = _tidy(text)
    reasons, score = [], 0
    if think_removed:
        reasons.append("think_tags")
    if garbage:
        reasons.append("garble")
        score += 1
    if len(glued) >= 2 or (glued and garbage):
        reasons.append("glue")
        score += 1
    if len(foreign) >= 3:
        reasons.append("foreign_script")
        score += 1
    if _META.search(text):
        reasons.append("meta_draft")
        score += 2
    headings = [h.lower() for h in _HEADING.findall(text)]
    if len(_GREETING.findall(text)) >= 2 or len(headings) != len(set(headings)):
        reasons.append("restarts")
        score += 2
    return ReplyCleaning(text, removed, score, reasons)


def sanitize_reply(text: str) -> tuple[str, list[str]]:
    """`(clean_text, removed_fragments)`; kept for the callers that only need the cleaned text."""
    out = clean_reply(text)
    return out.text, out.removed
