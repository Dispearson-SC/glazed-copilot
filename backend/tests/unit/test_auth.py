"""Auth: hashing, signed sessions, login throttle, the HTTP contract and store-scoped enforcement."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from glazed_backend.adapters.driving.app import Container, create_app
from glazed_backend.adapters.driven.memory import InMemoryUsers
from glazed_backend.application.auth import (LoginThrottle, ManageUsers, PasswordHasher, SessionTokens, ensure_admin)
from glazed_backend.scripts import users as users_cli
from tests.fakes import (FakeClock, FakeCore, FakeMetrics, InMemoryAlerts, InMemoryBacktests, InMemoryCases,
                         InMemoryExecutions, InMemoryProposals, InMemoryTrace)

FAST = PasswordHasher(n=2 ** 10)
OPT = {"option_id": "opt-place", "action_type": "place_order", "params": {"sku": "SKU-1", "qty": 12}, "tier": "N1",
       "tier_reasons": ["calibrated"], "net_usd_mid": 20.0}
ISSUE = {"issue_id": "S030|stockout_risk|SKU-1", "kind": "stockout_risk", "severity_usd": 50.0, "sku": "SKU-1", "options": [OPT]}
PW = "correct horse battery"


def make(required=True, secure=False):
    users = InMemoryUsers()
    mgr = ManageUsers(users, FAST)
    mgr.upsert("Admin@Glazed.demo", "Admin", "admin", [], PW)
    mgr.upsert("m30@glazed.demo", "Manager 30", "manager", ["S030"], PW)
    mgr.upsert("m01@glazed.demo", "Manager 01", "manager", ["S001"], PW)
    c = Container(metrics=FakeMetrics({date(2026, 3, 11): [ISSUE]}), core=FakeCore(), cases=InMemoryCases(),
                  alerts=InMemoryAlerts(), proposals=InMemoryProposals(), executions=InMemoryExecutions(),
                  backtests=InMemoryBacktests(), trace=InMemoryTrace(), clock=FakeClock(), users=users, hasher=FAST,
                  auth_required=required, cookie_secure=secure, sessions=SessionTokens(b"test-secret"))
    return c, TestClient(create_app(c))


def login(client, email, password=PW):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_hash_is_salted_verifiable_and_rejects_garbage():
    h = PasswordHasher()
    a, b = h.hash(PW), h.hash(PW)
    assert a != b and a.startswith("scrypt$") and PW not in a
    assert h.verify(PW, a) and not h.verify("nope", a) and not h.verify(PW, "garbage") and not h.verify(PW, "")


def test_token_roundtrip_tamper_expiry_and_foreign_secret():
    t = [1000.0]
    tok = SessionTokens(b"s", ttl_s=60, now=lambda: t[0])
    token, _ = tok.issue("u1")
    assert tok.verify(token) == "u1"
    body, sig = token.split(".")
    assert tok.verify(f"{body}.{sig[:-2]}xx") is None and tok.verify(body + ".") is None and tok.verify(None) is None
    assert SessionTokens(b"other", now=lambda: t[0]).verify(token) is None
    t[0] += 61
    assert tok.verify(token) is None


def test_throttle_blocks_after_limit_and_expires():
    t = [0.0]
    th = LoginThrottle(5, 300, now=lambda: t[0])
    for _ in range(5):
        assert th.retry_after("k") == 0
        th.failure("k")
    assert th.retry_after("k") > 0 and th.retry_after("other") == 0
    t[0] += 301
    assert th.retry_after("k") == 0


def test_login_me_logout_contract():
    _, client = make()
    r = login(client, "admin@glazed.demo")
    assert r.status_code == 200
    assert set(r.json()["user"]) == {"user_id", "email", "name", "role", "store_ids"} and r.json()["user"]["role"] == "admin"
    cookie = r.headers["set-cookie"].lower()
    assert "glazed_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie and "secure" not in cookie
    assert "max-age=43200" in cookie and "password_hash" not in r.text
    assert client.get("/api/v1/auth/me").json()["user"]["email"] == "admin@glazed.demo"
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_cookie_secure_flag_is_configurable():
    _, client = make(secure=True)
    assert "secure" in login(client, "admin@glazed.demo").headers["set-cookie"].lower()


def test_wrong_password_unknown_email_and_inactive_are_the_same_401():
    c, client = make()
    bad = login(client, "admin@glazed.demo", "wrong")
    unknown = login(client, "ghost@glazed.demo")
    assert bad.status_code == unknown.status_code == 401 and bad.json() == unknown.json()
    u = c.users.get_by_email("m30@glazed.demo")
    u.active = False
    c.users.add(u)
    assert login(client, "m30@glazed.demo").status_code == 401


def test_rate_limit_after_five_failures_blocks_even_the_right_password():
    _, client = make()
    for _ in range(5):
        assert login(client, "admin@glazed.demo", "wrong").status_code == 401
    r = login(client, "admin@glazed.demo")
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert login(client, "m30@glazed.demo").status_code == 200  # other email is unaffected


def test_bearer_token_is_accepted_and_garbage_is_not():
    c, client = make()
    token, _ = c.sessions.issue(c.users.get_by_email("m30@glazed.demo").user_id)
    fresh = TestClient(create_app(c))
    assert fresh.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert fresh.get("/api/v1/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_flag_off_keeps_api_open_and_me_still_401():
    _, client = make(required=False)
    assert client.get("/api/v1/health").json()["auth_required"] is False
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/stores").status_code == 200
    assert client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-03-10"}).status_code == 201


def test_flag_on_requires_a_session_everywhere_but_health_and_auth():
    _, client = make()
    assert client.get("/api/v1/health").json()["auth_required"] is True
    for method, path in (("get", "/api/v1/stores"), ("get", "/api/v1/cases"), ("get", "/api/v1/alerts"),
                         ("get", "/api/v1/proposals"), ("get", "/api/v1/agents/status"), ("get", "/api/v1/cases/x")):
        assert getattr(client, method)(path).status_code == 401, path
    assert client.post("/api/v1/cases", json={"bad": 1}).status_code == 401  # auth before body validation
    assert client.post("/api/v1/auth/logout").status_code == 200


def test_manager_is_scoped_to_their_stores():
    c, client = make()
    other = TestClient(create_app(c))
    login(other, "admin@glazed.demo")
    case = other.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-03-10"}).json()
    cid = case["case_id"]

    login(client, "m01@glazed.demo")  # manager of S001, not S030
    assert client.get(f"/api/v1/cases/{cid}").status_code == 403
    assert client.get(f"/api/v1/cases/{cid}/briefing").status_code == 403
    assert client.post(f"/api/v1/cases/{cid}/messages", json={"text": "hi"}).status_code == 403
    assert client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-03-10"}).status_code == 403
    assert client.get("/api/v1/cases", params={"store_id": "S030"}).status_code == 403
    assert client.get("/api/v1/cases").json() == []
    assert client.get("/api/v1/stores").json() == []
    assert client.get("/api/v1/alerts", params={"store_id": "S030"}).status_code == 403
    assert client.get("/api/v1/proposals", params={"case_id": cid}).status_code == 403
    assert client.get("/api/v1/trace", params={"case_id": cid}).status_code == 403
    assert client.post("/api/v1/promos/audit", json={"case_id": cid, "department": "d", "discount_pct": 10}).status_code == 403

    owner = TestClient(create_app(c))
    login(owner, "m30@glazed.demo")
    assert owner.get(f"/api/v1/cases/{cid}").status_code == 200
    assert [s["store_id"] for s in owner.get("/api/v1/stores").json()] == ["S030"]
    assert len(owner.get("/api/v1/cases").json()) == 1
    assert len(other.get("/api/v1/cases").json()) == 1  # admin sees everything


def test_proposal_routes_are_store_scoped_and_decisions_record_the_decider():
    c, admin = make()
    login(admin, "admin@glazed.demo")
    cid = admin.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-03-11"}).json()["case_id"]
    pid = admin.post("/api/v1/proposals", json={"case_id": cid, "issue_id": ISSUE["issue_id"], "option_id": "opt-place"}).json()["proposal_id"]
    stranger = TestClient(create_app(c))
    login(stranger, "m01@glazed.demo")
    assert stranger.post(f"/api/v1/proposals/{pid}/decision", json={"approved": True}).status_code == 403
    assert stranger.get("/api/v1/proposals").json() == []
    manager = TestClient(create_app(c))
    login(manager, "m30@glazed.demo")
    assert manager.post(f"/api/v1/proposals/{pid}/decision", json={"approved": True}).status_code == 200
    assert c.proposals.get(pid).decided_by == c.users.get_by_email("m30@glazed.demo").user_id


def test_decided_by_stays_empty_without_a_session_when_auth_is_off():
    c, client = make(required=False)
    cid = client.post("/api/v1/cases", json={"store_id": "S030", "sim_today": "2026-03-11"}).json()["case_id"]
    pid = client.post("/api/v1/proposals", json={"case_id": cid, "issue_id": ISSUE["issue_id"], "option_id": "opt-place"}).json()["proposal_id"]
    assert client.post(f"/api/v1/proposals/{pid}/decision", json={"approved": True}).status_code == 200
    assert c.proposals.get(pid).decided_by is None


def test_internal_api_is_not_guarded():
    _, client = make()
    assert client.get("/internal/v1/cases/nope/briefing").status_code != 401


def test_bootstrap_admin_creates_updates_and_ignores_missing_env():
    users = InMemoryUsers()
    ensure_admin(users, FAST, {})
    assert users.list() == []
    env = {"GLAZED_ADMIN_EMAIL": "Boss@x.io", "GLAZED_ADMIN_PASSWORD": PW}
    ensure_admin(users, FAST, env)
    boss = users.get_by_email("boss@x.io")
    assert boss.role == "admin" and FAST.verify(PW, boss.password_hash)
    ensure_admin(users, FAST, {**env, "GLAZED_ADMIN_PASSWORD": "another long password"})
    assert len(users.list()) == 1 and FAST.verify("another long password", users.get_by_email("boss@x.io").password_hash)


def test_manage_users_rejects_bad_input():
    mgr = ManageUsers(InMemoryUsers(), FAST)
    for args in (("bad", "N", "manager", [], PW), ("a@b.c", "N", "root", [], PW), ("a@b.c", "N", "manager", [], "short")):
        with pytest.raises(Exception):
            mgr.upsert(*args)


def test_users_cli_reads_password_from_stdin_and_lists_without_hashes(capsys):
    import io
    repo = InMemoryUsers()
    out = io.StringIO()
    code = users_cli.main(["add", "--email", "G@x.io", "--name", "G", "--role", "manager", "--stores", "S001,S030", "--password-stdin"],
                          repo=repo, stdin=io.StringIO(PW + "\n"), out=out)
    assert code == 0 and PW not in out.getvalue()
    u = repo.get_by_email("g@x.io")
    assert u.store_ids == ["S001", "S030"] and PasswordHasher().verify(PW, u.password_hash)
    lst = io.StringIO()
    users_cli.main(["list"], repo=repo, out=lst)
    assert "g@x.io" in lst.getvalue() and "scrypt" not in lst.getvalue()
    with pytest.raises(SystemExit):  # the password is never an argument
        users_cli.main(["add", "--email", "a@b.c", "--name", "A", "--role", "admin", "--password", "x"], repo=repo)
