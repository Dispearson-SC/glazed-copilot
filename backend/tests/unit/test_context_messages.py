"""C1: POST /cases/{id}/messages with a pinned issue context."""
from tests.unit.copilot_support import stockout_issue, with_issues


def ask(client, cid, **body):
    return client.post(f"/api/v1/cases/{cid}/messages", json=body)


def test_context_is_prepended_to_the_core_message_and_history_keeps_the_manager_text():
    client, cid, _ = with_issues(stockout_issue("A"))
    iid = "S030|stockout_risk|A"
    r = ask(client, cid, text="¿Qué hago?", context={"issue_id": iid, "mode": "analizar"})
    assert r.status_code == 202
    sent = client.container.core.sent[-1][2]
    assert sent.endswith("¿Qué hago?") and sent != "¿Qué hago?"
    block = sent[: -len("¿Qué hago?")]
    assert iid in block and "analyze this issue for the manager" in block.lower()
    assert "bestA" in block and "altA" in block and "dnA" in block  # options computed by code
    (turn,) = client.get(f"/api/v1/cases/{cid}/turns").json()
    assert turn["user_text"] == "¿Qué hago?"


def test_dialogo_mode_instruction_and_option_pin():
    client, cid, _ = with_issues(stockout_issue("A"))
    ask(client, cid, text="¿Por qué?", context={"issue_id": "S030|stockout_risk|A", "option_id": "altA", "mode": "dialogo"})
    sent = client.container.core.sent[-1][2].lower()
    assert "answer questions about this issue" in sent and "analyze this issue" not in sent
    assert "pinned option: alta" in sent


def test_turn_echoes_the_context_in_reply_meta_pending_and_done():
    client, cid, _ = with_issues(stockout_issue("A"))
    ctx = {"issue_id": "S030|stockout_risk|A", "option_id": "altA", "mode": "analizar"}
    tid = ask(client, cid, text="hola", context=ctx).json()["turn_id"]
    done = client.get(f"/api/v1/cases/{cid}/turns/{tid}").json()
    assert done["status"] == "done" and done["reply_meta"]["context"] == ctx
    (turn,) = client.get(f"/api/v1/cases/{cid}/turns").json()
    assert turn["reply_meta"]["context"] == ctx
    again = client.get(f"/api/v1/cases/{cid}/turns/{tid}").json()  # stable on re-read
    assert again["reply_meta"]["context"] == ctx


def test_unknown_issue_unknown_option_and_bad_mode_are_rejected_without_sending():
    client, cid, _ = with_issues(stockout_issue("A"))
    assert ask(client, cid, text="x", context={"issue_id": "S030|stockout_risk|NOPE", "mode": "analizar"}).status_code == 404
    assert ask(client, cid, text="x", context={"issue_id": "S030|stockout_risk|A", "option_id": "zz", "mode": "analizar"}).status_code == 400
    assert ask(client, cid, text="x", context={"issue_id": "S030|stockout_risk|A", "mode": "otro"}).status_code == 422
    assert client.container.core.sent == []


def test_message_without_context_is_unchanged():
    client, cid, _ = with_issues()
    tid = ask(client, cid, text="hola").json()["turn_id"]
    assert client.container.core.sent[-1][2] == "hola"
    assert "context" not in (client.get(f"/api/v1/cases/{cid}/turns/{tid}").json().get("reply_meta") or {})
