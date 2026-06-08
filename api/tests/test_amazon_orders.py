from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any

import pytest

from quid_api.ai_categorization import CategorizedBulkItems
from quid_api.amazon_csv_import import AmazonCsvFile, parse_amazon_csv
from quid_api.models import AmazonOrder
from quid_api.repositories.amazon_orders import AmazonOrderRepository, ParsedOrderInput
from quid_api.routers.amazon_orders import _ingest_orders
from quid_api.settings import get_settings, reset_settings

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_export_fixture() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (_FIXTURES_DIR / "amazon_export_sample.json").read_text(encoding="utf-8")
    )
    return data


async def _disable_ai(app_client) -> None:
    """Disable both AI features so ingest never calls OpenRouter — deterministic
    and network-free regardless of any QUID_OPENROUTER_API_KEY in the env/.env."""
    res = await app_client.patch(
        "/api/v1/settings",
        json={"aiShortNamesEnabled": False, "aiCategorizeEnabled": False},
    )
    assert res.status_code == 200, res.text


def _upload(name: str, body: str) -> tuple[str, tuple[str, bytes, str]]:
    return ("files", (name, body.encode("utf-8"), "text/csv"))


RETAIL_ORDER_CSV = (
    "Order ID,Order Date,Total Owed,Currency,Product Name,Quantity,Item Subtotal,Order Status,Last 4 Digits\n"
    "111-1234567-1234567,2026-04-20,42.50,GBP,USB-C Cable,2,12.50,Closed,1234\n"
    "111-1234567-1234567,2026-04-20,42.50,GBP,Mechanical Keyboard,1,17.50,Closed,1234\n"
    "222-7654321-7654321,2026-04-25,15.00,GBP,Notebook,1,15.00,Cancelled,1234\n"
    "333-9999999-1111111,2026-05-02,9.99,GBP,Pen Set,3,3.33,Delivered,9876\n"
)

EXPORTER_CSV = (
    "orderId,orderDate,totalAmount,currency,items\n"
    "444-1111111-2222222,2026-04-30,25.00,GBP,Stylus; Phone Stand\n"
    '555-3333333-4444444,2026-05-05,99.99,GBP,"[{""title"":""Headphones"",""quantity"":1,""price"":""99.99""}]"\n'
)

# Mimics Amazon's "Retail.OrderHistory" full export where each row is a single
# item in a shipment and "Total Amount" is per-row (item subtotal + tax). The
# order total must be SUM of these rows, not the first row's value.
RETAIL_ORDER_HISTORY_CSV = (
    "Order ID,Order Date,Total Amount,Currency,Product Name,"
    "Original Quantity,Shipment Item Subtotal,Order Status,"
    "Carrier Name & Tracking Number,Ship Date\n"
    "100-0000001-0000001,2026-04-20,9.99,GBP,Widget A,1,28.32,Closed,TRACK-A,2026-04-21\n"
    "100-0000001-0000001,2026-04-20,24.00,GBP,Widget B,1,28.32,Closed,TRACK-A,2026-04-21\n"
    "200-0000002-0000002,2026-04-22,15.00,GBP,Solo Item,1,12.50,Closed,TRACK-B,2026-04-23\n"
    "300-0000003-0000003,2026-04-25,7.50,GBP,Split A,1,7.50,Closed,TRACK-C,2026-04-26\n"
    "300-0000003-0000003,2026-04-25,12.30,GBP,Split B,1,12.30,Closed,TRACK-D,2026-04-27\n"
)


def test_parse_retail_history_groups_items_by_order():
    parsed = parse_amazon_csv(
        AmazonCsvFile(filename="retail.csv", content=RETAIL_ORDER_CSV.encode())
    )
    assert {order.order_id for order in parsed.orders} == {
        "111-1234567-1234567",
        "333-9999999-1111111",
    }
    grouped = next(o for o in parsed.orders if o.order_id == "111-1234567-1234567")
    titles = [item.title for item in grouped.items]
    assert "USB-C Cable" in titles
    assert "Mechanical Keyboard" in titles
    assert grouped.total == Decimal("42.50")
    assert grouped.payment_last4 == "1234"
    assert parsed.skipped_rows == 1


def test_parse_retail_history_sums_per_row_total_amount():
    """Real Amazon export uses per-row 'Total Amount' (a per-item charge).

    The parser must SUM per-row charges within an order to get the order
    total — historical bug took only the first row, breaking every
    multi-item order.
    """
    parsed = parse_amazon_csv(
        AmazonCsvFile(filename="full.csv", content=RETAIL_ORDER_HISTORY_CSV.encode())
    )
    multi = next(o for o in parsed.orders if o.order_id == "100-0000001-0000001")
    assert multi.total == Decimal("33.99")  # 9.99 + 24.00
    solo = next(o for o in parsed.orders if o.order_id == "200-0000002-0000002")
    assert solo.total == Decimal("15.00")


def test_parse_retail_history_groups_into_shipments():
    """Rows with the same tracking number form one shipment; distinct
    tracking IDs split into separate shipments."""
    parsed = parse_amazon_csv(
        AmazonCsvFile(filename="full.csv", content=RETAIL_ORDER_HISTORY_CSV.encode())
    )
    multi = next(o for o in parsed.orders if o.order_id == "100-0000001-0000001")
    assert len(multi.shipments) == 1
    assert multi.shipments[0].tracking == "TRACK-A"
    assert multi.shipments[0].ship_date == "2026-04-21"
    assert multi.shipments[0].total == Decimal("33.99")
    assert {item.title for item in multi.shipments[0].items} == {
        "Widget A",
        "Widget B",
    }

    split = next(o for o in parsed.orders if o.order_id == "300-0000003-0000003")
    assert len(split.shipments) == 2
    totals = sorted(s.total for s in split.shipments)
    assert totals == [Decimal("7.50"), Decimal("12.30")]
    assert split.total == Decimal("19.80")


def test_parse_legacy_per_order_total_keeps_single_shipment():
    """Legacy formats with 'Total Owed' (per-order) repeat the same total on
    every row. One shipment per order is the only sensible split, and its
    total must equal the order total."""
    parsed = parse_amazon_csv(
        AmazonCsvFile(filename="retail.csv", content=RETAIL_ORDER_CSV.encode())
    )
    grouped = next(o for o in parsed.orders if o.order_id == "111-1234567-1234567")
    assert len(grouped.shipments) == 1
    assert grouped.shipments[0].total == Decimal("42.50")


def test_parse_exporter_csv_accepts_json_and_delimited_items():
    parsed = parse_amazon_csv(AmazonCsvFile(filename="exporter.csv", content=EXPORTER_CSV.encode()))
    assert len(parsed.orders) == 2
    delim = next(o for o in parsed.orders if o.order_id == "444-1111111-2222222")
    assert [i.title for i in delim.items] == ["Stylus", "Phone Stand"]
    json_order = next(o for o in parsed.orders if o.order_id == "555-3333333-4444444")
    assert len(json_order.items) == 1
    assert json_order.items[0].title == "Headphones"
    assert json_order.items[0].price == Decimal("99.99")


def test_parse_missing_required_columns_raises():
    from quid_api.errors import RepositoryError

    bad = "Order ID,Product Name\nABC,Widget\n"
    with pytest.raises(RepositoryError, match="required column"):
        parse_amazon_csv(AmazonCsvFile(filename="bad.csv", content=bad.encode()))


async def test_import_creates_orders_and_lists_them(app_client):
    res = await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["created"] == 2
    assert body["updated"] == 0
    assert body["files"][0]["ordersParsed"] == 2

    listed = await app_client.get("/api/v1/amazon-orders")
    assert listed.status_code == 200
    rows = listed.json()
    assert {row["id"] for row in rows} == {
        "111-1234567-1234567",
        "333-9999999-1111111",
    }
    keyboard_order = next(row for row in rows if row["id"] == "111-1234567-1234567")
    titles = [item["title"] for item in keyboard_order["items"]]
    assert "USB-C Cable" in titles


