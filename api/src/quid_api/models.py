from __future__ import annotations

from decimal import Decimal  # noqa: TC003  SQLAlchemy needs runtime access for Mapped[]

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Text, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    color: Mapped[str] = mapped_column(String, nullable=False)
    icon: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    expenses: Mapped[list[Expense]] = relationship(
        back_populates="category",
        passive_deletes=True,
        lazy="raise_on_sql",
    )

    __table_args__ = (
        Index(
            "ix_categories_name_ci",
            text("lower(trim(name))"),
            unique=True,
        ),
    )


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date: Mapped[str] = mapped_column(String, nullable=False)
    category_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    note: Mapped[str] = mapped_column(String, nullable=False, default="")
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default=text("'important'"),
        default="important",
    )

    category: Mapped[Category] = relationship(
        back_populates="expenses",
        lazy="raise_on_sql",
    )
    amazon_order_links: Mapped[list[ExpenseAmazonOrderLink]] = relationship(
        back_populates="expense",
        cascade="all, delete-orphan",
        lazy="raise_on_sql",
    )

    @property
    def amazon_order_ids(self) -> list[str]:
        """Resolve linked Amazon order ids without forcing a lazy load.

        Returns an empty list when ``amazon_order_links`` hasn't been
        eager-loaded — callers that need the populated list must use
        ``selectinload(Expense.amazon_order_links)``.
        """
        state = inspect(self)
        if "amazon_order_links" in state.unloaded:
            return []
        return sorted(link.amazon_order_id for link in self.amazon_order_links)

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        CheckConstraint(
            "date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
            name="ck_expenses_date_iso",
        ),
        CheckConstraint(
            "importance IN ('essential', 'important', 'discretionary')",
            name="ck_expenses_importance",
        ),
        Index("ix_expenses_date", "date"),
        Index("ix_expenses_category", "category_id"),
    )


class ImportRule(Base):
    __tablename__ = "import_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    priority: Mapped[int] = mapped_column(nullable=False, default=100)
    action: Mapped[str] = mapped_column(String, nullable=False)
    target_category_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=True,
    )

    match_name_op: Mapped[str | None] = mapped_column(String, nullable=True)
    match_name_value: Mapped[str | None] = mapped_column(String, nullable=True)

    match_amount_op: Mapped[str | None] = mapped_column(String, nullable=True)
    match_amount_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    match_amount_value2: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    match_date_from: Mapped[str | None] = mapped_column(String, nullable=True)
    match_date_to: Mapped[str | None] = mapped_column(String, nullable=True)

    match_day_of_month: Mapped[int | None] = mapped_column(nullable=True)

    set_display_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "action IN ('exclude', 'categorize')",
            name="ck_import_rules_action",
        ),
        CheckConstraint(
            "(action = 'exclude' AND target_category_id IS NULL) "
            "OR (action = 'categorize' AND target_category_id IS NOT NULL)",
            name="ck_import_rules_action_target",
        ),
        CheckConstraint(
            "(match_name_op IS NULL) = (match_name_value IS NULL)",
            name="ck_import_rules_name_pair",
        ),
        CheckConstraint(
            "match_name_op IS NULL OR match_name_op IN "
            "('contains', 'equals', 'starts_with', 'ends_with')",
            name="ck_import_rules_name_op",
        ),
        CheckConstraint(
            "(match_amount_op IS NULL) = (match_amount_value IS NULL)",
            name="ck_import_rules_amount_pair",
        ),
        CheckConstraint(
            "match_amount_op IS NULL OR match_amount_op IN ('gte', 'lte', 'eq', 'between')",
            name="ck_import_rules_amount_op",
        ),
        CheckConstraint(
            "(match_amount_op = 'between') = (match_amount_value2 IS NOT NULL)",
            name="ck_import_rules_amount_v2",
        ),
        CheckConstraint(
            "match_date_from IS NULL OR "
            "match_date_from GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
            name="ck_import_rules_date_from_iso",
        ),
        CheckConstraint(
            "match_date_to IS NULL OR "
            "match_date_to GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
            name="ck_import_rules_date_to_iso",
        ),
        CheckConstraint(
            "match_name_op IS NOT NULL OR match_amount_op IS NOT NULL "
            "OR match_date_from IS NOT NULL OR match_date_to IS NOT NULL "
            "OR match_day_of_month IS NOT NULL",
            name="ck_import_rules_has_match",
        ),
        CheckConstraint(
            "match_day_of_month IS NULL OR (match_day_of_month >= 1 AND match_day_of_month <= 31)",
            name="ck_import_rules_day_of_month",
        ),
        Index("ix_import_rules_priority", "priority"),
    )


