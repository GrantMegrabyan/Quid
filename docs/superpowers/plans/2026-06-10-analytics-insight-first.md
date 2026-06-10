# Analytics Insight-First Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the descriptive Analytics page with an insight-first page: a verdict header, a "What went up" diagnosis zone (vs trailing 6-month average, with drill-down), a "Where you can save" zone (price creep / new recurring / habit spend / recurring stack), and an on-demand, persisted AI narrative.

**Architecture:** Backend adds two read-only aggregation methods (`diagnosis`, `savings`) to `AnalyticsRepository`, a new `analytics_narratives` table (migration `0021`) with its own small write-path repository, and an `ai_narrative.py` OpenRouter module. The router surface shrinks to `/summary`, `/monthly-totals`, `/diagnosis`, `/savings`, `/narrative`. Frontend rebuilds `/analytics` around four new components plus the surviving `MonthlyTrendChart`; one parallel load on mount, period selector filters the trend chart client-side.

**Tech Stack:** FastAPI + SQLAlchemy (async) + SQLite + Alembic + pytest (backend, run from `api/` with `uv run`); SvelteKit (Svelte 5 runes) + Tailwind/Catppuccin + Playwright (frontend, run from `webui/` with `npm`).

**Spec:** `docs/superpowers/specs/2026-06-10-analytics-redesign-design.md`

**Branch:** all work happens on `feat/analytics-insights` (created before this plan was committed). Do not push.

**Conventions that apply to every task:**
- Money is `Decimal` server-side, canonical 2dp strings over the wire (`_money_str` field serializers), never floats.
- API JSON is camelCase via the `_Camel` base schema; Python is snake_case.
- Backend verification per task: `uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest` (from `api/`). When a task says "backend checks", it means exactly this.
- Frontend verification per task: `npm run check` (from `webui/`). e2e runs in Task 13.
- Commit after each task, message style `feat(api)`, `feat(webui)`, `chore`, `docs`.

---

### Task 1: Diagnosis aggregation in AnalyticsRepository

**Files:**
- Modify: `api/src/quid_api/repositories/analytics.py`
- Test: `api/tests/test_analytics_diagnosis.py` (new file)

- [ ] **Step 1.1: Write failing tests**

Create `api/tests/test_analytics_diagnosis.py`. The baseline math is tested directly against the repository using a session built from the `engine` fixture in `api/tests/conftest.py` (as below); Task 2 adds endpoint-level tests through `app_client` on top.

```python
"""Repository-level tests for AnalyticsRepository.diagnosis."""

from __future__ import annotations

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from quid_api.models import Category, Expense
from quid_api.repositories.analytics import AnalyticsRepository

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def session(engine: AsyncEngine):
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as sess:
        yield sess


async def _seed(session, category_id: str, name: str, amount: str, date: str) -> None:
    session.add(
        Expense(
            id=f"e-{category_id}-{name}-{date}-{amount}",
            name=name,
            amount=Decimal(amount),
            date=date,
            category_id=category_id,
            note="",
            importance="important",
            category_source="import",
        )
    )


async def _seed_cat(session, category_id: str, name: str) -> None:
    session.add(
        Category(id=category_id, name=name, color="#22c55e", icon="tag", description="")
    )


async def test_diagnosis_empty_db(session):
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    assert result.latest_month is None
    assert result.increases == []
    assert result.baseline_month_count == 0


async def test_diagnosis_single_complete_month_has_no_baseline(session):
    await _seed_cat(session, "c1", "Groceries")
    await _seed(session, "c1", "Tesco", "50.00", "2026-05-10")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    assert result.latest_month == "2026-05"
    assert result.baseline_month_count == 0
    assert result.increases == []
    assert result.total_current == Decimal("50.00")


async def test_diagnosis_zero_months_count_in_baseline(session):
    # Groceries spends 60 in Feb only; baseline window Feb..Apr (3 months,
    # clipped to first data month) -> baseline avg 20, not 60.
    await _seed_cat(session, "c1", "Groceries")
    await _seed(session, "c1", "Tesco", "60.00", "2026-02-10")
    await _seed(session, "c1", "Tesco", "90.00", "2026-05-10")
    # Another category keeps Mar/Apr present in the data (months exist).
    await _seed_cat(session, "c2", "Transport")
    await _seed(session, "c2", "TfL", "10.00", "2026-03-05")
    await _seed(session, "c2", "TfL", "10.00", "2026-04-05")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    assert result.latest_month == "2026-05"
    assert result.baseline_from == "2026-02"
    assert result.baseline_to == "2026-04"
    assert result.baseline_month_count == 3
    groceries = next(c for c in result.increases if c.category_name == "Groceries")
    assert groceries.baseline == Decimal("20.00")
    assert groceries.delta == Decimal("70.00")


async def test_diagnosis_baseline_capped_at_six_months(session):
    await _seed_cat(session, "c1", "Groceries")
    # 8 months of history before the latest complete month (2026-05):
    # 2025-09 .. 2026-04 at 10/mo; only the last 6 (2025-11..2026-04) count.
    for month in ("2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"):
        await _seed(session, "c1", "Tesco", "10.00", f"{month}-15")
    await _seed(session, "c1", "Tesco", "40.00", "2026-05-15")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    assert result.baseline_from == "2025-11"
    assert result.baseline_to == "2026-04"
    assert result.baseline_month_count == 6
    groceries = result.increases[0]
    assert groceries.baseline == Decimal("10.00")
    assert groceries.delta == Decimal("30.00")


async def test_diagnosis_noise_floor_and_decreases(session):
    await _seed_cat(session, "c1", "Groceries")   # big increase: kept
    await _seed_cat(session, "c2", "Snacks")      # +5 on 100 (=5%): rolled up
    await _seed_cat(session, "c3", "Transport")   # decrease
    for month in ("2026-03", "2026-04"):
        await _seed(session, "c1", "Tesco", "50.00", f"{month}-10")
        await _seed(session, "c2", "Corner Shop", "100.00", f"{month}-11")
        await _seed(session, "c3", "TfL", "30.00", f"{month}-12")
    await _seed(session, "c1", "Tesco", "120.00", "2026-05-10")
    await _seed(session, "c2", "Corner Shop", "105.00", "2026-05-11")
    # Transport absent in May -> decrease of 30.
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    assert [c.category_name for c in result.increases] == ["Groceries"]
    assert result.other_increases_count == 1
    assert result.other_increases_total == Decimal("5.00")
    assert len(result.decreases) == 1
    assert result.decreases[0].category_name == "Transport"
    assert result.decreases[0].delta == Decimal("-30.00")


async def test_diagnosis_new_category_and_small_new_category(session):
    await _seed_cat(session, "c0", "Anchor")  # keeps baseline months populated
    await _seed_cat(session, "c1", "Hobbies")     # new, >=10 -> kept, is_new
    await _seed_cat(session, "c2", "Stationery")  # new, <10 -> rolled up
    for month in ("2026-03", "2026-04"):
        await _seed(session, "c0", "Anchor Shop", "20.00", f"{month}-10")
    await _seed(session, "c1", "Hobby Store", "45.00", "2026-05-10")
    await _seed(session, "c2", "Paper Co", "4.00", "2026-05-11")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    hobbies = next(c for c in result.increases if c.category_name == "Hobbies")
    assert hobbies.is_new is True
    assert hobbies.percent_change is None
    assert hobbies.baseline == Decimal("0.00")
    assert all(c.category_name != "Stationery" for c in result.increases)
    assert result.other_increases_count == 1


async def test_diagnosis_contributors_and_transactions(session):
    await _seed_cat(session, "c1", "Groceries")
    for month in ("2026-03", "2026-04"):
        await _seed(session, "c1", "Tesco", "50.00", f"{month}-10")
    await _seed(session, "c1", "Tesco", "60.00", "2026-05-10")
    await _seed(session, "c1", "Waitrose", "70.00", "2026-05-12")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    groceries = result.increases[0]
    # Contributors sorted by merchant delta desc: Waitrose (new, +70) then
    # Tesco (60 vs 50 avg = +10).
    assert [c.merchant for c in groceries.contributors] == ["Waitrose", "Tesco"]
    assert groceries.contributors[0].is_new is True
    assert groceries.contributors[0].delta == Decimal("70.00")
    assert groceries.contributors[1].is_new is False
    assert groceries.contributors[1].delta == Decimal("10.00")
    # Transactions: the latest month's rows, largest first.
    assert [t.name for t in groceries.transactions] == ["Waitrose", "Tesco"]
    assert groceries.transactions[0].amount == Decimal("70.00")


async def test_diagnosis_overall_totals(session):
    await _seed_cat(session, "c1", "Groceries")
    for month in ("2026-03", "2026-04"):
        await _seed(session, "c1", "Tesco", "50.00", f"{month}-10")
    await _seed(session, "c1", "Tesco", "80.00", "2026-05-10")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of="2026-06-10")
    assert result.total_current == Decimal("80.00")
    assert result.total_baseline == Decimal("50.00")
```

Note the `Expense` constructor kwargs: check `api/src/quid_api/models.py` for required fields (`importance`, `category_source`, `note` are NOT NULL with defaults — passing them explicitly as above is safe).

- [ ] **Step 1.2: Run tests to verify they fail**

Run from `api/`: `uv run pytest tests/test_analytics_diagnosis.py -v`
Expected: FAIL / ERROR with `AttributeError: 'AnalyticsRepository' object has no attribute 'diagnosis'`.

- [ ] **Step 1.3: Implement diagnosis in the repository**

In `api/src/quid_api/repositories/analytics.py`, add below the existing module constants (`_MONTH_EXPR` etc.):

```python
#: Diagnosis baseline: trailing N complete months before the latest complete month.
_BASELINE_MONTHS = 6
#: Increases below BOTH floors roll into a single "everything else" line.
_NOISE_FLOOR_ABS = Decimal("10.00")
_NOISE_FLOOR_PCT = 10.0
#: Max contributing merchants returned per increased category.
_CONTRIBUTOR_LIMIT = 3


def _month_add(month: str, delta: int) -> str:
    """Add ``delta`` calendar months to a ``YYYY-MM`` key."""
    idx = int(month[:4]) * 12 + int(month[5:7]) - 1 + delta
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def _months_between(a: str, b: str) -> int:
    """Calendar-month distance ``b - a`` between two ``YYYY-MM`` keys."""
    return (int(b[:4]) * 12 + int(b[5:7])) - (int(a[:4]) * 12 + int(a[5:7]))
```

Add the dataclasses (next to the existing ones):

```python
@dataclass(frozen=True)
class DiagnosisContributor:
    merchant: str
    current: Decimal
    baseline: Decimal
    delta: Decimal
    is_new: bool


@dataclass(frozen=True)
class DiagnosisTransaction:
    id: str
    name: str
    display_name: str | None
    amount: Decimal
    date: str


@dataclass(frozen=True)
class DiagnosisIncrease:
    category_id: str
    category_name: str
    color: str
    current: Decimal
    baseline: Decimal
    delta: Decimal
    percent_change: float | None  # None when there is no baseline (new spending)
    is_new: bool
    contributors: list[DiagnosisContributor]
    transactions: list[DiagnosisTransaction]


@dataclass(frozen=True)
class DiagnosisDecrease:
    category_id: str
    category_name: str
    color: str
    current: Decimal
    baseline: Decimal
    delta: Decimal  # negative


@dataclass(frozen=True)
class DiagnosisResult:
    latest_month: str | None
    baseline_from: str | None
    baseline_to: str | None
    baseline_month_count: int
    total_current: Decimal
    total_baseline: Decimal
    increases: list[DiagnosisIncrease]
    other_increases_total: Decimal
    other_increases_count: int
    decreases: list[DiagnosisDecrease]
```

Add methods to `AnalyticsRepository` (keep the class read-only — no commits):

```python
    async def diagnosis(self, *, as_of: str) -> DiagnosisResult:
        """'What went up': latest complete month vs the trailing-average baseline.

        The baseline is each category's mean monthly spend over the (up to)
        ``_BASELINE_MONTHS`` complete months before the latest complete month,
        dividing by the WINDOW LENGTH so zero-spend months count as 0.
        """
        try:
            current_month = validate_iso_date(as_of)[:7]
        except ValueError as exc:
            raise RepositoryError(RepositoryErrorCode.VALIDATION, str(exc)) from exc

        month = _MONTH_EXPR.label("month")
        month_rows = (
            (
                await self.session.execute(
                    select(month)
                    .where(_MONTH_EXPR < current_month)
                    .group_by(month)
                    .order_by(month)
                )
            )
            .scalars()
            .all()
        )
        months = [str(m) for m in month_rows]
        if not months:
            return DiagnosisResult(
                latest_month=None,
                baseline_from=None,
                baseline_to=None,
                baseline_month_count=0,
                total_current=_ZERO,
                total_baseline=_ZERO,
                increases=[],
                other_increases_total=_ZERO,
                other_increases_count=0,
                decreases=[],
            )

        latest = months[-1]
        first_data = months[0]
        cur_by_cat = await self._category_month_totals(latest, latest)
        total_current = sum(cur_by_cat.values(), _ZERO)

        base_to = _month_add(latest, -1)
        base_from = max(_month_add(latest, -_BASELINE_MONTHS), first_data)
        if base_to < first_data:
            # Only one complete month of history: nothing to compare against.
            return DiagnosisResult(
                latest_month=latest,
                baseline_from=None,
                baseline_to=None,
                baseline_month_count=0,
                total_current=total_current,
                total_baseline=_ZERO,
                increases=[],
                other_increases_total=_ZERO,
                other_increases_count=0,
                decreases=[],
            )
        base_count = _months_between(base_from, base_to) + 1

        base_totals = await self._category_month_totals(base_from, base_to)
        base_div = Decimal(base_count)
        base_by_cat = {cid: (t / base_div).quantize(_ZERO) for cid, t in base_totals.items()}
        total_baseline = sum(base_by_cat.values(), _ZERO)

        all_ids = set(cur_by_cat) | set(base_by_cat)
        names = await self._category_names(list(all_ids))

        kept: list[tuple[str, Decimal, Decimal, Decimal, float | None, bool]] = []
        other_total = _ZERO
        other_count = 0
        decreases: list[DiagnosisDecrease] = []
        for cid in all_ids:
            current = cur_by_cat.get(cid, _ZERO)
            baseline = base_by_cat.get(cid, _ZERO)
            delta = current - baseline
            name, color = names.get(cid, (cid, color_for_category_id(cid)))
            if delta > _ZERO:
                pct = float(delta / baseline * 100) if baseline > _ZERO else None
                if delta >= _NOISE_FLOOR_ABS or (pct is not None and pct >= _NOISE_FLOOR_PCT):
                    kept.append((cid, current, baseline, delta, pct, baseline == _ZERO))
                else:
                    other_total += delta
                    other_count += 1
            elif delta < _ZERO:
                decreases.append(
                    DiagnosisDecrease(
                        category_id=cid,
                        category_name=name,
                        color=color,
                        current=current,
                        baseline=baseline,
                        delta=delta,
                    )
                )

        kept.sort(key=lambda item: item[3], reverse=True)
        decreases.sort(key=lambda d: d.delta)

        kept_ids = [cid for cid, *_ in kept]
        cur_merchants = await self._merchant_category_totals(latest, latest, kept_ids)
        base_merchants = await self._merchant_category_totals(base_from, base_to, kept_ids)
        txns_by_cat = await self._transactions_for_month(latest, kept_ids)

        increases: list[DiagnosisIncrease] = []
        for cid, current, baseline, delta, pct, is_new in kept:
            name, color = names.get(cid, (cid, color_for_category_id(cid)))
            contributors: list[DiagnosisContributor] = []
            for mkey, (label, cur_total) in cur_merchants.get(cid, {}).items():
                base_pair = base_merchants.get(cid, {}).get(mkey)
                m_base = (base_pair[1] / base_div).quantize(_ZERO) if base_pair else _ZERO
                m_delta = cur_total - m_base
                if m_delta > _ZERO:
                    contributors.append(
                        DiagnosisContributor(
                            merchant=label,
                            current=cur_total,
                            baseline=m_base,
                            delta=m_delta,
                            is_new=base_pair is None,
                        )
                    )
            contributors.sort(key=lambda c: c.delta, reverse=True)
            increases.append(
                DiagnosisIncrease(
                    category_id=cid,
                    category_name=name,
                    color=color,
                    current=current,
                    baseline=baseline,
                    delta=delta,
                    percent_change=pct,
                    is_new=is_new,
                    contributors=contributors[:_CONTRIBUTOR_LIMIT],
                    transactions=txns_by_cat.get(cid, []),
                )
            )

        return DiagnosisResult(
            latest_month=latest,
            baseline_from=base_from,
            baseline_to=base_to,
            baseline_month_count=base_count,
            total_current=total_current,
            total_baseline=total_baseline,
            increases=increases,
            other_increases_total=other_total,
            other_increases_count=other_count,
            decreases=decreases,
        )

    async def _category_month_totals(self, month_from: str, month_to: str) -> dict[str, Decimal]:
        stmt = (
            select(Expense.category_id, func.sum(Expense.amount))
            .where(_MONTH_EXPR >= month_from, _MONTH_EXPR <= month_to)
            .group_by(Expense.category_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return {str(cid): _as_decimal(total) for cid, total in rows}

    async def _merchant_category_totals(
        self, month_from: str, month_to: str, category_ids: list[str]
    ) -> dict[str, dict[str, tuple[str, Decimal]]]:
        """category_id -> merchant_key -> (display label, total)."""
        if not category_ids:
            return {}
        key = func.lower(func.trim(Expense.name)).label("merchant_key")
        stmt = (
            select(Expense.category_id, key, func.max(Expense.name), func.sum(Expense.amount))
            .where(
                _MONTH_EXPR >= month_from,
                _MONTH_EXPR <= month_to,
                Expense.category_id.in_(category_ids),
            )
            .group_by(Expense.category_id, key)
        )
        rows = (await self.session.execute(stmt)).all()
        out: dict[str, dict[str, tuple[str, Decimal]]] = {}
        for cid, mkey, label, total in rows:
            out.setdefault(str(cid), {})[str(mkey)] = (str(label), _as_decimal(total))
        return out

    async def _transactions_for_month(
        self, month_key: str, category_ids: list[str]
    ) -> dict[str, list[DiagnosisTransaction]]:
        if not category_ids:
            return {}
        stmt = (
            select(
                Expense.id,
                Expense.name,
                Expense.display_name,
                Expense.amount,
                Expense.date,
                Expense.category_id,
            )
            .where(_MONTH_EXPR == month_key, Expense.category_id.in_(category_ids))
            .order_by(Expense.amount.desc(), Expense.date.desc())
        )
        rows = (await self.session.execute(stmt)).all()
        out: dict[str, list[DiagnosisTransaction]] = {}
        for rid, name, display_name, amount, date, cid in rows:
            out.setdefault(str(cid), []).append(
                DiagnosisTransaction(
                    id=str(rid),
                    name=str(name),
                    display_name=None if display_name is None else str(display_name),
                    amount=_as_decimal(amount),
                    date=str(date),
                )
            )
        return out
```

