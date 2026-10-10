"""Adapters for TextClassifierPort: Jev through Backboard System One, an LLM fallback (MiniMax, OpenAI-compatible
HTTP) and a deterministic keyword fake for tests. Keys are never logged or put in error messages."""
from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from typing import Any, Callable

import httpx

from ...ports.classifier import (DESCRIPTIONS, MIN_CONFIDENCE, Classification, ClassifierError, escape_label, labels_for)

JEV_MODEL = "jev-1.13.0"
MINIMAX_BASE = "https://api.minimax.io/v1"
MINIMAX_MODEL = "MiniMax-M3.1-flash-preview"


def _clamp(kind: str, label: Any, confidence: float, model: str, calibrated: bool, adapter: str) -> Classification:
    """Labels outside the closed set, or answers under the confidence floor, become the escape label."""
    labels = labels_for(kind)
    conf = max(0.0, min(1.0, float(confidence)))
    if label not in labels or conf < MIN_CONFIDENCE:
        return Classification(escape_label(kind), conf, model, calibrated, adapter)
    return Classification(label, conf, model, calibrated, adapter)


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()


class KeywordClassifier:
    """Deterministic fake: first label whose keywords appear in the text."""
    RULES = {
        "rejection_reason": [("precio", ("caro", "precio", "costo", "price", "expensive", "cost")),
                             ("imagen_de_marca", ("imagen", "marca", "brand")),
                             ("falta_personal", ("personal", "gente", "staff", "empleados")),
                             ("desconfia_del_dato", ("no confio", "dato", "numero", "distrust", "data")),
                             ("mal_momento", ("momento", "ocupado", "temporada", "timing", "busy")),
                             ("prefiere_no_quedarse_corto", ("faltar", "quedarme corto", "quedarse corto", "short", "stockout"))],
        "deviation_cause": [("bloqueo", ("bloqueo", "blockade", "carretera", "huelga")),
                            ("clima", ("lluvia", "tormenta", "clima", "weather", "storm", "nieve")),
                            ("evento_local", ("evento", "festival", "feria", "partido", "event")),
                            ("falla_proveedor", ("proveedor", "supplier", "entrega", "retraso")),
                            ("error_operativo", ("error", "olvid", "mistake", "forgot"))]}

    def classify(self, kind: str, text: str) -> Classification:
        labels_for(kind)
        t = _norm(text)
        for label, words in self.RULES[kind]:
            if any(w in t for w in words):
                return Classification(label, 0.9, "keyword-fake", False, "keyword_fake")
        return Classification(escape_label(kind), 0.0, "keyword-fake", False, "keyword_fake")