async def test_ingest_orders_counts_created_updated_and_auto_matched(
    app_client, session, monkeypatch
):
    monkeypatch.setenv("QUID_OPENROUTER_API_KEY", "")
    reset_settings()
    await app_client.patch(
        "/api/v1/settings", json={"aiShortNamesEnabled": False, "aiCategorizeEnabled": False}
    )
    expense = await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "Amazon Mktp",
            "amount": 42.50,
            "date": "2026-04-22",
            "categoryId": "uncategorized",
        },
    )
    assert expense.status_code == 201, expense.text

    parsed_orders = [
        ParsedOrderInput(
            order_id="111-1234567-1234567",
            order_date="2026-04-20",
            total=Decimal("42.50"),
            currency="GBP",
            items=[{"title": "USB-C Cable", "quantity": 2, "price": Decimal("12.50")}],
            shipments=[],
            payment_last4="1234",
            order_url=None,
        ),
        ParsedOrderInput(
            order_id="222-7654321-7654321",
            order_date="2026-04-25",
            total=Decimal("15.00"),
            currency="GBP",
            items=[{"title": "Notebook", "quantity": 1, "price": Decimal("15.00")}],
            shipments=[],
            payment_last4="1234",
            order_url=None,
        ),
    ]

    result = await _ingest_orders(session, parsed_orders, source="test")
    assert result.created == 2
    assert result.updated == 0
    assert result.auto_matched == 1


async def test_combined_match_pass_scales_to_large_unmatched_sets(app_client, session, monkeypatch):
    monkeypatch.setenv("QUID_OPENROUTER_API_KEY", "")
    reset_settings()
    await app_client.patch(
        "/api/v1/settings", json={"aiShortNamesEnabled": False, "aiCategorizeEnabled": False}
    )
    await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "Amazon Mktp",
            "amount": 6.00,
            "date": "2030-01-01",
            "categoryId": "uncategorized",
        },
    )

    parsed_orders = [
        ParsedOrderInput(
            order_id=f"{i:03d}-1111111-1111111",
            order_date=(date(2026, 1, 1) + timedelta(days=i)).isoformat(),
            total=Decimal("2.00"),
            currency="GBP",
            items=[{"title": f"Item {i}", "quantity": 1, "price": Decimal("2.00")}],
            shipments=[],
            payment_last4=None,
            order_url=None,
        )
        for i in range(1000)
    ]

    start = perf_counter()
    result = await _ingest_orders(session, parsed_orders, source="test")
    elapsed = perf_counter() - start
    assert result.auto_matched == 0
    assert elapsed < 2.0


async def test_combined_match_pass_scales_to_dense_same_date_cluster(
    app_client, session, monkeypatch
):
    """Worst case for the date-windowed combined pass: many UNMATCHED orders all
    on the SAME date (so every order's window contains every other). The bound
    anchors each combo at its earliest member so it's generated exactly once;
    without that anchor constraint overlapping windows regress to O(n**4) and
    this would hang. 300 same-date orders must still finish quickly."""
    monkeypatch.setenv("QUID_OPENROUTER_API_KEY", "")
    reset_settings()
    await app_client.patch(
        "/api/v1/settings", json={"aiShortNamesEnabled": False, "aiCategorizeEnabled": False}
    )
    # No Amazon-merchant expense → nothing matches → all 300 stay unmatched and
    # flow into the combined pass together.
    parsed_orders = [
        ParsedOrderInput(
            order_id=f"{i:03d}-2222222-2222222",
            order_date="2026-03-15",
            total=Decimal("3.00"),
            currency="GBP",
            items=[{"title": f"Dense {i}", "quantity": 1, "price": Decimal("3.00")}],
            shipments=[],
            payment_last4=None,
            order_url=None,
        )
        for i in range(300)
    ]

    start = perf_counter()
    result = await _ingest_orders(session, parsed_orders, source="test")
    elapsed = perf_counter() - start
    assert result.auto_matched == 0
    assert elapsed < 3.0


def _make_order(order_id: str, order_date: str, total: str) -> AmazonOrder:
    """Build a bare AmazonOrder for direct (DB-free) _generate_combos tests."""
    return AmazonOrder(
        id=order_id,
        order_date=order_date,
        total=Decimal(total),
        currency="GBP",
        items_json="[]",
        shipments_json="[]",
        imported_at="2026-01-01T00:00:00Z",
    )


def _combo_repo() -> AmazonOrderRepository:
    """A repository instance with no session — _generate_combos is pure and
    never touches the DB, so this is safe and keeps the perf tests fast."""
    return AmazonOrderRepository.__new__(AmazonOrderRepository)


@contextmanager
def _capture_combo_logs(monkeypatch):
    """Capture the combined-pass cap warnings deterministically.

    We swap the module-level ``logger`` for a tiny recorder rather than using
    ``caplog``. pytest's logging plugin manipulates the global
    ``logging.disable`` level / per-logger cache across tests, which made
    record-based capture flaky here (a stale ``isEnabledFor`` cache swallowed
    the WARNING). Replacing the logger object sidesteps the logging machinery
    entirely, so the assertion only depends on our code calling
    ``logger.warning(...)``."""
    messages: list[str] = []

    class _Recorder:
        def warning(self, msg: str, *args: object) -> None:
            messages.append(msg % args if args else msg)

        def info(self, *args: object, **kwargs: object) -> None:
            pass

        def debug(self, *args: object, **kwargs: object) -> None:
            pass

    monkeypatch.setattr("quid_api.repositories.amazon_orders.logger", _Recorder(), raising=True)
    yield messages


def test_generate_combos_dense_window_is_capped_and_logged(monkeypatch):
    """A single date window stuffed with thousands of unmatched orders must NOT
    enumerate global combinations. The per-window cap skips the pathological
    cluster wholesale (and logs it) so the pass stays bounded regardless of how
    dense the cluster is. Without the cap, 5000 same-date orders would generate
    ~2x10^10 size-3 combos and hang; with it, generation is near-instant."""
    reset_settings()
    settings = get_settings()
    monkeypatch.setattr(settings, "amazon_combined_max_window_orders", 60)

    repo = _combo_repo()
    orders = [_make_order(f"{i:05d}-9-9", "2026-06-01", "3.00") for i in range(5000)]
    parsed = {o.id: date(2026, 6, 1) for o in orders}

    with _capture_combo_logs(monkeypatch) as messages:
        start = perf_counter()
        combos = repo._generate_combos(orders, parsed)
        elapsed = perf_counter() - start

    # Every window past the first ~60 anchors exceeds the cap and is skipped,
    # so the combo count is bounded by the cap, not by the 5000 input size.
    assert elapsed < 1.0
    assert len(combos) < 100_000
    assert any("amazon.combined.window_capped" in m for m in messages), messages


def test_generate_combos_global_combination_cap_engages_and_logs(monkeypatch):
    """When many distinct date windows together produce more combos than the
    global ceiling, generation stops AT the ceiling (and logs) rather than
    running unbounded."""
    reset_settings()
    settings = get_settings()
    # Tiny global ceiling + a window cap above per-window size so windows aren't
    # skipped — only the global combination cap should engage.
    monkeypatch.setattr(settings, "amazon_combined_max_combinations", 100)
    monkeypatch.setattr(settings, "amazon_combined_max_window_orders", 10_000)

    repo = _combo_repo()
    # 1000 orders, two per day: each anchor window holds a handful of followers.
    orders = []
    parsed = {}
    for i in range(1000):
        day = date(2026, 1, 1) + timedelta(days=i // 2)
        oid = f"{i:05d}-8-8"
        orders.append(_make_order(oid, day.isoformat(), "4.00"))
        parsed[oid] = day
    orders.sort(key=lambda o: (parsed[o.id], o.id))

    with _capture_combo_logs(monkeypatch) as messages:
        combos = repo._generate_combos(orders, parsed)

    # Generation halts exactly at the ceiling, never running unbounded.
    assert len(combos) == 100
    assert any("amazon.combined.combination_capped" in m for m in messages), messages


async def test_combined_pass_dense_window_ingest_is_bounded(app_client, session, monkeypatch):
    """End-to-end: ingesting hundreds of unmatched same-date orders (the worst
    case for the combined pass) stays fast because the per-window cap prevents
    the combinatorial explosion. A candidate expense forces the pass to actually
    enter combo generation."""
    monkeypatch.setenv("QUID_OPENROUTER_API_KEY", "")
    reset_settings()
    await app_client.patch(
        "/api/v1/settings", json={"aiShortNamesEnabled": False, "aiCategorizeEnabled": False}
    )
    # £7.50 is not a multiple of £3, so no order/combo ever sums to it → nothing
    # links, but the candidate still drives the pass into combo generation.
    await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "Amazon Mktp",
            "amount": 7.50,
            "date": "2026-06-02",
            "categoryId": "uncategorized",
        },
    )
    parsed_orders = [
        ParsedOrderInput(
            order_id=f"{i:05d}-9999999-9999999",
            order_date="2026-06-01",
            total=Decimal("3.00"),
            currency="GBP",
            items=[{"title": f"Bulk {i}", "quantity": 1, "price": Decimal("3.00")}],
            shipments=[],
            payment_last4=None,
            order_url=None,
        )
        for i in range(800)
    ]

    start = perf_counter()
    result = await _ingest_orders(session, parsed_orders, source="test")
    elapsed = perf_counter() - start

    assert result.auto_matched == 0
    assert elapsed < 5.0


