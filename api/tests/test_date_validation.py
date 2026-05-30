"""Real calendar-date validation across every input seam.

Quid stores dates as ``YYYY-MM-DD`` text. Inputs are validated with
``date.fromisoformat`` (via ``quid_api.datelib``) so pattern-valid-but-impossible
dates (``2026-13-40``, ``2025-02-29``) are rejected rather than silently stored.

These tests cover the shared helper directly plus each API seam that accepts a
date: expense create/update, bulk add, CSV import, import rules, and the
testing seed-state router.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from quid_api.datelib import normalize_iso_date, validate_iso_date

if TYPE_CHECKING:
    from httpx import AsyncClient


# --- Unit: the shared helper -------------------------------------------------

VALID_DATES = [
    "2026-04-22",
    "2024-02-29",  # leap year (2024 divisible by 4, not 100)
    "2000-02-29",  # leap year (divisible by 400)
    "2026-01-01",
    "2026-12-31",
]

IMPOSSIBLE_DATES = [
    "2025-02-29",  # 2025 is not a leap year
    "2100-02-29",  # divisible by 100 but not 400 -> not a leap year
    "2026-13-01",  # month 13
    "2026-00-10",  # month 0
    "2026-04-31",  # April has 30 days
    "2026-06-31",  # June has 30 days
    "2026-11-31",  # November has 30 days
    "2026-04-00",  # day 0
]

BAD_SHAPES = [
    "22/05/2026",
    "2026-4-2",  # not zero-padded
    "20260402",  # basic ISO form, not our contract
    "2026-W01-1",  # ISO week date
    "2026-04-22T00:00:00",  # has time
    "not-a-date",
    "",
    "   ",
]


@pytest.mark.parametrize("value", VALID_DATES)
def test_validate_iso_date_accepts_valid(value: str) -> None:
    assert validate_iso_date(value) == value.strip()


def test_validate_iso_date_strips_surrounding_whitespace() -> None:
    assert validate_iso_date("  2026-04-22  ") == "2026-04-22"


@pytest.mark.parametrize("value", IMPOSSIBLE_DATES)
def test_validate_iso_date_rejects_impossible(value: str) -> None:
    with pytest.raises(ValueError, match="valid YYYY-MM-DD calendar date"):
        validate_iso_date(value)


@pytest.mark.parametrize("value", BAD_SHAPES)
def test_validate_iso_date_rejects_bad_shape(value: str) -> None:
    with pytest.raises(ValueError, match="valid YYYY-MM-DD calendar date"):
        validate_iso_date(value)


@pytest.mark.parametrize("value", IMPOSSIBLE_DATES + BAD_SHAPES)
def test_normalize_iso_date_returns_none_for_bad(value: str) -> None:
    assert normalize_iso_date(value) is None


@pytest.mark.parametrize("value", VALID_DATES)
def test_normalize_iso_date_returns_valid(value: str) -> None:
    assert normalize_iso_date(value) == value.strip()


# --- API seam: expense create/update ----------------------------------------


async def _make_cat(client: AsyncClient, name: str = "Food") -> dict[str, Any]:
    res = await client.post("/api/v1/categories", json={"name": name})
    return res.json()  # type: ignore[no-any-return]


async def test_expense_create_accepts_leap_day(app_client) -> None:
    cat = await _make_cat(app_client)
    res = await app_client.post(
        "/api/v1/expenses",
        json={"name": "Coffee", "amount": "4.50", "date": "2024-02-29", "categoryId": cat["id"]},
    )
    assert res.status_code == 201, res.text
    assert res.json()["date"] == "2024-02-29"


@pytest.mark.parametrize("bad", ["2025-02-29", "2026-13-01", "2026-04-31", "2026-00-10"])
async def test_expense_create_rejects_impossible_date(app_client, bad: str) -> None:
    cat = await _make_cat(app_client)
    res = await app_client.post(
        "/api/v1/expenses",
        json={"name": "Bad", "amount": "5", "date": bad, "categoryId": cat["id"]},
    )
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "VALIDATION"


async def test_expense_update_rejects_impossible_date(app_client) -> None:
    cat = await _make_cat(app_client)
    created = await app_client.post(
        "/api/v1/expenses",
        json={"name": "Coffee", "amount": "4.50", "date": "2026-05-22", "categoryId": cat["id"]},
    )
    eid = created.json()["id"]
    res = await app_client.patch(f"/api/v1/expenses/{eid}", json={"date": "2026-02-30"})
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "VALIDATION"


async def test_expense_update_accepts_valid_date(app_client) -> None:
    cat = await _make_cat(app_client)
    created = await app_client.post(
        "/api/v1/expenses",
        json={"name": "Coffee", "amount": "4.50", "date": "2026-05-22", "categoryId": cat["id"]},
    )
    eid = created.json()["id"]
    res = await app_client.patch(f"/api/v1/expenses/{eid}", json={"date": "2024-02-29"})
    assert res.status_code == 200, res.text
    assert res.json()["date"] == "2024-02-29"


# --- API seam: bulk add ------------------------------------------------------


async def test_bulk_add_rejects_impossible_date(app_client) -> None:
    res = await app_client.post(
        "/api/v1/expenses/bulk",
        json={
            "items": [
                {"name": "Coffee", "category": "eating_out", "amount": -3.50, "date": "2026-13-40"}
            ]
        },
    )
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "VALIDATION"


async def test_bulk_add_accepts_leap_day(app_client) -> None:
    res = await app_client.post(
        "/api/v1/expenses/bulk",
        json={
            "items": [
                {"name": "Coffee", "category": "eating_out", "amount": -3.50, "date": "2024-02-29"}
            ]
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["expenses"][0]["date"] == "2024-02-29"


# --- API seam: CSV import ----------------------------------------------------


def _upload(name: str, body: str) -> tuple[str, tuple[str, bytes, str]]:
    return ("files", (name, body.encode("utf-8"), "text/csv"))


async def test_csv_import_accepts_leap_day(app_client) -> None:
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    csv = "name,category,amount,date,note\nPret,eating_out,-3.50,2024-02-29,\n"
    res = await app_client.post("/api/v1/expenses/import-csv", files=[_upload("leap.csv", csv)])
    assert res.status_code == 201, res.text
    assert res.json()["imported"] == 1
    assert res.json()["expenses"][0]["date"] == "2024-02-29"


async def test_csv_import_rejects_impossible_calendar_date(app_client) -> None:
    """A shaped-but-impossible date (passes the old regex) now fails the import
    with a 422, instead of being stored as an unmatchable bad date."""
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    csv = "name,category,amount,date,note\nPret,eating_out,-3.50,2025-02-29,\n"
    res = await app_client.post("/api/v1/expenses/import-csv", files=[_upload("bad.csv", csv)])
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "VALIDATION"


async def test_csv_import_preview_rejects_impossible_date(app_client) -> None:
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": False})
    csv = "name,category,amount,date,note\nPret,eating_out,-3.50,2026-04-31,\n"
    res = await app_client.post(
        "/api/v1/expenses/import-csv/preview", files=[_upload("bad.csv", csv)]
    )
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "VALIDATION"


# --- API seam: import rules --------------------------------------------------


async def test_rule_create_rejects_impossible_match_date(app_client) -> None:
    res = await app_client.post(
        "/api/v1/import-rules",
        json={"name": "Bad", "action": "exclude", "matchDateFrom": "2026-02-30"},
    )
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "VALIDATION"


async def test_rule_create_accepts_leap_day_match_date(app_client) -> None:
    res = await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Window",
            "action": "exclude",
            "matchDateFrom": "2024-02-29",
            "matchDateTo": "2024-03-01",
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["matchDateFrom"] == "2024-02-29"


async def test_rule_preview_rejects_impossible_match_date(app_client) -> None:
    res = await app_client.post(
        "/api/v1/import-rules/preview",
        json={"matchDateFrom": "2026-13-01"},
    )
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "VALIDATION"


# --- API seam: testing seed-state -------------------------------------------


async def test_seed_state_rejects_impossible_expense_date(app_client) -> None:
    res = await app_client.post(
        "/api/v1/testing/seed-state",
        json={
            "categories": [],
            "expenses": [
                {
                    "id": "exp-1",
                    "name": "Bad",
                    "amount": "5",
                    "date": "2026-02-30",
                    "categoryId": "uncategorized",
                }
            ],
        },
    )
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "VALIDATION"
