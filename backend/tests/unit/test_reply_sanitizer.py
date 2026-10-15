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
        "El analista del presente dice que sí; Centinela, el enlace entre sucursales y el copiloto.")
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


# --- foreign / glued tokens leaked inside Spanish prose ---
import pytest


@pytest.mark.parametrize("raw, expected", [
    ("Si no, tengasalski sobrante en bodega.", "Si no, tengas sobrante en bodega."),
    ("Md aplicas rebajas al producto.", "aplicas rebajas al producto."),
    ("Si te interesa seriously el traslado, avísame.", "Si te interesa el traslado, avísame."),
    ("Merece la pena perguntarlo a la sucursal.", "Merece la pena preguntarlo a la sucursal."),
    ("Mira cómo sirvin las ventas.", "Mira cómo sirven las ventas."),
    ("Ahora puedeHelp con el pedido.", "Ahora puede con el pedido."),
    ("Es probable que relies de la demanda.", "Es probable que depende de la demanda."),
    ("Todo bien, presenteDDDD y listo.", "Todo bien,  y listo.".replace("  ", " ")),
    ("Es caro, however hay stock; therefore pide.", "Es caro, sin embargo hay stock; por lo tanto pide."),
    ("Dile que não hay, obrigado.", "Dile que no hay, gracias."),
    ("Dile a você que please espere.", "Dile a usted que por favor espere."),
])
def test_foreign_tokens_are_dropped_or_mapped(raw, expected):
    assert clean_reply(raw).text == expected


@pytest.mark.parametrize("text", [
    "Md Choc Stout C.B. tiene 12 cajas.",
    "El Md Choc Stout aplica rebajas.",
    "SKU-AAA1 y 4500 unidades, tienes 3.5% de merma.",
    "Help Wanted Ale: 24 botellas; Seriously Good IPA: 6.",
    "Tienes que revisar si puedes pedir más; tengamos cuidado, sirven bien.",
    "Si no tienes stock, pregunta; no hay problema, ya lo sabes.",
    "Se aplica la regla y Es útil: puedes ordenar hoy.",
    "Tengas lo que tengas, la cerveza real sale bien.",
])
def test_legit_spanish_and_product_names_are_untouched(text):
    out = clean_reply(text)
    assert out.text == text and not out.removed and out.score == 0


def test_many_foreign_tokens_raise_contamination_but_one_does_not():
    assert not clean_reply("Si te interesa seriously el traslado.").contaminated
    out = clean_reply("Md aplicas rebajas, tengasalski sobrante, perguntarlo, seriously no relies de eso.")
    assert "foreign_tokens" in out.reasons and out.contaminated
    assert out.text == "aplicas rebajas, tengas sobrante, preguntarlo, no depende de eso."


def test_foreign_fixes_skip_code_and_urls():
    text = "Usa `seriously` y https://x.io/please/help para ver."
    assert clean_reply(text).text == text


def test_the_integrity_auditor_is_presented_as_centinela():
    out = sanitize_reply("Consulté al Auditor de Integridad y el auditor de datos confirma la diferencia.")[0]
    assert "uditor" not in out and out.count("Centinela") == 2


@pytest.mark.parametrize("raw, expected", [
    # Live P14 replies (the model glued a Spanish function word to the number after it).
    ("Como el quiebre se proyecta también el21, el pedido llega justo.",
     "Como el quiebre se proyecta también el 21, el pedido llega justo."),
    ("Vendiste 12 piezas del19 al 22 con58,90 kg de merma.",
     "Vendiste 12 piezas del 19 al 22 con 58,90 kg de merma."),
    ("Las11 entregas llegan en14 días, por130.50 en total.",
     "Las 11 entregas llegan en 14 días, por 130.50 en total."),
    ("Sube al100 % para el2026 y de11 a 15 cajas.",
     "Sube al 100 % para el 2026 y de 11 a 15 cajas."),
])
def test_a_function_word_glued_to_a_number_is_spaced(raw, expected):
    out = clean_reply(raw)
    assert out.text == expected and out.score == 0


def test_full_width_punctuation_becomes_ascii():
    out = clean_reply("Hay stock，pide hoy：12 cajas（croissant）；listo。¿Algo más？")
    assert out.text == "Hay stock, pide hoy: 12 cajas (croissant); listo. ¿Algo más?"
    assert out.score == 0


@pytest.mark.parametrize("text", [
    "SKU-AAA1, lote A12, IPA2 y P2 siguen igual; Hotel21 y Gel10 son nombres.",
    "El 21 llega en 14 días, del 19 al 22, con 58,90 kg.",
    "Revisa `el21` y https://x.io/del19 para ver.",
    "EL21 es el código del pasillo y Q4 el trimestre.",
])
def test_codes_names_and_already_spaced_numbers_are_untouched(text):
    out = clean_reply(text)
    assert out.text == text and not out.removed and out.score == 0
