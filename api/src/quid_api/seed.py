from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from quid_api.category_helpers import UNCATEGORIZED_ID, color_for_category_id
from quid_api.models import Category, Expense

if TYPE_CHECKING:
    from quid_api.repositories.categories import CategoryRepository
    from quid_api.repositories.expenses import ExpenseRepository


@dataclass(frozen=True)
class _CatSeed:
    id: str
    name: str
    icon: str
    description: str


@dataclass(frozen=True)
class _ExpSeed:
    id: str
    name: str
    amount: str
    category_id: str
    note: str
    months_ago: int
    day: int


CATEGORY_SEEDS: tuple[_CatSeed, ...] = (
    _CatSeed(
        "cat-housing",
        "Housing",
        "house",
        "Home-related expenses and utilities: rent, mortgage, electricity, water, gas, internet, maintenance, furniture, and household items.",
    ),
    _CatSeed(
        "cat-groceries",
        "Groceries",
        "shopping-cart",
        "Food and household consumables bought for home use, including supermarkets, baby food, cleaning supplies, and toiletries bought with groceries. Do not use for restaurants, cafes, or delivery.",
    ),
    _CatSeed(
        "cat-health",
        "Health",
        "heart-pulse",
        "Medical and healthcare spending: pharmacy, doctor, dental, vitamins, supplements, tests, and health-related products.",
    ),
    _CatSeed(
        "cat-childcare",
        "Childcare",
        "baby",
        "Direct child care costs: nursery, kindergarten, nanny, babysitter, child activities, and school-related care. Do not use for toys, clothes, or baby food.",
    ),
    _CatSeed(
        "cat-car",
        "Car",
        "car",
        "Car ownership and maintenance: fuel, insurance, parking, repairs, car wash, registration, and vehicle taxes.",
    ),
    _CatSeed(
        "cat-public-transport",
        "Public Transport",
        "train-front",
        "Daily non-taxi transport: bus, metro, train, tram, and similar public transit fares.",
    ),
    _CatSeed(
        "cat-eating-out",
        "Eating Out",
        "utensils",
        "Food and drinks bought outside the home: restaurants, cafes, coffee shops, food delivery, fast food, and outside snacks.",
    ),
    _CatSeed(
        "cat-taxi",
        "Taxi",
        "car-taxi-front",
        "Taxi and ride-sharing convenience transport, including Uber, Bolt, local taxis, and similar services.",
    ),
    _CatSeed(
        "cat-shopping",
        "Shopping",
        "shopping-bag",
        "General personal and household shopping: clothes, shoes, cosmetics, toys, small household purchases, and non-essential purchases. Do not use for technology purchases.",
    ),
    _CatSeed(
        "cat-technology-gadgets",
        "Technology & Gadgets",
        "smartphone",
        "Technology purchases and accessories: phones, laptops, tablets, smart watches, smart home devices, headphones, and computer accessories.",
    ),
    _CatSeed(
        "cat-sports-fitness",
        "Sports & Fitness",
        "dumbbell",
        "Fitness and sports spending: gym memberships, fitness classes, sporting equipment, running shoes, sports clubs, and fitness apps.",
    ),
    _CatSeed(
        "cat-entertainment-leisure",
        "Entertainment & Leisure",
        "ticket",
        "Entertainment, hobbies, and leisure: cinema, concerts, video games, books, hobbies, events, and recreational activities. Do not use for recurring subscriptions.",
    ),
    _CatSeed(
        "cat-subscriptions",
        "Subscriptions",
        "repeat",
        "Recurring digital or membership payments only: Netflix, Spotify, iCloud, YouTube Premium, software subscriptions, and Amazon Prime.",
    ),
    _CatSeed(
        "cat-travel",
        "Travel",
        "plane",
        "Non-daily travel and vacation costs: flights, hotels, vacation transportation, travel activities, and travel bookings.",
    ),
    _CatSeed(
        "cat-gifts",
        "Gifts",
        "gift",
        "Gifts and celebrations: birthday gifts, holiday gifts, flowers, celebration expenses, and special occasions.",
    ),
)

