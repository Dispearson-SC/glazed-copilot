"""Manager memories: deterministic category and Spanish text per record. Pure."""
from __future__ import annotations

from ..domain.models import ACTION_TYPES, MEMORY_CATEGORIES

ACTION_ES = {"place_order": "un pedido", "adjust_order_qty": "un ajuste de pedido", "skip_order": "omitir el pedido",
             "markdown_end_of_day": "una rebaja al cierre", "run_promo": "una promoción", "transfer_stock": "una transferencia de inventario",
             "shift_staff_hours": "un cambio de horas de personal", "data_fix_task": "una corrección de datos", "do_nothing": "no hacer nada"}
# supplier-facing orders teach about suppliers; everything else shapes demand
_ACTION_CATEGORY = {"place_order": "proveedores", "adjust_order_qty": "proveedores", "skip_order": "proveedores"}
_SUPPLIER_KINDS = ("late_delivery", "supplier_variability", "short_shipment", "min_order")
_EVENT_KINDS = ("calendar_uplift",)
_REASON_CATEGORY = {"falla_proveedor": "proveedores", "bloqueo": "eventos", "clima": "eventos", "evento_local": "eventos",
                    "mal_momento": "eventos"}


def category_of(action_type: str | None = None, reason_category: str | None = None, kind: str | None = None) -> str:
    """Decision records are categorised by the issue kind and the action; a classified rejection reason by its label."""
    if reason_category in _REASON_CATEGORY:
        return _REASON_CATEGORY[reason_category]
    if reason_category:
        return "preferencias"
    if kind in _SUPPLIER_KINDS:
        return "proveedores"
    if kind in _EVENT_KINDS:
        return "eventos"
    return _ACTION_CATEGORY.get(action_type or "", "demanda")


def action_in_text(text: str) -> str | None:
    return next((a for a in sorted(ACTION_TYPES) if a in text), None)


def approved_text(action_type: str, product: str, when: str | None) -> str:
    text = f"Aprobaste {ACTION_ES.get(action_type, action_type)} de {product}" + (f" el {when}." if when else ".")
    return text.replace(" de el ", " del ")


def rejected_text(action_type: str, product: str, when: str | None, reason: str, reason_category: str | None) -> str:
    base = f"Rechazaste {ACTION_ES.get(action_type, action_type)} de {product}" + (f" el {when}" if when else "")
    tag = f" (motivo: {reason_category.replace('_', ' ')})" if reason_category and reason_category != "needs_review" else ""
    return f"{base}: «{reason.strip()}»{tag}."


def valid_category(category: str | None) -> bool:
    return category is None or category in MEMORY_CATEGORIES
