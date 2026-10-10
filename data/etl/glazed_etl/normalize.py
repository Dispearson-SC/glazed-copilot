"""Pure, side-effect free normalization helpers.

They are plain Python so they can be unit-tested directly and also registered
as DuckDB scalar UDFs (see ``register_udfs``). Every helper maps unparseable
input to ``None`` instead of raising; the caller decides how to log it.
"""
from __future__ import annotations

import re
from datetime import date, datetime

_DATE_FORMATS = ("%Y-%m-%d", "%d-%b-%y", "%m/%d/%Y")
_STORE_RE = re.compile(r"^S0*(\d{1,3})$")
_SKU_RE = re.compile(r"^SKU-?(\d{6})$")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
_CURRENCY_ALIASES = {"USD", "US$"}


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def parse_date(value: str | None) -> date | None:
    """Parse ISO, ``DD-Mon-YY`` and ``MM/DD/YYYY`` dates (slashes are MM/DD)."""
    value = _clean(value)
    if value is None:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def normalize_store_id(value: str | None) -> str | None:
    """``s001``, ``S001 ``, ``S0001`` -> ``S001``."""
    value = _clean(value)
    if value is None:
        return None
    match = _STORE_RE.match(value.upper())
    return f"S{int(match.group(1)):03d}" if match else None


def normalize_sku(value: str | None) -> str | None:
    """``sku-100003``, ``SKU100003``, `` SKU-100003 `` -> ``SKU-100003``."""
    value = _clean(value)
    if value is None:
        return None
    match = _SKU_RE.match(value.upper())
    return f"SKU-{match.group(1)}" if match else None


def normalize_currency(value: str | None) -> str | None:
    value = _clean(value)
    if value is None:
        return None
    return "USD" if value.upper() in _CURRENCY_ALIASES else None


def clean_name(value: str | None) -> str | None:
    """Trim, collapse whitespace; title-case only names that are fully UPPER or lower case."""
    value = _clean(value)
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value)
    if value.isupper() or value.islower():
        value = re.sub(r"(?<=\w)-In-(?=\w)", "-in-", value.title())
    return value


def to_float(value: str | None) -> float | None:
    value = _clean(value)
    if value is None:
        return None
    try:
        result = float(value)
    except ValueError:
        return None
    return result if result == result else None  # reject NaN


def parse_time(value: str | None) -> str | None:
    """``3:00`` -> ``03:00``; ``#N/A``/blank -> None."""
    value = _clean(value)
    if value is None:
        return None
    match = _TIME_RE.match(value)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 24 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


# kind -> (python helper, DuckDB result type). Exposed in SQL as ``norm_<kind>(x)``.
NORMALIZERS = {
    "date": (parse_date, "DATE"),
    "store": (normalize_store_id, "VARCHAR"),
    "sku": (normalize_sku, "VARCHAR"),
    "currency": (normalize_currency, "VARCHAR"),
    "name": (clean_name, "VARCHAR"),
    "float": (to_float, "DOUBLE"),
    "time": (parse_time, "VARCHAR"),
}


def register_normalizers(con) -> None:
    """Create lookup tables ``nm_<kind>`` and scalar macros ``norm_<kind>(x)``.

    Python UDFs need numpy and are slow on 600k-row tables, so the pure helpers
    are applied once per *distinct* raw value (``populate``) and SQL does an
    indexed lookup through the macro.
    """
    for kind, (_, sqltype) in NORMALIZERS.items():
        con.execute(f"create or replace table nm_{kind}(raw VARCHAR, val {sqltype})")
        con.execute(
            f"create or replace macro norm_{kind}(x) as "
            f"(select val from nm_{kind} where raw = x)"
        )


def populate(con, kind: str, values) -> None:
    """Add the normalized form of every not-yet-seen raw value for ``kind``."""
    fn, _ = NORMALIZERS[kind]
    known = {r[0] for r in con.execute(f"select raw from nm_{kind}").fetchall()}
    rows = [(v, fn(v)) for v in set(values) if v is not None and v not in known]
    if rows:
        con.executemany(f"insert into nm_{kind} values (?, ?)", rows)
