from __future__ import annotations

import re

UNCATEGORIZED_ID = "uncategorized"
UNCATEGORIZED_COLOR = "#9ca3af"
FALLBACK_ICON = "circle-help"

_SATURATION = 68
_LIGHTNESS = 52

_ICON_KEY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_LEGACY_EMOJI_TO_ICON: dict[str, str] = {
    "•": FALLBACK_ICON,
    "🛒": "shopping-cart",
    "🚇": "train-front",
    "🏠": "house",
    "🍽️": "utensils",
    "🍽": "utensils",
    "🧾": "receipt",
    "☕": "coffee",
    "🍎": "shopping-cart",
    "🥑": "shopping-cart",
}


def normalize_icon(value: object, fallback: str = FALLBACK_ICON) -> str:
    if not isinstance(value, str):
        return fallback
    trimmed = value.strip()
    if _ICON_KEY_RE.fullmatch(trimmed):
        return trimmed
    return _LEGACY_EMOJI_TO_ICON.get(trimmed, fallback)


def _hash_string(value: str) -> int:
    h = 0
    for ch in value:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def _hsl_to_hex(hue: float, saturation: float, lightness: float) -> str:
    hue_norm = ((hue % 360) + 360) % 360
    s = max(0, min(100, saturation)) / 100
    l = max(0, min(100, lightness)) / 100  # noqa: E741  matches TS source

    chroma = (1 - abs(2 * l - 1)) * s
    h_prime = hue_norm / 60
    x = chroma * (1 - abs((h_prime % 2) - 1))

    if 0 <= h_prime < 1:
        r1, g1, b1 = chroma, x, 0.0
    elif h_prime < 2:
        r1, g1, b1 = x, chroma, 0.0
    elif h_prime < 3:
        r1, g1, b1 = 0.0, chroma, x
    elif h_prime < 4:
        r1, g1, b1 = 0.0, x, chroma
    elif h_prime < 5:
        r1, g1, b1 = x, 0.0, chroma
    else:
        r1, g1, b1 = chroma, 0.0, x

    match = l - chroma / 2

    def to_hex(channel: float) -> str:
        return format(round((channel + match) * 255), "02x")

    return f"#{to_hex(r1)}{to_hex(g1)}{to_hex(b1)}"


def color_for_category_id(category_id: str) -> str:
    if category_id.strip().lower() == UNCATEGORIZED_ID:
        return UNCATEGORIZED_COLOR
    hue = _hash_string(category_id) % 360
    return _hsl_to_hex(hue, _SATURATION, _LIGHTNESS).lower()


def slugify_category(value: str) -> str:
    cleaned = value.strip().lower()
    out: list[str] = []
    prev_dash = False
    for ch in cleaned:
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash and out:
            out.append("-")
            prev_dash = True
    while out and out[-1] == "-":
        out.pop()
    return "".join(out)


def titleize_slug(slug: str) -> str:
    parts = [p for p in slug.replace("_", " ").replace("-", " ").split() if p]
    return " ".join(word.capitalize() for word in parts)
