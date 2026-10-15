import httpx
import pytest

from glazed_backend.adapters.driven.agent_core_http import AgentCoreHttp
from glazed_backend.domain import NotFound
from glazed_backend.domain.models import CoreError


def make(handler):
    return AgentCoreHttp("http://core", client=httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://core"))


def test_create_conversation_maps_session_to_case_id():
    assert make(lambda r: httpx.Response(500)).create_conversation("c1", "S030") == "c1"


def test_send_turn_posts_identity_headers_and_body():
    seen = {}

    def h(req: httpx.Request):
        seen["req"] = req
        return httpx.Response(202, json={"turn_id": "t9", "status": "accepted"}, headers={"Location": "/turns/t9"})

    tid = make(h).send_turn("c1", "S030", "hola")
    r = seen["req"]
    assert tid == "t9" and r.url.path == "/turns" and r.method == "POST"
    assert r.headers["x-tenant-id"] == "S030" and r.headers["x-subject-id"] == "manager-1"
    assert r.headers["x-channel"] == "glazed" and r.headers["x-roles"] == "glazed-manager"
    import json
    assert json.loads(r.content) == {"session_id": "c1", "profile_id": "glazed_orchestrator", "text": "hola"}


def test_scheduled_turns_use_the_service_role():
    seen = {}

    def h(req):
        seen["roles"] = req.headers["x-roles"]
        return httpx.Response(202, json={"turn_id": "t1"})

    make(h).send_turn("c1", "S030", "tick", service=True)
    assert seen["roles"] == "glazed-service"


def test_identity_is_configurable():
    seen = {}

    def h(req):
        seen.update(req.headers)
        return httpx.Response(202, json={"turn_id": "t1"})

    c = AgentCoreHttp("http://core", profile_id="p", subject_id="boss", channel="ch", roles="r1", service_roles="r2",
                      client=httpx.Client(transport=httpx.MockTransport(h), base_url="http://core"))
    c.send_turn("c", "S1", "x")
    assert (seen["x-subject-id"], seen["x-channel"], seen["x-roles"]) == ("boss", "ch", "r1")


def test_from_env_defaults_and_overrides():
    d = AgentCoreHttp.from_env("http://core", {})
    assert (d.profile_id, d.channel, d.roles, d.service_roles, d.subject_id) == (
        "glazed_orchestrator", "glazed", "glazed-manager", "glazed-service", "manager-1")
    o = AgentCoreHttp.from_env("http://core", {"GLAZED_CORE_PROFILE": "x", "GLAZED_CORE_SUBJECT": "s"})
    assert (o.profile_id, o.subject_id) == ("x", "s")


def test_get_turn_and_404():
    ok = make(lambda r: httpx.Response(200, json={"turn_id": "t", "status": "finished", "text": "hi"}))
    assert ok.get_turn("t", "S030")["text"] == "hi"
    with pytest.raises(NotFound):
        make(lambda r: httpx.Response(404, json={"detail": "x"})).get_turn("t", "S030")


def test_transcript_follows_cursor_and_uses_admin_role():
    pages = {None: {"entries": [{"entry_id": "a"}], "next_cursor": "n", "has_more": True},
             "n": {"entries": [{"entry_id": "b"}], "next_cursor": None, "has_more": False}}
    roles = []

    def h(req):
        roles.append(req.headers["x-roles"])
        assert req.url.path == "/admin/conversations/c1"
        return httpx.Response(200, json={"session_id": "c1", "audience": "admin", **pages[req.url.params.get("cursor")]})

    got = make(h).list_transcript("c1", "S030")
    assert [e["entry_id"] for e in got] == ["a", "b"] and all(r.split(",") == ["glazed-manager", "admin"] for r in roles)


def test_core_down_raises_core_error():
    def boom(req):
        raise httpx.ConnectError("down")
    with pytest.raises(CoreError):
        make(boom).send_turn("c", "S", "x")


def test_health_probes_the_schema_route_and_reports_latency():
    seen = {}

    def h(req: httpx.Request):
        seen["path"] = req.url.path
        return httpx.Response(200, json={"openapi": "3.1.0"})

    out = make(h).health()
    assert seen["path"] == "/openapi.json" and out["ok"] is True and out["latency_ms"] >= 0


def test_health_raises_core_error_when_unreachable():
    def h(req: httpx.Request):
        raise httpx.ConnectError("refused")

    with pytest.raises(CoreError):
        make(h).health()


def test_send_turn_sends_the_data_version_header_only_when_given():
    seen = []

    def h(req):
        seen.append(req.headers)
        return httpx.Response(202, json={"turn_id": "t1"})

    client = make(h)
    client.send_turn("c1", "S030", "hola", data_version="2026-10-15")
    client.send_turn("c1", "S030", "hola")
    assert seen[0]["x-data-version"] == "2026-10-15"
    assert "x-data-version" not in seen[1]
