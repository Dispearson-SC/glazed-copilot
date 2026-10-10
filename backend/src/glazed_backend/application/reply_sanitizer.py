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

_GARBLE = re.compile(r"\w*([^\W\d_])\1{3,}\w*", re.I)
_GLUE = re.compile(r"\b([a-záéíóúñ]{2,})([A-Z][a-záéíóúñ]+)\b")
_ENGLISH = frozenset("help the and with for you can will this that please sure here just also".split())
_CODE = re.compile(r"(`[^`\n]*`|https?://\S+|\S+@\S+)")

_META = re.compile(
    r"no tengo acceso a (?:los|las|el|la)\b|necesito que me (?:pases|pase|proporciones|compartas|des)\b"
    r"|como (?:modelo de lenguaje|una? ia\b|asistente de ia)|\bthe user (?:is|wants|asks|said)\b|\blet me (?:think|draft|rewrite)\b"
    r"|\bborrador\b|\bdraft (?:answer|reply|response)\b", re.I)
_GREETING = re.compile(r"^\s*(?:¡\s*)?(?:hola|buen(?:os|as)? (?:d[ií]as?|tardes|noches))\b", re.I | re.M)
_HEADING = re.compile(r"^\s{0,3}#{1,3}\s+(.+?)\s*$", re.M)


_ROLES = {"present": "el analista del presente", "past": "el analista histórico", "supply": "el analista de abastecimiento",
          "strategist": "el estratega", "sentinel": "Centinela", "auditor": "Centinela",
          "liaison": "el enlace entre sucursales", "orchestrator": "el copiloto"}
_AGENT = re.compile(r"`?\bglazed_([a-z]+)\b`?")
_HIDDEN_ROLE = re.compile(r"\b(?:el |la )?(?:agente )?auditor(?:a)? de (?:integridad|datos)\b", re.I)
_TOOL = re.compile(r"(?:\b(?:la|el|mi|su) (?:herramienta|tool|función) )?`?\b(?:(?:get|forecast|project|propose)_[a-z0-9_]+|ask_peer)\b(?:\(\))?`?",
                   re.I)
_FIELDS = {"deadline_passed": "pedidos con fecha límite vencida", "below_min_order": "por debajo del pedido mínimo",
           "sanitized": "respuesta depurada", "net_usd_mid": "efecto neto estimado (USD)",
           "lost_sales_usd": "venta perdida (USD)", "expected_waste_usd": "merma esperada (USD)",
           "days_of_cover": "días de cobertura", "do_nothing": "no hacer nada", "skip_order": "omitir el pedido",
           "order_up_to": "nivel objetivo de pedido"}
_KEY = r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*"
_TICKED = re.compile(rf"`({_KEY})(?:\s*[:=]\s*([^`]*?))?\s*`")
_BARE = re.compile(rf"\b({'|'.join(k for k in _FIELDS if '_' in k)})\b")
_NUMERIC = re.compile(r"-?\$?\d[\d,]*(?:\.\d+)?%?")
_SENTENCE_START = re.compile(r"(?:^|[.!?:]\s+|\n\s*(?:[-*#>]+\s*)?|^\s*#+\s*)$")


def role_name_es(agent_id: str) -> str:
    """Spanish display name of an agent role (`supply` or `glazed_supply`), as a label: no leading article."""
    role = _ROLES.get(agent_id.removeprefix("glazed_"), "un agente especialista")
    role = re.sub(r"^(?:el|la|un|una) ", "", role)
    return role[0].upper() + role[1:]


def _role(text: str, m: re.Match[str]) -> str:
    role = _ROLES.get(m.group(1), "un agente especialista")
    return role[0].upper() + role[1:] if _SENTENCE_START.search(text[:m.start()]) else role


def humanize_internal_names(text: str) -> str:
    """Agent ids, tool names and raw field keys are internal: the manager reads Spanish roles and plain labels."""
    text = _AGENT.sub(lambda m: _role(text, m), text)
    text = _HIDDEN_ROLE.sub("Centinela", text)  # the auditor is presented as Centinela (seven original roles)
    text = re.sub(r"\b(de|a) el\b", lambda m: "del" if m.group(1) == "de" else "al", text)

    def ticked(m: re.Match[str]) -> str:
        key, value = m.group(1), (m.group(2) or "").strip()
        if key in _FIELDS:
            value = {"true": "sí", "false": "no"}.get(value.lower(), value)
            return f"{_FIELDS[key]}: {value}" if value else _FIELDS[key]
        if "_" not in key:
            return m.group(0)
        return value if _NUMERIC.fullmatch(value) else ""
    text = _TICKED.sub(ticked, text)
    text = _TOOL.sub("", text)
    return _BARE.sub(lambda m: _FIELDS[m.group(1)], text)


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


