import json

import httpx
import pytest

from glazed_cli import client as client_mod
from glazed_cli.client import Api, ApiError, BackendDown
from glazed_cli.state import State


def test_state_roundtrip_and_env_path(tmp_path, monkeypatch):
    path = tmp_path / "sub" / "state.json"
    monkeypatch.setenv("GLAZED_STATE", str(path))
    assert State.load().current_case is None
    State(current_case="abc").save()
    assert json.loads(path.read_text())["current_case"] == "abc"
    assert State.load().current_case == "abc"


def test_state_corrupt_file_is_empty(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_text("{nope")
    monkeypatch.setenv("GLAZED_STATE", str(path))
    assert State.load().current_case is None


def test_state_default_path(monkeypatch, tmp_path):
    monkeypatch.delenv("GLAZED_STATE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    State(current_case="x").save()
    assert (tmp_path / ".glazed" / "state.json").exists()


def _api(handler):
    return Api("http://x.test/", transport=httpx.MockTransport(handler))


def test_api_get_builds_url_and_drops_none_params():
    seen = {}

    def h(req):
        seen["url"] = str(req.url)
        return httpx.Response(200, json=[1])

    assert _api(h).get("/api/v1/cases", store_id=None, state="nueva") == [1]
    assert seen["url"] == "http://x.test/api/v1/cases?state=nueva"


def test_api_error_uses_detail():
    api = _api(lambda r: httpx.Response(422, json={"detail": "bad date"}))
    with pytest.raises(ApiError, match="bad date"):
        api.post("/api/v1/cases", {})


def test_backend_down_is_friendly():
    def h(req):
        raise httpx.ConnectError("refused")

    with pytest.raises(BackendDown, match="http://x.test"):
        _api(h).get("/api/v1/health")


def test_default_url_from_env(monkeypatch):
    monkeypatch.setenv("GLAZED_API_URL", "http://env.test")
    assert client_mod.resolve_url(None) == "http://env.test"
    assert client_mod.resolve_url("http://flag.test") == "http://flag.test"
    monkeypatch.delenv("GLAZED_API_URL")
    assert client_mod.resolve_url(None) == "http://localhost:8080"
