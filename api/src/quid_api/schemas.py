from __future__ import annotations

from decimal import Decimal  # noqa: TC003  pydantic Field reads this at runtime
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
    skipped_excluded: int = 0
    skipped_invalid_rows: int


class ImportCsvResponse(_Camel):
    imported: int
    skipped_duplicates: int
    skipped_excluded: int = 0
    skipped_invalid_rows: int
    transactions_found: int = 0
    ai_categorized: int = 0
    categories_created: list[CategoryOut]
    expenses: list[ExpenseOut]
    files: list[ImportCsvFileReport]


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


class ErrorBody(_Camel):
    code: str
    message: str


def dump_camel(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(by_alias=True, exclude_unset=True)