async def test_combined_pass_still_matches_small_cluster_in_large_history(
    app_client, session, monkeypatch
):
    """Behaviour preservation: a genuine 2-order combined charge embedded in a
    large, sparse history must still auto-match. The caps only suppress
    pathological dense windows — ordinary small clusters are untouched."""
    monkeypatch.setenv("QUID_OPENROUTER_API_KEY", "")
    reset_settings()
    await app_client.patch(
        "/api/v1/settings", json={"aiShortNamesEnabled": False, "aiCategorizeEnabled": False}
    )
    # One real combined charge: two orders on 2026-07-10 summing to £40.
    await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "Amazon Mktp",
            "amount": 40.00,
            "date": "2026-07-11",
            "categoryId": "uncategorized",
        },
    )

    parsed_orders = [
        ParsedOrderInput(
            order_id="AAA-7777777-7777777",
            order_date="2026-07-10",
            total=Decimal("18.00"),
            currency="GBP",
            items=[{"title": "Combo A", "quantity": 1, "price": Decimal("18.00")}],
            shipments=[],
            payment_last4=None,
            order_url=None,
        ),
        ParsedOrderInput(
            order_id="BBB-7777777-7777777",
            order_date="2026-07-10",
            total=Decimal("22.00"),
            currency="GBP",
            items=[{"title": "Combo B", "quantity": 1, "price": Decimal("22.00")}],
            shipments=[],
            payment_last4=None,
            order_url=None,
        ),
    ]
    # Surround the real cluster with hundreds of unrelated sparse orders that
    # never sum to a real charge (one per distant day, no matching expense).
    for i in range(800):
        day = date(2027, 1, 1) + timedelta(days=i)
        parsed_orders.append(
            ParsedOrderInput(
                order_id=f"{i:05d}-6666666-6666666",
                order_date=day.isoformat(),
                total=Decimal("7.00"),
                currency="GBP",
                items=[{"title": f"Lonely {i}", "quantity": 1, "price": Decimal("7.00")}],
                shipments=[],
                payment_last4=None,
                order_url=None,
            )
        )

    start = perf_counter()
    result = await _ingest_orders(session, parsed_orders, source="test")
    elapsed = perf_counter() - start

    assert result.combined_matched == 2
    assert elapsed < 3.0

    listed = await app_client.get("/api/v1/amazon-orders")
    rows = {row["id"]: row for row in listed.json()}
    assert (
        rows["AAA-7777777-7777777"]["linkedExpenseIds"]
        == rows["BBB-7777777-7777777"]["linkedExpenseIds"]
    )
    assert len(rows["AAA-7777777-7777777"]["linkedExpenseIds"]) == 1


async def test_import_generates_short_name_fallback(app_client, monkeypatch):
    monkeypatch.setenv("QUID_OPENROUTER_API_KEY", "")
    reset_settings()
    res = await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    assert res.status_code == 201, res.text

    listed = await app_client.get("/api/v1/amazon-orders")
    assert listed.status_code == 200
    rows = listed.json()
    assert all(row["shortName"] for row in rows)

    multi_item = next(row for row in rows if row["id"] == "111-1234567-1234567")
    assert multi_item["shortName"] == "USB-C Cable + 1 more"

    single_item = next(row for row in rows if row["id"] == "333-9999999-1111111")
    assert single_item["shortName"] == "Pen Set"


async def test_short_names_skipped_when_ai_disabled(app_client):
    await app_client.patch("/api/v1/settings", json={"aiShortNamesEnabled": False})
    res = await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    assert res.status_code == 201, res.text

    listed = await app_client.get("/api/v1/amazon-orders")
    assert listed.status_code == 200
    rows = listed.json()
    assert all(row["shortName"] is None for row in rows)


async def test_short_names_generated_when_ai_enabled(app_client):
    await app_client.patch("/api/v1/settings", json={"aiShortNamesEnabled": True})
    res = await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    assert res.status_code == 201, res.text

    listed = await app_client.get("/api/v1/amazon-orders")
    assert listed.status_code == 200
    rows = listed.json()
    assert all(row["shortName"] for row in rows)
    single_item = next(row for row in rows if row["id"] == "333-9999999-1111111")
    assert single_item["shortName"] == "Pen Set"


async def test_update_short_name_endpoint(app_client):
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    res = await app_client.patch(
        "/api/v1/amazon-orders/333-9999999-1111111/short-name",
        json={"shortName": "Box of pens"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["shortName"] == "Box of pens"

    fetched = await app_client.get("/api/v1/amazon-orders/333-9999999-1111111")
    assert fetched.status_code == 200
    assert fetched.json()["shortName"] == "Box of pens"


async def test_update_category_endpoint_sets_and_clears(app_client):
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    travel = (await app_client.post("/api/v1/categories", json={"name": "Travel"})).json()

    res = await app_client.patch(
        "/api/v1/amazon-orders/333-9999999-1111111/category",
        json={"categoryId": travel["id"]},
    )
    assert res.status_code == 200, res.text
    assert res.json()["categoryId"] == travel["id"]

    fetched = await app_client.get("/api/v1/amazon-orders/333-9999999-1111111")
    assert fetched.json()["categoryId"] == travel["id"]

    cleared = await app_client.patch(
        "/api/v1/amazon-orders/333-9999999-1111111/category",
        json={"categoryId": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["categoryId"] is None


async def test_update_category_rejects_unknown_category(app_client):
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    res = await app_client.patch(
        "/api/v1/amazon-orders/333-9999999-1111111/category",
        json={"categoryId": "cat-does-not-exist"},
    )
    assert res.status_code == 422, res.text


async def test_update_category_propagates_to_linked_overridable_expense(app_client):
    """Manually setting an order's category pushes it onto a linked expense
    whose category is still a low-priority guess (uncategorized/import)."""
    expense_id = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=9.99, date="2026-05-03"
    )
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    # Order 333 (9.99, 2026-05-02) auto-matches the seeded expense.
    order = await app_client.get("/api/v1/amazon-orders/333-9999999-1111111")
    assert order.json()["linkedExpenseIds"] == [expense_id]

    travel = (await app_client.post("/api/v1/categories", json={"name": "Travel"})).json()
    await app_client.patch(
        "/api/v1/amazon-orders/333-9999999-1111111/category",
        json={"categoryId": travel["id"]},
    )

    expenses = (await app_client.get("/api/v1/expenses")).json()
    exp = next(e for e in expenses if e["id"] == expense_id)
    assert exp["categoryId"] == travel["id"]
    assert exp["categorySource"] == "amazon"


async def test_update_category_does_not_override_manual_linked_expense(app_client):
    expense = await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "Amazon Mktp",
            "amount": 9.99,
            "date": "2026-05-03",
            "categoryId": "uncategorized",
        },
    )
    expense_id = expense.json()["id"]
    health = (await app_client.post("/api/v1/categories", json={"name": "Health"})).json()
    await app_client.patch(f"/api/v1/expenses/{expense_id}", json={"categoryId": health["id"]})

    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    await app_client.post(
        "/api/v1/amazon-orders/333-9999999-1111111/link",
        json={"expenseId": expense_id},
    )
    travel = (await app_client.post("/api/v1/categories", json={"name": "Travel"})).json()
    await app_client.patch(
        "/api/v1/amazon-orders/333-9999999-1111111/category",
        json={"categoryId": travel["id"]},
    )

    expenses = (await app_client.get("/api/v1/expenses")).json()
    exp = next(e for e in expenses if e["id"] == expense_id)
    assert exp["categoryId"] == health["id"]
    assert exp["categorySource"] == "manual"


async def test_reimport_preserves_edited_short_name(app_client):
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    await app_client.patch(
        "/api/v1/amazon-orders/333-9999999-1111111/short-name",
        json={"shortName": "Custom name"},
    )
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )

    fetched = await app_client.get("/api/v1/amazon-orders/333-9999999-1111111")
    assert fetched.status_code == 200
    assert fetched.json()["shortName"] == "Custom name"


