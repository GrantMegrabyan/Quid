from __future__ import annotations

import json
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import (
    AliasGenerator,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)
from pydantic.alias_generators import to_camel

from quid_api.datelib import validate_iso_date, validate_iso_datetime

# Canonical money transport: every monetary value crosses the API boundary as a
# decimal STRING with exactly two fractional digits ("19.99", "42.00"), never a
# JSON number. JSON numbers are IEEE-754 floats; round-tripping money through
# them risks silent precision drift (e.g. 19.990000000000002) that breaks the
# exact-Decimal matching used for Amazon orders and dedup. The server stores
# money as Numeric(12, 2) and quantises to 2dp, so a fixed 2-digit string is
# the lossless canonical form. Requests may send money as a string OR number
# (Pydantic coerces both into Decimal); responses always emit strings.
_MONEY_QUANTUM = Decimal("0.01")


def _money_str(value: Decimal) -> str:
    """Render a Decimal as a canonical 2dp money string ("19.99")."""
    return str(value.quantize(_MONEY_QUANTUM))


def _validate_required_date(value: str) -> str:
    """Pydantic validator for a required ``YYYY-MM-DD`` calendar date.

    Strict date-only — used for import-rule date bounds, whose DB columns keep a
    date-only CHECK constraint.
    """
    return validate_iso_date(value)


def _validate_optional_date(value: str | None) -> str | None:
    """Pydantic validator for an optional ``YYYY-MM-DD`` calendar date."""
    return None if value is None else validate_iso_date(value)


def _validate_required_datetime(value: str) -> str:
    """Pydantic validator for a required expense date.

    Accepts a bare ``YYYY-MM-DD`` date or a full ``YYYY-MM-DDTHH:MM:SS``
    timestamp. Expenses carry an optional time so same-day duplicates can be
    disambiguated during import dedupe.
    """
    return validate_iso_datetime(value)


def _validate_optional_datetime(value: str | None) -> str | None:
    """Pydantic validator for an optional expense date (date or datetime)."""
    return None if value is None else validate_iso_datetime(value)


class _Camel(BaseModel):
    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            validation_alias=to_camel,
            serialization_alias=to_camel,
        ),
        populate_by_name=True,
        from_attributes=True,
        str_strip_whitespace=False,
    )


Importance = Literal["essential", "important", "discretionary"]


class CategoryOut(_Camel):
    id: str
    name: str
    color: str
    icon: str
    description: str


class CategoryDeleteResult(_Camel):
    reassigned: int