EXPENSE_SEEDS: tuple[_ExpSeed, ...] = (
    _ExpSeed("exp-001", "Whole Foods", "58.24", "cat-groceries", "Weekly groceries", 0, 3),
    _ExpSeed("exp-002", "Transport for London", "14.50", "cat-public-transport", "Bus fare", 0, 7),
    _ExpSeed("exp-003", "Starbucks", "42.80", "cat-eating-out", "Coffee and lunch", 1, 11),
    _ExpSeed("exp-004", "Greystar Rent", "1200.00", "cat-housing", "", 1, 1),
    _ExpSeed("exp-005", "Comcast Xfinity", "96.12", "cat-housing", "Internet bill", 2, 5),
    _ExpSeed("exp-006", "Trader Joes", "33.75", "cat-groceries", "Pantry restock", 2, 13),
    _ExpSeed("exp-007", "Uber", "22.00", "cat-taxi", "Rideshare", 3, 9),
    _ExpSeed("exp-008", "Deliveroo", "68.40", "cat-eating-out", "Dinner out", 3, 19),
    _ExpSeed("exp-009", "Sainsbury's", "48.90", "cat-groceries", "Farmers market", 4, 6),
    _ExpSeed("exp-010", "Pacific Gas & Electric", "74.30", "cat-housing", "Electricity", 4, 16),
    _ExpSeed("exp-011", "NCP Parking", "15.20", "cat-car", "Parking", 5, 4),
    _ExpSeed("exp-012", "Chipotle", "89.95", "cat-eating-out", "Team lunch", 5, 10),
    _ExpSeed("exp-013", "Amazon Prime", "27.60", "cat-groceries", "Snacks", 0, 21),
    _ExpSeed("exp-014", "Thames Water", "110.40", "cat-housing", "Water bill", 2, 24),
    _ExpSeed("exp-015", "IKEA", "210.85", "cat-housing", "Maintenance supplies", 3, 27),
    _ExpSeed("exp-016", "Patreon", "12.00", UNCATEGORIZED_ID, "Monthly membership", 1, 14),
    _ExpSeed("exp-017", "Netflix", "17.99", "cat-subscriptions", "Streaming", 0, 18),
)


def _months_ago_date(reference: datetime, months_ago: int, day: int) -> str:
    year = reference.year
    month = reference.month - months_ago
    while month <= 0:
        month += 12
        year -= 1
    return f"{year:04d}-{month:02d}-{day:02d}"


async def seed_samples(
    cat_repo: CategoryRepository,
    exp_repo: ExpenseRepository,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    session = cat_repo.session
    reference = now or datetime.now(tz=UTC)
    cat_inserted = 0
    exp_inserted = 0

    for cat_seed in CATEGORY_SEEDS:
        existing_cat = await session.get(Category, cat_seed.id)
        if existing_cat is not None:
            continue
        cat = Category(
            id=cat_seed.id,
            name=cat_seed.name,
            color=color_for_category_id(cat_seed.id),
            icon=cat_seed.icon,
            description=cat_seed.description,
        )
        session.add(cat)
        cat_inserted += 1
    await session.flush()

    for exp_seed in EXPENSE_SEEDS:
        existing_exp = await session.get(Expense, exp_seed.id)
        if existing_exp is not None:
            continue
        exp = Expense(
            id=exp_seed.id,
            name=exp_seed.name,
            amount=Decimal(exp_seed.amount),
            date=_months_ago_date(reference, exp_seed.months_ago, exp_seed.day),
            category_id=exp_seed.category_id,
            note=exp_seed.note,
        )
        session.add(exp)
        exp_inserted += 1
    await session.flush()

    return {"categories": cat_inserted, "expenses": exp_inserted}


async def reset_and_seed(
    cat_repo: CategoryRepository,
    exp_repo: ExpenseRepository,
) -> dict[str, int]:
    from sqlalchemy import text

    session = cat_repo.session
    await session.execute(text("DELETE FROM import_rules"))
    await session.execute(text("DELETE FROM expenses"))
    await session.execute(
        text("DELETE FROM categories WHERE id != :uid"), {"uid": UNCATEGORIZED_ID}
    )
    await session.flush()
    return await seed_samples(cat_repo, exp_repo)