async def test_update_short_name_rejects_too_long(app_client):
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    res = await app_client.patch(
        "/api/v1/amazon-orders/333-9999999-1111111/short-name",
        json={"shortName": "x" * 61},
    )
    assert res.status_code == 422


async def test_import_is_idempotent_on_reupload(app_client):
    first = await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    assert first.json()["created"] == 2
    again = await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    assert again.status_code == 201
    body = again.json()
    assert body["created"] == 0
    assert body["updated"] == 2


async def _seed_categories_and_expense(app_client, *, name: str, amount: float, date: str) -> str:
    res = await app_client.post(
        "/api/v1/expenses",
        json={
            "name": name,
            "amount": amount,
            "date": date,
            "categoryId": "uncategorized",
        },
    )
    assert res.status_code == 201, res.text
    expense_id: str = res.json()["id"]
    return expense_id


async def test_auto_match_links_single_candidate(app_client):
    await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=42.50, date="2026-04-22"
    )
    res = await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    body = res.json()
    assert body["autoMatched"] == 1
    assert body["ambiguous"] == 1

    listed = await app_client.get("/api/v1/amazon-orders")
    keyboard = next(row for row in listed.json() if row["id"] == "111-1234567-1234567")
    assert len(keyboard["linkedExpenseIds"]) == 1


async def test_auto_match_links_expense_with_timestamp_date(app_client):
    # Regression: expenses may store a full ``YYYY-MM-DDTHH:MM:SS`` timestamp
    # (not just a bare date). Matching must parse the day prefix and still link
    # rather than silently skipping every timestamped expense.
    await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=42.50, date="2026-04-22T14:30:00"
    )
    res = await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    assert res.json()["autoMatched"] == 1

    listed = await app_client.get("/api/v1/amazon-orders")
    keyboard = next(row for row in listed.json() if row["id"] == "111-1234567-1234567")
    assert len(keyboard["linkedExpenseIds"]) == 1


async def test_auto_match_ambiguous_when_multiple_candidates(app_client):
    await _seed_categories_and_expense(
        app_client, name="Amazon Mktp A", amount=42.50, date="2026-04-21"
    )
    await _seed_categories_and_expense(
        app_client, name="Amazon Mktp B", amount=42.50, date="2026-04-23"
    )
    res = await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    assert res.json()["autoMatched"] == 0
    assert res.json()["ambiguous"] == 2

    listed = await app_client.get("/api/v1/amazon-orders")
    for row in listed.json():
        assert row["linkedExpenseIds"] == []


async def test_suggested_matches_filters_by_window_and_amount(app_client):
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    matching = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=42.50, date="2026-04-25"
    )
    out_of_window = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=42.50, date="2026-05-15"
    )
    wrong_amount = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=99.00, date="2026-04-21"
    )
    suggested = await app_client.get("/api/v1/amazon-orders/111-1234567-1234567/suggested-matches")
    assert suggested.status_code == 200
    ids = [row["id"] for row in suggested.json()]
    assert matching in ids
    assert out_of_window not in ids
    assert wrong_amount not in ids
    assert len(ids) == 1


async def test_auto_match_ignores_non_amazon_merchant_expense(app_client):
    tesco = await _seed_categories_and_expense(
        app_client, name="Tesco", amount=42.50, date="2026-04-22"
    )
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )

    listed = await app_client.get("/api/v1/amazon-orders")
    order = next(row for row in listed.json() if row["id"] == "111-1234567-1234567")
    assert order["linkedExpenseIds"] == []

    amazon = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=42.50, date="2026-04-22"
    )
    rerun = await app_client.post("/api/v1/amazon-orders/match-all")
    assert rerun.status_code == 200

    listed = await app_client.get("/api/v1/amazon-orders")
    order = next(row for row in listed.json() if row["id"] == "111-1234567-1234567")
    assert order["linkedExpenseIds"] == [amazon]
    assert tesco not in order["linkedExpenseIds"]


async def test_suggested_matches_excludes_non_amazon(app_client):
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    costa = await _seed_categories_and_expense(
        app_client, name="Costa", amount=42.50, date="2026-04-25"
    )
    amazon = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=42.50, date="2026-04-25"
    )

    suggested = await app_client.get("/api/v1/amazon-orders/111-1234567-1234567/suggested-matches")
    assert suggested.status_code == 200
    ids = [row["id"] for row in suggested.json()]
    assert ids == [amazon]
    assert costa not in ids


async def test_import_ai_categorizes_orders(app_client, monkeypatch):
    async def fake(items, *, existing_categories, ai_rules, api_key, model, **kwargs: object):
        return CategorizedBulkItems(
            items=[replace(i, category="Office Supplies") for i in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.ai_order_categorization.categorize_transactions", fake)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})
    res = await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    assert res.status_code == 201, res.text

    listed = await app_client.get("/api/v1/amazon-orders")
    assert all(row["categoryId"] == "cat-office-supplies" for row in listed.json())


async def test_linked_uncategorized_expense_inherits_order_category(app_client, monkeypatch):
    async def fake(items, *, existing_categories, ai_rules, api_key, model, **kwargs: object):
        return CategorizedBulkItems(
            items=[replace(i, category="Office Supplies") for i in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.ai_order_categorization.categorize_transactions", fake)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})
    expense_id = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=42.50, date="2026-04-22"
    )
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )

    listed = await app_client.get("/api/v1/expenses")
    expense = next(row for row in listed.json() if row["id"] == expense_id)
    assert expense["categoryId"] == "cat-office-supplies"


async def test_link_does_not_overwrite_existing_expense_category(app_client, monkeypatch):
    async def fake(items, *, existing_categories, ai_rules, api_key, model, **kwargs: object):
        return CategorizedBulkItems(
            items=[replace(i, category="Office Supplies") for i in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.ai_order_categorization.categorize_transactions", fake)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})
    real_category = (await app_client.post("/api/v1/categories", json={"name": "Travel"})).json()
    expense = await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "Amazon Mktp",
            "amount": 99.99,
            "date": "2026-05-04",
            "categoryId": "uncategorized",
        },
    )
    assert expense.status_code == 201, expense.text
    expense_id = expense.json()["id"]
    patched = await app_client.patch(
        f"/api/v1/expenses/{expense_id}",
        json={"categoryId": real_category["id"]},
    )
    assert patched.status_code == 200, patched.text

    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("exporter.csv", EXPORTER_CSV)],
    )
    linked = await app_client.post(
        "/api/v1/amazon-orders/555-3333333-4444444/link",
        json={"expenseId": expense_id},
    )
    assert linked.status_code == 200, linked.text

    fetched = await app_client.get("/api/v1/expenses")
    expense_row = next(row for row in fetched.json() if row["id"] == expense_id)
    assert expense_row["categoryId"] == real_category["id"]