class BackboardSystemOne:
    """Jev (TypeSafe System One) through Backboard: llm_provider "typesafe", a Choice question over the label set.
    The classifier assistant is created lazily and kept in memory."""

    def __init__(self, api_key: str, client_factory: Callable[[], Any] | None = None, model: str = JEV_MODEL) -> None:
        self.api_key, self.model = api_key, model
        self._factory = client_factory or self._default_client
        self._assistant_id: str | None = None

    def _default_client(self) -> Any:
        from backboard import BackboardClient
        return BackboardClient(api_key=self.api_key)

    async def _ask(self, kind: str, text: str) -> Any:
        client = self._factory()
        if self._assistant_id is None:
            a = await client.create_assistant(name="Glazed · Jev classifier",
                                              description="Closed-label text classification (System One)",
                                              system_prompt="Classify the text into one label. Not a source of numbers.")
            self._assistant_id = str(a.assistant_id)
        thread = await client.create_thread(self._assistant_id)
        question = {"type": "choice", "instructions": f"Classify this {kind.replace('_', ' ')}.",
                    "criteria": {label: DESCRIPTIONS[label] for label in labels_for(kind)}}
        return await client.add_message(thread.thread_id, content=text, llm_provider="typesafe", model_name=self.model,
                                        stream=False, system_one={"questions": {"label": question}})

    def classify(self, kind: str, text: str) -> Classification:
        labels_for(kind)
        if not self.api_key:
            raise ClassifierError("BACKBOARD_API_KEY missing")
        try:
            resp = asyncio.run(self._ask(kind, text))
            so = resp.system_one
            answer = so.answers["label"]
            model = getattr(so, "model", None) or self.model
        except ClassifierError:
            raise
        except Exception as exc:  # noqa: BLE001 - any provider failure lets the chain fall back
            raise ClassifierError(f"Backboard System One failed: {type(exc).__name__}: {exc}") from exc
        label, conf = self._read(answer)
        return _clamp(kind, label, conf, model, True, "backboard_system_one")

    @staticmethod
    def _read(answer: Any) -> tuple[str, float]:
        if isinstance(answer, str):
            return answer, 1.0
        if not isinstance(answer, dict):
            raise ClassifierError("unusable System One answer")
        probs = next((answer[k] for k in ("probabilities", "probs", "scores") if isinstance(answer.get(k), dict)), None)
        label = next((answer[k] for k in ("choice", "label", "answer", "selected", "value", "top") if isinstance(answer.get(k), str)), None)
        if label is None and probs:
            label = max(probs, key=probs.get)
        if label is None:
            raise ClassifierError("System One answer has no label")
        conf = probs.get(label) if probs else next((answer[k] for k in ("confidence", "probability", "score")
                                                   if isinstance(answer.get(k), (int, float))), None)
        if conf is None:
            raise ClassifierError("System One answer has no probability")
        return label, float(conf)


class LLMFallback:
    """MiniMax through an OpenAI-compatible chat completion with a strict JSON answer. Never calibrated."""

    def __init__(self, api_key: str, base_url: str = MINIMAX_BASE, model: str = MINIMAX_MODEL,
                 transport: httpx.BaseTransport | None = None, timeout: float = 30.0) -> None:
        self.api_key, self.base_url, self.model = api_key, base_url.rstrip("/"), model
        self._transport, self._timeout = transport, timeout

    def classify(self, kind: str, text: str) -> Classification:
        labels = labels_for(kind)
        if not self.api_key:
            raise ClassifierError("MINIMAX_API_KEY missing")
        system = ("You classify a store manager's free text into exactly one label. Labels: "
                  + "; ".join(f"{l} = {DESCRIPTIONS[l]}" for l in labels)
                  + f'. If unsure answer "{escape_label(kind)}". Reply with JSON only: {{"label": "<label>", "confidence": <0-1>}}')
        try:
            with httpx.Client(transport=self._transport, timeout=self._timeout) as http:
                r = http.post(f"{self.base_url}/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"},
                              json={"model": self.model, "temperature": 0,
                                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}]})
            if r.status_code >= 400:
                raise ClassifierError(f"MiniMax HTTP {r.status_code}")
            content = r.json()["choices"][0]["message"]["content"]
        except ClassifierError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ClassifierError(f"MiniMax request failed: {type(exc).__name__}") from exc
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.S)
        m = re.search(r"\{.*\}", content, flags=re.S)
        try:
            data = json.loads(m.group(0)) if m else None
            label, conf = data["label"], float(data.get("confidence", 0.5))
        except Exception as exc:  # noqa: BLE001
            raise ClassifierError("MiniMax answer is not the strict JSON format") from exc
        return _clamp(kind, label, conf, self.model, False, "llm_fallback")


class ChainClassifier:
    """First adapter that answers wins; when all fail the answer is the escape label with confidence 0."""

    def __init__(self, adapters: list[Any]) -> None:
        self.adapters = adapters

    def classify(self, kind: str, text: str) -> Classification:
        labels_for(kind)
        warnings = []
        for a in self.adapters:
            try:
                res = a.classify(kind, text)
                return res if not warnings else Classification(res.label, res.confidence, res.model, res.calibrated,
                                                               res.adapter, "; ".join(warnings))
            except ClassifierError as exc:
                warnings.append(str(exc))
        return Classification(escape_label(kind), 0.0, "none", False, "none", "; ".join(warnings) or "no classifier configured")
