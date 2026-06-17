"""Tests for the data layer."""
from app.data_loader import VALID_LABELS, load_dataset


def test_split_is_80_20_and_reproducible():
    ds1 = load_dataset()
    ds2 = load_dataset()
    total = len(ds1.train) + len(ds1.holdout)
    assert total == 300
    # 80/20 split
    assert len(ds1.holdout) == 60
    assert len(ds1.train) == 240
    # deterministic: same holdout ids both times
    assert [m["id"] for m in ds1.holdout] == [m["id"] for m in ds2.holdout]


def test_all_labels_valid():
    ds = load_dataset()
    assert all(m["true_label"] in VALID_LABELS for m in ds.all_messages)


def test_sop_and_feed_loaded():
    ds = load_dataset()
    assert "P1" in ds.sop and "bias-to-escalate" in ds.sop.lower()
    assert ds.country_feed["active_incidents"]
    assert any("Hat Yai" in inc["location"] for inc in ds.country_feed["active_incidents"])


def test_holdout_contains_p1_needles():
    # The demo depends on P1s existing in the holdout to score recall.
    ds = load_dataset()
    assert any(m["true_label"] == "P1" for m in ds.holdout)
