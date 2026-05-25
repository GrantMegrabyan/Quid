from __future__ import annotations

import pytest

from quid_api.category_helpers import (
    UNCATEGORIZED_COLOR,
    UNCATEGORIZED_ID,
    color_for_category_id,
    normalize_icon,
    slugify_category,
    titleize_slug,
)


def test_color_for_uncategorized_is_fixed():
    assert color_for_category_id(UNCATEGORIZED_ID) == UNCATEGORIZED_COLOR


@pytest.mark.parametrize("cat_id", ["cat-groceries", "cat-transport", "cat-bills"])
def test_color_is_hex_lowercase(cat_id):
    color = color_for_category_id(cat_id)
    assert color.startswith("#")
    assert len(color) == 7
    assert color == color.lower()


def test_color_is_deterministic():
    assert color_for_category_id("cat-x") == color_for_category_id("cat-x")


def test_color_differs_across_ids():
    a = color_for_category_id("cat-a")
    b = color_for_category_id("cat-b")
    assert a != b


def test_normalize_icon_passes_known_keys():
    assert normalize_icon("shopping-cart") == "shopping-cart"
    assert normalize_icon("car-taxi-front") == "car-taxi-front"
    assert normalize_icon("ticket") == "ticket"


def test_normalize_icon_maps_legacy_emoji():
    assert normalize_icon("🛒") == "shopping-cart"


def test_normalize_icon_falls_back_for_unknown():
    assert normalize_icon("not an icon key") == "circle-help"


def test_normalize_icon_falls_back_for_non_string():
    assert normalize_icon(None) == "circle-help"
    assert normalize_icon(42) == "circle-help"


def test_slugify_basic():
    assert slugify_category("Eating Out") == "eating-out"
    assert slugify_category("eating_out") == "eating-out"
    assert slugify_category("  Bills  ") == "bills"
    assert slugify_category("Trader Joe\u2019s") == "trader-joe-s"


def test_titleize_slug():
    assert titleize_slug("eating-out") == "Eating Out"
    assert titleize_slug("eating_out") == "Eating Out"
    assert titleize_slug("bills") == "Bills"
