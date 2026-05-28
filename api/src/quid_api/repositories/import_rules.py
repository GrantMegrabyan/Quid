from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select, update

from quid_api.errors import RepositoryError, RepositoryErrorCode
from quid_api.models import Category, Expense, ImportRule

if TYPE_CHECKING:
    from decimal import Decimal

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class RuleMatchItem:
    name: str
    amount: Decimal
    date: str


@dataclass(frozen=True)
class ApplyResult:
    matched: int
    updated: int
    deleted: int


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_name(name: str | None) -> str:
    cleaned = (name or "").strip()
    if cleaned == "":
        raise RepositoryError(RepositoryErrorCode.VALIDATION, "Rule name cannot be blank.")
    return cleaned


def _matches_name(rule: ImportRule, value: str) -> bool:
    if rule.match_name_op is None:
        return True
    assert rule.match_name_value is not None
    needle = rule.match_name_value.strip().lower()
    haystack = value.strip().lower()
    match rule.match_name_op:
        case "contains":
            return needle in haystack
        case "equals":
            return haystack == needle
        case "starts_with":
            return haystack.startswith(needle)
        case "ends_with":
            return haystack.endswith(needle)
    return False


def _matches_amount(rule: ImportRule, amount: Decimal) -> bool:
    if rule.match_amount_op is None:
        return True
    assert rule.match_amount_value is not None
    threshold = rule.match_amount_value
    match rule.match_amount_op:
        case "gte":
            return amount >= threshold
        case "lte":
            return amount <= threshold
        case "eq":
            return amount == threshold
        case "between":
            assert rule.match_amount_value2 is not None
            low = min(threshold, rule.match_amount_value2)
            high = max(threshold, rule.match_amount_value2)
            return low <= amount <= high
    return False


def _matches_date(rule: ImportRule, date: str) -> bool:
    if rule.match_date_from is not None and date < rule.match_date_from:
        return False
    return not (rule.match_date_to is not None and date > rule.match_date_to)


def _matches_day_of_month(rule: ImportRule, date: str) -> bool:
    if rule.match_day_of_month is None:
        return True
    try:
        day = int(date[8:10])
    except (ValueError, IndexError):
        return False
    return day == rule.match_day_of_month


def matches_rule(rule: ImportRule, item: RuleMatchItem) -> bool:
    return (
        rule.enabled
        and _matches_name(rule, item.name)
        and _matches_amount(rule, item.amount)
        and _matches_date(rule, item.date)
        and _matches_day_of_month(rule, item.date)
    )


class ImportRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self, *, enabled_only: bool = False) -> list[ImportRule]:
        stmt = select(ImportRule).order_by(
            ImportRule.priority, ImportRule.created_at, ImportRule.id
        )
        if enabled_only:
            stmt = stmt.where(ImportRule.enabled.is_(True))
        return list((await self.session.scalars(stmt)).all())

    async def get(self, rule_id: str) -> ImportRule:
        row = await self.session.get(ImportRule, rule_id)
        if row is None:
            raise RepositoryError(
                RepositoryErrorCode.NOT_FOUND,
                f"Import rule not found: {rule_id}",
            )
        return row

    async def create(
        self,
        *,
        name: str,
        enabled: bool,
        priority: int,
        action: str,
        target_category_id: str | None,
        match_name_op: str | None,
        match_name_value: str | None,
        match_amount_op: str | None,
        match_amount_value: Decimal | None,
        match_amount_value2: Decimal | None,
        match_date_from: str | None,
        match_date_to: str | None,
        match_day_of_month: int | None = None,
        set_display_name: str | None = None,
    ) -> ImportRule:
        row = ImportRule(
            id=f"rule-{uuid4()}",
            name=_clean_name(name),
            enabled=enabled,
            priority=priority,
            action=action,
            target_category_id=target_category_id,
            match_name_op=match_name_op,
            match_name_value=match_name_value.strip() if match_name_value else None,
            match_amount_op=match_amount_op,
            match_amount_value=match_amount_value,
            match_amount_value2=match_amount_value2,
            match_date_from=match_date_from,
            match_date_to=match_date_to,
            match_day_of_month=match_day_of_month,
            set_display_name=set_display_name,
            created_at=_now_iso(),
        )
        await self._validate(row)
        self.session.add(row)
        await self.session.flush()
        return row

    async def update(self, rule_id: str, **patch: object) -> ImportRule:
        row = await self.get(rule_id)
        for key, value in patch.items():
            if key == "name" and value is not None:
                value = _clean_name(str(value))
            if key == "match_name_value" and isinstance(value, str):
                value = value.strip() or None
            setattr(row, key, value)
        await self._validate(row)
        await self.session.flush()
        return row

    async def delete(self, rule_id: str) -> None:
        row = await self.get(rule_id)
        await self.session.delete(row)
        await self.session.flush()

    async def first_match(self, item: RuleMatchItem) -> ImportRule | None:
        for rule in await self.list_all(enabled_only=True):
            if matches_rule(rule, item):
                return rule
        return None

    async def apply_to_existing(self, rule_id: str) -> ApplyResult:
        rule = await self.get(rule_id)
        if not rule.enabled:
            return ApplyResult(matched=0, updated=0, deleted=0)

        expenses = list((await self.session.scalars(select(Expense))).all())
        matched = [
            expense
            for expense in expenses
            if matches_rule(
                rule,
                RuleMatchItem(name=expense.name, amount=expense.amount, date=expense.date),
            )
        ]
        if rule.action == "exclude":
            for expense in matched:
                await self.session.delete(expense)
            await self.session.flush()
            return ApplyResult(matched=len(matched), updated=0, deleted=len(matched))

        assert rule.target_category_id is not None
        await self.session.execute(
            update(Expense)
            .where(Expense.id.in_([expense.id for expense in matched]))
            .values(category_id=rule.target_category_id)
        )
        await self.session.flush()
        return ApplyResult(matched=len(matched), updated=len(matched), deleted=0)

    async def apply_all_to_existing(self) -> ApplyResult:
        rules = await self.list_all(enabled_only=True)
        if not rules:
            return ApplyResult(matched=0, updated=0, deleted=0)

        expenses = list((await self.session.scalars(select(Expense))).all())
        category_updates: dict[str, list[str]] = {}
        to_delete: list[Expense] = []
        matched_total = 0

        for expense in expenses:
            item = RuleMatchItem(name=expense.name, amount=expense.amount, date=expense.date)
            for rule in rules:
                if not matches_rule(rule, item):
                    continue
                matched_total += 1
                if rule.action == "exclude":
                    to_delete.append(expense)
                else:
                    assert rule.target_category_id is not None
                    if expense.category_id != rule.target_category_id:
                        category_updates.setdefault(rule.target_category_id, []).append(expense.id)
                break

        updated_total = 0
        for target_category_id, expense_ids in category_updates.items():
            await self.session.execute(
                update(Expense)
                .where(Expense.id.in_(expense_ids))
                .values(category_id=target_category_id)
            )
            updated_total += len(expense_ids)

        for expense in to_delete:
            await self.session.delete(expense)

        await self.session.flush()
        return ApplyResult(
            matched=matched_total,
            updated=updated_total,
            deleted=len(to_delete),
        )

    async def _validate(self, row: ImportRule) -> None:
        if row.action not in {"exclude", "categorize"}:
            raise RepositoryError(RepositoryErrorCode.VALIDATION, "Rule action is invalid.")
        if row.action == "exclude" and row.target_category_id is not None:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                "Exclude rules cannot target a category.",
            )
        if row.action == "categorize":
            if row.target_category_id is None:
                raise RepositoryError(
                    RepositoryErrorCode.VALIDATION,
                    "Categorize rules require a target category.",
                )
            if await self.session.get(Category, row.target_category_id) is None:
                raise RepositoryError(
                    RepositoryErrorCode.VALIDATION,
                    f'Category "{row.target_category_id}" does not exist.',
                )
        if (row.match_name_op is None) != (row.match_name_value is None):
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                "Name match operator and value must be set together.",
            )
        if row.match_name_op not in {None, "contains", "equals", "starts_with", "ends_with"}:
            raise RepositoryError(RepositoryErrorCode.VALIDATION, "Name match operator is invalid.")
        if (row.match_amount_op is None) != (row.match_amount_value is None):
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                "Amount match operator and value must be set together.",
            )
        if row.match_amount_op not in {None, "gte", "lte", "eq", "between"}:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION, "Amount match operator is invalid."
            )
        if row.match_amount_op == "between" and row.match_amount_value2 is None:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                "Between amount rules require a second value.",
            )
        if row.match_amount_op != "between" and row.match_amount_value2 is not None:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                "Second amount value is only valid for between rules.",
            )
        if row.match_day_of_month is not None and not 1 <= row.match_day_of_month <= 31:
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                "Day of month must be between 1 and 31.",
            )
        if (
            row.match_name_op is None
            and row.match_amount_op is None
            and row.match_date_from is None
            and row.match_date_to is None
            and row.match_day_of_month is None
        ):
            raise RepositoryError(
                RepositoryErrorCode.VALIDATION,
                "At least one match condition is required.",
            )
