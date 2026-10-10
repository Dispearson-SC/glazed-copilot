"""TextClassifierPort: turn free text into a closed label (Jev, section 18 of the architecture).

Jev's confidence only measures how well free text maps to a label; it is not the statistical confidence of a
recommendation (that comes from glazed_metrics) and it is not a safety barrier. Every label set carries an escape
label so the classifier can always say "I do not know"."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

REJECTION_REASON = ("precio", "imagen_de_marca", "falta_personal", "desconfia_del_dato", "mal_momento",
                    "prefiere_no_quedarse_corto", "otro", "needs_review")
DEVIATION_CAUSE = ("bloqueo", "clima", "evento_local", "falla_proveedor", "error_operativo", "no_match")
LABEL_SETS = {"rejection_reason": REJECTION_REASON, "deviation_cause": DEVIATION_CAUSE}
ESCAPE = {"rejection_reason": "needs_review", "deviation_cause": "no_match"}
MIN_CONFIDENCE = 0.4  # below this the label is replaced by the escape label

DESCRIPTIONS = {
    "precio": "the manager says it costs too much or the price/cost is the problem",
    "imagen_de_marca": "the action would hurt the brand image or customer perception",
    "falta_personal": "there is not enough staff to carry it out",
    "desconfia_del_dato": "the manager does not trust the data or the number",
    "mal_momento": "bad timing: too busy, a bad day or the wrong moment",
    "prefiere_no_quedarse_corto": "prefers to keep more stock rather than risk running out",
    "otro": "a clear reason that fits none of the other labels",
    "needs_review": "unclear, empty or contradictory: a person must read it",
    "bloqueo": "a road, access or strike blockade",
    "clima": "extreme weather",
    "evento_local": "a local event (festival, game, fair, closure nearby)",
    "falla_proveedor": "the supplier failed or delivered late or short",
    "error_operativo": "an operational mistake inside the store",
    "no_match": "none of the causes applies or the text is unclear",
}


class ClassifierError(RuntimeError):
    """The adapter could not classify (not configured, provider down, unusable answer)."""


def labels_for(kind: str) -> tuple[str, ...]:
    if kind not in LABEL_SETS:
        raise ClassifierError(f"unknown kind {kind!r}; expected one of {tuple(LABEL_SETS)}")
    return LABEL_SETS[kind]


def escape_label(kind: str) -> str:
    labels_for(kind)
    return ESCAPE[kind]


@dataclass(frozen=True)
class Classification:
    label: str
    confidence: float
    model: str
    calibrated: bool
    adapter: str = ""
    warning: str | None = None

    def as_dict(self) -> dict:
        out = {"label": self.label, "confidence": round(self.confidence, 4), "model": self.model,
               "calibrated": self.calibrated, "adapter": self.adapter}
        if self.warning:
            out["warning"] = self.warning
        return out


class TextClassifierPort(Protocol):
    def classify(self, kind: str, text: str) -> Classification: ...
