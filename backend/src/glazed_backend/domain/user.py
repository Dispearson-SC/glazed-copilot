"""User aggregate and the auth errors. Pure domain: no hashing, tokens or I/O here."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .models import DomainError, new_id, utcnow

ROLES = ("admin", "manager")


class InvalidCredentials(DomainError):
    """Wrong email or password. The message is deliberately generic."""


class TooManyAttempts(DomainError):
    def __init__(self, retry_after_s: int) -> None:
        super().__init__("too many failed attempts, try again later")
        self.retry_after_s = retry_after_s


def normalize_email(email: str) -> str:
    e = (email or "").strip().lower()
    if "@" not in e or any(ch.isspace() for ch in e) or e.startswith("@") or e.endswith("@"):
        raise DomainError(f"invalid email {email!r}")
    return e


@dataclass
class User:
    user_id: str
    email: str
    name: str
    role: str
    store_ids: list[str]
    password_hash: str
    active: bool = True
    created_at: datetime = field(default_factory=utcnow)

    @classmethod
    def new(cls, email: str, name: str, role: str, store_ids: list[str], password_hash: str) -> "User":
        if role not in ROLES:
            raise DomainError(f"role must be one of {ROLES}")
        return cls(new_id(), normalize_email(email), name.strip() or email, role,
                   sorted({s.strip() for s in store_ids if s.strip()}), password_hash)

    def can_access(self, store_id: str) -> bool:
        return self.role == "admin" or store_id in self.store_ids

    def public(self) -> dict[str, Any]:
        return {"user_id": self.user_id, "email": self.email, "name": self.name, "role": self.role,
                "store_ids": list(self.store_ids)}