class CategoryCreate(_Camel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    color: str | None = None
    icon: str | None = None
    description: Annotated[str, Field(max_length=1000)] = ""


class CategoryUpdate(_Camel):
    name: str | None = None
    color: str | None = None
    icon: str | None = None
    description: Annotated[str | None, Field(max_length=1000)] = None


CategorySource = Literal["manual", "rule", "amazon", "ai", "import"]


class ExpenseOut(_Camel):
    id: str
    name: str
    amount: Decimal
    date: str
    category_id: str
    note: str
    display_name: str | None = None
    importance: Importance
    category_source: CategorySource = "import"
    amazon_order_ids: list[str] = Field(default_factory=list)
    # Effective note: the expense's own note, else a linked Amazon order's
    # short name (computed server-side via ``Expense.resolved_note`` so the
    # client needn't fetch the whole Amazon-orders table just to label rows).
    resolved_note: str = ""

    @field_serializer("amount")
    def _ser_amount(self, value: Decimal) -> str:
        return _money_str(value)


class ExpenseCreate(_Camel):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    amount: Decimal
    date: str
    category_id: Annotated[str, Field(min_length=1)]
    note: str = ""
    importance: Importance = "important"

    _validate_date = field_validator("date")(_validate_required_datetime)

    @field_validator("amount")
    @classmethod
    def _amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive.")
        return v


class ExpenseUpdate(_Camel):
    name: str | None = None
    amount: Decimal | None = None
    date: str | None = None
    category_id: str | None = None
    note: str | None = None
    display_name: str | None = None
    importance: Importance | None = None

    _validate_date = field_validator("date")(_validate_optional_datetime)

    @field_validator("amount")
    @classmethod
    def _amount_positive(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("Amount must be positive.")
        return v


class BulkExpenseItem(_Camel):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    category: str
    amount: Decimal
    date: str
    note: str = ""
    importance: Importance = "important"

    _validate_date = field_validator("date")(_validate_required_datetime)


class BulkExpenseRequest(_Camel):
    items: Annotated[list[BulkExpenseItem], Field(min_length=1, max_length=5000)]


class BulkExpenseResponse(_Camel):
    created: int
    categories_created: list[CategoryOut]
    expenses: list[ExpenseOut]


class ImportCsvFileReport(_Camel):
    filename: str
    rows: int
    imported: int
    skipped_duplicates: int
    skipped_excluded: int = 0
    skipped_invalid_rows: int


class ImportCsvResponse(_Camel):
    imported: int
    skipped_duplicates: int
    skipped_excluded: int = 0
    skipped_refunds: int = 0
    skipped_income: int = 0
    skipped_invalid_rows: int
    transactions_found: int = 0
    ai_categorized: int = 0
    categories_created: list[CategoryOut]
    expenses: list[ExpenseOut]
    files: list[ImportCsvFileReport]


ImportPreviewKind = Literal["create", "category_update", "duplicate_same_category", "excluded"]


class ImportPreviewCategory(_Camel):
    id: str | None = None
    name: str
    exists: bool = False


class ImportPreviewRow(_Camel):
    preview_row_id: str
    filename: str
    source_row: int
    dedupe_key_hash: str
    name: str
    # The name a matching ``categorize`` import rule will apply on confirm
    # (rule ``set_display_name``). ``None`` when no rule overrides it. Lets the
    # preview show the FINAL name instead of the raw merchant string.
    display_name: str | None = None
    amount: Decimal
    date: str
    note: str
    kind: ImportPreviewKind
    # Human-readable explanation for ``kind == "excluded"`` rows (why the row
    # won't be imported by default): AI exclusion, a matching exclude rule, a
    # detected refund, or detected incoming money. ``None`` for non-excluded
    # rows.
    reason: str | None = None
    existing_expense_id: str | None = None
    existing_category_id: str | None = None
    suggested_category: ImportPreviewCategory
    # True when ``suggested_category`` came from a matching ``categorize`` import
    # rule (not AI/heuristic). Lets the preview flag the category as rule-driven,
    # mirroring ``display_name``.
    category_from_rule: bool = False
    # The AI/CSV-derived category a matching rule overrode, set ONLY when it
    # differs from ``suggested_category``. Lets the preview show what the AI
    # identified before the rule replaced it. ``None`` otherwise.
    overridden_category_name: str | None = None
    existing_category_name: str | None = None
    suggested_importance: Importance = "important"
    existing_importance: Importance | None = None

    @field_serializer("amount")
    def _ser_amount(self, value: Decimal) -> str:
        return _money_str(value)


class ImportCsvPreviewSummary(_Camel):
    creates: int
    category_updates: int
    hidden_duplicates: int
    excluded: int
    invalid_rows: int
    ai_categorized: int
    skipped_refunds: int = 0
    skipped_income: int = 0


class ImportPreviewInvalidRow(_Camel):
    """A row dropped during parsing (CSV) with a human-readable reason.

    Surfaced so the import preview can explain WHICH rows were invalid and WHY
    instead of only showing an aggregate count. Free-form import produces no
    invalid rows (malformed AI output is dropped upstream).
    """

    filename: str
    source_row: int
    reason: str
    name: str
    amount: str
    date: str


class ImportCsvPreviewResponse(_Camel):
    import_id: str
    rows: list[ImportPreviewRow]
    invalid: list[ImportPreviewInvalidRow] = []
    summary: ImportCsvPreviewSummary
    files: list[ImportCsvFileReport]


class ImportCsvConfirmCreateRow(_Camel):
    preview_row_id: str
    dedupe_key_hash: str
    name: Annotated[str, Field(min_length=1, max_length=200)]
    amount: Decimal
    date: str
    note: str = ""
    category_name: Annotated[str, Field(min_length=1, max_length=120)]
    importance: Importance = "important"

    _validate_date = field_validator("date")(_validate_required_datetime)


class ImportCsvConfirmCategoryUpdateRow(_Camel):
    preview_row_id: str
    dedupe_key_hash: str
    existing_expense_id: str
    category_name: Annotated[str, Field(min_length=1, max_length=120)]
    importance: Importance = "important"
    accept: bool = True


class ImportCsvConfirmRequest(_Camel):
    import_id: str
    files: list[str] = Field(default_factory=list)
    creates: list[ImportCsvConfirmCreateRow] = Field(default_factory=list)
    category_updates: list[ImportCsvConfirmCategoryUpdateRow] = Field(default_factory=list)


class ImportCsvConfirmResponse(_Camel):
    created: int
    updated: int
    skipped_duplicates: int
    skipped_stale_updates: int
    kept_existing: int
    categories_created: list[CategoryOut]
    expenses: list[ExpenseOut]


NameMatchOp = Literal["contains", "equals", "starts_with", "ends_with"]
AmountMatchOp = Literal["gte", "lte", "eq", "between"]
RuleAction = Literal["exclude", "categorize"]


class ImportRuleOut(_Camel):
    id: str
    name: str
    enabled: bool
    priority: int
    action: RuleAction
    target_category_id: str | None
    match_name_op: NameMatchOp | None
    match_name_value: str | None
    match_amount_op: AmountMatchOp | None
    match_amount_value: Decimal | None
    match_amount_value2: Decimal | None
    match_date_from: str | None
    match_date_to: str | None
    match_day_of_month: int | None = None
    set_display_name: str | None = None
    set_note: str | None = None
    created_at: str

    @field_serializer("match_amount_value", "match_amount_value2")
    def _ser_amount(self, value: Decimal | None) -> str | None:
        return None if value is None else _money_str(value)


class ImportRuleCreate(_Camel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    enabled: bool = True
    priority: int = 100
    action: RuleAction
    target_category_id: str | None = None
    match_name_op: NameMatchOp | None = None
    match_name_value: str | None = None
    match_amount_op: AmountMatchOp | None = None
    match_amount_value: Decimal | None = None
    match_amount_value2: Decimal | None = None
    match_date_from: str | None = None
    match_date_to: str | None = None
    match_day_of_month: Annotated[int | None, Field(ge=1, le=31)] = None
    set_display_name: str | None = None
    set_note: str | None = None

    _validate_dates = field_validator("match_date_from", "match_date_to")(_validate_optional_date)


class ImportRuleUpdate(_Camel):
    name: str | None = None
    enabled: bool | None = None
    priority: int | None = None
    action: RuleAction | None = None
    target_category_id: str | None = None
    match_name_op: NameMatchOp | None = None
    match_name_value: str | None = None
    match_amount_op: AmountMatchOp | None = None
    match_amount_value: Decimal | None = None
    match_amount_value2: Decimal | None = None
    match_date_from: str | None = None
    match_date_to: str | None = None
    match_day_of_month: Annotated[int | None, Field(ge=1, le=31)] = None
    set_display_name: str | None = None
    set_note: str | None = None

    _validate_dates = field_validator("match_date_from", "match_date_to")(_validate_optional_date)


class ImportRuleApplyResponse(_Camel):
    matched: int
    updated: int
    deleted: int


class ImportRulePreviewRequest(_Camel):
    """Match-condition fields for a (possibly unsaved) rule.

    Action/target-category are omitted: a preview only reports which existing
    transactions the conditions match, so a draft can be checked before saving.
    """

    match_name_op: NameMatchOp | None = None
    match_name_value: str | None = None
    match_amount_op: AmountMatchOp | None = None
    match_amount_value: Decimal | None = None
    match_amount_value2: Decimal | None = None
    match_date_from: str | None = None
    match_date_to: str | None = None
    match_day_of_month: Annotated[int | None, Field(ge=1, le=31)] = None

    _validate_dates = field_validator("match_date_from", "match_date_to")(_validate_optional_date)


class ImportRulePreviewResponse(_Camel):
    matched: int
    expenses: list[ExpenseOut]


class AiRuleOut(_Camel):
    id: str
    text: str
    enabled: bool
    priority: int
    created_at: str


class AiRuleCreate(_Camel):
    text: Annotated[str, Field(min_length=1, max_length=2000)]
    enabled: bool = True
    priority: int = 100


class AiRuleUpdate(_Camel):
    text: Annotated[str | None, Field(min_length=1, max_length=2000)] = None
    enabled: bool | None = None
    priority: int | None = None


ImportSource = Literal["csv", "freeform"]


class ImportFreeformPreviewRequest(_Camel):
    raw_input: Annotated[str, Field(min_length=1, max_length=10_000)]


class ImportFreeformConfirmRequest(_Camel):
    import_id: str
    raw_input: Annotated[str, Field(min_length=1, max_length=10_000)]
    files: list[str] = Field(default_factory=list)
    creates: list[ImportCsvConfirmCreateRow] = Field(default_factory=list)
    category_updates: list[ImportCsvConfirmCategoryUpdateRow] = Field(default_factory=list)


class ImportLogOut(_Camel):
    id: str
    imported_at: str
    source: ImportSource = "csv"
    files: list[str]
    raw_input: str | None = None
    imported: int
    updated: int
    skipped_duplicates: int
    skipped_excluded: int
    skipped_invalid_rows: int

    @field_validator("files", mode="before")
    @classmethod
    def _parse_files(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)  # type: ignore[no-any-return]
        return v  # type: ignore[return-value]


class AmazonOrderItem(_Camel):
    title: str
    quantity: int = 1
    price: Decimal | None = None

    @field_serializer("price")
    def _ser_price(self, value: Decimal | None) -> str | None:
        return None if value is None else _money_str(value)


class AmazonOrderShipment(_Camel):
    ship_date: str | None = None
    tracking: str | None = None
    total: Decimal = Decimal(0)
    items: list[AmazonOrderItem] = Field(default_factory=list)

    @field_serializer("total")
    def _ser_total(self, value: Decimal) -> str:
        return _money_str(value)


class AmazonLinkedExpense(_Camel):
    """Minimal expense fields needed to label a linked Amazon charge.

    Embedded in ``AmazonOrderOut`` so the ``/amazon`` page can render
    "Linked to ..." labels without fetching the entire expense table just to
    resolve a handful of linked ids.
    """

    id: str
    name: str
    amount: Decimal
    display_name: str | None = None

    @field_serializer("amount")
    def _ser_amount(self, value: Decimal) -> str:
        return _money_str(value)


class AmazonOrderOut(_Camel):
    id: str
    order_date: str
    total: Decimal
    currency: str
    items: list[AmazonOrderItem] = Field(default_factory=list)
    shipments: list[AmazonOrderShipment] = Field(default_factory=list)
    payment_last4: str | None = None
    order_url: str | None = None
    short_name: str | None = None
    category_id: str | None = None
    imported_at: str
    linked_expense_ids: list[str] = Field(default_factory=list)
    linked_expenses: list[AmazonLinkedExpense] = Field(default_factory=list)

    @field_serializer("total")
    def _ser_total(self, value: Decimal) -> str:
        return _money_str(value)


class AmazonOrderListOut(_Camel):
    """Paginated Amazon order list: a page of orders plus the total count of
    orders matching the active filters (so the UI can render page controls
    without fetching the whole table)."""

    items: list[AmazonOrderOut] = Field(default_factory=list)
    total: int = 0
    limit: int = 0
    offset: int = 0


class AmazonImportSkippedOrder(_Camel):
    """An order dropped during import, with a human-readable reason.

    Surfaced in the response so the user can see which scraped orders were not
    imported and why. The CSV path leaves this empty (it tracks only an
    aggregate ``skipped_rows`` count, with no per-row order id).
    """

    order_id: str
    reason: str


class AmazonImportFileReport(_Camel):
    filename: str
    orders_parsed: int
    skipped_rows: int
    # Per-order skip reasons. Populated by the browser-export import; left
    # empty by CSV import (additive + backwards compatible).
    skipped: list[AmazonImportSkippedOrder] = Field(default_factory=list)


class AmazonImportResponse(_Camel):
    created: int
    updated: int
    auto_matched: int
    ambiguous: int
    combined_matched: int = 0
    files: list[AmazonImportFileReport]


class AmazonExportItem(_Camel):
    """A single line item from a browser-scraped Amazon order.

    ``price`` is a per-item price transported as a STRING ("9.99"); see
    ``AmazonExportRequest`` for the money-as-strings contract.
    """

    title: str
    quantity: int = 1
    price: str | None = None


class AmazonExportShipment(_Camel):
    """A scraped shipment group.

    Display-only for matching: a single shipment contributes nothing to amount
    matching (only multi-shipment orders use per-shipment totals,
    ``repositories/amazon_orders.py`` ``_charge_amounts``), so the MVP scraper
    emits none. ``total`` is a money STRING (see ``AmazonExportRequest``).
    """

    total: str | None = None
    ship_date: str | None = None
    tracking: str | None = None
    items: list[AmazonExportItem] = Field(default_factory=list)


class AmazonExportOrder(_Camel):
    """One browser-scraped Amazon order.

    Row-level fields are intentionally lenient so a partial scrape still
    imports its good orders, mirroring the CSV importer: a blank/absent
    ``order_id`` or ``order_date``, a non-importable ``status``, or a
    missing/non-positive ``total`` causes the SERVER to skip just this order
    (with a reason) — it does not 422 the whole request. ``total`` is therefore
    optional (a missing total is skipped, not rejected) and enforced ``> 0`` in
    code, never via the DB CHECK.
    """

    order_id: str = ""
    order_date: str = ""
    total: str | None = None
    currency: str | None = None
    status: str | None = None
    items: list[AmazonExportItem] = Field(default_factory=list)
    shipments: list[AmazonExportShipment] = Field(default_factory=list)
    payment_last4: str | None = None
    order_url: str | None = None


class AmazonExportRequest(_Camel):
    """Browser-scraped Amazon order history POSTed to ``/import-export``.

    MONEY-AS-STRINGS CONTRACT (B2): every monetary field (order ``total``, item
    ``price``, shipment ``total``) MUST be a JSON string ("19.99"), never a
    JSON number. The amount matcher does exact ``Decimal`` equality, and a JSON
    number produced by the scraper's own float arithmetic (e.g.
    ``19.990000000000002``) would transport faithfully and then silently fail
    to match a ``Decimal("19.99")`` expense. Typing money as ``str`` makes a
    JSON number a hard 422 (Pydantic ``string_type``), forcing the scraper to
    emit the exact scraped text; the server then parses each string to an exact
    ``Decimal`` in code (the same ``_parse_decimal`` the CSV importer uses).

    Structural problems (body not an object; ``orders`` missing, not an array,
    or empty) are 422s; row-level problems are skipped per-order with a reason
    (see ``AmazonExportOrder``).
    """

    scraper_version: str | None = None
    domain: str | None = None
    # Upper bound is defense-in-depth against a pathological pasted payload
    # (a heavy buyer's full history is well under this); structural so an
    # over-size payload 422s rather than tying up the ingest/match pass.
    orders: list[AmazonExportOrder] = Field(min_length=1, max_length=5000)


class AmazonMatchAllResponse(_Camel):
    auto_matched: int
    ambiguous: int
    total_orders: int
    combined_matched: int = 0


class AmazonLinkRequest(_Camel):
    expense_id: Annotated[str, Field(min_length=1)]


class AmazonShortNameRequest(_Camel):
    short_name: Annotated[str, Field(max_length=60)]


class AmazonCategoryRequest(_Camel):
    # null clears the order's category; a non-null value must be an existing id.
    category_id: str | None = None


class AmazonRecategorizePreviewRow(_Camel):
    """One order's AI re-categorisation suggestion (read-only preview).

    ``changed`` is True when the suggested category differs from the order's
    current category (the UI hides unchanged rows behind a toggle).
    ``suggested_category_exists`` is True when the suggested name maps to an
    existing category (a False means confirming would create a new ``cat-*``).
    """

    order_id: str
    name: str
    total: Decimal
    order_date: str
    current_category_id: str | None = None
    current_category_name: str | None = None
    suggested_category_name: str
    suggested_category_exists: bool
    changed: bool

    @field_serializer("total")
    def _ser_total(self, value: Decimal) -> str:
        return _money_str(value)


class AmazonRecategorizePreviewResponse(_Camel):
    rows: list[AmazonRecategorizePreviewRow] = Field(default_factory=list)
    eligible: int
    changed: int
    unchanged: int


class AmazonRecategorizeConfirmRow(_Camel):
    order_id: Annotated[str, Field(min_length=1)]
    category_name: Annotated[str, Field(min_length=1, max_length=120)]


class AmazonRecategorizeConfirmRequest(_Camel):
    rows: list[AmazonRecategorizeConfirmRow] = Field(default_factory=list)


class AmazonRecategorizeConfirmResponse(_Camel):
    updated: int
    categories_created: int
    expenses_updated: int


class AppSettingsOut(_Camel):
    currency: str
    show_importance_badge: bool
    ai_categorize_enabled: bool
    ai_short_names_enabled: bool
    categorize_model: str
    updated_at: str


class AppSettingsUpdate(_Camel):
    currency: Annotated[str | None, Field(min_length=3, max_length=3)] = None
    show_importance_badge: bool | None = None
    ai_categorize_enabled: bool | None = None
    ai_short_names_enabled: bool | None = None
    categorize_model: Annotated[str | None, Field(min_length=1)] = None


class ErrorBody(_Camel):
    code: str
    message: str


# --------------------------------------------------------------------------- #
# Analytics                                                                    #
# --------------------------------------------------------------------------- #
# All analytics responses aggregate expenses server-side. Money is emitted as
# the canonical 2dp string (via ``_money_str``); deltas/percentages that can be
# negative are also strings for the money fields and floats for percentages.


class MonthlyTotalOut(_Camel):
    """Total spend + transaction count for a single calendar month."""

    month: str  # "YYYY-MM"
    total: Decimal
    count: int

    @field_serializer("total")
    def _ser_total(self, value: Decimal) -> str:
        return _money_str(value)


class MonthlyTotalsResponse(_Camel):
    months: list[MonthlyTotalOut] = Field(default_factory=list)
    total: Decimal
    average: Decimal
    count: int

    @field_serializer("total", "average")
    def _ser_money(self, value: Decimal) -> str:
        return _money_str(value)


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


class NarrativeOut(_Camel):
    month: str
    content: str
    generated_at: str
    model: str


class NarrativeResponse(_Camel):
    narrative: NarrativeOut | None = None


class NarrativeGenerateRequest(_Camel):
    as_of: str


def dump_camel(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(by_alias=True, exclude_unset=True)
