"""Which other cases' decisions a case may see. Test (archived) cases never leak, only live cases of the same store
count, and an item is dated by the simulated day it was decided on, never by the wall clock: nothing decided after
this case's date is visible (no look-ahead through memory)."""
from __future__ import annotations

from datetime import date
from typing import Any

from ..domain import Case


def decision_date(p: Any, owners: dict[str, Case]) -> date | None:
    """The simulated day of a proposal/decision: `decision_as_of`, else the date of the case that holds it."""
    raw = (p.params or {}).get("decision_as_of")
    if raw:
        try:
            return date.fromisoformat(str(raw)[:10])
        except ValueError:
            pass
    owner = owners.get(p.case_id)
    return owner.sim_today if owner is not None else None


def in_scope(case: Case, owner_id: str, owners: dict[str, Case]) -> bool:
    """The case itself (even archived), or another live, non-archived case of the same store (live cases only)."""
    if owner_id == case.case_id:
        return True
    o = owners.get(owner_id)
    return case.mode == "live" and o is not None and o.mode == "live" and not o.archived and o.store_id == case.store_id


def visible(case: Case, p: Any, owners: dict[str, Case]) -> bool:
    """A proposal of this store that this case may show: in scope and not decided after this case's date."""
    if p.case_id == case.case_id:
        return True
    if not in_scope(case, p.case_id, owners):
        return False
    d = decision_date(p, owners)
    return d is None or d <= case.sim_today


def experience_visible(case: Case, e: Any, proposals: Any, owners: dict[str, Case]) -> bool:
    """A store experience (Backboard) may be cited by this case unless it is tied to a decision the case cannot see:
    one from an archived or sandbox case, or one made after this case's date."""
    p = proposals.get(e.decision_id) if e.decision_id else None
    if p is None or p.store_id != case.store_id:
        return True  # nothing ties it to a case of this store
    return visible(case, p, owners)
