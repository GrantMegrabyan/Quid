from __future__ import annotations

from decimal import Decimal  # noqa: TC003  SQLAlchemy needs runtime access for Mapped[]

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Text, text
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

    category: Mapped[Category] = relationship(
        back_populates="expenses",
        lazy="raise_on_sql",
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        CheckConstraint(
            "date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
            name="ck_expenses_date_iso",
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
            "OR match_date_from IS NOT NULL OR match_date_to IS NOT NULL",
            name="ck_import_rules_has_match",
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