- [ ] **Step 1.4: Run tests to verify they pass**

Run: `uv run pytest tests/test_analytics_diagnosis.py -v`
Expected: all PASS. Then full backend checks (`uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest`). Fix lint/typing complaints (e.g. `ruff format` may rewrap long signatures — run `uv run ruff format .` and re-check).

- [ ] **Step 1.5: Commit**

```bash
git add api/src/quid_api/repositories/analytics.py api/tests/test_analytics_diagnosis.py
git commit -m "feat(api): add trailing-average diagnosis aggregation to analytics repo"
```

---

### Task 2: /analytics/diagnosis endpoint

**Files:**
- Modify: `api/src/quid_api/schemas.py` (add after the existing analytics schemas, around line 1014)
- Modify: `api/src/quid_api/routers/analytics.py`
- Test: `api/tests/test_analytics_diagnosis.py` (extend)

- [ ] **Step 2.1: Write failing endpoint tests**

Append to `api/tests/test_analytics_diagnosis.py` (these use `app_client`; the seeding helpers `_make_cat` / `_make_expense` are copied from `test_analytics_api.py`):

```python
from typing import Any

from httpx import AsyncClient


async def _make_cat(client: AsyncClient, name: str) -> dict[str, Any]:
    res = await client.post("/api/v1/categories", json={"name": name})
    assert res.status_code == 201
    return res.json()  # type: ignore[no-any-return]


async def _make_expense(
    client: AsyncClient, *, name: str, amount: str, date: str, category_id: str
) -> dict[str, Any]:
    res = await client.post(
        "/api/v1/expenses",
        json={"name": name, "amount": amount, "date": date, "categoryId": category_id},
    )
    assert res.status_code == 201, res.text
    return res.json()  # type: ignore[no-any-return]


async def test_diagnosis_endpoint_shape(app_client):
    cat = await _make_cat(app_client, "Groceries")
    for month in ("2026-03", "2026-04"):
        await _make_expense(
            app_client, name="Tesco", amount="50.00", date=f"{month}-10", category_id=cat["id"]
        )
    await _make_expense(
        app_client, name="Waitrose", amount="120.00", date="2026-05-10", category_id=cat["id"]
    )

    res = await app_client.get("/api/v1/analytics/diagnosis", params={"as_of": "2026-06-10"})
    assert res.status_code == 200
    body = res.json()
    assert body["latestMonth"] == "2026-05"
    assert body["baselineMonthCount"] == 2
    assert body["totalCurrent"] == "120.00"
    assert body["totalBaseline"] == "50.00"
    increase = body["increases"][0]
    assert increase["categoryName"] == "Groceries"
    assert increase["delta"] == "70.00"
    assert increase["isNew"] is False
    assert increase["contributors"][0]["merchant"] == "Waitrose"
    assert increase["contributors"][0]["isNew"] is True
    assert increase["transactions"][0]["amount"] == "120.00"
    assert body["decreases"] == []


async def test_diagnosis_endpoint_bad_as_of(app_client):
    res = await app_client.get("/api/v1/analytics/diagnosis", params={"as_of": "junk"})
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION"
```

- [ ] **Step 2.2: Run to verify failure**

Run: `uv run pytest tests/test_analytics_diagnosis.py -k endpoint -v`
Expected: FAIL with 404 (route not found).

- [ ] **Step 2.3: Add schemas**

In `api/src/quid_api/schemas.py`, after `AnalyticsSummaryResponse`:

```python
class DiagnosisTransactionOut(_Camel):
    id: str
    name: str
    display_name: str | None = None
    amount: Decimal
    date: str

    @field_serializer("amount")
    def _ser_amount(self, value: Decimal) -> str:
        return _money_str(value)


class DiagnosisContributorOut(_Camel):
    merchant: str
    current: Decimal
    baseline: Decimal
    delta: Decimal
    is_new: bool

    @field_serializer("current", "baseline", "delta")
    def _ser_money(self, value: Decimal) -> str:
        return _money_str(value)


class DiagnosisIncreaseOut(_Camel):
    category_id: str
    category_name: str
    color: str
    current: Decimal
    baseline: Decimal
    delta: Decimal
    percent_change: float | None = None
    is_new: bool
    contributors: list[DiagnosisContributorOut] = Field(default_factory=list)
    transactions: list[DiagnosisTransactionOut] = Field(default_factory=list)

    @field_serializer("current", "baseline", "delta")
    def _ser_money(self, value: Decimal) -> str:
        return _money_str(value)


class DiagnosisDecreaseOut(_Camel):
    category_id: str
    category_name: str
    color: str
    current: Decimal
    baseline: Decimal
    delta: Decimal

    @field_serializer("current", "baseline", "delta")
    def _ser_money(self, value: Decimal) -> str:
        return _money_str(value)


class DiagnosisResponse(_Camel):
    latest_month: str | None = None
    baseline_from: str | None = None
    baseline_to: str | None = None
    baseline_month_count: int
    total_current: Decimal
    total_baseline: Decimal
    increases: list[DiagnosisIncreaseOut] = Field(default_factory=list)
    other_increases_total: Decimal
    other_increases_count: int
    decreases: list[DiagnosisDecreaseOut] = Field(default_factory=list)

    @field_serializer("total_current", "total_baseline", "other_increases_total")
    def _ser_money(self, value: Decimal) -> str:
        return _money_str(value)
```

- [ ] **Step 2.4: Add the endpoint**

In `api/src/quid_api/routers/analytics.py` add to the imports `DiagnosisResponse` (and the nested Out models used below), then:

```python
@router.get("/diagnosis", response_model=DiagnosisResponse)
async def diagnosis(
    session: SessionDep,
    as_of: Annotated[str, Query(alias="as_of")],
) -> DiagnosisResponse:
    repo = AnalyticsRepository(session)
    result = await repo.diagnosis(as_of=as_of)
    return DiagnosisResponse(
        latest_month=result.latest_month,
        baseline_from=result.baseline_from,
        baseline_to=result.baseline_to,
        baseline_month_count=result.baseline_month_count,
        total_current=result.total_current,
        total_baseline=result.total_baseline,
        increases=[
            DiagnosisIncreaseOut(
                category_id=c.category_id,
                category_name=c.category_name,
                color=c.color,
                current=c.current,
                baseline=c.baseline,
                delta=c.delta,
                percent_change=c.percent_change,
                is_new=c.is_new,
                contributors=[
                    DiagnosisContributorOut(
                        merchant=m.merchant,
                        current=m.current,
                        baseline=m.baseline,
                        delta=m.delta,
                        is_new=m.is_new,
                    )
                    for m in c.contributors
                ],
                transactions=[
                    DiagnosisTransactionOut(
                        id=t.id,
                        name=t.name,
                        display_name=t.display_name,
                        amount=t.amount,
                        date=t.date,
                    )
                    for t in c.transactions
                ],
            )
            for c in result.increases
        ],
        other_increases_total=result.other_increases_total,
        other_increases_count=result.other_increases_count,
        decreases=[
            DiagnosisDecreaseOut(
                category_id=d.category_id,
                category_name=d.category_name,
                color=d.color,
                current=d.current,
                baseline=d.baseline,
                delta=d.delta,
            )
            for d in result.decreases
        ],
    )
```

- [ ] **Step 2.5: Run tests, then full backend checks**

`uv run pytest tests/test_analytics_diagnosis.py -v` → PASS; then full backend checks.

- [ ] **Step 2.6: Commit**

```bash
git add api/src/quid_api/schemas.py api/src/quid_api/routers/analytics.py api/tests/test_analytics_diagnosis.py
git commit -m "feat(api): add /analytics/diagnosis endpoint"
```

---

### Task 3: Savings detectors in AnalyticsRepository

**Files:**
- Modify: `api/src/quid_api/repositories/analytics.py`
- Test: `api/tests/test_analytics_savings.py` (new file)

- [ ] **Step 3.1: Write failing tests**

Create `api/tests/test_analytics_savings.py` (reuse the `session`, `_seed`, `_seed_cat` helpers — import them is not possible across test modules here, so repeat the small fixtures):

```python
"""Repository-level tests for AnalyticsRepository.savings."""

from __future__ import annotations

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from quid_api.models import Category, Expense
from quid_api.repositories.analytics import AnalyticsRepository

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def session(engine: AsyncEngine):
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as sess:
        yield sess


async def _seed(session, name: str, amount: str, date: str) -> None:
    session.add(
        Expense(
            id=f"e-{name}-{date}-{amount}",
            name=name,
            amount=Decimal(amount),
            date=date,
            category_id="c1",
            note="",
            importance="important",
            category_source="import",
        )
    )


@pytest_asyncio.fixture(autouse=True)
async def category(session):
    session.add(Category(id="c1", name="Subs", color="#888888", icon="tag", description=""))
    await session.flush()


async def test_savings_empty_db(session):
    repo = AnalyticsRepository(session)
    result = await repo.savings(as_of="2026-06-10")
    assert result.latest_month is None
    assert result.price_creep == []
    assert result.stack_monthly_total == Decimal("0.00")


async def test_price_creep_detected(session):
    # Netflix at 10.99 for 4 months, then 12.99 for 3 consecutive months.
    for month in ("2025-11", "2025-12", "2026-01", "2026-02"):
        await _seed(session, "Netflix", "10.99", f"{month}-05")
    for month in ("2026-03", "2026-04", "2026-05"):
        await _seed(session, "Netflix", "12.99", f"{month}-05")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.savings(as_of="2026-06-10")
    assert len(result.price_creep) == 1
    item = result.price_creep[0]
    assert item.name == "Netflix"
    assert item.old_amount == Decimal("10.99")
    assert item.new_amount == Decimal("12.99")
    assert item.monthly_delta == Decimal("2.00")
    assert item.annual_delta == Decimal("24.00")
    assert item.since_month == "2026-03"


async def test_price_creep_requires_consecutive_new_months(session):
    # New amount appears in two NON-consecutive months -> not creep.
    for month in ("2025-11", "2025-12", "2026-01"):
        await _seed(session, "Gym", "32.00", f"{month}-05")
    await _seed(session, "Gym", "35.00", "2026-03-05")
    await _seed(session, "Gym", "35.00", "2026-05-05")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.savings(as_of="2026-06-10")
    assert result.price_creep == []


async def test_new_recurring_detected_and_creep_not_double_reported(session):
    # iCloud: first-ever in March, recurring 3 months -> NEW.
    for month in ("2026-03", "2026-04", "2026-05"):
        await _seed(session, "iCloud", "2.99", f"{month}-05")
    # Netflix creep (first-ever long ago) must NOT appear as new recurring.
    for month in ("2025-11", "2025-12", "2026-01"):
        await _seed(session, "Netflix", "10.99", f"{month}-05")
    for month in ("2026-03", "2026-04", "2026-05"):
        await _seed(session, "Netflix", "12.99", f"{month}-05")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.savings(as_of="2026-06-10")
    assert [n.name for n in result.new_recurring] == ["iCloud"]
    assert result.new_recurring[0].annual_cost == Decimal("35.88")
    assert result.new_recurring[0].first_month == "2026-03"


async def test_habit_spend(session):
    # 7 small Pret visits in the latest complete month (2026-05).
    for day in range(2, 9):
        await _seed(session, "Pret", "3.50", f"2026-05-0{day}")
    # High-ticket frequent merchant is NOT a habit (avg > 20).
    for day in range(10, 17):
        await _seed(session, "Fancy Restaurant", "45.00", f"2026-05-{day}")
    # Frequent merchant in an OLDER month doesn't count.
    for day in range(2, 9):
        await _seed(session, "Costa", "3.00", f"2026-04-0{day}")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.savings(as_of="2026-06-10")
    assert [h.name for h in result.habits] == ["Pret"]
    habit = result.habits[0]
    assert habit.count == 7
    assert habit.total == Decimal("24.50")
    assert habit.average == Decimal("3.50")


async def test_recurring_stack_active_and_estimate_scaling(session):
    # Monthly active sub: estimate = amount.
    for month in ("2026-02", "2026-03", "2026-04", "2026-05"):
        await _seed(session, "Spotify", "9.99", f"{month}-05")
    # Quarterly bill: 3 charges spanning 7 months -> estimate scaled by 3/7.
    for month in ("2025-11", "2026-02", "2026-05"):
        await _seed(session, "Water Co", "90.00", f"{month}-05")
    # Cancelled sub (last seen 3 months before latest): excluded.
    for month in ("2025-11", "2025-12", "2026-01", "2026-02"):
        await _seed(session, "Old Mag", "5.00", f"{month}-05")
    await session.flush()
    repo = AnalyticsRepository(session)
    result = await repo.savings(as_of="2026-06-10")
    names = [s.name for s in result.stack_items]
    assert "Spotify" in names and "Water Co" in names and "Old Mag" not in names
    water = next(s for s in result.stack_items if s.name == "Water Co")
    # 90 * 3 / 7 = 38.57
    assert water.monthly_estimate == Decimal("38.57")
    spotify = next(s for s in result.stack_items if s.name == "Spotify")
    assert spotify.monthly_estimate == Decimal("9.99")
    assert result.stack_monthly_total == Decimal("48.56")
    assert result.stack_annual_total == Decimal("582.72")
```

