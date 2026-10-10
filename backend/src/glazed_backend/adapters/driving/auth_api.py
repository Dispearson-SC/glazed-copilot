"""Auth routes (/api/v1/auth/*) and the guard applied to the rest of /api/v1."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ... import application as uc
from ...application.auth import Login, ResolveSession, expires_iso

COOKIE = "glazed_session"


class LoginBody(BaseModel):
    email: str
    password: str


def _token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header[:7].lower() == "bearer ":
        return header[7:].strip()
    return request.cookies.get(COOKIE)


class AuthGuard:
    """Router dependency. Always resolves the session (so decided_by works with the flag off); with auth required it
    answers 401 without one and 403 when the case, proposal, alert or backtest in the path belongs to another store."""

    def __init__(self, c: Any) -> None:
        self.c = c
        self.resolver = ResolveSession(c.users, c.sessions)

    def user(self, request: Request) -> Any:
        if not hasattr(request.state, "user"):
            request.state.user = self.resolver.execute(_token(request))
        return request.state.user

    def forbid(self) -> HTTPException:
        return HTTPException(403, "this store is not available to your user")

    def ensure_store(self, request: Request, store_id: str) -> None:
        u = self.user(request)
        if self.c.auth_required and u is not None and not u.can_access(store_id):
            raise self.forbid()

    def allowed(self, request: Request, store_id: str) -> bool:
        u = self.user(request)
        return not self.c.auth_required or (u is not None and u.can_access(store_id))

    def __call__(self, request: Request) -> None:
        u = self.user(request)
        if not self.c.auth_required:
            return
        if u is None:
            raise HTTPException(401, "authentication required")
        c, p = self.c, request.path_params
        if "case_id" in p:
            self.ensure_store(request, uc._case(c.cases, p["case_id"]).store_id)
        for key, repo in (("proposal_id", c.proposals), ("alert_id", c.alerts), ("run_id", c.backtests)):
            if key in p:
                row = repo.get(p[key])
                if row is not None:
                    self.ensure_store(request, row.store_id)


def build_auth_router(c: Any, guard: AuthGuard) -> APIRouter:
    r = APIRouter(prefix="/api/v1/auth")
    login_uc = Login(c.users, c.hasher, c.login_throttle)
    cookie = dict(key=COOKIE, httponly=True, secure=c.cookie_secure, samesite="lax", path="/")

    @r.post("/login")
    def login(b: LoginBody, request: Request, response: Response):
        client = request.client.host if request.client else "?"
        user = login_uc.execute(b.email, b.password, client)
        token, exp = c.sessions.issue(user.user_id)
        response.set_cookie(value=token, max_age=c.sessions.ttl_s, **cookie)
        return {"user": user.public(), "expires_at": expires_iso(exp)}

    @r.post("/logout")
    def logout(response: Response):
        response.delete_cookie(**{k: v for k, v in cookie.items()})
        return {"ok": True}

    @r.get("/me")
    def me(request: Request):
        u = guard.user(request)
        if u is None:
            raise HTTPException(401, "authentication required")
        return {"user": u.public()}

    return r