async def test_categorizing_order_propagates_to_already_linked_expense(app_client, monkeypatch):
    """A NULL-category order that is already linked (auto-matched at first
    import with AI off) gets categorised on a later AI-enabled import, and
    that category propagates to the already-linked uncategorised expense.
    This is the same propagation path the backfill CLI command exercises."""
    # First import with AI off (no key, default settings) -> NULL category.
    expense_id = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=42.50, date="2026-04-22"
    )
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    # Order 111 auto-matched to the expense while both are uncategorised.
    listed = await app_client.get("/api/v1/amazon-orders")
    order = next(row for row in listed.json() if row["id"] == "111-1234567-1234567")
    assert order["categoryId"] is None
    assert order["linkedExpenseIds"] == [expense_id]
    pre = await app_client.get("/api/v1/expenses")
    assert next(r for r in pre.json() if r["id"] == expense_id)["categoryId"] == "uncategorized"

    # Re-import with AI on + mocked: order 111 still NULL -> gets categorised
    # and propagates to the already-linked uncategorised expense.
    async def fake(items, *, existing_categories, ai_rules, api_key, model, **kwargs: object):
        return CategorizedBulkItems(
            items=[replace(i, category="Office Supplies") for i in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.ai_order_categorization.categorize_transactions", fake)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )

    after_orders = await app_client.get("/api/v1/amazon-orders")
    after_order = next(row for row in after_orders.json() if row["id"] == "111-1234567-1234567")
    assert after_order["categoryId"] == "cat-office-supplies"
    after_expenses = await app_client.get("/api/v1/expenses")
    after_expense = next(r for r in after_expenses.json() if r["id"] == expense_id)
    assert after_expense["categoryId"] == "cat-office-supplies"


async def test_reimport_does_not_overwrite_existing_order_category(app_client, monkeypatch):
    async def office(items, *, existing_categories, ai_rules, api_key, model, **kwargs: object):
        return CategorizedBulkItems(
            items=[replace(i, category="Office Supplies") for i in items],
            categorized=len(items),
        )

    async def groceries(items, *, existing_categories, ai_rules, api_key, model, **kwargs: object):
        return CategorizedBulkItems(
            items=[replace(i, category="Groceries") for i in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.ai_order_categorization.categorize_transactions", office)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )

    monkeypatch.setattr("quid_api.ai_order_categorization.categorize_transactions", groceries)
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )

    listed = await app_client.get("/api/v1/amazon-orders")
    order = next(row for row in listed.json() if row["id"] == "111-1234567-1234567")
    assert order["categoryId"] == "cat-office-supplies"


async def _import_expenses_with_ai(app_client, monkeypatch, csv_body: str, category: str) -> None:
    """Import expenses via CSV with mocked expense-AI assigning `category`."""

    async def fake(items, *, existing_categories, ai_rules, api_key, model, **kwargs: object):
        return CategorizedBulkItems(
            items=[replace(i, category=category) for i in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.routers.expenses.categorize_transactions", fake)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})
    res = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[_upload("monzo.csv", csv_body)],
    )
    assert res.status_code == 201, res.text


async def test_order_category_overrides_ai_shopping_on_expense(app_client, monkeypatch):
    """The core precision fix: an Amazon expense the expense-AI coarsely tagged
    'Shopping' (source 'ai') is overridden by the order's precise category."""
    # Expense imported via CSV + expense-AI -> "Shopping" (source 'ai').
    await _import_expenses_with_ai(
        app_client,
        monkeypatch,
        "name,amount,date\nAmazon Mktp,-42.50,2026-04-22\n",
        "Shopping",
    )
    expenses = (await app_client.get("/api/v1/expenses")).json()
    exp = next(e for e in expenses if e["name"] == "Amazon Mktp")
    assert exp["categoryId"] == "cat-shopping"
    assert exp["categorySource"] == "ai"

    # Order import categorises the order precisely and auto-matches it.
    async def order_fake(items, *, existing_categories, ai_rules, api_key, model, **kwargs: object):
        return CategorizedBulkItems(
            items=[replace(i, category="Office Supplies") for i in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.ai_order_categorization.categorize_transactions", order_fake)
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )

    after = (await app_client.get("/api/v1/expenses")).json()
    exp_after = next(e for e in after if e["name"] == "Amazon Mktp")
    assert exp_after["categoryId"] == "cat-office-supplies"
    assert exp_after["categorySource"] == "amazon"


async def test_order_category_does_not_override_manual_expense(app_client, monkeypatch):
    """A hand-set (manual) expense category is protected from order overrides."""
    expense = await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "Amazon Mktp",
            "amount": 42.50,
            "date": "2026-04-22",
            "categoryId": "uncategorized",
        },
    )
    expense_id = expense.json()["id"]
    travel = (await app_client.post("/api/v1/categories", json={"name": "Travel"})).json()
    await app_client.patch(f"/api/v1/expenses/{expense_id}", json={"categoryId": travel["id"]})

    async def order_fake(items, *, existing_categories, ai_rules, api_key, model, **kwargs: object):
        return CategorizedBulkItems(
            items=[replace(i, category="Office Supplies") for i in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.ai_order_categorization.categorize_transactions", order_fake)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )

    after = (await app_client.get("/api/v1/expenses")).json()
    exp_after = next(e for e in after if e["id"] == expense_id)
    assert exp_after["categoryId"] == travel["id"]
    assert exp_after["categorySource"] == "manual"


async def test_manual_link_and_unlink(app_client):
    expense_id = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=99.99, date="2026-05-04"
    )
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("exporter.csv", EXPORTER_CSV)],
    )
    link = await app_client.post(
        "/api/v1/amazon-orders/555-3333333-4444444/link",
        json={"expenseId": expense_id},
    )
    assert link.status_code == 200, link.text
    assert link.json()["amazonOrderIds"] == ["555-3333333-4444444"]

    unlink = await app_client.post(
        "/api/v1/amazon-orders/555-3333333-4444444/unlink",
        json={"expenseId": expense_id},
    )
    assert unlink.status_code == 200
    assert unlink.json()["amazonOrderIds"] == []


async def test_list_orders_embeds_linked_expense_labels(app_client):
    """The orders list embeds minimal label data for each linked expense so the
    ``/amazon`` page can render "Linked to ..." without fetching every expense.
    Unlinked orders carry an empty ``linkedExpenses`` list."""
    expense_id = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=99.99, date="2026-05-04"
    )
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("exporter.csv", EXPORTER_CSV)],
    )
    await app_client.post(
        "/api/v1/amazon-orders/555-3333333-4444444/link",
        json={"expenseId": expense_id},
    )

    listing = await app_client.get("/api/v1/amazon-orders")
    assert listing.status_code == 200, listing.text
    orders = {o["id"]: o for o in listing.json()}

    linked = orders["555-3333333-4444444"]
    assert linked["linkedExpenseIds"] == [expense_id]
    assert len(linked["linkedExpenses"]) == 1
    label = linked["linkedExpenses"][0]
    assert label["id"] == expense_id
    assert label["name"] == "Amazon Mktp"
    assert label["amount"] == "99.99"
    assert "displayName" in label

    # Every other order in the export is unlinked → empty label list.
    for other in orders.values():
        if other["id"] != "555-3333333-4444444":
            assert other["linkedExpenses"] == []


async def test_expense_resolved_note_falls_back_to_linked_order_short_name(app_client):
    """``resolvedNote`` on the expense list is the expense's own note, else a
    linked Amazon order's short name (resolved server-side so the client need
    not fetch the whole orders table). Covers all three branches."""
    # An expense with NO note of its own, linked to an order whose short name
    # should surface as the resolved note.
    no_note_id = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=99.99, date="2026-05-04"
    )
    # A second expense WITH its own note, also linked — its note must win.
    own_note = await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "Amazon Mktp",
            "amount": 99.99,
            "date": "2026-05-06",
            "categoryId": "uncategorized",
            "note": "My own note",
        },
    )
    assert own_note.status_code == 201, own_note.text
    own_note_id: str = own_note.json()["id"]

    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("exporter.csv", EXPORTER_CSV)],
    )
    # Pin a deterministic short name (independent of AI) on the order.
    named = await app_client.patch(
        "/api/v1/amazon-orders/555-3333333-4444444/short-name",
        json={"shortName": "Wireless headphones"},
    )
    assert named.status_code == 200, named.text

    for expense_id in (no_note_id, own_note_id):
        linked = await app_client.post(
            "/api/v1/amazon-orders/555-3333333-4444444/link",
            json={"expenseId": expense_id},
        )
        assert linked.status_code == 200, linked.text

    listed = await app_client.get("/api/v1/expenses")
    assert listed.status_code == 200, listed.text
    by_id = {row["id"]: row for row in listed.json()}

    # No own note -> falls back to the linked order's short name.
    assert by_id[no_note_id]["resolvedNote"] == "Wireless headphones"
    # Own note -> wins over the linked order's short name.
    assert by_id[own_note_id]["resolvedNote"] == "My own note"


async def test_expense_resolved_note_empty_without_note_or_link(app_client):
    """An expense with no note and no linked order resolves to ""."""
    expense_id = await _seed_categories_and_expense(
        app_client, name="Tesco", amount=12.34, date="2026-05-04"
    )
    listed = await app_client.get("/api/v1/expenses")
    assert listed.status_code == 200, listed.text
    row = next(r for r in listed.json() if r["id"] == expense_id)
    assert row["resolvedNote"] == ""