- [ ] **Step 3.2: Run to verify failure**

`uv run pytest tests/test_analytics_savings.py -v` → FAIL with `AttributeError: ... no attribute 'savings'`.

- [ ] **Step 3.3: Implement savings**

In `api/src/quid_api/repositories/analytics.py` add constants next to the diagnosis ones:

```python
#: Savings detectors scan this many trailing complete months.
_SAVINGS_WINDOW_MONTHS = 12
#: A (merchant, amount) group is "recurring" at this many distinct months.
_RECURRING_MIN_MONTHS = 3
#: Price creep: the higher amount must appear in at least this many
#: CONSECUTIVE months after the established group's last month.
_CREEP_MIN_NEW_MONTHS = 2
#: New recurring: merchant's first-ever transaction within this many months.
_NEW_RECURRING_RECENT_MONTHS = 4
#: Habit spend: >= this many transactions at <= this average ticket.
_HABIT_MIN_COUNT = 6
_HABIT_MAX_AVG_TICKET = Decimal("20.00")
_HABIT_LIMIT = 5
#: Recurring stack: group counts as active if seen within this many months.
_STACK_ACTIVE_WITHIN_MONTHS = 2
```

Dataclasses:

```python
@dataclass
class _RecurringGroup:
    key: str
    amount: Decimal
    months: list[str]


@dataclass(frozen=True)
class PriceCreepItem:
    name: str
    old_amount: Decimal
    new_amount: Decimal
    monthly_delta: Decimal
    annual_delta: Decimal
    since_month: str


@dataclass(frozen=True)
class NewRecurringItem:
    name: str
    amount: Decimal
    first_month: str
    annual_cost: Decimal


@dataclass(frozen=True)
class HabitItem:
    name: str
    count: int
    total: Decimal
    average: Decimal


@dataclass(frozen=True)
class RecurringStackItem:
    name: str
    amount: Decimal
    months_covered: int
    first_month: str
    last_month: str
    monthly_estimate: Decimal


@dataclass(frozen=True)
class SavingsResult:
    latest_month: str | None
    window_from: str | None
    price_creep: list[PriceCreepItem]
    new_recurring: list[NewRecurringItem]
    habits: list[HabitItem]
    stack_items: list[RecurringStackItem]
    stack_monthly_total: Decimal
    stack_annual_total: Decimal
```

Module helper:

```python
def _is_consecutive(months: list[str]) -> bool:
    return all(_months_between(months[i], months[i + 1]) == 1 for i in range(len(months) - 1))
```

Method on `AnalyticsRepository`:

```python
    async def savings(self, *, as_of: str) -> SavingsResult:
        """Saving-opportunity detectors over the trailing 12 complete months."""
        try:
            current_month = validate_iso_date(as_of)[:7]
        except ValueError as exc:
            raise RepositoryError(RepositoryErrorCode.VALIDATION, str(exc)) from exc

        latest_raw = (
            await self.session.execute(
                select(func.max(_MONTH_EXPR)).where(_MONTH_EXPR < current_month)
            )
        ).scalar_one_or_none()
        if latest_raw is None:
            return SavingsResult(
                latest_month=None,
                window_from=None,
                price_creep=[],
                new_recurring=[],
                habits=[],
                stack_items=[],
                stack_monthly_total=_ZERO,
                stack_annual_total=_ZERO,
            )
        latest = str(latest_raw)
        window_from = _month_add(latest, -(_SAVINGS_WINDOW_MONTHS - 1))

        key = func.lower(func.trim(Expense.name)).label("merchant_key")
        month = _MONTH_EXPR.label("month")
        group_stmt = (
            select(key, func.max(Expense.name), Expense.amount, month)
            .where(_MONTH_EXPR >= window_from, _MONTH_EXPR <= latest)
            .group_by(key, Expense.amount, month)
            .order_by(month)
        )
        rows = (await self.session.execute(group_stmt)).all()
        groups: dict[tuple[str, Decimal], _RecurringGroup] = {}
        labels: dict[str, str] = {}
        for mkey, label, amount, month_key in rows:
            k = str(mkey)
            amt = _as_decimal(amount)
            labels[k] = str(label)
            group = groups.setdefault(
                (k, amt), _RecurringGroup(key=k, amount=amt, months=[])
            )
            group.months.append(str(month_key))

        first_stmt = select(key, func.min(_MONTH_EXPR)).group_by(key)
        first_ever = {
            str(k): str(m) for k, m in (await self.session.execute(first_stmt)).all()
        }

        by_merchant: dict[str, list[_RecurringGroup]] = {}
        for group in groups.values():
            by_merchant.setdefault(group.key, []).append(group)

        price_creep: list[PriceCreepItem] = []
        for mkey, merchant_groups in by_merchant.items():
            established = [
                g for g in merchant_groups if len(g.months) >= _RECURRING_MIN_MONTHS
            ]
            best: tuple[_RecurringGroup, _RecurringGroup] | None = None
            for est in established:
                for cand in merchant_groups:
                    if cand.amount <= est.amount:
                        continue
                    if len(cand.months) < _CREEP_MIN_NEW_MONTHS:
                        continue
                    if cand.months[0] <= est.months[-1]:
                        continue
                    if not _is_consecutive(cand.months):
                        continue
                    if best is None or cand.months[0] > best[1].months[0]:
                        best = (est, cand)
            if best is not None:
                est, cand = best
                delta = (cand.amount - est.amount).quantize(_ZERO)
                price_creep.append(
                    PriceCreepItem(
                        name=labels[mkey],
                        old_amount=est.amount,
                        new_amount=cand.amount,
                        monthly_delta=delta,
                        annual_delta=(delta * 12).quantize(_ZERO),
                        since_month=cand.months[0],
                    )
                )
        price_creep.sort(key=lambda c: c.annual_delta, reverse=True)

        recent_cutoff = _month_add(latest, -(_NEW_RECURRING_RECENT_MONTHS - 1))
        new_recurring = [
            NewRecurringItem(
                name=labels[g.key],
                amount=g.amount,
                first_month=g.months[0],
                annual_cost=(g.amount * 12).quantize(_ZERO),
            )
            for g in groups.values()
            if len(g.months) >= _RECURRING_MIN_MONTHS
            and first_ever.get(g.key, "") >= recent_cutoff
        ]
        new_recurring.sort(key=lambda n: n.annual_cost, reverse=True)

        habit_stmt = (
            select(func.max(Expense.name), func.count(), func.sum(Expense.amount))
            .where(_MONTH_EXPR == latest)
            .group_by(key)
            .having(func.count() >= _HABIT_MIN_COUNT)
        )
        habits: list[HabitItem] = []
        for label, count, total in (await self.session.execute(habit_stmt)).all():
            total_d = _as_decimal(total)
            average = (total_d / int(count)).quantize(_ZERO)
            if average <= _HABIT_MAX_AVG_TICKET:
                habits.append(
                    HabitItem(name=str(label), count=int(count), total=total_d, average=average)
                )
        habits.sort(key=lambda h: h.total, reverse=True)
        habits = habits[:_HABIT_LIMIT]

        active_cutoff = _month_add(latest, -(_STACK_ACTIVE_WITHIN_MONTHS - 1))
        stack_items: list[RecurringStackItem] = []
        for group in groups.values():
            if len(group.months) < _RECURRING_MIN_MONTHS:
                continue
            if group.months[-1] < active_cutoff:
                continue
            span = _months_between(group.months[0], group.months[-1]) + 1
            estimate = min(
                group.amount,
                (group.amount * Decimal(len(group.months)) / Decimal(span)).quantize(_ZERO),
            )
            stack_items.append(
                RecurringStackItem(
                    name=labels[group.key],
                    amount=group.amount,
                    months_covered=len(group.months),
                    first_month=group.months[0],
                    last_month=group.months[-1],
                    monthly_estimate=estimate,
                )
            )
        stack_items.sort(key=lambda s: s.monthly_estimate, reverse=True)
        stack_monthly_total = sum((s.monthly_estimate for s in stack_items), _ZERO)

        return SavingsResult(
            latest_month=latest,
            window_from=window_from,
            price_creep=price_creep,
            new_recurring=new_recurring,
            habits=habits,
            stack_items=stack_items,
            stack_monthly_total=stack_monthly_total,
            stack_annual_total=(stack_monthly_total * 12).quantize(_ZERO),
        )
```

- [ ] **Step 3.4: Run tests, then full backend checks**

`uv run pytest tests/test_analytics_savings.py -v` → PASS; then full backend checks. Note: in `test_recurring_stack_active_and_estimate_scaling` the Netflix-style creep stack interplay is intentionally absent — keep the test data as written.

- [ ] **Step 3.5: Commit**

```bash
git add api/src/quid_api/repositories/analytics.py api/tests/test_analytics_savings.py
git commit -m "feat(api): add savings detectors (price creep, new recurring, habits, stack)"
```

---

### Task 4: /analytics/savings endpoint

**Files:**
- Modify: `api/src/quid_api/schemas.py`
- Modify: `api/src/quid_api/routers/analytics.py`
- Test: `api/tests/test_analytics_savings.py` (extend)

- [ ] **Step 4.1: Write failing endpoint test**

Append to `api/tests/test_analytics_savings.py`:

```python
from typing import Any

from httpx import AsyncClient


async def _api_cat(client: AsyncClient, name: str) -> dict[str, Any]:
    res = await client.post("/api/v1/categories", json={"name": name})
    assert res.status_code == 201
    return res.json()  # type: ignore[no-any-return]


async def _api_expense(client: AsyncClient, *, name: str, amount: str, date: str, category_id: str) -> None:
    res = await client.post(
        "/api/v1/expenses",
        json={"name": name, "amount": amount, "date": date, "categoryId": category_id},
    )
    assert res.status_code == 201, res.text


async def test_savings_endpoint_shape(app_client):
    cat = await _api_cat(app_client, "Subscriptions")
    for month in ("2026-03", "2026-04", "2026-05"):
        await _api_expense(
            app_client, name="iCloud", amount="2.99", date=f"{month}-05", category_id=cat["id"]
        )
    res = await app_client.get("/api/v1/analytics/savings", params={"as_of": "2026-06-10"})
    assert res.status_code == 200
    body = res.json()
    assert body["latestMonth"] == "2026-05"
    assert body["priceCreep"] == []
    assert body["newRecurring"][0]["name"] == "iCloud"
    assert body["newRecurring"][0]["annualCost"] == "35.88"
    assert body["recurringStack"]["monthlyTotal"] == "2.99"
    assert body["recurringStack"]["items"][0]["monthlyEstimate"] == "2.99"
    assert body["habits"] == []
```

- [ ] **Step 4.2: Run to verify failure** — `uv run pytest tests/test_analytics_savings.py -k endpoint -v` → 404.

- [ ] **Step 4.3: Add schemas**

In `api/src/quid_api/schemas.py` after the diagnosis schemas:

```python
class PriceCreepOut(_Camel):
    name: str
    old_amount: Decimal
    new_amount: Decimal
    monthly_delta: Decimal
    annual_delta: Decimal
    since_month: str

    @field_serializer("old_amount", "new_amount", "monthly_delta", "annual_delta")
    def _ser_money(self, value: Decimal) -> str:
        return _money_str(value)


class NewRecurringOut(_Camel):
    name: str
    amount: Decimal
    first_month: str
    annual_cost: Decimal

    @field_serializer("amount", "annual_cost")
    def _ser_money(self, value: Decimal) -> str:
        return _money_str(value)


class HabitOut(_Camel):
    name: str
    count: int
    total: Decimal
    average: Decimal

    @field_serializer("total", "average")
    def _ser_money(self, value: Decimal) -> str:
        return _money_str(value)


class RecurringStackItemOut(_Camel):
    name: str
    amount: Decimal
    months_covered: int
    first_month: str
    last_month: str
    monthly_estimate: Decimal

    @field_serializer("amount", "monthly_estimate")
    def _ser_money(self, value: Decimal) -> str:
        return _money_str(value)


class RecurringStackOut(_Camel):
    items: list[RecurringStackItemOut] = Field(default_factory=list)
    monthly_total: Decimal
    annual_total: Decimal

    @field_serializer("monthly_total", "annual_total")
    def _ser_money(self, value: Decimal) -> str:
        return _money_str(value)


class SavingsResponse(_Camel):
    latest_month: str | None = None
    window_from: str | None = None
    price_creep: list[PriceCreepOut] = Field(default_factory=list)
    new_recurring: list[NewRecurringOut] = Field(default_factory=list)
    habits: list[HabitOut] = Field(default_factory=list)
    recurring_stack: RecurringStackOut
```

- [ ] **Step 4.4: Add the endpoint**

In `api/src/quid_api/routers/analytics.py`:

```python
@router.get("/savings", response_model=SavingsResponse)
async def savings(
    session: SessionDep,
    as_of: Annotated[str, Query(alias="as_of")],
) -> SavingsResponse:
    repo = AnalyticsRepository(session)
    result = await repo.savings(as_of=as_of)
    return SavingsResponse(
        latest_month=result.latest_month,
        window_from=result.window_from,
        price_creep=[
            PriceCreepOut(
                name=i.name,
                old_amount=i.old_amount,
                new_amount=i.new_amount,
                monthly_delta=i.monthly_delta,
                annual_delta=i.annual_delta,
                since_month=i.since_month,
            )
            for i in result.price_creep
        ],
        new_recurring=[
            NewRecurringOut(
                name=i.name, amount=i.amount, first_month=i.first_month, annual_cost=i.annual_cost
            )
            for i in result.new_recurring
        ],
        habits=[
            HabitOut(name=i.name, count=i.count, total=i.total, average=i.average)
            for i in result.habits
        ],
        recurring_stack=RecurringStackOut(
            items=[
                RecurringStackItemOut(
                    name=i.name,
                    amount=i.amount,
                    months_covered=i.months_covered,
                    first_month=i.first_month,
                    last_month=i.last_month,
                    monthly_estimate=i.monthly_estimate,
                )
                for i in result.stack_items
            ],
            monthly_total=result.stack_monthly_total,
            annual_total=result.stack_annual_total,
        ),
    )
```

- [ ] **Step 4.5: Run tests + full backend checks** → PASS.

- [ ] **Step 4.6: Commit**

```bash
git add api/src/quid_api/schemas.py api/src/quid_api/routers/analytics.py api/tests/test_analytics_savings.py
git commit -m "feat(api): add /analytics/savings endpoint"
```

---

### Task 5: AnalyticsNarrative model, migration 0021, repository

**Files:**
- Modify: `api/src/quid_api/models.py`
- Create: `api/alembic/versions/0021_analytics_narratives.py`
- Create: `api/src/quid_api/repositories/analytics_narrative.py`
- Test: `api/tests/test_analytics_narrative.py` (new file)

- [ ] **Step 5.1: Write failing repository tests**