# --- foreign tokens leaked by the model inside Spanish prose (conservative: lowercase, curated, outside code) ---
_VERB_FORMS = ("tengas tienes tiene puedes puede quieres quiere necesitas necesita sabes sabe haces hace debes debe "
               "aplicas aplica pides pide buscas busca prefieres prefiere sirve sirven revisas revisa ordenas ordena "
               "compras compra vendes vende ves vas ve").split()
_GLUED = re.compile(rf"\b({'|'.join(sorted(_VERB_FORMS, key=len, reverse=True))})([a-z]{{3,}})\b")
_NON_SPANISH_TAIL = re.compile(r"[kw]|[^aeiouáéíóú\W\d_]{3}")  # k/w or three consonants in a row
_LEAK_DROP = re.compile(r"\b(?:seriously|actually|basically|really|literally|honestly)\b[ ]?")
_LEAK_MAP = (
    (re.compile(r"\bpergunt(?=[a-záéíóúñ]*\b)"), "pregunt"),
    (re.compile(r"\brelies\b"), "depende"),
    (re.compile(r"\bhowever\b"), "sin embargo"),
    (re.compile(r"\btherefore\b"), "por lo tanto"),
    (re.compile(r"\bvocê\b"), "usted"),
    (re.compile(r"\bnão\b"), "no"),
    (re.compile(r"\bobrigad[oa]\b"), "gracias"),
    (re.compile(r"\bplease\b"), "por favor"),
    (re.compile(r"\bsirvin\b"), "sirven"),
)
_LEAK_HELP = re.compile(r"\bhelp\b[ ]?")
# 1-2 consonant-only capitalised fragment right before a lowercase Spanish verb ("Md aplicas")
_STRAY = re.compile(rf"(?<![\w.])(?P<frag>[B-DF-HJ-NP-TV-Z][b-df-hj-np-tv-z])[ ]+(?=(?:{'|'.join(_VERB_FORMS)})\b)")


def _fix_foreign_tokens(segment: str, hits: list[str]) -> str:
    def glued(m: re.Match[str]) -> str:
        if not _NON_SPANISH_TAIL.search(m.group(2)):
            return m.group(0)
        hits.append(m.group(0))
        return m.group(1)

    def stray(m: re.Match[str]) -> str:
        frag = m.group("frag")
        before = segment[:m.start()].rstrip()
        prev = re.search(r"(\S+)$", before)
        if prev and re.search(r"[A-Z0-9]", prev.group(1)):  # product / SKU context: when unsure, keep it
            return m.group(0)
        hits.append(frag)
        return ""

    def drop(m: re.Match[str]) -> str:
        hits.append(m.group(0).strip())
        return ""

    def mapped(pattern: re.Pattern[str], repl: str):
        def fix(m: re.Match[str]) -> str:
            hits.append(m.group(0))
            return repl
        return fix

    segment = _STRAY.sub(stray, segment)
    segment = _GLUED.sub(glued, segment)
    segment = _LEAK_DROP.sub(drop, segment)
    segment = _LEAK_HELP.sub(drop, segment)
    for pattern, repl in _LEAK_MAP:
        segment = pattern.sub(mapped(pattern, repl), segment)
    return segment


def _fix_foreign(text: str, hits: list[str]) -> str:
    parts = _CODE.split(text)
    return "".join(p if i % 2 else _fix_foreign_tokens(p, hits) for i, p in enumerate(parts))


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
    text = humanize_internal_names(_strip_think(text, removed))
    think_removed = bool(removed)
    foreign = _FOREIGN_RUN.findall(text)
    text = _FOREIGN_RUN.sub("", text)
    removed += foreign
    garbage = [m.group(0) for m in _GARBLE.finditer(text)]
    text = _GARBLE.sub("", text)
    removed += garbage
    glued: list[str] = []
    text = _fix_glue(text, glued)
    leaks: list[str] = []
    text = _fix_foreign(text, leaks)
    removed += leaks
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
    if len(leaks) >= 2:
        reasons.append("foreign_tokens")
        score += 2 if len(leaks) >= 4 else 1
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
