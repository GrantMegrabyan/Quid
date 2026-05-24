from __future__ import annotations

from decimal import Decimal

from quid_api.refund_detection import detect_refund_pairs
from quid_api.repositories.expenses import BulkItem


def _item(name: str, amount: str, date: str = "2026-04-10") -> BulkItem:
    return BulkItem(name=name, category="other", amount=Decimal(amount), date=date)


def test_empty_list_returns_empty():
    assert detect_refund_pairs([]) == frozenset()


def test_no_credits_returns_empty():
    items = [_item("Pret", "-3.50"), _item("Tesco", "-12.00")]
    assert detect_refund_pairs(items) == frozenset()


def test_no_charges_returns_empty():
    items = [_item("Pret", "3.50"), _item("Tesco", "12.00")]
    assert detect_refund_pairs(items) == frozenset()


def test_exact_name_and_amount_match():
    items = [
        _item("Pret", "-3.50", "2026-04-01"),
        _item("Pret", "3.50", "2026-04-05"),
    ]
    assert detect_refund_pairs(items) == frozenset({1})


def test_refund_suffix_in_name_matches():
    items = [
        _item("Amazon", "-29.99", "2026-04-01"),
        _item("Amazon Refund", "29.99", "2026-04-10"),
    ]
    assert detect_refund_pairs(items) == frozenset({1})


def test_charge_name_starts_with_credit_name_matches():
    items = [
        _item("Pret A Manger", "-3.50", "2026-04-01"),
        _item("Pret", "3.50", "2026-04-05"),
    ]
    assert detect_refund_pairs(items) == frozenset({1})


def test_different_amounts_do_not_match():
    items = [
        _item("Pret", "-3.50", "2026-04-01"),
        _item("Pret", "4.00", "2026-04-05"),
    ]
    assert detect_refund_pairs(items) == frozenset()


def test_completely_different_names_do_not_match():
    items = [
        _item("Pret", "-3.50", "2026-04-01"),
        _item("Tesco", "3.50", "2026-04-05"),
    ]
    assert detect_refund_pairs(items) == frozenset()


def test_outside_window_does_not_match():
    items = [
        _item("Pret", "-3.50", "2026-01-01"),
        _item("Pret", "3.50", "2026-04-10"),
    ]
    assert detect_refund_pairs(items, window_days=30) == frozenset()


def test_within_window_matches():
    items = [
        _item("Pret", "-3.50", "2026-03-11"),
        _item("Pret", "3.50", "2026-04-10"),
    ]
    assert detect_refund_pairs(items, window_days=30) == frozenset({1})


def test_greedy_one_to_one_matching():
    items = [
        _item("Pret", "-3.50", "2026-04-01"),
        _item("Pret", "3.50", "2026-04-05"),
        _item("Pret", "3.50", "2026-04-06"),
    ]
    result = detect_refund_pairs(items)
    assert len(result) == 1
    assert result.issubset({1, 2})


def test_two_independent_pairs_both_detected():
    items = [
        _item("Pret", "-3.50", "2026-04-01"),
        _item("Tesco", "-12.00", "2026-04-02"),
        _item("Pret", "3.50", "2026-04-05"),
        _item("Tesco", "12.00", "2026-04-06"),
    ]
    assert detect_refund_pairs(items) == frozenset({2, 3})


def test_credit_before_charge_still_matches():
    items = [
        _item("Pret", "3.50", "2026-04-01"),
        _item("Pret", "-3.50", "2026-04-05"),
    ]
    assert detect_refund_pairs(items) == frozenset({0})


def test_case_insensitive_name_match():
    items = [
        _item("PRET A MANGER", "-3.50", "2026-04-01"),
        _item("pret a manger", "3.50", "2026-04-05"),
    ]
    assert detect_refund_pairs(items) == frozenset({1})


def test_window_days_zero_only_same_day():
    items = [
        _item("Pret", "-3.50", "2026-04-01"),
        _item("Pret", "3.50", "2026-04-01"),
        _item("Pret", "3.50", "2026-04-02"),
    ]
    result = detect_refund_pairs(items, window_days=0)
    assert result == frozenset({1})


def test_invalid_date_item_skipped_gracefully():
    items = [
        _item("Pret", "-3.50", "not-a-date"),
        _item("Pret", "3.50", "2026-04-05"),
    ]
    assert detect_refund_pairs(items) == frozenset()


def test_zero_amount_items_ignored():
    items = [
        BulkItem(name="Pret", category="other", amount=Decimal("0"), date="2026-04-01"),
        BulkItem(name="Pret", category="other", amount=Decimal("0"), date="2026-04-05"),
    ]
    assert detect_refund_pairs(items) == frozenset()