async def test_one_expense_can_link_to_multiple_orders(app_client):
    """When Amazon bills several orders together, the same expense should
    be linkable to each contributing order."""
    expense_id = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=124.99, date="2026-05-04"
    )
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("exporter.csv", EXPORTER_CSV)],
    )
    first = await app_client.post(
        "/api/v1/amazon-orders/555-3333333-4444444/link",
        json={"expenseId": expense_id},
    )
    second = await app_client.post(
        "/api/v1/amazon-orders/444-1111111-2222222/link",
        json={"expenseId": expense_id},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert sorted(second.json()["amazonOrderIds"]) == [
        "444-1111111-2222222",
        "555-3333333-4444444",
    ]


async def test_get_404_and_delete_round_trip(app_client):
    missing = await app_client.get("/api/v1/amazon-orders/does-not-exist")
    assert missing.status_code == 404

    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    deleted = await app_client.delete("/api/v1/amazon-orders/111-1234567-1234567")
    assert deleted.status_code == 204
    after = await app_client.get("/api/v1/amazon-orders/111-1234567-1234567")
    assert after.status_code == 404


COMBINED_ORDERS_CSV = (
    "Order ID,Order Date,Total Amount,Currency,Product Name,Order Status,"
    "Carrier Name & Tracking Number,Ship Date\n"
    # Two small orders placed the same day that should sum to one bank
    # charge of 30.00 (well above the £25 safeguard threshold).
    "AAA-1111111-1111111,2026-04-20,12.50,GBP,Item A1,Closed,T-A,2026-04-21\n"
    "AAA-1111111-1111111,2026-04-20,5.00,GBP,Item A2,Closed,T-A,2026-04-21\n"
    "BBB-2222222-2222222,2026-04-20,12.50,GBP,Item B1,Closed,T-B,2026-04-21\n"
)


async def test_combined_orders_link_to_shared_expense(app_client):
    """When Amazon bills two orders together, auto-match should link both
    orders to the single expense whose amount equals the combined total."""
    expense_id = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=30.00, date="2026-04-22"
    )
    res = await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("combined.csv", COMBINED_ORDERS_CSV)],
    )
    body = res.json()
    assert body["combinedMatched"] == 2, body

    listed = await app_client.get("/api/v1/amazon-orders")
    rows = {row["id"]: row for row in listed.json()}
    assert rows["AAA-1111111-1111111"]["linkedExpenseIds"] == [expense_id]
    assert rows["BBB-2222222-2222222"]["linkedExpenseIds"] == [expense_id]


async def test_combined_pass_skipped_below_min_threshold(app_client):
    """Tiny combinations are skipped — coincidental sum matches at very
    small amounts are too noisy to auto-link."""
    SMALL_COMBINED = (
        "Order ID,Order Date,Total Amount,Currency,Product Name,Order Status,"
        "Carrier Name & Tracking Number,Ship Date\n"
        "CCC-3333333-3333333,2026-04-20,1.50,GBP,Tiny A,Closed,T-C,2026-04-21\n"
        "DDD-4444444-4444444,2026-04-20,1.50,GBP,Tiny B,Closed,T-D,2026-04-21\n"
    )
    await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=3.00, date="2026-04-22"
    )
    res = await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("small.csv", SMALL_COMBINED)],
    )
    body = res.json()
    assert body["combinedMatched"] == 0
    assert body["ambiguous"] == 2


async def test_auto_match_is_idempotent(app_client):
    """Re-running match-all on already-linked orders must not change links."""
    await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=42.50, date="2026-04-22"
    )
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    first = await app_client.post("/api/v1/amazon-orders/match-all")
    second = await app_client.post("/api/v1/amazon-orders/match-all")
    # No new links on the second pass.
    assert second.json()["autoMatched"] == 0
    assert first.json()["totalOrders"] == second.json()["totalOrders"]


async def test_match_all_endpoint_runs_after_seeding(app_client):
    await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=9.99, date="2026-05-03"
    )
    await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    rerun = await app_client.post("/api/v1/amazon-orders/match-all")
    assert rerun.status_code == 200
    body = rerun.json()
    assert body["autoMatched"] == 0
    assert body["totalOrders"] == 2


async def test_expense_out_includes_amazon_order_id(app_client):
    res = await app_client.get("/api/v1/expenses")
    if res.json():
        first = res.json()[0]
        assert "amazonOrderId" in first


# --- /import-export (browser-scraped JSON) ----------------------------------


async def test_import_export_creates_and_matches_like_csv(app_client):
    """Happy path: a captured export payload upserts orders and auto-matches
    exactly like the CSV path."""
    await _disable_ai(app_client)
    await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=19.99, date="2026-05-05"
    )

    res = await app_client.post("/api/v1/amazon-orders/import-export", json=_load_export_fixture())
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["created"] == 3
    assert body["updated"] == 0
    assert body["autoMatched"] == 1
    report = body["files"][0]
    assert report["filename"] == "amazon.co.uk"
    assert report["ordersParsed"] == 3
    assert report["skippedRows"] == 0
    assert report["skipped"] == []

    listed = {row["id"]: row for row in (await app_client.get("/api/v1/amazon-orders")).json()}
    assert set(listed) == {
        "111-2223334-4445556",
        "222-3334445-5556667",
        "333-4445556-6667778",
    }
    assert len(listed["111-2223334-4445556"]["linkedExpenseIds"]) == 1


async def test_import_export_preserves_exact_decimal_and_matches(app_client, session):
    """B2: a money string "19.99" is stored as exactly Decimal("19.99") and
    auto-matches a 19.99 expense (the match itself proves exact fidelity — a
    float-contaminated total would never equal the expense amount). Also
    covers the synthetic-file-report filename fallback when domain is absent."""
    await _disable_ai(app_client)
    await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=19.99, date="2026-05-05"
    )

    payload = {
        "scraperVersion": "1.0.0",
        "orders": [
            {
                "orderId": "999-0000001-0000001",
                "orderDate": "2026-05-05",
                "total": "19.99",
                "currency": "GBP",
                "status": "Delivered",
                "items": [{"title": "Widget", "quantity": 1, "price": "19.99"}],
            }
        ],
    }
    res = await app_client.post("/api/v1/amazon-orders/import-export", json=payload)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["created"] == 1
    assert body["autoMatched"] == 1
    assert body["files"][0]["filename"] == "Amazon browser export"

    stored = await session.get(AmazonOrder, "999-0000001-0000001")
    assert stored is not None
    assert stored.total == Decimal("19.99")


async def test_import_export_rejects_numeric_money_as_422(app_client):
    """B2 contract: money must be a JSON string. A JSON number is a hard 422
    (Pydantic string_type) so a scraper float-artifact can never silently
    corrupt the amount matcher."""
    payload = {
        "scraperVersion": "1.0.0",
        "domain": "amazon.co.uk",
        "orders": [
            {
                "orderId": "777-0000001-0000001",
                "orderDate": "2026-05-05",
                "total": 19.99,
                "items": [],
            }
        ],
    }
    res = await app_client.post("/api/v1/amazon-orders/import-export", json=payload)
    assert res.status_code == 422, res.text


async def test_import_export_large_history_is_fast(app_client):
    """B1 at the endpoint level: 1,000 unmatched orders import well under ~2s,
    guarding the bounded combined-match pass (a £6 candidate expense ensures
    the combined pass actually runs)."""
    await _disable_ai(app_client)
    await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=6.00, date="2030-01-01"
    )
    orders = [
        {
            "orderId": f"{i:03d}-1111111-2222222",
            "orderDate": (date(2026, 1, 1) + timedelta(days=i)).isoformat(),
            "total": "2.00",
            "currency": "GBP",
            "status": "Delivered",
            "items": [{"title": f"Item {i}", "quantity": 1, "price": "2.00"}],
        }
        for i in range(1000)
    ]
    payload = {"scraperVersion": "1.0.0", "domain": "amazon.co.uk", "orders": orders}

    start = perf_counter()
    res = await app_client.post("/api/v1/amazon-orders/import-export", json=payload)
    elapsed = perf_counter() - start
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["created"] == 1000
    assert body["autoMatched"] == 0
    assert elapsed < 2.0


