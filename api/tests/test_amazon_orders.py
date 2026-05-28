from __future__ import annotations

from decimal import Decimal

from quid_api.amazon_csv_import import AmazonCsvFile, parse_amazon_csv
from quid_api.settings import reset_settings


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
    import pytest

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
