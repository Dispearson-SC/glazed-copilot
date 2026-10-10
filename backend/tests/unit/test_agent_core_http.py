import httpx
import pytest

from glazed_backend.adapters.driven.agent_core_http import AgentCoreHttp
from glazed_backend.domain import NotFound
from glazed_backend.domain.models import CoreError


def make(handler):
    return AgentCoreHttp("http://core", profile_id="orchestrator", client=httpx.Client(
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
    assert r.headers["x-tenant-id"] == "S030" and r.headers["x-subject-id"] and r.headers["x-channel"] == "http"
    import json
    assert json.loads(r.content) == {"session_id": "c1", "profile_id": "orchestrator", "text": "hola"}


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
    assert [e["entry_id"] for e in got] == ["a", "b"] and all("admin" in r for r in roles)


def test_core_down_raises_core_error():
    def boom(req):
        raise httpx.ConnectError("down")
    with pytest.raises(CoreError):
        make(boom).send_turn("c", "S", "x")