@pytest.mark.parametrize(
    ("variant", "mutator"),
    [
        (
            "item_price",
            lambda order: order.__setitem__(
                "items", [{"title": "Widget", "quantity": 1, "price": 19.99}]
            ),
        ),
        (
            "shipment_total",
            lambda order: order.__setitem__(
                "shipments",
                [
                    {
                        "total": 19.99,
                        "shipDate": "2026-05-05",
                        "tracking": "T1",
                        "items": [],
                    }
                ],
            ),
        ),
    ],
)
async def test_import_export_rejects_numeric_item_price_and_shipment_total_as_422(
    app_client, variant, mutator
):
    payload = _load_export_fixture()
    order = payload["orders"][0]
    order.update(
        {
            "orderId": "777-0000001-0000001",
            "orderDate": "2026-05-05",
            "total": "19.99",
            "currency": "GBP",
            "status": "Delivered",
            "items": [],
            "shipments": [],
        }
    )
    mutator(order)

    res = await app_client.post("/api/v1/amazon-orders/import-export", json=payload)
    assert res.status_code == 422, (variant, res.text)


async def test_amazon_order_category_does_not_override_rule_sourced_expense(app_client):
    await _disable_ai(app_client)

    rule_category = (await app_client.post("/api/v1/categories", json={"name": "RuleCat"})).json()
    other_category = (await app_client.post("/api/v1/categories", json={"name": "OtherCat"})).json()

    rule_res = await app_client.post(
        "/api/v1/import-rules",
        json={
            "name": "Amazon name rule",
            "action": "categorize",
            "targetCategoryId": rule_category["id"],
            "matchNameOp": "contains",
            "matchNameValue": "amazon",
        },
    )
    assert rule_res.status_code == 201, rule_res.text

    expense_res = await app_client.post(
        "/api/v1/expenses/import-csv",
        files=[
            _upload(
                "rule-expense.csv",
                "name,amount,date\nAmazon Mktp,-19.99,2026-05-05\n",
            )
        ],
    )
    assert expense_res.status_code == 201, expense_res.text
    expense_id = expense_res.json()["expenses"][0]["id"]

    listed_before = await app_client.get("/api/v1/expenses")
    expense_before = next(row for row in listed_before.json() if row["id"] == expense_id)
    assert expense_before["categoryId"] == rule_category["id"]
    assert expense_before["categorySource"] == "rule"

    import_payload = {
        "scraperVersion": "1.0.0",
        "domain": "amazon.co.uk",
        "orders": [
            {
                "orderId": "777-0000001-0000001",
                "orderDate": "2026-05-05",
                "total": "19.99",
                "currency": "GBP",
                "status": "Delivered",
                "items": [{"title": "Widget", "quantity": 1, "price": "19.99"}],
            }
        ],
    }
    import_res = await app_client.post("/api/v1/amazon-orders/import-export", json=import_payload)
    assert import_res.status_code == 201, import_res.text

    patch_res = await app_client.patch(
        "/api/v1/amazon-orders/777-0000001-0000001/category",
        json={"categoryId": other_category["id"]},
    )
    assert patch_res.status_code == 200, patch_res.text

    listed_after = await app_client.get("/api/v1/expenses")
    expense_after = next(row for row in listed_after.json() if row["id"] == expense_id)
    assert expense_after["categoryId"] == rule_category["id"]
    assert expense_after["categorySource"] == "rule"


async def test_import_export_skips_order_missing_total(app_client):
    """B3: one order missing its total -> 201, that order reported in `skipped`
    with a reason, the others import."""
    await _disable_ai(app_client)
    payload = _load_export_fixture()
    payload["orders"][0]["total"] = None  # 111-... loses its total

    res = await app_client.post("/api/v1/amazon-orders/import-export", json=payload)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["created"] == 2
    report = body["files"][0]
    assert report["skippedRows"] == 1
    assert len(report["skipped"]) == 1
    assert report["skipped"][0]["orderId"] == "111-2223334-4445556"
    assert "total" in report["skipped"][0]["reason"].lower()

    ids = {row["id"] for row in (await app_client.get("/api/v1/amazon-orders")).json()}
    assert ids == {"222-3334445-5556667", "333-4445556-6667778"}


async def test_import_export_skips_cancelled_status(app_client):
    """S2: cancelled/returned orders are skipped, not imported."""
    await _disable_ai(app_client)
    payload = _load_export_fixture()
    payload["orders"][1]["status"] = "Cancelled"  # 222-...

    res = await app_client.post("/api/v1/amazon-orders/import-export", json=payload)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["created"] == 2
    report = body["files"][0]
    assert report["skippedRows"] == 1
    assert report["skipped"][0]["orderId"] == "222-3334445-5556667"
    assert "status" in report["skipped"][0]["reason"].lower()

    ids = {row["id"] for row in (await app_client.get("/api/v1/amazon-orders")).json()}
    assert "222-3334445-5556667" not in ids


async def test_import_export_skips_invalid_dates_without_422_or_500(app_client):
    """B3: a bad order date is SKIPPED (201 + reason), never a 422 and never a
    500. Covers a non-pattern date, a pattern-valid-but-impossible date (the DB
    GLOB would accept "2026-13-40" -> the in-code fromisoformat check prevents
    a silently-unmatchable order), and a slash date that won't normalise."""
    await _disable_ai(app_client)
    for bad_date in ("not-a-date", "2026-13-40", "13/2026"):
        payload = _load_export_fixture()
        payload["orders"] = [payload["orders"][0]]
        payload["orders"][0]["orderDate"] = bad_date

        res = await app_client.post("/api/v1/amazon-orders/import-export", json=payload)
        assert res.status_code == 201, (bad_date, res.text)
        body = res.json()
        assert body["created"] == 0, bad_date
        report = body["files"][0]
        assert report["skippedRows"] == 1, bad_date
        assert "date" in report["skipped"][0]["reason"].lower(), bad_date


async def test_import_export_structural_errors_are_422(app_client):
    """B3: structural problems (empty orders, orders not an array, missing
    orders) are 422s, in contrast to row-level problems which are skipped."""
    empty = await app_client.post(
        "/api/v1/amazon-orders/import-export",
        json={"scraperVersion": "1.0.0", "domain": "amazon.co.uk", "orders": []},
    )
    assert empty.status_code == 422, empty.text

    not_array = await app_client.post(
        "/api/v1/amazon-orders/import-export",
        json={"orders": "nope"},
    )
    assert not_array.status_code == 422, not_array.text

    missing = await app_client.post(
        "/api/v1/amazon-orders/import-export",
        json={"domain": "amazon.co.uk"},
    )
    assert missing.status_code == 422, missing.text


async def test_import_export_is_idempotent(app_client):
    """Re-POSTing the same payload upserts (all `updated`), creates no
    duplicate links, and never overwrites a write-once short_name/category
    (mirrors the CSV idempotency guarantee; upsert leaves those fields alone)."""
    await _disable_ai(app_client)
    await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=19.99, date="2026-05-05"
    )
    payload = _load_export_fixture()

    first = await app_client.post("/api/v1/amazon-orders/import-export", json=payload)
    assert first.status_code == 201, first.text
    assert first.json()["created"] == 3
    assert first.json()["autoMatched"] == 1

    # Write-once fields, set after the first import, must survive a re-import.
    await app_client.patch(
        "/api/v1/amazon-orders/222-3334445-5556667/short-name",
        json={"shortName": "My custom name"},
    )
    travel = (await app_client.post("/api/v1/categories", json={"name": "Travel"})).json()
    await app_client.patch(
        "/api/v1/amazon-orders/333-4445556-6667778/category",
        json={"categoryId": travel["id"]},
    )

    second = await app_client.post("/api/v1/amazon-orders/import-export", json=payload)
    assert second.status_code == 201, second.text
    body = second.json()
    assert body["created"] == 0
    assert body["updated"] == 3

    listed = {row["id"]: row for row in (await app_client.get("/api/v1/amazon-orders")).json()}
    assert listed["222-3334445-5556667"]["shortName"] == "My custom name"
    assert listed["333-4445556-6667778"]["categoryId"] == travel["id"]
    # The auto-matched order still has exactly one link (no duplicates).
    assert len(listed["111-2223334-4445556"]["linkedExpenseIds"]) == 1


# --- AI re-categorise (preview + confirm) -----------------------------------