```python
"""Tests for the analytics narrative store (the analytics layer's only write path)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from quid_api.repositories.analytics_narrative import AnalyticsNarrativeRepository

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def session(engine: AsyncEngine):
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as sess:
        yield sess


async def test_get_latest_empty(session):
    repo = AnalyticsNarrativeRepository(session)
    assert await repo.get_latest() is None


async def test_upsert_and_get_latest(session):
    repo = AnalyticsNarrativeRepository(session)
    row = await repo.upsert(month="2026-04", content="April summary.", model="m1")
    assert row.month == "2026-04"
    later = await repo.upsert(month="2026-05", content="May summary.", model="m1")
    assert later.month == "2026-05"
    latest = await repo.get_latest()
    assert latest is not None and latest.month == "2026-05"


async def test_upsert_same_month_replaces(session):
    repo = AnalyticsNarrativeRepository(session)
    first = await repo.upsert(month="2026-05", content="v1", model="m1")
    second = await repo.upsert(month="2026-05", content="v2", model="m2")
    assert second.id == first.id
    assert second.content == "v2"
    assert second.model == "m2"
    latest = await repo.get_latest()
    assert latest is not None and latest.content == "v2"
```

- [ ] **Step 5.2: Run to verify failure** — `uv run pytest tests/test_analytics_narrative.py -v` → ImportError.

- [ ] **Step 5.3: Add the model**

In `api/src/quid_api/models.py` (add `UniqueConstraint` to the existing `sqlalchemy` import if missing), append:

```python
class AnalyticsNarrative(Base):
    """Stored AI narrative for the Analytics page, one row per analysed month.

    Generation is strictly on-demand (user clicks Generate); regenerating the
    same month replaces that month's row.
    """

    __tablename__ = "analytics_narratives"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    month: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (UniqueConstraint("month", name="uq_analytics_narratives_month"),)
```

- [ ] **Step 5.4: Add migration**

Create `api/alembic/versions/0021_analytics_narratives.py`:

```python
"""analytics narratives

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analytics_narratives",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("month", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.UniqueConstraint("month", name="uq_analytics_narratives_month"),
    )


def downgrade() -> None:
    op.drop_table("analytics_narratives")
```

- [ ] **Step 5.5: Add the repository**

Create `api/src/quid_api/repositories/analytics_narrative.py`:

```python
"""Persistence for the on-demand Analytics AI narrative.

This is deliberately the ONLY write path in the analytics layer; the
aggregation repository (``repositories/analytics.py``) stays read-only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from quid_api.models import AnalyticsNarrative

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class AnalyticsNarrativeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_latest(self) -> AnalyticsNarrative | None:
        stmt = select(AnalyticsNarrative).order_by(AnalyticsNarrative.month.desc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def upsert(self, *, month: str, content: str, model: str) -> AnalyticsNarrative:
        stmt = select(AnalyticsNarrative).where(AnalyticsNarrative.month == month)
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            row = AnalyticsNarrative(
                id=str(uuid4()),
                month=month,
                content=content,
                generated_at=_now_iso(),
                model=model,
            )
            self.session.add(row)
        else:
            row.content = content
            row.model = model
            row.generated_at = _now_iso()
        await self.session.flush()
        return row
```

Before finalising, check the id convention in `api/src/quid_api/repositories/expenses.py` (one `grep -n "uuid" api/src/quid_api/repositories/expenses.py`) and match it (`str(uuid4())` vs `uuid4().hex`).

- [ ] **Step 5.6: Run tests + full backend checks** → PASS. (The test engine creates tables from `Base.metadata`, so the model alone makes tests pass; the migration is for real DBs — verify it parses with `uv run alembic upgrade head` against the dev DB later, in Task 14.)

- [ ] **Step 5.7: Commit**

```bash
git add api/src/quid_api/models.py api/alembic/versions/0021_analytics_narratives.py api/src/quid_api/repositories/analytics_narrative.py api/tests/test_analytics_narrative.py
git commit -m "feat(api): add analytics_narratives table and repository (migration 0021)"
```

---

### Task 6: ai_narrative module

**Files:**
- Create: `api/src/quid_api/ai_narrative.py`
- Test: `api/tests/test_ai_narrative.py` (new file)

- [ ] **Step 6.1: Write failing tests**

```python
"""Tests for the analytics narrative OpenRouter module."""

from __future__ import annotations

import httpx
import pytest

from quid_api.ai_narrative import generate_narrative
from quid_api.errors import RepositoryError

pytestmark = pytest.mark.asyncio


def _mock_client(content: str | None, status: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if content is None:
            return httpx.Response(status, json={})
        return httpx.Response(
            status, json={"choices": [{"message": {"content": content}}]}
        )

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_missing_api_key_raises():
    with pytest.raises(RepositoryError, match="QUID_OPENROUTER_API_KEY"):
        await generate_narrative("{}", api_key=None, model="m")


async def test_happy_path_returns_text():
    client = _mock_client("Your spending rose 12% driven by Eating Out.")
    out = await generate_narrative('{"month": "2026-05"}', api_key="k", model="m", client=client)
    assert "Eating Out" in out


async def test_http_error_status_raises():
    client = _mock_client("irrelevant", status=500)
    with pytest.raises(RepositoryError, match="HTTP 500"):
        await generate_narrative("{}", api_key="k", model="m", client=client)


async def test_empty_content_raises():
    client = _mock_client(None)
    with pytest.raises(RepositoryError):
        await generate_narrative("{}", api_key="k", model="m", client=client)
```

- [ ] **Step 6.2: Run to verify failure** — ImportError.

- [ ] **Step 6.3: Implement**

