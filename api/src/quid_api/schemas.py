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

    @field_serializer("amount")
    def _ser_amount(self, value: Decimal) -> float:
        return float(value)


class ExpenseCreate(_Camel):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    amount: Decimal
    date: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    category_id: Annotated[str, Field(min_length=1)]
    note: str = ""
    importance: Importance = "important"

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
    date: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    note: str = ""
    importance: Importance = "important"


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
    amount: Decimal
    date: str
    note: str
    kind: ImportPreviewKind
    existing_expense_id: str | None = None
    existing_category_id: str | None = None
    suggested_category: ImportPreviewCategory
    existing_category_name: str | None = None
    suggested_importance: Importance = "important"
    existing_importance: Importance | None = None

    @field_serializer("amount")
    def _ser_amount(self, value: Decimal) -> float:
        return float(value)


class ImportCsvPreviewSummary(_Camel):
    creates: int
    category_updates: int
    hidden_duplicates: int
    excluded: int
    invalid_rows: int
    ai_categorized: int
    skipped_refunds: int = 0


class ImportCsvPreviewResponse(_Camel):
    import_id: str
    rows: list[ImportPreviewRow]
    summary: ImportCsvPreviewSummary
    files: list[ImportCsvFileReport]


class ImportCsvConfirmCreateRow(_Camel):
    preview_row_id: str
    dedupe_key_hash: str
    name: Annotated[str, Field(min_length=1, max_length=200)]
    amount: Decimal
    date: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    note: str = ""
    category_name: Annotated[str, Field(min_length=1, max_length=120)]
    importance: Importance = "important"


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
    created_at: str

    @field_serializer("match_amount_value", "match_amount_value2")
    def _ser_amount(self, value: Decimal | None) -> float | None:
        return None if value is None else float(value)


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
    match_date_from: Annotated[str | None, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None
    match_date_to: Annotated[str | None, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None
    match_day_of_month: Annotated[int | None, Field(ge=1, le=31)] = None
    set_display_name: str | None = None


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
    match_date_from: Annotated[str | None, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None
    match_date_to: Annotated[str | None, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None
    match_day_of_month: Annotated[int | None, Field(ge=1, le=31)] = None
    set_display_name: str | None = None


class ImportRuleApplyResponse(_Camel):
    matched: int
    updated: int
    deleted: int


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
    def _ser_price(self, value: Decimal | None) -> float | None:
        return None if value is None else float(value)


class AmazonOrderShipment(_Camel):
    ship_date: str | None = None
    tracking: str | None = None
    total: Decimal = Decimal(0)
    items: list[AmazonOrderItem] = Field(default_factory=list)

    @field_serializer("total")
    def _ser_total(self, value: Decimal) -> float:
        return float(value)


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

    @field_serializer("total")
    def _ser_total(self, value: Decimal) -> float:
        return float(value)


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


class AppSettingsOut(_Camel):
    currency: str
    show_importance_badge: bool
    ai_categorize_enabled: bool
    ai_short_names_enabled: bool
    updated_at: str


class AppSettingsUpdate(_Camel):
    currency: Annotated[str | None, Field(min_length=3, max_length=3)] = None
    show_importance_badge: bool | None = None
    ai_categorize_enabled: bool | None = None
    ai_short_names_enabled: bool | None = None


class ErrorBody(_Camel):
    code: str
    message: str


def dump_camel(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(by_alias=True, exclude_unset=True)