class AiRule(Base):
    __tablename__ = "ai_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    text: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    priority: Mapped[int] = mapped_column(nullable=False, default=100)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint("length(trim(text)) > 0", name="ck_ai_rules_text_not_blank"),
        Index("ix_ai_rules_priority", "priority"),
    )


class ImportLog(Base):
    __tablename__ = "import_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    imported_at: Mapped[str] = mapped_column(String, nullable=False)
    files: Mapped[str] = mapped_column(Text, nullable=False)
    imported: Mapped[int] = mapped_column(nullable=False, default=0)
    updated: Mapped[int] = mapped_column(nullable=False, default=0)
    skipped_duplicates: Mapped[int] = mapped_column(nullable=False, default=0)
    skipped_excluded: Mapped[int] = mapped_column(nullable=False, default=0)
    skipped_invalid_rows: Mapped[int] = mapped_column(nullable=False, default=0)

    __table_args__ = (Index("ix_import_logs_imported_at", "imported_at"),)


class AmazonOrder(Base):
    """An Amazon order imported from a CSV/JSON export.

    `id` IS the Amazon order id (e.g. ``111-1234567-1234567``). Re-importing
    the same order id replaces its details, which keeps the table idempotent
    against repeated exports.
    """

    __tablename__ = "amazon_orders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    order_date: Mapped[str] = mapped_column(String, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="GBP")
    # JSON-serialised list of {"title": str, "quantity": int, "price": float}.
    items_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # JSON-serialised list of per-shipment groups so the UI can show which
    # items shipped together and so matching can try per-shipment totals.
    # Each entry: {"ship_date": str|None, "tracking": str|None, "total": str,
    # "items": [{"title": str, "quantity": int, "price": str|None}]}.
    shipments_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", server_default=text("'[]'")
    )
    payment_last4: Mapped[str | None] = mapped_column(String, nullable=True)
    order_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Short AI-generated (or user-edited) description of what was purchased,
    # generated once at import time and stored. Editable by the user.
    short_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # AI-derived spending category for the order, generated once at import
    # (gated by ai_categorize_enabled) and stored. Optional/derived, so the
    # FK uses ON DELETE SET NULL rather than RESTRICT. When the order is
    # linked to an expense, an uncategorised expense inherits this category.
    category_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    imported_at: Mapped[str] = mapped_column(String, nullable=False)

    expense_links: Mapped[list[ExpenseAmazonOrderLink]] = relationship(
        back_populates="amazon_order",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise_on_sql",
    )

    __table_args__ = (
        CheckConstraint("total > 0", name="ck_amazon_orders_total_positive"),
        CheckConstraint(
            "order_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
            name="ck_amazon_orders_date_iso",
        ),
        Index("ix_amazon_orders_date", "order_date"),
        Index("ix_amazon_orders_total", "total"),
    )


class ExpenseAmazonOrderLink(Base):
    """Join table: an expense may cover multiple Amazon orders (when Amazon
    bills them as a combined charge) and an Amazon order may be billed
    across multiple expenses (when shipments are billed separately)."""

    __tablename__ = "expense_amazon_orders"

    expense_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("expenses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    amazon_order_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("amazon_orders.id", ondelete="CASCADE"),
        primary_key=True,
    )

    expense: Mapped[Expense] = relationship(
        back_populates="amazon_order_links",
        lazy="raise_on_sql",
    )
    amazon_order: Mapped[AmazonOrder] = relationship(
        back_populates="expense_links",
        lazy="raise_on_sql",
    )

    __table_args__ = (
        Index(
            "ix_expense_amazon_orders_amazon_order_id",
            "amazon_order_id",
        ),
    )


class AppSettings(Base):
    """Singleton row holding global application settings.

    The single row uses the fixed id ``"singleton"``. New settings are added
    by extending this table; this avoids a generic key/value store that would
    lose strong typing.
    """

    __tablename__ = "app_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    currency: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default=text("'GBP'"),
        default="GBP",
    )
    show_importance_badge: Mapped[bool] = mapped_column(
        nullable=False,
        server_default=text("1"),
        default=True,
    )
    ai_categorize_enabled: Mapped[bool] = mapped_column(
        nullable=False,
        server_default=text("1"),
        default=True,
    )
    ai_short_names_enabled: Mapped[bool] = mapped_column(
        nullable=False,
        server_default=text("1"),
        default=True,
    )
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint("id = 'singleton'", name="ck_app_settings_singleton"),
        CheckConstraint(
            "length(trim(currency)) = 3",
            name="ck_app_settings_currency_len",
        ),
    )