Create `api/src/quid_api/ai_narrative.py` (mirrors `ai_freeform.py`'s transport/error handling; plain-text response, no JSON schema):

```python
"""AI narrative for the Analytics page.

Takes a compact JSON facts payload (the same aggregates the page renders:
verdict numbers, top increases with contributing merchants, detector findings,
recurring-stack total) and asks OpenRouter for a short plain-language summary.
Strictly on-demand — callers decide when to spend the API call.
"""

from __future__ import annotations

import logging

import httpx

from quid_api.ai_categorization import OPENROUTER_CHAT_COMPLETIONS_URL
from quid_api.errors import RepositoryError, RepositoryErrorCode

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a personal-finance analyst. You write short, plain-language "
    "summaries of a single month's spending. Respond with prose only — no "
    "markdown, no headings, no bullet points."
)


def _build_prompt(facts_json: str) -> str:
    return (
        "Summarise this month's spending for the user in 3-6 sentences.\n\n"
        "Rules:\n"
        "- Name the biggest driver of any change vs the user's average.\n"
        "- Point at the most concrete saving opportunities in the data "
        "(price increases, new subscriptions, habit spend), with their costs.\n"
        "- Use ONLY numbers present in the data below; never invent figures.\n"
        "- Currency amounts are plain decimals; present them naturally.\n"
        "- Address the user as 'you'.\n\n"
        f"Data (JSON):\n{facts_json}"
    )


async def generate_narrative(
    facts_json: str,
    *,
    api_key: str | None,
    model: str,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Generate the narrative text via OpenRouter.

    Raises ``RepositoryError`` (VALIDATION) when the key is missing or the
    call fails, mirroring ``ai_freeform.parse_freeform_transactions``.
    """
    if api_key is None or api_key.strip() == "":
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "AI insights require QUID_OPENROUTER_API_KEY to be configured.",
        )

    body = {
        "model": model,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(facts_json)},
        ],
    }
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=60)
    logger.info("ai.narrative.request model=%s chars=%d", model, len(facts_json))
    try:
        try:
            response = await active_client.post(
                OPENROUTER_CHAT_COMPLETIONS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/grant/quid",
                    "X-OpenRouter-Title": "Quid",
                },
                json=body,
            )
        except httpx.HTTPError as exc:
            logger.warning("ai.narrative.http_error err=%s", exc)
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                f"AI narrative request failed: {exc}",
            ) from exc
        if response.status_code >= 400:
            logger.warning(
                "ai.narrative.bad_status status=%d body=%r",
                response.status_code,
                response.text[:500],
            )
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                f"AI narrative generation failed with HTTP {response.status_code}.",
            )
        payload = response.json()
    finally:
        if owns_client:
            await active_client.aclose()

    content = _extract_content(payload)
    logger.info("ai.narrative.done chars=%d model=%s", len(content), model)
    return content


def _extract_content(payload: object) -> str:
    if not isinstance(payload, dict):
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION, "OpenRouter returned an invalid response."
        )
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise RepositoryError(RepositoryErrorCode.VALIDATION, "OpenRouter returned no choices.")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION, "OpenRouter returned an invalid message."
        )
    content = message.get("content")
    if not isinstance(content, str) or content.strip() == "":
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION, "OpenRouter returned an empty message."
        )
    return content.strip()
```

- [ ] **Step 6.4: Run tests + full backend checks** → PASS.

- [ ] **Step 6.5: Commit**

```bash
git add api/src/quid_api/ai_narrative.py api/tests/test_ai_narrative.py
git commit -m "feat(api): add ai_narrative OpenRouter module"
```

---

### Task 7: GET/POST /analytics/narrative endpoints

**Files:**
- Modify: `api/src/quid_api/schemas.py`
- Modify: `api/src/quid_api/routers/analytics.py`
- Test: `api/tests/test_analytics_narrative.py` (extend)

- [ ] **Step 7.1: Write failing endpoint tests**

Append to `api/tests/test_analytics_narrative.py`:

```python
from typing import Any

from httpx import AsyncClient


async def _api_cat(client: AsyncClient, name: str) -> dict[str, Any]:
    res = await client.post("/api/v1/categories", json={"name": name})
    assert res.status_code == 201
    return res.json()  # type: ignore[no-any-return]


async def _api_expense(client: AsyncClient, *, name: str, amount: str, date: str, category_id: str) -> None:
    res = await client.post(
        "/api/v1/expenses",
        json={"name": name, "amount": amount, "date": date, "categoryId": category_id},
    )
    assert res.status_code == 201, res.text


async def test_get_narrative_empty(app_client):
    res = await app_client.get("/api/v1/analytics/narrative")
    assert res.status_code == 200
    assert res.json() == {"narrative": None}


async def test_post_narrative_without_key_fails_cleanly(app_client):
    # conftest's app_client runs with openrouter_api_key=None.
    cat = await _api_cat(app_client, "Groceries")
    for month in ("2026-03", "2026-04", "2026-05"):
        await _api_expense(
            app_client, name="Tesco", amount="50.00", date=f"{month}-10", category_id=cat["id"]
        )
    res = await app_client.post("/api/v1/analytics/narrative", json={"asOf": "2026-06-10"})
    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "VALIDATION"
    assert "QUID_OPENROUTER_API_KEY" in body["message"]


async def test_post_narrative_no_data_fails(app_client, monkeypatch):
    res = await app_client.post("/api/v1/analytics/narrative", json={"asOf": "2026-06-10"})
    assert res.status_code == 422
    assert "complete month" in res.json()["message"]


async def test_post_narrative_generates_and_persists(app_client, monkeypatch):
    cat = await _api_cat(app_client, "Groceries")
    for month in ("2026-03", "2026-04", "2026-05"):
        await _api_expense(
            app_client, name="Tesco", amount="50.00", date=f"{month}-10", category_id=cat["id"]
        )

    captured: dict[str, Any] = {}

    async def fake_generate(facts_json, *, api_key, model, client=None):
        captured["facts"] = facts_json
        return "Spending was steady."

    # The missing-key check lives inside ai_narrative.generate_narrative, which
    # this fake replaces — so the call succeeds despite app_client having no key.
    monkeypatch.setattr("quid_api.routers.analytics.ai_generate_narrative", fake_generate)

    res = await app_client.post("/api/v1/analytics/narrative", json={"asOf": "2026-06-10"})
    assert res.status_code == 200, res.text
    body = res.json()["narrative"]
    assert body["month"] == "2026-05"
    assert body["content"] == "Spending was steady."
    assert "2026-05" in captured["facts"]

    # Persisted: GET returns it.
    res2 = await app_client.get("/api/v1/analytics/narrative")
    assert res2.json()["narrative"]["content"] == "Spending was steady."
```

- [ ] **Step 7.2: Run to verify failure** — 404 on the new routes.

- [ ] **Step 7.3: Add schemas**

```python
class NarrativeOut(_Camel):
    month: str
    content: str
    generated_at: str
    model: str


class NarrativeResponse(_Camel):
    narrative: NarrativeOut | None = None


class NarrativeGenerateRequest(_Camel):
    as_of: str
```

- [ ] **Step 7.4: Add endpoints**

In `api/src/quid_api/routers/analytics.py`. New imports:

```python
from quid_api.ai_narrative import generate_narrative as ai_generate_narrative
from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.repositories.analytics_narrative import AnalyticsNarrativeRepository
from quid_api.settings import Settings, get_settings
```

(Check how `routers/expenses.py` declares its settings dependency and match it — it is `Annotated[Settings, Depends(get_settings)]`.)

```python
import json

SettingsDep = Annotated[Settings, Depends(get_settings)]


def _narrative_out(row: object) -> NarrativeOut:
    return NarrativeOut(
        month=row.month,  # type: ignore[attr-defined]
        content=row.content,  # type: ignore[attr-defined]
        generated_at=row.generated_at,  # type: ignore[attr-defined]
        model=row.model,  # type: ignore[attr-defined]
    )
```

(If mypy is unhappy with `object`, import `AnalyticsNarrative` under `TYPE_CHECKING` and type it properly — prefer that.)

```python
@router.get("/narrative", response_model=NarrativeResponse)
async def latest_narrative(session: SessionDep) -> NarrativeResponse:
    row = await AnalyticsNarrativeRepository(session).get_latest()
    return NarrativeResponse(narrative=None if row is None else _narrative_out(row))


@router.post("/narrative", response_model=NarrativeResponse)
async def generate_narrative(
    payload: NarrativeGenerateRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> NarrativeResponse:
    repo = AnalyticsRepository(session)
    diag = await repo.diagnosis(as_of=payload.as_of)
    if diag.latest_month is None:
        raise RepositoryError(
            RepositoryErrorCode.VALIDATION,
            "Not enough data: at least one complete month is needed.",
        )
    sav = await repo.savings(as_of=payload.as_of)
    facts = {
        "month": diag.latest_month,
        "totalCurrent": str(diag.total_current),
        "totalBaseline": str(diag.total_baseline),
        "baselineMonths": diag.baseline_month_count,
        "increases": [
            {
                "category": c.category_name,
                "current": str(c.current),
                "baselineAvg": str(c.baseline),
                "delta": str(c.delta),
                "isNew": c.is_new,
                "topMerchants": [
                    {"name": m.merchant, "delta": str(m.delta), "isNew": m.is_new}
                    for m in c.contributors
                ],
            }
            for c in diag.increases[:6]
        ],
        "decreases": [
            {"category": d.category_name, "delta": str(d.delta)} for d in diag.decreases[:4]
        ],
        "priceCreep": [
            {
                "name": i.name,
                "oldAmount": str(i.old_amount),
                "newAmount": str(i.new_amount),
                "annualDelta": str(i.annual_delta),
            }
            for i in sav.price_creep
        ],
        "newRecurring": [
            {"name": i.name, "monthly": str(i.amount), "annualCost": str(i.annual_cost)}
            for i in sav.new_recurring
        ],
        "habits": [
            {"name": i.name, "visits": i.count, "total": str(i.total)} for i in sav.habits
        ],
        "recurringStackMonthly": str(sav.stack_monthly_total),
    }
    content = await ai_generate_narrative(
        json.dumps(facts),
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
    )
    nrepo = AnalyticsNarrativeRepository(session)
    row = await nrepo.upsert(
        month=diag.latest_month, content=content, model=settings.openrouter_model
    )
    await session.commit()
    return NarrativeResponse(narrative=_narrative_out(row))
```

Note: the router module previously had zero commits; this POST is the deliberate exception (documented in Task 14's CLAUDE.md update). Also update the router's module docstring ("Read-only analytics endpoints") to mention the narrative exception.

- [ ] **Step 7.5: Run tests + full backend checks** → PASS.

- [ ] **Step 7.6: Commit**

```bash
git add api/src/quid_api/schemas.py api/src/quid_api/routers/analytics.py api/tests/test_analytics_narrative.py
git commit -m "feat(api): add GET/POST /analytics/narrative endpoints"
```

---

### Task 8: Backend cleanup — trim summary, remove dead endpoints/schemas/repo methods, api/README

**Files:**
- Modify: `api/src/quid_api/routers/analytics.py`
- Modify: `api/src/quid_api/repositories/analytics.py`
- Modify: `api/src/quid_api/schemas.py`
- Modify: `api/tests/test_analytics_api.py`
- Modify: `api/README.md` (analytics section, lines ~467–546)

- [ ] **Step 8.1: Trim the summary endpoint and schema**

New `AnalyticsSummaryResponse` (replaces the old one in `schemas.py`):

```python
class AnalyticsSummaryResponse(_Camel):
    """Headline numbers for the Analytics verdict header + empty state."""

    total: Decimal
    transaction_count: int
    months_covered: int
    complete_months_covered: int
    average_per_complete_month: Decimal
    latest_month: str | None = None
    latest_month_total: Decimal
    current_month: str | None = None
    current_month_to_date: Decimal = Decimal("0.00")
    current_month_projected: Decimal = Decimal("0.00")
    current_month_pace_vs_average: float | None = None

    @field_serializer(
        "total",
        "average_per_complete_month",
        "latest_month_total",
        "current_month_to_date",
        "current_month_projected",
    )
    def _ser_money(self, value: Decimal) -> str:
        return _money_str(value)
```

New `summary()` in the router (replaces the old one; note it no longer calls `category_trends`):

```python
@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def summary(
    session: SessionDep,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    as_of: AsOf = None,
) -> AnalyticsSummaryResponse:
    repo = AnalyticsRepository(session)
    months = await repo.monthly_totals(date_from=date_from, date_to=date_to)

    total = sum((m.total for m in months), _ZERO)
    transaction_count = sum(m.count for m in months)
    months_covered = len(months)
    if as_of is not None:
        validate_iso_date(as_of)
    current_month = as_of[:7] if as_of is not None else None
    complete_months = [m for m in months if m.month != current_month] if current_month else months
    complete_months_covered = len(complete_months)
    complete_total = sum((m.total for m in complete_months), _ZERO)
    average_per_complete_month = (
        (complete_total / complete_months_covered).quantize(_ZERO)
        if complete_months_covered
        else _ZERO
    )

    latest = complete_months[-1] if complete_months else None
    current_month_row = (
        next((m for m in months if m.month == current_month), None) if current_month else None
    )
    current_month_to_date = current_month_row.total if current_month_row else _ZERO
    current_month_projected = _ZERO
    current_month_pace_vs_average = None
    if as_of is not None and current_month and current_month_row is not None:
        day_of_month = int(validate_iso_date(as_of)[8:10])
        projected = current_month_to_date / day_of_month * Decimal(str(_month_days(current_month)))
        current_month_projected = projected.quantize(_ZERO)
        current_month_pace_vs_average = _percent_change(
            current_month_projected, average_per_complete_month
        )

    return AnalyticsSummaryResponse(
        total=total,
        transaction_count=transaction_count,
        months_covered=months_covered,
        complete_months_covered=complete_months_covered,
        average_per_complete_month=average_per_complete_month,
        latest_month=latest.month if latest else None,
        latest_month_total=latest.total if latest else _ZERO,
        current_month=current_month,
        current_month_to_date=current_month_to_date,
        current_month_projected=current_month_projected,
        current_month_pace_vs_average=current_month_pace_vs_average,
    )
```

- [ ] **Step 8.2: Delete dead endpoints, repo methods, schemas**

- Router: delete the `category_trends`, `category_comparison`, `top_merchants`, `importance_breakdown`, `weekday_breakdown`, `recurring`, `large_transactions`, `distribution`, `importance_trend` endpoint functions; remove `import math` and all now-unused schema imports. `calendar`, `_month_days`, `_percent_change` stay (used by summary).
- Repository: delete methods `category_trends`, `category_movers`, `top_merchants`, `importance_breakdown`, `recurring`, `large_transactions`, `distribution`, `importance_trend`, `weekday_breakdown`, and helper `_category_totals`; delete dataclasses `CategoryTrendSeries`, `CategoryMover`, `TopMerchant`, `ImportancePoint`, `RecurringItem`, `LargeTransaction`, `ImportanceTrendPoint`, `ImportanceTrendSeries`, `WeekdayPoint`. Keep `monthly_totals`, `_window`, `_category_names`, `_DAY_EXPR` can go too if now unused (it will be — `weekday_breakdown` was its only consumer). Check `UNCATEGORIZED_ID` import usage in `_category_names` body before removing imports.
- Schemas: delete `CategoryTrendPointOut`, `CategoryTrendSeriesOut`, `CategoryTrendsResponse`, `CategoryMoverOut`, `CategoryComparisonResponse`, `TopMerchantOut`, `TopMerchantsResponse`, `ImportanceBreakdownPointOut`, `ImportanceBreakdownResponse`, `WeekdayBreakdownPointOut`, `WeekdayBreakdownResponse`, `RecurringItemOut`, `RecurringResponse`, `LargeTransactionOut`, `LargeTransactionsResponse`, `DistributionResponse`, `ImportanceTrendPointOut`, `ImportanceTrendSeriesOut`, `ImportanceTrendResponse`.
- Grep for any other usage before deleting: `grep -rn "RecurringResponse\|CategoryTrendsResponse\|LargeTransactionsResponse" api/src api/tests`.

- [ ] **Step 8.3: Update `api/tests/test_analytics_api.py`**

Delete tests covering removed endpoints (`category-trends`, `category-comparison`, `top-merchants`, `recurring`, `large-transactions`, `distribution`, `importance-trend`, `importance-breakdown`, `weekday-breakdown`). Update summary tests: remove assertions on dropped fields (`averagePerMonth`, `averagePerTransaction`, `busiestMonth*`, `topCategory*`, `monthOverMonth*`, `previousMonthTotal`); keep/extend assertions on the retained fields (`completeMonthsCovered`, `averagePerCompleteMonth`, `latestMonth`, `latestMonthTotal`, `currentMonth*` projection behaviour with `as_of`). Keep `monthly-totals` tests untouched.

- [ ] **Step 8.4: Rewrite the analytics section of `api/README.md`**

Replace the whole "## Analytics" section (starts ~line 467) with:

```markdown
## Analytics

Spending insights over the `expenses` table, aggregated server-side
(`/api/v1/analytics`, web UI **Analytics** page). Aggregation endpoints are
read-only; the one write path is the stored AI narrative (below). Money fields
are canonical 2dp strings. Month grouping uses the 7-char `YYYY-MM` prefix and
works for both date-only and timestamped expense dates.

The insight endpoints take a required `as_of` (`YYYY-MM-DD`, the client's
"today") and have FIXED windows anchored on the latest **complete** month
(the last month strictly before `as_of`'s month) — they do not accept
`date_from`/`date_to`:

- `GET /api/v1/analytics/diagnosis?as_of=` — "what went up": each category's
  latest-complete-month spend vs its trailing-average baseline (mean over up to
  6 complete months before the latest one; zero-spend months count as 0).
  Returns `{ latestMonth, baselineFrom, baselineTo, baselineMonthCount,
  totalCurrent, totalBaseline, increases, otherIncreasesTotal,
  otherIncreasesCount, decreases }`. Each increase carries `current`,
  `baseline`, `delta`, `percentChange` (`null` for new spending), `isNew`, top-3
  `contributors` (merchant vs its own baseline, `isNew` flag) and the month's
  `transactions` for that category. Increases under £10 AND under 10% are
  rolled into the `otherIncreases*` line. Decreases are returned separately.
- `GET /api/v1/analytics/savings?as_of=` — saving opportunities over the
  trailing 12 complete months: `{ priceCreep, newRecurring, habits,
  recurringStack }`.
  - `priceCreep`: an established recurring charge (same merchant+amount ≥3
    distinct months) followed by a HIGHER amount in ≥2 consecutive months
    (`oldAmount`, `newAmount`, `monthlyDelta`, `annualDelta`, `sinceMonth`).
  - `newRecurring`: merchant whose first-ever transaction is within the last
    4 complete months and that already recurs (≥3 months, same amount).
  - `habits`: latest complete month's merchants with ≥6 transactions at ≤£20
    average ticket (top 5 by total).
  - `recurringStack`: currently-active recurring groups (seen within 2 months);
    `monthlyEstimate = amount × monthsCovered ÷ monthsSpanned` (capped at
    `amount`), plus `monthlyTotal` / `annualTotal`.
- `GET /api/v1/analytics/narrative` — the stored AI narrative
  (`{ narrative: { month, content, generatedAt, model } | null }`).
- `POST /api/v1/analytics/narrative` (body `{ "asOf": "YYYY-MM-DD" }`) —
  generates a 3–6 sentence plain-language summary of the latest complete month
  via OpenRouter (needs `QUID_OPENROUTER_API_KEY`; 422 without it), stores it
  (one row per month, regenerate replaces), and returns it. Strictly
  on-demand: nothing is generated automatically.

The two remaining window-style endpoints accept optional inclusive
`date_from` / `date_to` (`YYYY-MM-DD`; half-open internally so a timestamped
boundary-day row is counted):

- `GET /api/v1/analytics/summary` — verdict-header numbers: `total`,
  `transactionCount`, `monthsCovered`, `completeMonthsCovered`,
  `averagePerCompleteMonth`, `latestMonth(+Total)`, and (when `as_of` is given)
  the in-progress month run-rate: `currentMonth`, `currentMonthToDate`,
  `currentMonthProjected`, `currentMonthPaceVsAverage`.
- `GET /api/v1/analytics/monthly-totals` — `{ months: [{ month, total,
  count }], total, average, count }`, ascending. Feeds the trend chart and
  sparkline.

A bad date param returns 422 with `{ "code": "VALIDATION" }`.
```

- [ ] **Step 8.5: Full backend checks** → all green. Expect mypy/ruff to catch leftover imports.

- [ ] **Step 8.6: Commit**

```bash
git add api/src/quid_api/routers/analytics.py api/src/quid_api/repositories/analytics.py api/src/quid_api/schemas.py api/tests/test_analytics_api.py api/README.md
git commit -m "feat(api): trim analytics surface to summary/monthly-totals/diagnosis/savings/narrative"
```

---

### Task 9: Frontend types + repository (additive)

**Files:**
- Modify: `webui/src/lib/types/domain.ts` (analytics section is lines ~481–670)
- Modify: `webui/src/lib/repos/types.ts`
- Modify: `webui/src/lib/repos/httpAnalyticsRepository.ts`

The old page keeps compiling in this task: ADD the new types/methods, do not delete anything yet (deletion happens in Task 12). One exception: `AnalyticsSummary` must be REPLACED (the backend changed in Task 8), and the old page reads dropped fields — so this task also patches the 3 spots in the old page that reference them, keeping `npm run check` green without building the new page yet.

- [ ] **Step 9.1: Replace `AnalyticsSummary` and add new types in `domain.ts`**

Replace the existing `AnalyticsSummary` interface with:

```typescript
export interface AnalyticsSummary {
	total: string;
	transactionCount: number;
	monthsCovered: number;
	completeMonthsCovered: number;
	averagePerCompleteMonth: string;
	latestMonth: string | null;
	latestMonthTotal: string;
	currentMonth: string | null;
	currentMonthToDate: string;
	currentMonthProjected: string;
	currentMonthPaceVsAverage: number | null;
}
```

Add the new types after it:

```typescript
export interface DiagnosisTransaction {
	id: string;
	name: string;
	displayName: string | null;
	amount: string;
	date: string;
}

export interface DiagnosisContributor {
	merchant: string;
	current: string;
	baseline: string;
	delta: string;
	isNew: boolean;
}

export interface DiagnosisIncrease {
	categoryId: string;
	categoryName: string;
	color: string;
	current: string;
	baseline: string;
	delta: string;
	percentChange: number | null;
	isNew: boolean;
	contributors: DiagnosisContributor[];
	transactions: DiagnosisTransaction[];
}

export interface DiagnosisDecrease {
	categoryId: string;
	categoryName: string;
	color: string;
	current: string;
	baseline: string;
	delta: string;
}

export interface DiagnosisResult {
	latestMonth: string | null;
	baselineFrom: string | null;
	baselineTo: string | null;
	baselineMonthCount: number;
	totalCurrent: string;
	totalBaseline: string;
	increases: DiagnosisIncrease[];
	otherIncreasesTotal: string;
	otherIncreasesCount: number;
	decreases: DiagnosisDecrease[];
}

export interface PriceCreepItem {
	name: string;
	oldAmount: string;
	newAmount: string;
	monthlyDelta: string;
	annualDelta: string;
	sinceMonth: string;
}

export interface NewRecurringItem {
	name: string;
	amount: string;
	firstMonth: string;
	annualCost: string;
}

export interface HabitItem {
	name: string;
	count: number;
	total: string;
	average: string;
}

export interface RecurringStackItem {
	name: string;
	amount: string;
	monthsCovered: number;
	firstMonth: string;
	lastMonth: string;
	monthlyEstimate: string;
}

export interface RecurringStack {
	items: RecurringStackItem[];
	monthlyTotal: string;
	annualTotal: string;
}

export interface SavingsResult {
	latestMonth: string | null;
	windowFrom: string | null;
	priceCreep: PriceCreepItem[];
	newRecurring: NewRecurringItem[];
	habits: HabitItem[];
	recurringStack: RecurringStack;
}

export interface AnalyticsNarrative {
	month: string;
	content: string;
	generatedAt: string;
	model: string;
}

export interface NarrativeResult {
	narrative: AnalyticsNarrative | null;
}
```

Make sure these are re-exported wherever `$types` re-exports `domain.ts` types (check `webui/src/lib/types/index.ts`).

- [ ] **Step 9.2: Extend the repository interface and HTTP repo**

In `webui/src/lib/repos/types.ts`, add to the `AnalyticsRepository` interface (keep existing members for now):

```typescript
	diagnosis(asOf: string): Promise<DiagnosisResult>;
	savings(asOf: string): Promise<SavingsResult>;
	narrative(): Promise<NarrativeResult>;
	generateNarrative(input: { asOf: string }): Promise<NarrativeResult>;
```

In `webui/src/lib/repos/httpAnalyticsRepository.ts`, add the methods:

```typescript
	async diagnosis(asOf: string): Promise<DiagnosisResult> {
		return this.client.request<DiagnosisResult>('api/v1/analytics/diagnosis', {
			query: { as_of: asOf }
		});
	}

	async savings(asOf: string): Promise<SavingsResult> {
		return this.client.request<SavingsResult>('api/v1/analytics/savings', {
			query: { as_of: asOf }
		});
	}

	async narrative(): Promise<NarrativeResult> {
		return this.client.request<NarrativeResult>('api/v1/analytics/narrative');
	}

	async generateNarrative(input: { asOf: string }): Promise<NarrativeResult> {
		return this.client.request<NarrativeResult>('api/v1/analytics/narrative', {
			method: 'POST',
			body: { asOf: input.asOf }
		});
	}
```

- [ ] **Step 9.3: Patch the old page's references to dropped summary fields**

In `webui/src/routes/analytics/+page.svelte` (the OLD page, still live):
- `summary.averagePerTransaction` (Avg transaction KPI) → replace the KPI value with `'—'` placeholder or compute `totalNum / summary.transactionCount`; simplest compile-safe patch: change the two references (`averagePerTransaction`) to `'0'` literals.
- `summary.monthOverMonthDelta` / `summary.monthOverMonthPercent` (`momDelta`, `momPercentLabel`) → hardcode `momDelta = 0` and `momPercentLabel = null` in their `$derived` bodies.

This is throwaway glue for one task; the page is rewritten in Task 11.

- [ ] **Step 9.4: Verify** — from `webui/`: `npm run check` → green.

- [ ] **Step 9.5: Commit**

```bash
git add webui/src/lib/types/domain.ts webui/src/lib/repos/types.ts webui/src/lib/repos/httpAnalyticsRepository.ts webui/src/routes/analytics/+page.svelte
git commit -m "feat(webui): add diagnosis/savings/narrative analytics repo methods + types"
```

---

### Task 10: VerdictHeader and AiNarrativeStrip components

**Files:**
- Create: `webui/src/lib/components/analytics/VerdictHeader.svelte`
- Create: `webui/src/lib/components/analytics/AiNarrativeStrip.svelte`

- [ ] **Step 10.1: Create `VerdictHeader.svelte`**

```svelte
<script lang="ts">
	import { settings } from '$lib/stores/settings';
	import { amountToNumber, formatAmount } from '$utils/money';
	import { formatMonthLabel } from '$utils/dates';
	import { CalendarCheck, TrendingDown, TrendingUp } from '@lucide/svelte';
	import type { AnalyticsSummary, DiagnosisResult, MonthlyTotal } from '$types';

	let {
		diagnosis,
		summary,
		months
	}: { diagnosis: DiagnosisResult; summary: AnalyticsSummary; months: MonthlyTotal[] } = $props();

	const totalCurrent = $derived(amountToNumber(diagnosis.totalCurrent));
	const totalBaseline = $derived(amountToNumber(diagnosis.totalBaseline));
	const delta = $derived(totalCurrent - totalBaseline);
	const isOver = $derived(delta > 0);
	const hasBaseline = $derived(diagnosis.baselineMonthCount > 0);
	const pctLabel = $derived.by(() => {
		if (!hasBaseline || totalBaseline <= 0) return null;
		const pct = Math.round((delta / totalBaseline) * 100);
		return `${pct > 0 ? '+' : ''}${pct}%`;
	});

	// Inline SVG sparkline over the last 7 COMPLETE months.
	const SPARK_W = 140;
	const SPARK_H = 36;
	const sparkPoints = $derived.by(() => {
		const complete = months.filter((m) => m.month !== summary.currentMonth).slice(-7);
		if (complete.length < 2) return '';
		const values = complete.map((m) => amountToNumber(m.total));
		const max = Math.max(...values, 1);
		const pad = 2;
		return values
			.map((v, i) => {
				const x = pad + (i * (SPARK_W - 2 * pad)) / (values.length - 1);
				const y = SPARK_H - pad - (v / max) * (SPARK_H - 2 * pad);
				return `${x.toFixed(1)},${y.toFixed(1)}`;
			})
			.join(' ');
	});

	const paceLabel = $derived.by(() => {
		if (!summary.currentMonth || amountToNumber(summary.currentMonthToDate) <= 0) return null;
		const monthName = formatMonthLabel(summary.currentMonth);
		const toDate = formatAmount(summary.currentMonthToDate, $settings.currency);
		const projected = formatAmount(summary.currentMonthProjected, $settings.currency);
		return `${monthName} so far: ${toDate}, on pace for ~${projected}`;
	});
</script>

<div
	class="rounded-xl border-2 border-ctp-accent/50 bg-gradient-to-br from-ctp-accent/[0.07] to-ctp-base p-4 shadow-lg shadow-black/20"
	data-testid="analytics-verdict"
>
	{#if diagnosis.latestMonth}
		<div class="flex flex-wrap items-start justify-between gap-3">
			<div class="flex items-start gap-3">
				<span
					class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ctp-accent/20 text-ctp-accent"
				>
					<CalendarCheck class="h-5 w-5" />
				</span>
				<div>
					<p class="text-xs font-medium text-ctp-subtext0">
						{formatMonthLabel(diagnosis.latestMonth)} — your last complete month
					</p>
					<p
						class="text-3xl font-bold leading-tight tracking-tight text-ctp-text"
						data-testid="analytics-verdict-total"
					>
						{formatAmount(diagnosis.totalCurrent, $settings.currency)}
					</p>
					{#if hasBaseline}
						<div class="mt-1.5 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm">
							<span class="text-ctp-subtext0">
								vs <span class="font-semibold text-ctp-text"
									>{formatAmount(diagnosis.totalBaseline, $settings.currency)}</span
								>
								{diagnosis.baselineMonthCount}-month average
							</span>
							{#if pctLabel}
								<span
									class="inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-xs font-semibold tabular-nums {isOver
										? 'bg-ctp-red/15 text-ctp-red'
										: 'bg-ctp-green/15 text-ctp-green'}"
									data-testid="analytics-verdict-badge"
								>
									{#if isOver}
										<TrendingUp class="h-3 w-3" />
									{:else}
										<TrendingDown class="h-3 w-3" />
									{/if}
									{pctLabel}
								</span>
							{/if}
						</div>
					{:else}
						<p class="mt-1.5 text-sm text-ctp-overlay0">
							Not enough history for a baseline yet — one more complete month needed.
						</p>
					{/if}
					{#if paceLabel}
						<p class="mt-1 text-xs text-ctp-overlay0">{paceLabel}</p>
					{/if}
				</div>
			</div>
			{#if sparkPoints}
				<svg
					viewBox="0 0 {SPARK_W} {SPARK_H}"
					class="h-9 w-36 shrink-0 self-center text-ctp-accent"
					aria-hidden="true"
				>
					<polyline
						points={sparkPoints}
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linejoin="round"
						stroke-linecap="round"
					/>
				</svg>
			{/if}
		</div>
	{:else}
		<p class="text-sm text-ctp-overlay0">
			No complete month of data yet — insights appear after your first full month.
		</p>
	{/if}
</div>
```

- [ ] **Step 10.2: Create `AiNarrativeStrip.svelte`**

```svelte
<script lang="ts">
	import { analyticsRepository } from '$lib/repos';
	import { todayIso, formatMonthLabel } from '$utils/dates';
	import { Sparkles } from '@lucide/svelte';
	import type { AnalyticsNarrative } from '$types';

	let { initial = null }: { initial?: AnalyticsNarrative | null } = $props();

	let narrative = $state<AnalyticsNarrative | null>(initial);
	let generating = $state(false);
	let error = $state<string | null>(null);

	const generatedLabel = $derived.by(() => {
		if (!narrative) return null;
		const day = narrative.generatedAt.slice(0, 10);
		return `Generated ${day} · about ${formatMonthLabel(narrative.month)}`;
	});

	async function generate(): Promise<void> {
		generating = true;
		error = null;
		try {
			const res = await analyticsRepository.generateNarrative({ asOf: todayIso() });
			narrative = res.narrative;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to generate insights.';
		} finally {
			generating = false;
		}
	}
</script>

<div
	class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20"
	data-testid="analytics-narrative"
>
	<div class="flex flex-wrap items-center justify-between gap-2">
		<p class="flex items-center gap-2 text-sm font-semibold text-ctp-text">
			<Sparkles class="h-4 w-4 text-ctp-mauve" />
			AI summary
		</p>
		<button
			type="button"
			class="inline-flex items-center gap-2 rounded-lg border border-ctp-surface1 px-3 py-1.5 text-xs font-semibold text-ctp-text transition-colors hover:border-ctp-surface2 disabled:opacity-50"
			data-testid="analytics-narrative-generate"
			onclick={generate}
			disabled={generating}
		>
			{#if generating}
				<span
					class="h-3 w-3 animate-spin rounded-full border-2 border-ctp-surface2 border-t-ctp-accent"
				></span>
				Generating…
			{:else}
				{narrative ? 'Regenerate' : 'Generate'}
			{/if}
		</button>
	</div>
	{#if error}
		<p class="mt-2 text-sm text-ctp-red" data-testid="analytics-narrative-error">{error}</p>
	{:else if narrative}
		<p class="mt-2 text-sm leading-relaxed text-ctp-subtext0" data-testid="analytics-narrative-content">
			{narrative.content}
		</p>
		{#if generatedLabel}
			<p class="mt-1.5 text-[11px] text-ctp-overlay0">{generatedLabel}</p>
		{/if}
	{:else}
		<p class="mt-2 text-sm text-ctp-overlay0">
			A short plain-language read on what changed and where you can save. Uses your OpenRouter
			key; nothing is generated until you click.
		</p>
	{/if}
</div>
```

- [ ] **Step 10.3: Verify** — `npm run check` → green (components compile even if unused).

- [ ] **Step 10.4: Commit**

```bash
git add webui/src/lib/components/analytics/VerdictHeader.svelte webui/src/lib/components/analytics/AiNarrativeStrip.svelte
git commit -m "feat(webui): add VerdictHeader and AiNarrativeStrip analytics components"
```

---

### Task 11: WentUpZone and SavingsZone components

**Files:**
- Create: `webui/src/lib/components/analytics/WentUpZone.svelte`
- Create: `webui/src/lib/components/analytics/SavingsZone.svelte`

- [ ] **Step 11.1: Create `WentUpZone.svelte`**

```svelte
<script lang="ts">
	import { settings } from '$lib/stores/settings';
	import { formatAmount, amountToNumber } from '$utils/money';
	import { formatMonthLabel } from '$utils/dates';
	import { ChevronDown, TrendingDown, TrendingUp } from '@lucide/svelte';
	import type { DiagnosisResult } from '$types';

	let { diagnosis }: { diagnosis: DiagnosisResult } = $props();

	let expanded = $state<Set<string>>(new Set());
	let showDecreases = $state(false);

	function toggle(categoryId: string): void {
		const next = new Set(expanded);
		if (next.has(categoryId)) {
			next.delete(categoryId);
		} else {
			next.add(categoryId);
		}
		expanded = next;
	}

	const decreasesSummary = $derived(
		diagnosis.decreases
			.slice(0, 4)
			.map(
				(d) =>
					`${d.categoryName} −${formatAmount(Math.abs(amountToNumber(d.delta)), $settings.currency)}`
			)
			.join(' · ')
	);

	function pctBadge(pct: number | null): string | null {
		if (pct === null) return null;
		return `+${Math.round(pct)}%`;
	}
</script>

<section
	class="rounded-xl border border-ctp-surface1 bg-ctp-base p-4 shadow-lg shadow-black/20"
	data-testid="analytics-wentup"
>
	<h2 class="text-xs font-bold uppercase tracking-wider text-ctp-subtext0">What went up</h2>
	{#if diagnosis.baselineMonthCount === 0}
		<p class="mt-3 text-sm text-ctp-overlay0" data-testid="analytics-wentup-empty">
			Not enough history to compare yet — this fills in after two complete months.
		</p>
	{:else if diagnosis.increases.length === 0}
		<p class="mt-3 text-sm text-ctp-overlay0" data-testid="analytics-wentup-empty">
			Nothing went up meaningfully vs your average. Nice.
		</p>
	{:else}
		<ul class="mt-2 divide-y divide-ctp-surface0">
			{#each diagnosis.increases as inc (inc.categoryId)}
				{@const isOpen = expanded.has(inc.categoryId)}
				<li data-testid="analytics-wentup-row">
					<button
						type="button"
						class="flex w-full flex-wrap items-baseline gap-x-3 gap-y-1 py-2.5 text-left transition-colors hover:bg-ctp-surface0/40"
						data-testid={`analytics-wentup-toggle-${inc.categoryId}`}
						aria-expanded={isOpen}
						onclick={() => toggle(inc.categoryId)}
					>
						<span class="inline-flex items-center gap-2 text-sm font-semibold text-ctp-text">
							<span
								class="h-2.5 w-2.5 shrink-0 rounded-full"
								style="background-color: {inc.color}"
							></span>
							<TrendingUp class="h-4 w-4 text-ctp-red" />
							{inc.categoryName}
							{#if inc.isNew}
								<span
									class="rounded-full bg-ctp-mauve/15 px-1.5 py-0.5 text-[10px] font-semibold text-ctp-mauve"
									>new</span
								>
							{/if}
						</span>
						<span class="text-sm tabular-nums text-ctp-text"
							>{formatAmount(inc.current, $settings.currency)}</span
						>
						{#if !inc.isNew}
							<span class="text-xs text-ctp-subtext0"
								>vs {formatAmount(inc.baseline, $settings.currency)} avg</span
							>
						{/if}
						<span class="ml-auto inline-flex items-center gap-1.5">
							<span class="text-sm font-semibold tabular-nums text-ctp-red"
								>+{formatAmount(inc.delta, $settings.currency)}</span
							>
							{#if pctBadge(inc.percentChange)}
								<span class="text-xs tabular-nums text-ctp-red/80">{pctBadge(inc.percentChange)}</span>
							{/if}
							<ChevronDown
								class="h-4 w-4 text-ctp-overlay0 transition-transform {isOpen ? 'rotate-180' : ''}"
							/>
						</span>
					</button>
					{#if isOpen}
						<div class="pb-3 pl-5" data-testid={`analytics-wentup-detail-${inc.categoryId}`}>
							{#if inc.contributors.length > 0}
								<ul class="flex flex-col gap-1">
									{#each inc.contributors as c (c.merchant)}
										<li class="text-xs text-ctp-subtext0">
											<span class="font-semibold text-ctp-text">{c.merchant}</span>
											{formatAmount(c.current, $settings.currency)}
											{#if c.isNew}
												<span class="text-ctp-mauve">(new)</span>
											{:else}
												vs {formatAmount(c.baseline, $settings.currency)} avg
											{/if}
											<span class="font-semibold text-ctp-red"
												>+{formatAmount(c.delta, $settings.currency)}</span
											>
										</li>
									{/each}
								</ul>
							{/if}
							<ul
								class="mt-2 flex flex-col gap-0.5"
								data-testid={`analytics-wentup-transactions-${inc.categoryId}`}
							>
								{#each inc.transactions as t (t.id)}
									<li class="flex items-baseline gap-2 text-xs text-ctp-subtext0">
										<span class="tabular-nums text-ctp-overlay0">{t.date.slice(0, 10)}</span>
										<span class="truncate">{t.displayName ?? t.name}</span>
										<span class="ml-auto tabular-nums text-ctp-text"
											>{formatAmount(t.amount, $settings.currency)}</span
										>
									</li>
								{/each}
							</ul>
						</div>
					{/if}
				</li>
			{/each}
		</ul>
		{#if diagnosis.otherIncreasesCount > 0}
			<p class="mt-2 text-xs text-ctp-overlay0" data-testid="analytics-wentup-other">
				Everything else: {diagnosis.otherIncreasesCount} small increases totalling +{formatAmount(
					diagnosis.otherIncreasesTotal,
					$settings.currency
				)}
			</p>
		{/if}
	{/if}
	{#if diagnosis.decreases.length > 0}
		<button
			type="button"
			class="mt-3 flex items-center gap-1.5 text-xs text-ctp-green transition-colors hover:text-ctp-text"
			data-testid="analytics-wentdown-toggle"
			aria-expanded={showDecreases}
			onclick={() => (showDecreases = !showDecreases)}
		>
			<TrendingDown class="h-3.5 w-3.5" />
			What went down: {decreasesSummary}
			<ChevronDown class="h-3.5 w-3.5 transition-transform {showDecreases ? 'rotate-180' : ''}" />
		</button>
		{#if showDecreases}
			<ul class="mt-1.5 flex flex-col gap-1 pl-5" data-testid="analytics-wentdown-list">
				{#each diagnosis.decreases as d (d.categoryId)}
					<li class="text-xs text-ctp-subtext0">
						<span class="font-semibold text-ctp-text">{d.categoryName}</span>
						{formatAmount(d.current, $settings.currency)} vs
						{formatAmount(d.baseline, $settings.currency)} avg
						<span class="font-semibold text-ctp-green"
							>−{formatAmount(Math.abs(amountToNumber(d.delta)), $settings.currency)}</span
						>
					</li>
				{/each}
			</ul>
		{/if}
	{/if}
	{#if diagnosis.latestMonth && diagnosis.baselineFrom && diagnosis.baselineTo}
		<p class="mt-3 text-[11px] text-ctp-overlay0">
			{formatMonthLabel(diagnosis.latestMonth)} vs your monthly average over
			{formatMonthLabel(diagnosis.baselineFrom)}–{formatMonthLabel(diagnosis.baselineTo)}.
		</p>
	{/if}
</section>
```

- [ ] **Step 11.2: Create `SavingsZone.svelte`**

```svelte
<script lang="ts">
	import { settings } from '$lib/stores/settings';
	import { formatAmount } from '$utils/money';
	import { formatMonthLabel } from '$utils/dates';
	import { ChevronDown, Coffee, PiggyBank, Repeat, Sparkle } from '@lucide/svelte';
	import type { SavingsResult } from '$types';

	let { savings }: { savings: SavingsResult } = $props();

	let stackOpen = $state(false);
</script>

<section
	class="rounded-xl border border-ctp-green/30 bg-ctp-base p-4 shadow-lg shadow-black/20"
	data-testid="analytics-savings"
>
	<h2 class="text-xs font-bold uppercase tracking-wider text-ctp-subtext0">Where you can save</h2>

	<div class="mt-2 divide-y divide-ctp-surface0">
		<!-- Price creep -->
		<div class="py-3" data-testid="analytics-savings-creep">
			<p class="flex items-center gap-2 text-sm font-semibold text-ctp-text">
				<PiggyBank class="h-4 w-4 text-ctp-green" />
				Price creep
			</p>
			{#if savings.priceCreep.length === 0}
				<p class="mt-1 text-xs text-ctp-overlay0">
					No price increases detected in your recurring charges over the last 12 months.
				</p>
			{:else}
				<ul class="mt-1.5 flex flex-col gap-1">
					{#each savings.priceCreep as item (item.name + item.sinceMonth)}
						<li class="text-xs text-ctp-subtext0" data-testid="analytics-creep-item">
							<span class="font-semibold text-ctp-text">{item.name}</span>
							{formatAmount(item.oldAmount, $settings.currency)} →
							{formatAmount(item.newAmount, $settings.currency)}
							since {formatMonthLabel(item.sinceMonth)}
							<span class="font-semibold text-ctp-red"
								>(+{formatAmount(item.annualDelta, $settings.currency)}/yr)</span
							>
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		<!-- New recurring -->
		<div class="py-3" data-testid="analytics-savings-newrecurring">
			<p class="flex items-center gap-2 text-sm font-semibold text-ctp-text">
				<Sparkle class="h-4 w-4 text-ctp-green" />
				New recurring charges
			</p>
			{#if savings.newRecurring.length === 0}
				<p class="mt-1 text-xs text-ctp-overlay0">No new subscriptions in the last few months.</p>
			{:else}
				<ul class="mt-1.5 flex flex-col gap-1">
					{#each savings.newRecurring as item (item.name + item.firstMonth)}
						<li class="text-xs text-ctp-subtext0" data-testid="analytics-newrecurring-item">
							<span class="font-semibold text-ctp-text">{item.name}</span>
							{formatAmount(item.amount, $settings.currency)}/mo, first seen
							{formatMonthLabel(item.firstMonth)}
							<span class="font-semibold text-ctp-red"
								>({formatAmount(item.annualCost, $settings.currency)}/yr)</span
							>
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		<!-- Habit spend -->
		<div class="py-3" data-testid="analytics-savings-habits">
			<p class="flex items-center gap-2 text-sm font-semibold text-ctp-text">
				<Coffee class="h-4 w-4 text-ctp-green" />
				Habit spend
				{#if savings.latestMonth}
					<span class="text-xs font-normal text-ctp-overlay0"
						>({formatMonthLabel(savings.latestMonth)})</span
					>
				{/if}
			</p>
			{#if savings.habits.length === 0}
				<p class="mt-1 text-xs text-ctp-overlay0">
					No high-frequency small purchases last month.
				</p>
			{:else}
				<ul class="mt-1.5 flex flex-col gap-1">
					{#each savings.habits as item (item.name)}
						<li class="text-xs text-ctp-subtext0" data-testid="analytics-habit-item">
							<span class="font-semibold text-ctp-text">{item.name}</span>
							— {item.count} visits,
							<span class="font-semibold text-ctp-text"
								>{formatAmount(item.total, $settings.currency)}</span
							>
							(avg {formatAmount(item.average, $settings.currency)})
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		<!-- Recurring stack -->
		<div class="py-3" data-testid="analytics-savings-stack">
			<button
				type="button"
				class="flex w-full items-center gap-2 text-left text-sm font-semibold text-ctp-text"
				data-testid="analytics-stack-toggle"
				aria-expanded={stackOpen}
				onclick={() => (stackOpen = !stackOpen)}
			>
				<Repeat class="h-4 w-4 text-ctp-green" />
				Recurring stack
				<span class="text-xs font-normal text-ctp-subtext0" data-testid="analytics-stack-total">
					{formatAmount(savings.recurringStack.monthlyTotal, $settings.currency)}/mo =
					{formatAmount(savings.recurringStack.annualTotal, $settings.currency)}/yr
				</span>
				{#if savings.recurringStack.items.length > 0}
					<ChevronDown
						class="ml-auto h-4 w-4 text-ctp-overlay0 transition-transform {stackOpen
							? 'rotate-180'
							: ''}"
					/>
				{/if}
			</button>
			{#if savings.recurringStack.items.length === 0}
				<p class="mt-1 text-xs text-ctp-overlay0">No active recurring charges detected.</p>
			{:else if stackOpen}
				<ul class="mt-2 flex flex-col gap-1 pl-6" data-testid="analytics-stack-list">
					{#each savings.recurringStack.items as item (item.name + item.amount)}
						<li class="flex items-baseline gap-2 text-xs text-ctp-subtext0">
							<span class="truncate font-semibold text-ctp-text">{item.name}</span>
							<span class="text-ctp-overlay0">
								{item.monthsCovered}× since {formatMonthLabel(item.firstMonth)}
							</span>
							<span class="ml-auto tabular-nums"
								>{formatAmount(item.monthlyEstimate, $settings.currency)}/mo</span
							>
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	</div>
</section>
```

- [ ] **Step 11.3: Verify** — `npm run check` → green.

- [ ] **Step 11.4: Commit**

```bash
git add webui/src/lib/components/analytics/WentUpZone.svelte webui/src/lib/components/analytics/SavingsZone.svelte
git commit -m "feat(webui): add WentUpZone and SavingsZone analytics components"
```

---

### Task 12: Rewrite the Analytics page + frontend cleanup + webui README

**Files:**
- Rewrite: `webui/src/routes/analytics/+page.svelte`
- Modify: `webui/src/lib/stores/analyticsPeriod.ts` (remove `monthOverMonthComparisonQuery`)
- Modify: `webui/src/lib/repos/types.ts`, `webui/src/lib/repos/httpAnalyticsRepository.ts` (remove dead members)
- Modify: `webui/src/lib/types/domain.ts` (remove dead types)
- Delete: `webui/src/lib/components/analytics/{CategoryTrendChart,CategoryMoversList,TopMerchantsChart,ImportanceTrendChart,ImportanceBreakdownCard,RecurringPanel,LargeTransactionsList,DistributionCard}.svelte`
- Modify: `webui/README.md` (Analytics section, lines ~40–73)

- [ ] **Step 12.1: Rewrite the page**

Replace `webui/src/routes/analytics/+page.svelte` entirely with:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { analyticsRepository } from '$lib/repos';
	import { refreshSettings } from '$lib/stores/settings';
	import {
		analyticsPeriod,
		ANALYTICS_PERIODS,
		periodToWindow,
		type AnalyticsPeriod
	} from '$lib/stores/analyticsPeriod';
	import { todayIso } from '$utils/dates';
	import MonthlyTrendChart from '$components/analytics/MonthlyTrendChart.svelte';
	import VerdictHeader from '$components/analytics/VerdictHeader.svelte';
	import AiNarrativeStrip from '$components/analytics/AiNarrativeStrip.svelte';
	import WentUpZone from '$components/analytics/WentUpZone.svelte';
	import SavingsZone from '$components/analytics/SavingsZone.svelte';
	import { TrendingUp } from '@lucide/svelte';
	import type {
		AnalyticsSummary,
		DiagnosisResult,
		MonthlyTotalsResult,
		NarrativeResult,
		SavingsResult
	} from '$types';

	const PERIOD_LABELS: Record<AnalyticsPeriod, string> = {
		'3m': '3M',
		'6m': '6M',
		'12m': '12M',
		all: 'All'
	};

	let summary = $state<AnalyticsSummary | null>(null);
	let monthly = $state<MonthlyTotalsResult | null>(null);
	let diagnosis = $state<DiagnosisResult | null>(null);
	let savings = $state<SavingsResult | null>(null);
	let narrative = $state<NarrativeResult | null>(null);

	let loaded = $state(false);
	let loadError = $state<string | null>(null);

	onMount(() => {
		void refreshSettings();
		void load();
	});

	// One parallel load on mount. The period selector below filters the trend
	// chart CLIENT-SIDE from the all-history monthly totals, so there is no
	// reload on period change (and no request-ordering hazards).
	async function load(): Promise<void> {
		const asOf = todayIso();
		try {
			const [summaryRes, monthlyRes, diagnosisRes, savingsRes, narrativeRes] = await Promise.all([
				analyticsRepository.summary({ asOf }),
				analyticsRepository.monthlyTotals(),
				analyticsRepository.diagnosis(asOf),
				analyticsRepository.savings(asOf),
				analyticsRepository.narrative()
			]);
			summary = summaryRes;
			monthly = monthlyRes;
			diagnosis = diagnosisRes;
			savings = savingsRes;
			narrative = narrativeRes;
			loadError = null;
		} catch (error) {
			loadError = error instanceof Error ? error.message : 'Failed to load analytics.';
		} finally {
			loaded = true;
		}
	}

	const isEmpty = $derived(loaded && summary !== null && summary.transactionCount === 0);

	// Trend chart months, windowed by the persisted period preset.
	const trendMonths = $derived.by(() => {
		if (!monthly) return [];
		const window = periodToWindow($analyticsPeriod);
		if (!window.dateFrom) return monthly.months;
		const fromMonth = window.dateFrom.slice(0, 7);
		return monthly.months.filter((m) => m.month >= fromMonth);
	});

	function selectPeriod(period: AnalyticsPeriod): void {
		analyticsPeriod.set(period);
	}
</script>

<svelte:head>
	<title>Analytics</title>
</svelte:head>

<section class="flex flex-col gap-6">
	<div>
		<h1 class="text-2xl font-bold tracking-tight text-ctp-text">Analytics</h1>
		<p class="text-sm text-ctp-subtext0">What went up, and where you can claw it back.</p>
	</div>

	{#if loadError}
		<div
			class="rounded-xl border border-ctp-red/40 bg-ctp-red/10 p-4 text-sm text-ctp-red"
			data-testid="analytics-error"
		>
			Couldn't load analytics: {loadError}
		</div>
	{:else if !loaded}
		<div
			class="flex items-center justify-center gap-3 rounded-xl border border-ctp-surface1 bg-ctp-base p-12 text-sm text-ctp-subtext0 shadow-lg shadow-black/20"
			data-testid="analytics-loading"
		>
			<span
				class="h-4 w-4 animate-spin rounded-full border-2 border-ctp-surface2 border-t-ctp-accent"
			></span>
			Loading analytics…
		</div>
	{:else if isEmpty}
		<div
			class="flex flex-col items-center justify-center gap-3 rounded-xl border border-ctp-surface1 bg-ctp-base p-12 text-center shadow-lg shadow-black/20"
			data-testid="analytics-empty"
		>
			<span
				class="flex h-12 w-12 items-center justify-center rounded-full bg-ctp-accent/15 text-ctp-accent"
			>
				<TrendingUp class="h-6 w-6" />
			</span>
			<p class="text-base font-semibold text-ctp-text">No data yet</p>
			<p class="max-w-sm text-sm text-ctp-subtext0">
				Import some transactions and your spending insights will appear here.
			</p>
			<a
				href="/import"
				class="mt-1 inline-flex items-center gap-2 rounded-lg bg-ctp-accent px-4 py-2 text-sm font-semibold text-ctp-on-accent transition-opacity hover:opacity-90"
			>
				Import transactions
			</a>
		</div>
	{:else}
		{#if diagnosis && summary && monthly}
			<VerdictHeader {diagnosis} {summary} months={monthly.months} />
		{/if}

		<AiNarrativeStrip initial={narrative?.narrative ?? null} />

		{#if diagnosis}
			<WentUpZone {diagnosis} />
		{/if}

		{#if savings}
			<SavingsZone {savings} />
		{/if}

		<!-- Context: spend trend, windowed by the period selector. -->
		{#if monthly}
			<div class="flex flex-col gap-3">
				<div class="flex items-center justify-between gap-3">
					<h2 class="text-xs font-bold uppercase tracking-wider text-ctp-subtext0">Context</h2>
					<div
						class="inline-flex items-center gap-1 rounded-full border border-ctp-surface1 bg-ctp-base p-1 shadow-lg shadow-black/20"
						data-testid="analytics-period-selector"
						role="group"
						aria-label="Select trend period"
					>
						{#each ANALYTICS_PERIODS as period (period)}
							{@const active = $analyticsPeriod === period}
							<button
								type="button"
								data-testid={`analytics-period-${period}`}
								aria-pressed={active}
								onclick={() => selectPeriod(period)}
								class="rounded-full px-3 py-1.5 text-sm font-medium transition-colors {active
									? 'bg-ctp-accent text-ctp-on-accent shadow-sm'
									: 'text-ctp-subtext0 hover:bg-ctp-surface0/60 hover:text-ctp-text'}"
							>
								{PERIOD_LABELS[period]}
							</button>
						{/each}
					</div>
				</div>
				<MonthlyTrendChart months={trendMonths} currentMonth={summary?.currentMonth ?? null} />
			</div>
		{/if}
	{/if}
</section>
```

Note: check how `MonthlyTrendChart` is wrapped on the old page — if the old page wrapped it in a card with `data-testid="analytics-monthly-trend"`, look at `MonthlyTrendChart.svelte` itself: the testid lives inside the component (the e2e asserts `analytics-monthly-trend`); keep whatever element carries it intact.

- [ ] **Step 12.2: Frontend cleanup**

- `webui/src/lib/stores/analyticsPeriod.ts`: delete `monthOverMonthComparisonQuery` and its `CategoryComparisonQuery`/`monthDateRange` imports (keep `periodToWindow`, the store, `ANALYTICS_PERIODS`).
- `webui/src/lib/repos/types.ts`: in the `AnalyticsRepository` interface delete `categoryTrends`, `categoryComparison`, `topMerchants`, `importanceBreakdown`, `weekdayBreakdown`, `recurring`, `largeTransactions`, `distribution`, `importanceTrend`, and the `CategoryComparisonQuery` type (grep first: `grep -rn "CategoryComparisonQuery" webui/src`).
- `webui/src/lib/repos/httpAnalyticsRepository.ts`: delete the corresponding methods and now-unused type imports.
- `webui/src/lib/types/domain.ts`: delete `CategoryTrendsResult`/`CategoryTrendPoint`/`CategoryTrendSeries`, `CategoryComparisonResult`/`CategoryMover`, `TopMerchantsResult`/`TopMerchant`, `ImportanceBreakdownResult`, `WeekdayBreakdownResult`, `RecurringResult`/`RecurringItem`, `LargeTransactionsResult`/`LargeTransaction`, `DistributionResult`, `ImportanceTrendResult` (+ point/series). Grep each name across `webui/src` before deleting; `MonthlyTotal`/`MonthlyTotalsResult` and `AnalyticsSummary` stay.
- Delete component files: `CategoryTrendChart.svelte`, `CategoryMoversList.svelte`, `TopMerchantsChart.svelte`, `ImportanceTrendChart.svelte`, `ImportanceBreakdownCard.svelte`, `RecurringPanel.svelte`, `LargeTransactionsList.svelte`, `DistributionCard.svelte` (`git rm`). Keep `MonthlyTrendChart.svelte` and `CumulativeChart.svelte` (the latter is used by the dashboard — verify with `grep -rn "CumulativeChart" webui/src`).

- [ ] **Step 12.3: Update `webui/README.md`**

Replace the Analytics bullet (lines ~40–73) with:

```markdown
- **Analytics** (`/analytics`) — insight-first review of your spending, anchored
  on the latest **complete** month (the in-progress month is never the
  headline). Top to bottom:
  - **Verdict header** — "May 2026 — £2,140 · +12% vs your 6-month average",
    with a sparkline of the last 7 complete months and, mid-month, a "June so
    far: £480, on pace for ~£1,950" run-rate line.
  - **AI summary** — an on-demand (never automatic) OpenRouter-generated 3–6
    sentence narrative of the month. The last result is stored server-side and
    shown on revisit with a Regenerate button; a missing
    `QUID_OPENROUTER_API_KEY` surfaces as an inline error.
  - **What went up** — categories above their trailing 6-month average (zero
    months count toward the average), sorted by £ delta. Each row expands to
    the top contributing merchants (vs their own baseline, with "new" badges)
    and the month's transactions. Increases under £10 and 10% roll into one
    "everything else" line; decreases collapse into a "what went down" line.
  - **Where you can save** — price creep on recurring charges (old → new,
    annualised), new recurring charges (first seen in the last 4 months),
    habit spend (≥6 visits at ≤£20 average last month), and the recurring
    stack total (£/mo and £/yr, expandable inventory).
  - **Context** — the monthly trend chart with the 3M/6M/12M/All selector
    (persisted in `localStorage`); the selector only windows this chart —
    the insight zones have fixed windows.

  Empty until transactions are imported. Backed by `GET /api/v1/analytics/*`
  (`summary`, `monthly-totals`, `diagnosis`, `savings`, `narrative`) and
  `POST /api/v1/analytics/narrative`.
```

- [ ] **Step 12.4: Verify** — `npm run check && npm run build` → green. The e2e suite WILL fail until Task 13 — that's expected; do not run it yet.

- [ ] **Step 12.5: Commit**

```bash
git add -A webui/src webui/README.md
git commit -m "feat(webui): rebuild Analytics page around insight zones"
```

---

### Task 13: Rework the analytics e2e suite

**Files:**
- Rewrite: `webui/tests/analytics.e2e.ts`

- [ ] **Step 13.1: Rewrite the spec**

Replace `webui/tests/analytics.e2e.ts` entirely. Seed dates are relative to "now" via `isoMonthOffset(offset, day)`; the latest complete month is offset `-1`.

```typescript
import { expect, test } from '@playwright/test';
import { buildSeed, isoMonthOffset, seedApiState, type SeedExpense } from './helpers.js';

function expense(
	id: string,
	name: string,
	amount: string,
	monthOffset: number,
	day: number,
	categoryId: string
): SeedExpense {
	return { id, name, amount, date: isoMonthOffset(monthOffset, day), categoryId, note: '' };
}

const expenses: SeedExpense[] = [];
let n = 0;
const add = (name: string, amount: string, monthOffset: number, day: number, categoryId: string) =>
	expenses.push(expense(`exp-${n++}`, name, amount, monthOffset, day, categoryId));

// Groceries: £50/mo baseline (months -7..-2), then £120 in the latest
// complete month (-1) split across an old and a NEW merchant.
for (let m = -7; m <= -2; m++) add('Tesco', '50.00', m, 10, 'cat-groceries');
add('Tesco', '60.00', -1, 10, 'cat-groceries');
add('Waitrose', '60.00', -1, 12, 'cat-groceries');

// Transport: £30/mo baseline, absent in -1 -> a decrease.
for (let m = -7; m <= -2; m++) add('TfL', '30.00', m, 5, 'cat-transport');

// Netflix price creep: 10.99 in -7..-4, then 12.99 in -3..-1.
for (let m = -7; m <= -4; m++) add('Netflix', '10.99', m, 3, 'cat-subs');
for (let m = -3; m <= -1; m++) add('Netflix', '12.99', m, 3, 'cat-subs');

// iCloud new recurring: first ever in -3, recurring -3..-1.
for (let m = -3; m <= -1; m++) add('iCloud', '2.99', m, 4, 'cat-subs');

// Pret habit: 7 small visits in the latest complete month.
for (let day = 2; day <= 8; day++) add('Pret', '3.50', -1, day, 'cat-eating');

const analyticsSeed = buildSeed({
	categories: [
		{ id: 'uncategorized', name: 'Uncategorized', color: '#9ca3af', icon: 'circle-help' },
		{ id: 'cat-groceries', name: 'Groceries', color: '#22c55e', icon: 'shopping-cart' },
		{ id: 'cat-transport', name: 'Public Transport', color: '#3b82f6', icon: 'train-front' },
		{ id: 'cat-subs', name: 'Subscriptions', color: '#a855f7', icon: 'repeat' },
		{ id: 'cat-eating', name: 'Eating Out', color: '#f97316', icon: 'utensils' }
	],
	expenses
});

test.describe('analytics page', () => {
	test.beforeEach(async ({ page }) => {
		await seedApiState(page, analyticsSeed);
	});

	test('renders verdict, went-up zone with drill-down, and savings zone', async ({ page }) => {
		const consoleErrors: string[] = [];
		page.on('console', (msg) => {
			if (msg.type() === 'error') consoleErrors.push(msg.text());
		});

		await page.goto('/analytics');

		await expect(page.getByRole('heading', { name: 'Analytics', level: 1 })).toBeVisible();

		// Verdict header: a currency total and a vs-average badge.
		await expect(page.getByTestId('analytics-verdict-total')).toHaveText(/£\d/);
		await expect(page.getByTestId('analytics-verdict-badge')).toBeVisible();

		// What went up: Groceries is an increase; expanding shows contributors
		// (new-merchant Waitrose) and the month's transactions.
		await expect(page.getByTestId('analytics-wentup')).toBeVisible();
		const groceriesToggle = page.getByTestId('analytics-wentup-toggle-cat-groceries');
		await expect(groceriesToggle).toContainText('Groceries');
		await groceriesToggle.click();
		const detail = page.getByTestId('analytics-wentup-detail-cat-groceries');
		await expect(detail).toContainText('Waitrose');
		await expect(detail).toContainText('(new)');
		await expect(
			page.getByTestId('analytics-wentup-transactions-cat-groceries').locator('li')
		).toHaveCount(2);

		// What went down: Transport decreased.
		await expect(page.getByTestId('analytics-wentdown-toggle')).toContainText('Public Transport');

		// Savings: creep, new recurring, habit, stack total.
		await expect(page.getByTestId('analytics-creep-item')).toContainText('Netflix');
		await expect(page.getByTestId('analytics-creep-item')).toContainText('£10.99 → £12.99');
		await expect(page.getByTestId('analytics-newrecurring-item')).toContainText('iCloud');
		await expect(page.getByTestId('analytics-habit-item')).toContainText('Pret');
		await expect(page.getByTestId('analytics-habit-item')).toContainText('7 visits');
		await expect(page.getByTestId('analytics-stack-total')).toContainText('/mo');

		// Trend chart present.
		await expect(page.getByTestId('analytics-monthly-trend')).toBeVisible();

		expect(consoleErrors).toEqual([]);
	});

	test('narrative strip is on-demand and surfaces the missing-key error inline', async ({
		page
	}) => {
		await page.goto('/analytics');

		const strip = page.getByTestId('analytics-narrative');
		await expect(strip).toBeVisible();
		// Nothing generated yet.
		await expect(page.getByTestId('analytics-narrative-generate')).toHaveText(/Generate/);

		// The e2e API has no OpenRouter key: clicking surfaces the API error inline.
		await page.getByTestId('analytics-narrative-generate').click();
		await expect(page.getByTestId('analytics-narrative-error')).toContainText(
			'QUID_OPENROUTER_API_KEY'
		);
	});

	test('period selector windows the trend chart', async ({ page }) => {
		const consoleErrors: string[] = [];
		page.on('console', (msg) => {
			if (msg.type() === 'error') consoleErrors.push(msg.text());
		});

		await page.goto('/analytics');
		await expect(page.getByTestId('analytics-monthly-trend')).toBeVisible();

		await page.getByTestId('analytics-period-3m').click();
		await expect(page.getByTestId('analytics-period-3m')).toHaveAttribute('aria-pressed', 'true');
		await expect(page.getByTestId('analytics-monthly-trend')).toBeVisible();

		await page.getByTestId('analytics-period-all').click();
		await expect(page.getByTestId('analytics-period-all')).toHaveAttribute('aria-pressed', 'true');
		await expect(page.getByTestId('analytics-monthly-trend')).toBeVisible();

		expect(consoleErrors).toEqual([]);
	});

	test('empty state shows import CTA', async ({ page }) => {
		await seedApiState(page, { categories: analyticsSeed.categories, expenses: [] });
		await page.goto('/analytics');
		await expect(page.getByTestId('analytics-empty')).toBeVisible();
		await expect(page.getByRole('link', { name: 'Import transactions' })).toBeVisible();
	});
});
```

Check `helpers.ts` exports `SeedExpense` as a type (it does, per the interface). Also check the old spec for a seed nuance: if `seedApiState` requires the `uncategorized` category, keep it in the list (it's included above).

One timing caveat to verify while running: the diagnosis baseline is months `-7..-2` only if every one of those months has data — Transport and Groceries cover `-7..-2`, so the baseline window is full. The Netflix creep test needs `-7..-4` established + `-3..-1` candidate, all within the 12-month savings window — they are.

- [ ] **Step 13.2: Run the e2e suite**

From `webui/`: `npm run test:e2e`
Expected: analytics specs pass AND the rest of the suite stays green (other specs never touched analytics endpoints; the seeds are reset per test). If `amazon`/`expenses` specs assert on toasts or shared state, they are unaffected.

If a wentup/savings assertion fails on data, debug by curling the e2e API directly:
`curl -s "http://localhost:8001/api/v1/analytics/diagnosis?as_of=$(date +%F)" | python3 -m json.tool` (only while the Playwright-booted API is up, or boot it manually with the e2e env).

- [ ] **Step 13.3: Commit**

```bash
git add webui/tests/analytics.e2e.ts
git commit -m "test(webui): rework analytics e2e for insight-first page"
```

---

### Task 14: CLAUDE.md update, dev-DB migration, browser smoke check, final verification

**Files:**
- Modify: `CLAUDE.md` (the "## Analytics context" section)

- [ ] **Step 14.1: Replace the "## Analytics context" section of CLAUDE.md**

```markdown
## Analytics context

- The **Analytics** page (`webui/src/routes/analytics/+page.svelte`) is
  insight-first: verdict header → on-demand AI narrative strip → "What went
  up" (diagnosis) → "Where you can save" (savings detectors) → monthly trend
  chart (the only thing the persisted 3M/6M/12M/All period selector affects —
  and it windows CLIENT-SIDE from all-history monthly totals; one parallel
  load on mount, no reload on period change).
- Backend surface is exactly: `/summary`, `/monthly-totals` (optional
  date_from/date_to window) and `/diagnosis`, `/savings`, `/narrative`
  (GET+POST), the last three anchored on the latest COMPLETE month via a
  required `as_of` (the client's today). The old
  category-trends/comparison/top-merchants/importance/weekday/recurring/
  large-transactions/distribution endpoints are GONE — don't resurrect them.
- The aggregation repository (`repositories/analytics.py`) is READ-ONLY (no
  commit). The ONE analytics write path is the stored AI narrative:
  `repositories/analytics_narrative.py` (one row per month, upsert on
  regenerate; table `analytics_narratives`, migration `0021`), written by
  `POST /analytics/narrative` which builds a JSON facts payload from
  diagnosis+savings and calls `ai_narrative.generate_narrative` (OpenRouter,
  `QUID_OPENROUTER_*`, 422 without a key). Generation is strictly on-demand —
  never generate automatically.
- Diagnosis semantics: latest complete month vs each category's trailing
  ≤6-complete-month average where zero-spend months count as £0 (divide by
  window length, not months-with-spend). Increases below £10 AND 10%
  (`_NOISE_FLOOR_*`) roll into "everything else"; new categories have
  `percentChange=null`. Contributors compare each merchant
  (`lower(trim(name))`) to its own baseline, top 3 by delta.
- Savings detectors (constants in `repositories/analytics.py`): scan trailing
  12 complete months on the (merchant, exact amount, ≥3 distinct months)
  recurring grouping. Price creep = established group then a HIGHER amount in
  ≥2 CONSECUTIVE months after it. New recurring = recurring group whose
  merchant's first-EVER transaction is within the last 4 months (this is what
  stops a price change double-reporting as new). Habits = ≥6 txns at ≤£20 avg
  in the latest month. Stack estimate = `amount × monthsCovered ÷ span`
  (capped at amount) so quarterly bills don't read as monthly.
- Month grouping uses the `YYYY-MM` prefix of the date string (works for both
  date-only and timestamped dates). `_month_add`/`_months_between` do calendar
  month arithmetic on `YYYY-MM` keys.
- Charts: only `MonthlyTrendChart` survives on this page (chart.js +
  theme-observer pattern; `CumulativeChart` still serves the dashboard). The
  e2e spec is `webui/tests/analytics.e2e.ts`; it asserts on
  `analytics-verdict*`, `analytics-wentup*`, `analytics-creep-item`,
  `analytics-newrecurring-item`, `analytics-habit-item`, `analytics-stack-*`,
  `analytics-narrative*` testids.
```

Keep the existing "Movers gotcha" paragraph DELETED (it describes removed behaviour).

- [ ] **Step 14.2: Migrate the dev DB**

From `api/`: `uv run alembic upgrade head`
Expected output mentions `0021`. This is REQUIRED before the smoke check — a stale dev DB 500s on `/narrative`.

- [ ] **Step 14.3: Full verification**

- From `api/`: `uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest` → all green.
- From `webui/`: `npm run check && npm run build && npm run test:e2e` → all green.

- [ ] **Step 14.4: Browser smoke check (agent-browser / Playwright MCP)**

Boot the dev stack (API from `api/` with `uv run quid-api serve` or the project's usual dev command — check `api/README.md` for the serve command; webui with `npm run dev`). Then:
1. Load `/analytics`; confirm no non-2xx in the network log and no console errors.
2. Expand a went-up row; confirm contributors + transactions render.
3. Expand the recurring stack.
4. Click Generate on the AI strip: with a real key configured it renders a narrative; without one it must show the inline error (not a toast, not a crash).
5. Toggle the period selector; confirm the chart re-windows without network requests to `/analytics/*`.

- [ ] **Step 14.5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update analytics context for insight-first page"
```

---

## Self-review checklist (run after writing, before execution)

- Spec coverage: verdict header (T10), AI strip on-demand + persisted + inline error (T5-T7, T10), what-went-up with baseline/floor/decreases/contributors/transactions (T1-T2, T11), savings detectors + stack scaling (T3-T4, T11), trend chart demotion + period selector (T12), cuts both sides (T8, T12), migration 0021 (T5), docs (T8, T12, T14), e2e (T13), browser smoke (T14).
- Out of scope honoured: no budgets, no auto-generation, no discretionary detector, thresholds are constants.
