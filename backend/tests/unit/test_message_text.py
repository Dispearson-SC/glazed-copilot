import json

from glazed_backend.application import _message_text


def test_a_serialized_core_envelope_yields_its_plain_content():
    env = json.dumps({"kind": "request", "parts": [{"content": "¿Qué tengo que pedir hoy?"}]})
    assert _message_text({"text": env}) == "¿Qué tengo que pedir hoy?"


def test_plain_text_and_non_envelope_json_pass_through():
    assert _message_text({"text": "hola"}) == "hola"
    assert _message_text({"text": '{"a": 1}'}) == '{"a": 1}'
