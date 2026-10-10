"""Q1: the reply sanitizer strips leaked reasoning, garbled runs, glue and holes, and scores contamination."""
import re

from glazed_backend.application import sanitize_reply
from glazed_backend.application.reply_sanitizer import clean_reply


def test_think_blocks_are_removed_raw_and_html_escaped():
    clean, removed = sanitize_reply("<think>voy a calcular</think>Hay 12 cajas.")
    assert clean == "Hay 12 cajas." and removed
    clean, _ = sanitize_reply("&lt;think&gt;borrador&lt;/think&gt;Hay 12 cajas.")
    assert clean == "Hay 12 cajas."
    clean, _ = sanitize_reply("Antes <mm:think>x\ny</mm:think> después")
    assert clean == "Antes después"


def test_orphan_closing_think_tag_drops_the_reasoning_before_it():
    assert sanitize_reply("pensando en voz alta...</mm:think>Respuesta final: 5 cajas.")[0] == "Respuesta final: 5 cajas."
    assert sanitize_reply("pensando...&lt;/mm:think&gt;Final: 5")[0] == "Final: 5"
    assert sanitize_reply("Solo texto </think>")[0] == "Solo texto"  # nothing after the tag: keep what is there


def test_orphan_opening_tag_drops_the_unfinished_reasoning():
    assert sanitize_reply("Respuesta lista. <think>y ahora dudo")[0] == "Respuesta lista."


def test_runs_of_five_identical_letters_drop_the_garbage_token():
    clean, removed = sanitize_reply("El stock presenteDDDDDxxFFF es alto.")
    assert clean == "El stock es alto." and removed
    assert sanitize_reply("jajaja y 1000000 unidades, 0.00000")[0] == "jajaja y 1000000 unidades, 0.00000"


def test_camel_case_glue_between_lowercase_word_and_uppercase_is_split_or_dropped():
    assert sanitize_reply("revisar lasPresentería hoy")[0] == "revisar las Presentería hoy"
    assert sanitize_reply("se puedeHelp con eso")[0] == "se puede con eso"
    # legitimate camel case and code are left alone
    text = "Usa WhatsApp o iPhone; `orderUpTo` y McDonald."
    assert sanitize_reply(text)[0] == text


def test_holes_and_orphan_punctuation_are_tidied_but_numbers_are_not_touched():
    clean, _ = sanitize_reply("sabemos que el 螃蟹 está mal , porque ( ) cuesta $1,392.15 ,, ok .")
    assert clean == "sabemos que el está mal, porque cuesta $1,392.15, ok."
    nums = lambda s: re.findall(r"\d+(?:[.,]\d+)*", s)
    src = "Total 1,392.15 y 0.74 y 12% con 螃蟹 3.5 ,"
    assert nums(sanitize_reply(src)[0]) == nums(src)


def test_clean_reply_is_idempotent_and_keeps_clean_markdown():
    text = "## Resumen\n\n- **Venta** 12%\n  - sub item\n| a | b |\n"
    out = clean_reply(text)
    assert out.text == text and not out.contaminated
    assert clean_reply(out.text).text == out.text


def test_meta_drafts_are_flagged_as_contaminated():
    out = clean_reply("No tengo acceso a los archivos, necesito que me pases los datos reales.")
    assert out.contaminated and out.score >= 2 and "meta_draft" in out.reasons


def test_concatenated_drafts_are_flagged():
    out = clean_reply("Hola, jefe. Hoy vendimos 12.\n\nHola, jefe. Hoy vendimos 13 cajas.\n\n## Resumen\nx\n## Resumen\ny")
    assert out.contaminated and "restarts" in out.reasons


def test_a_normal_answer_is_not_contaminated():
    out = clean_reply("Hola. Hoy vendimos $1,392.15 en 12 cajas.\n\n## Resumen\nTodo bien.")
    assert not out.contaminated and out.score == 0


# ---- Q2: internal names never reach the manager ----
def test_agent_ids_become_spanish_roles():
    out = sanitize_reply("Según glazed_past y `glazed_supply`, consulté a glazed_sentinel. Pregunté al de glazed_strategist.")[0]
    assert out == ("Según el analista histórico y el analista de abastecimiento, consulté a Centinela. "
                   "Pregunté al de el estratega.".replace("de el estratega", "del estratega"))
    assert sanitize_reply("glazed_present dice que sí; glazed_auditor, glazed_liaison y glazed_orchestrator.")[0] == (
        "El analista del presente dice que sí; el auditor de datos, el enlace entre sucursales y el copiloto.")
    assert "glazed_" not in sanitize_reply("glazed_nuevo opina")[0]


def test_tool_names_are_removed():
    out = sanitize_reply("Usé la herramienta get_briefing y `forecast_demand()` luego propose_action y ask_peer para verlo.")[0]
    assert out == "Usé y luego y para verlo."
    for name in ("get_snapshot", "project_inventory", "propose_action", "ask_peer"):
        assert name not in sanitize_reply(f"x {name} y")[0]


def test_known_field_keys_in_backticks_become_plain_spanish():
    out = sanitize_reply("`deadline_passed: 0`, `below_min_order: true`, `sanitized: false` y `days_of_cover: 3.5`")[0]
    assert out == ("pedidos con fecha límite vencida: 0, por debajo del pedido mínimo: sí, "
                   "respuesta depurada: no y días de cobertura: 3.5")
    assert sanitize_reply("Opciones `do_nothing` o `skip_order`; `order_up_to` 12")[0] == (
        "Opciones no hacer nada o omitir el pedido; nivel objetivo de pedido 12")
    assert sanitize_reply("`net_usd_mid`, `lost_sales_usd`, `expected_waste_usd`")[0] == (
        "efecto neto estimado (USD), venta perdida (USD), merma esperada (USD)")


def test_leftover_backticked_snake_case_keys_are_dropped_keeping_numeric_values():
    assert sanitize_reply("Vale `foo_bar: 12.5` y `baz_qux: hola` ok `x` y `S030`")[0] == "Vale 12.5 y ok `x` y `S030`"
    assert sanitize_reply("el `weird_key` aparece")[0] == "el aparece"
