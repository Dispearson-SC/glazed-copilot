"""Authentication use cases: password hashing, signed expiring session tokens, login throttling, user management.
Standard library only (hashlib.scrypt, hmac)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

from ..domain import DomainError, InvalidCredentials, TooManyAttempts, User, normalize_email
from ..domain.user import ROLES

log = logging.getLogger("glazed.auth")
SESSION_TTL_S = 12 * 3600
MIN_PASSWORD_LEN = 8


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class PasswordHasher:
    """scrypt with a random salt per password. Format: scrypt$n$r$p$salt$hash (parameters travel with the hash)."""

    def __init__(self, n: int = 2 ** 15, r: int = 8, p: int = 1) -> None:
        self.n, self.r, self.p = n, r, p

    @staticmethod
    def _derive(pw: str, salt: bytes, n: int, r: int, p: int) -> bytes:
        return hashlib.scrypt(pw.encode(), salt=salt, n=n, r=r, p=p, dklen=32, maxmem=128 * n * r * 2 + (1 << 20))

    def hash(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        return f"scrypt${self.n}${self.r}${self.p}${_b64(salt)}${_b64(self._derive(password, salt, self.n, self.r, self.p))}"

    def verify(self, password: str, stored: str) -> bool:
        try:
            algo, n, r, p, salt, digest = stored.split("$")
            if algo != "scrypt":
                return False
            got = self._derive(password, _unb64(salt), int(n), int(r), int(p))
            return hmac.compare_digest(got, _unb64(digest))
        except Exception:  # noqa: BLE001 - a malformed hash never authenticates
            return False


class SessionTokens:
    """token = b64(json{uid,exp}) . b64(HMAC-SHA256). Stateless: valid until it expires."""

    def __init__(self, secret: bytes, ttl_s: int = SESSION_TTL_S, now: Callable[[], float] = time.time) -> None:
        if not secret:
            raise ValueError("session secret must not be empty")
        self.secret, self.ttl_s, self.now = secret, ttl_s, now

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "SessionTokens":
        secret = env.get("GLAZED_SESSION_SECRET", "")
        if not secret:
            log.warning("GLAZED_SESSION_SECRET is not set: using a random secret, sessions will not survive a restart")
            return cls(secrets.token_bytes(32))
        return cls(secret.encode())

    def _sig(self, body: str) -> str:
        return _b64(hmac.new(self.secret, body.encode(), hashlib.sha256).digest())

    def issue(self, user_id: str) -> tuple[str, int]:
        exp = int(self.now()) + self.ttl_s
        body = _b64(json.dumps({"uid": user_id, "exp": exp}, separators=(",", ":")).encode())
        return f"{body}.{self._sig(body)}", exp

    def verify(self, token: str | None) -> str | None:
        try:
            body, sig = (token or "").split(".")
            if not hmac.compare_digest(sig, self._sig(body)):
                return None
            data = json.loads(_unb64(body))
            return data["uid"] if int(data["exp"]) > self.now() else None
        except Exception:  # noqa: BLE001
            return None


class LoginThrottle:
    """In-memory: `limit` failures per key within `window_s` block further attempts until the oldest ages out."""

    def __init__(self, limit: int = 5, window_s: int = 300, now: Callable[[], float] = time.time) -> None:
        self.limit, self.window_s, self.now = limit, window_s, now
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _live(self, key: str) -> list[float]:
        cutoff = self.now() - self.window_s
        live = [t for t in self._fails.get(key, []) if t > cutoff]
        if live:
            self._fails[key] = live
        else:
            self._fails.pop(key, None)
        return live

    def retry_after(self, key: str) -> int:
        """Seconds until a new attempt is allowed; 0 when not blocked."""
        with self._lock:
            live = self._live(key)
            return int(live[0] + self.window_s - self.now()) + 1 if len(live) >= self.limit else 0

    def failure(self, key: str) -> None:
        with self._lock:
            self._live(key)
            self._fails.setdefault(key, []).append(self.now())

    def success(self, key: str) -> None:
        with self._lock:
            self._fails.pop(key, None)


class Login:
    def __init__(self, users: Any, hasher: PasswordHasher, throttle: LoginThrottle) -> None:
        self.users, self.hasher, self.throttle = users, hasher, throttle
        self._dummy: str | None = None  # hashed on first use; verified when the email is unknown, to even out timing

    def execute(self, email: str, password: str, client: str) -> User:
        key = f"{(email or '').strip().lower()}|{client}"
        wait = self.throttle.retry_after(key)
        if wait:
            raise TooManyAttempts(wait)
        try:
            user = self.users.get_by_email(normalize_email(email))
        except DomainError:
            user = None
        if user is None and self._dummy is None:
            self._dummy = self.hasher.hash("not-a-real-password")
        ok = self.hasher.verify(password or "", user.password_hash if user else self._dummy)
        if not (user and ok and user.active):
            self.throttle.failure(key)
            raise InvalidCredentials("invalid credentials")
        self.throttle.success(key)
        return user


class ResolveSession:
    def __init__(self, users: Any, tokens: SessionTokens) -> None:
        self.users, self.tokens = users, tokens

    def execute(self, token: str | None) -> User | None:
        uid = self.tokens.verify(token)
        user = self.users.get(uid) if uid else None
        return user if user and user.active else None


class ManageUsers:
    def __init__(self, users: Any, hasher: PasswordHasher) -> None:
        self.users, self.hasher = users, hasher

    def upsert(self, email: str, name: str, role: str, store_ids: list[str], password: str) -> tuple[User, bool]:
        if role not in ROLES:
            raise DomainError(f"role must be one of {ROLES}")
        if len(password) < MIN_PASSWORD_LEN:
            raise DomainError(f"password must have at least {MIN_PASSWORD_LEN} characters")
        email = normalize_email(email)
        user = self.users.get_by_email(email)
        phash = self.hasher.hash(password)
        if user is None:
            user = User.new(email, name, role, store_ids, phash)
            self.users.add(user)
            return user, True
        fresh = User.new(email, name or user.name, role, store_ids, phash)
        user.name, user.role, user.store_ids, user.password_hash, user.active = fresh.name, role, fresh.store_ids, phash, True
        self.users.add(user)
        return user, False

    def list(self) -> list[User]:
        return self.users.list()


def ensure_admin(users: Any, hasher: PasswordHasher, env: dict[str, str]) -> None:
    """Optional bootstrap: GLAZED_ADMIN_EMAIL + GLAZED_ADMIN_PASSWORD create or update the admin at startup."""
    email, password = env.get("GLAZED_ADMIN_EMAIL", ""), env.get("GLAZED_ADMIN_PASSWORD", "")
    if not (email and password):
        return
    try:
        current = users.get_by_email(normalize_email(email))
        if current and current.role == "admin" and current.active and hasher.verify(password, current.password_hash):
            return  # already in sync: no rehash on every restart
        ManageUsers(users, hasher).upsert(email, current.name if current else "Admin", "admin", [], password)
        log.info("admin user %s ensured", email.strip().lower())
    except Exception as exc:  # noqa: BLE001 - a bad bootstrap never stops the service
        log.warning("GLAZED_ADMIN_* bootstrap failed: %s", exc)


def expires_iso(exp: int) -> str:
    return datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()