async def _import_retail_with_category(app_client, monkeypatch, category: str) -> None:
    """Import the retail CSV with mocked order-AI assigning `category` to all."""

    async def fake(items, *, existing_categories, ai_rules, api_key, model, **kwargs: object):
        return CategorizedBulkItems(
            items=[replace(i, category=category) for i in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.ai_order_categorization.categorize_transactions", fake)
    await app_client.patch("/api/v1/settings", json={"aiCategorizeEnabled": True})
    res = await app_client.post(
        "/api/v1/amazon-orders/import-csv",
        files=[_upload("retail.csv", RETAIL_ORDER_CSV)],
    )
    assert res.status_code == 201, res.text


async def test_recategorize_preview_splits_changed_and_unchanged(app_client, monkeypatch):
    """Preview re-runs AI against current rules; rows whose suggestion equals the
    order's current category are unchanged, the rest are changed. No writes."""
    await _import_retail_with_category(app_client, monkeypatch, "Office Supplies")

    # Now the AI (rules changed) suggests a different category for everything.
    async def groceries(items, *, existing_categories, ai_rules, api_key, model, **kwargs: object):
        return CategorizedBulkItems(
            items=[replace(i, category="Groceries") for i in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.ai_order_categorization.categorize_transactions", groceries)
    res = await app_client.post("/api/v1/amazon-orders/recategorize/preview")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["eligible"] == len(body["rows"]) > 0
    assert body["changed"] == len(body["rows"])
    assert body["unchanged"] == 0
    for row in body["rows"]:
        assert row["changed"] is True
        assert row["suggestedCategoryName"] == "Groceries"
        assert row["currentCategoryName"] == "Office Supplies"

    # Preview must not have written anything.
    listed = await app_client.get("/api/v1/amazon-orders")
    assert all(r["categoryId"] == "cat-office-supplies" for r in listed.json())


async def test_recategorize_preview_marks_same_suggestion_unchanged(app_client, monkeypatch):
    await _import_retail_with_category(app_client, monkeypatch, "Office Supplies")
    # Same suggestion as the current category -> unchanged.
    res = await app_client.post("/api/v1/amazon-orders/recategorize/preview")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["changed"] == 0
    assert body["unchanged"] == len(body["rows"]) > 0
    for row in body["rows"]:
        assert row["changed"] is False
        assert row["suggestedCategoryExists"] is True


async def test_recategorize_confirm_overwrites_and_propagates(app_client, monkeypatch):
    """Confirming an accepted row overwrites the order category AND pushes it onto
    a linked overridable (ai/import) expense."""
    expense_id = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=9.99, date="2026-05-03"
    )
    await _import_retail_with_category(app_client, monkeypatch, "Office Supplies")
    # Order 333 (9.99) auto-matched the seeded uncategorised expense and
    # propagated "Office Supplies" onto it.
    order = await app_client.get("/api/v1/amazon-orders/333-9999999-1111111")
    assert order.json()["categoryId"] == "cat-office-supplies"
    assert order.json()["linkedExpenseIds"] == [expense_id]

    res = await app_client.post(
        "/api/v1/amazon-orders/recategorize/confirm",
        json={"rows": [{"orderId": "333-9999999-1111111", "categoryName": "Groceries"}]},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["updated"] == 1
    assert body["categoriesCreated"] == 1  # cat-groceries is new
    assert body["expensesUpdated"] == 1

    refetched = await app_client.get("/api/v1/amazon-orders/333-9999999-1111111")
    assert refetched.json()["categoryId"] == "cat-groceries"
    expenses = (await app_client.get("/api/v1/expenses")).json()
    exp = next(e for e in expenses if e["id"] == expense_id)
    assert exp["categoryId"] == "cat-groceries"
    assert exp["categorySource"] == "amazon"


async def test_recategorize_confirm_skips_unknown_order(app_client, monkeypatch):
    await _import_retail_with_category(app_client, monkeypatch, "Office Supplies")
    res = await app_client.post(
        "/api/v1/amazon-orders/recategorize/confirm",
        json={
            "rows": [
                {"orderId": "does-not-exist", "categoryName": "Groceries"},
                {"orderId": "333-9999999-1111111", "categoryName": "Groceries"},
            ]
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["updated"] == 1


async def test_recategorize_preview_marks_new_category_not_existing(app_client, monkeypatch):
    """A suggestion that doesn't map to an existing category is flagged
    suggestedCategoryExists=False (confirm would create it) and the label is the
    canonical titleized name confirm would create."""
    await _import_retail_with_category(app_client, monkeypatch, "Office Supplies")

    async def suggest(items, *, existing_categories, ai_rules, api_key, model, **kwargs: object):
        return CategorizedBulkItems(
            items=[replace(i, category="garden TOOLS") for i in items],
            categorized=len(items),
        )

    monkeypatch.setattr("quid_api.ai_order_categorization.categorize_transactions", suggest)
    res = await app_client.post("/api/v1/amazon-orders/recategorize/preview")
    assert res.status_code == 200, res.text
    rows = res.json()["rows"]
    assert rows
    assert all(row["changed"] for row in rows)
    for row in rows:
        assert row["suggestedCategoryExists"] is False
        assert row["suggestedCategoryName"] == "Garden Tools"


async def test_recategorize_confirm_recount_is_accurate_on_reapply(app_client, monkeypatch):
    """Re-confirming a row whose order+expense already carry the target category
    reports expensesUpdated=0 (no phantom writes counted)."""
    expense_id = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=9.99, date="2026-05-03"
    )
    await _import_retail_with_category(app_client, monkeypatch, "Office Supplies")

    body = {"rows": [{"orderId": "333-9999999-1111111", "categoryName": "Groceries"}]}
    first = await app_client.post("/api/v1/amazon-orders/recategorize/confirm", json=body)
    assert first.json()["expensesUpdated"] == 1

    # Re-applying the identical row changes nothing now.
    second = await app_client.post("/api/v1/amazon-orders/recategorize/confirm", json=body)
    assert second.status_code == 200, second.text
    assert second.json()["updated"] == 1
    assert second.json()["expensesUpdated"] == 0
    assert second.json()["categoriesCreated"] == 0
    expenses = (await app_client.get("/api/v1/expenses")).json()
    assert next(e for e in expenses if e["id"] == expense_id)["categoryId"] == "cat-groceries"


async def test_manual_category_edit_updates_amazon_sourced_expense(app_client, monkeypatch):
    """A manual order category edit is DELIBERATE: it updates a linked expense
    whose category previously came from this order's own `amazon` stamp, so the
    order and the expense it categorised don't drift apart."""
    expense_id = await _seed_categories_and_expense(
        app_client, name="Amazon Mktp", amount=9.99, date="2026-05-03"
    )
    await _import_retail_with_category(app_client, monkeypatch, "Office Supplies")
    # Order 333 auto-matched and stamped the expense `amazon`/cat-office-supplies.
    expenses = (await app_client.get("/api/v1/expenses")).json()
    exp = next(e for e in expenses if e["id"] == expense_id)
    assert exp["categoryId"] == "cat-office-supplies"
    assert exp["categorySource"] == "amazon"

    travel = (await app_client.post("/api/v1/categories", json={"name": "Travel"})).json()
    await app_client.patch(
        "/api/v1/amazon-orders/333-9999999-1111111/category",
        json={"categoryId": travel["id"]},
    )

    after = (await app_client.get("/api/v1/expenses")).json()
    exp_after = next(e for e in after if e["id"] == expense_id)
    assert exp_after["categoryId"] == travel["id"]
    assert exp_after["categorySource"] == "amazon"


async def test_recategorize_confirm_does_not_override_manual_expense(app_client, monkeypatch):
    """A hand-set (manual) expense category is protected even when the linked
    order is re-categorised via confirm."""
    expense = await app_client.post(
        "/api/v1/expenses",
        json={
            "name": "Amazon Mktp",
            "amount": 9.99,
            "date": "2026-05-03",
            "categoryId": "uncategorized",
        },
    )
    expense_id = expense.json()["id"]
    travel = (await app_client.post("/api/v1/categories", json={"name": "Travel"})).json()
    await app_client.patch(f"/api/v1/expenses/{expense_id}", json={"categoryId": travel["id"]})

    await _import_retail_with_category(app_client, monkeypatch, "Office Supplies")
    await app_client.post(
        "/api/v1/amazon-orders/333-9999999-1111111/link",
        json={"expenseId": expense_id},
    )

    res = await app_client.post(
        "/api/v1/amazon-orders/recategorize/confirm",
        json={"rows": [{"orderId": "333-9999999-1111111", "categoryName": "Groceries"}]},
    )
    assert res.status_code == 200, res.text
    assert res.json()["expensesUpdated"] == 0

    expenses = (await app_client.get("/api/v1/expenses")).json()
    exp = next(e for e in expenses if e["id"] == expense_id)
    assert exp["categoryId"] == travel["id"]
