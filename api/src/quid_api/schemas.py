from __future__ import annotations

from decimal import Decimal  # noqa: TC003  pydantic Field reads this at runtime
from typing import Annotated, Any

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


class CategoryOut(_Camel):
    id: str
    name: str
    color: str
    icon: str


class CategoryCreate(_Camel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    color: str | None = None
    icon: str | None = None


class CategoryUpdate(_Camel):
    name: str | None = None
    color: str | None = None
    icon: str | None = None


class ExpenseOut(_Camel):
    id: str
    name: str
    amount: Decimal
    date: str
    category_id: str
    note: str

    @field_serializer("amount")
    def _ser_amount(self, value: Decimal) -> float:
        return float(value)


class ExpenseCreate(_Camel):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    amount: Decimal
    date: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    category_id: Annotated[str, Field(min_length=1)]
    note: str = ""

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
    skipped_invalid_rows: int


class ImportCsvResponse(_Camel):
    imported: int
    skipped_duplicates: int
    skipped_invalid_rows: int
    categories_created: list[CategoryOut]
    expenses: list[ExpenseOut]
    files: list[ImportCsvFileReport]


class ErrorBody(_Camel):
    code: str
    message: str


def dump_camel(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(by_alias=True, exclude_unset=True)
