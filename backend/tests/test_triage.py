"""Triage Agent tests. These call Vertex AI — run in Cloud Shell where ADC is set.

  cd backend && python -m pytest tests/test_triage.py -v
"""
from app.data_loader import load_dataset
from app.agents.triage import triage_message


def _ctx():
    ds = load_dataset()
    return ds.sop, ds.country_feed


def test_obvious_p1_is_flagged():
    sop, feed = _ctx()
    res = triage_message(
        "We are trapped on the roof, water is rising and my child can't swim. Help now!",
        sop, feed,
    )
    assert res.severity.value == "P1"
    assert res.sop_reference  # must cite the SOP
    assert res.reason


def test_obvious_p4_is_routine():
    sop, feed = _ctx()
    res = triage_message("Is Hat Yai airport open today? Just planning my trip.", sop, feed)
    assert res.severity.value == "P4"


def test_detention_is_p1():
    sop, feed = _ctx()
    res = triage_message(
        "I'm a Singaporean detained by police at the border, they won't let me call anyone.",
        sop, feed,
    )
    assert res.severity.value == "P1"
