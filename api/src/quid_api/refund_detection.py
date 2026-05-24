from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quid_api.repositories.expenses import BulkItem

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text.strip().lower())


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _names_match(charge_name: str, refund_name: str) -> bool:
    cn = _norm(charge_name)
    rn = _norm(refund_name)
    return cn == rn or rn.startswith(cn) or cn.startswith(rn)


def detect_refund_pairs(
    items: list[BulkItem],
    *,
    window_days: int = 60,
) -> frozenset[int]:
    effective_window = max(0, window_days)

    charges: list[tuple[int, BulkItem, date]] = []
    credits: list[tuple[int, BulkItem, date]] = []

    for idx, item in enumerate(items):
        try:
            d = _parse_date(item.date)
        except ValueError:
            continue
        if item.amount < 0:
            charges.append((idx, item, d))
        elif item.amount > 0:
            credits.append((idx, item, d))

    matched_charge_indices: set[int] = set()
    matched_credit_indices: set[int] = set()

    for c_idx, credit, c_date in credits:
        candidates: list[tuple[int, date]] = []
        for ch_idx, charge, ch_date in charges:
            if ch_idx in matched_charge_indices:
                continue
            if abs(credit.amount) != abs(charge.amount):
                continue
            if not _names_match(charge.name, credit.name):
                continue
            delta = abs((c_date - ch_date).days)
            if delta > effective_window:
                continue
            candidates.append((ch_idx, ch_date))

        if not candidates:
            continue

        best_ch_idx = min(candidates, key=lambda t: abs((c_date - t[1]).days))[0]
        matched_charge_indices.add(best_ch_idx)
        matched_credit_indices.add(c_idx)

    return frozenset(matched_credit_indices)
