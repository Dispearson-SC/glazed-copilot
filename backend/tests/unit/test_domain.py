from datetime import date, datetime, timezone

import pytest

from glazed_backend.domain import (
    ACTION_TYPES, Alert, AlertState, Case, Proposal, InvalidTransition, DomainError,
    alert_type_for_kind,
)


def mk_alert(state=AlertState.NUEVA):
    return Alert(alert_id="a1", alert_type=2, store_id="S030", case_id="c1", severity_usd=10.0,
                 state=state, issue={"issue_id": "i1"}, issue_key="k1", as_of=date(2026, 3, 10),
                 created_at=datetime(2026, 3, 10, tzinfo=timezone.utc))


def test_alert_walks_canonical_path():
    a = mk_alert()
    a.advance(AlertState.VISTA)
    a.advance(AlertState.EN_ANALISIS)
    assert a.state is AlertState.EN_ANALISIS


def test_alert_rejects_skipping_states():
    with pytest.raises(InvalidTransition):
        mk_alert().advance(AlertState.DECIDIDA)


def test_alert_advance_to_walks_forward_through_intermediate_states():
    a = mk_alert()
    a.advance_to(AlertState.DECIDIDA)
    assert a.state is AlertState.DECIDIDA
    a.advance_to(AlertState.RECHAZADA)
    a.advance(AlertState.MEDIDA)
    assert a.state is AlertState.MEDIDA


def test_terminal_state_has_no_exit():
    with pytest.raises(InvalidTransition):
        mk_alert(AlertState.MEDIDA).advance(AlertState.VISTA)


def test_alert_can_be_postponed_from_any_open_state():
    a = mk_alert(AlertState.VISTA)
    a.advance(AlertState.POSPUESTA)
    assert a.state is AlertState.POSPUESTA


def test_action_types_are_closed_list():
    assert ACTION_TYPES == {"place_order", "adjust_order_qty", "skip_order", "markdown_end_of_day",
                            "run_promo", "transfer_stock", "shift_staff_hours", "data_fix_task", "do_nothing"}


def test_proposal_rejects_unknown_action_and_tier():
    with pytest.raises(DomainError):
        Proposal.new(case_id="c", store_id="S", issue_id="i", action_type="launch_rocket",
                     params={}, tier="N2", rationale="x")
    with pytest.raises(DomainError):
        Proposal.new(case_id="c", store_id="S", issue_id="i", action_type="place_order",
                     params={}, tier="N9", rationale="x")


def test_proposal_decide_requires_reason_on_reject_and_only_once():
    p = Proposal.new(case_id="c", store_id="S", issue_id="i", action_type="place_order",
                     params={"sku": "A"}, tier="N2", rationale="r")
    with pytest.raises(DomainError):
        p.decide(approved=False, reason="")
    p.decide(approved=False, reason="too expensive")
    assert p.status == "rejected" and p.reason == "too expensive"
    with pytest.raises(DomainError):
        p.decide(approved=True, reason="")


def test_case_mode_validated():
    with pytest.raises(DomainError):
        Case.new(store_id="S030", sim_today=date(2026, 3, 10), mode="prod")


def test_alert_type_for_kind():
    assert alert_type_for_kind("stockout_risk") == 2
    assert alert_type_for_kind("expiring") == 1
    assert alert_type_for_kind("short_shipment") == 8
    assert alert_type_for_kind("late_delivery") == 20
