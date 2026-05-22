from __future__ import annotations

from decimal import Decimal  # noqa: TC003  SQLAlchemy needs runtime access for Mapped[]

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    color: Mapped[str] = mapped_column(String, nullable=False)
    icon: Mapped[str] = mapped_column(String, nullable=False)

    expenses: Mapped[list[Expense]] = relationship(back_populates="category")

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

    category: Mapped[Category] = relationship(back_populates="expenses")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        CheckConstraint(
            "date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'",
            name="ck_expenses_date_iso",
        ),
        Index("ix_expenses_date", "date"),
        Index("ix_expenses_category", "category_id"),
    )
