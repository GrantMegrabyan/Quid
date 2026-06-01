#!/usr/bin/env python
"""Golden-set evaluation harness for AI transaction categorisation.

Runs the SAME production categorisation pipeline (`categorize_transactions` +
`_snap_to_existing`) against a hand-labelled golden set, once per candidate
model, and reports the metrics that actually matter for this app:

  * new-category-creation rate  -- the headline risk (category proliferation)
  * category match (raw vs after-snap) -- a high snap-rescue rate flags a model
    that won't reuse existing spelling on its own
  * rule / exclude accuracy     -- excluding drops a transaction entirely, the
    costliest mistake; we measure how often the model's exclude matches truth
  * importance agreement
  * schema/parse failures        -- should be ~0; if not, weak structured output
  * cost (from real token usage) and wall-clock per run

Usage:
    # 1. Build a golden set (copy + edit the example):
    cp scripts/golden_set.example.json scripts/golden_set.json
    # 2. Set your key and run (defaults to the configured model):
    QUID_OPENROUTER_API_KEY=sk-... uv run python scripts/eval_categorization.py
    # 3. Compare several candidates:
    uv run python scripts/eval_categorization.py \\
        --model openai/gpt-5.4-mini \\
        --model google/gemini-2.5-flash \\
        --model deepseek/deepseek-v4-pro

Pricing for the cost column is best-effort and lives in PRICES below (USD per
1M tokens). Update it as OpenRouter pricing changes; unknown models report
tokens only. This is a dev tool: it makes real OpenRouter calls and is NOT part
of the shipped `quid-api` CLI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import httpx

# Make `quid_api` importable when run as a plain script from api/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quid_api.ai_categorization import categorize_transactions
from quid_api.repositories.expenses import BulkItem
from quid_api.settings import get_settings

# USD per 1M tokens (input, output). Best-effort; update as pricing changes.
PRICES: dict[str, tuple[float, float]] = {
    "openai/gpt-5.4-mini": (0.75, 4.50),
    "openai/gpt-5.4-nano": (0.20, 1.25),
    "google/gemini-2.5-flash": (0.30, 2.50),
    "google/gemini-2.5-flash-lite": (0.10, 0.40),
    "anthropic/claude-haiku-4.5": (1.00, 5.00),
    "qwen/qwen3.5-27b": (0.195, 1.56),
    "deepseek/deepseek-v4-pro": (0.435, 0.87),
}


@dataclass
class GoldenTransaction:
    name: str
    amount: str
    date: str
    note: str
    expected_category: str
    importance: str | None = None
    exclude: bool = False


@dataclass
class GoldenSet:
    categories: list[tuple[str, str]]
    ai_rules: list[str]
    transactions: list[GoldenTransaction]


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    requests: int = 0
    seconds: float = 0.0


@dataclass
class Metrics:
    model: str
    total: int
    raw_match: int = 0
    snapped_match: int = 0
    new_category: int = 0
    new_category_labels: set[str] = field(default_factory=set)
    importance_correct: int = 0
    importance_scored: int = 0
    exclude_tp: int = 0  # truth=exclude, predicted=exclude
    exclude_fp: int = 0  # truth=keep, predicted=exclude (DANGER: deletes a real tx)
    exclude_fn: int = 0  # truth=exclude, predicted=keep
    exclude_truth: int = 0
    parse_failures: int = 0
    usage: Usage = field(default_factory=Usage)


def load_golden_set(path: Path) -> GoldenSet:
    data = json.loads(path.read_text(encoding="utf-8"))
    categories = [(c["name"], c.get("description", "")) for c in data["categories"]]
    known = {name for name, _ in categories}
    txs: list[GoldenTransaction] = []
    for raw in data["transactions"]:
        expected = raw["expected_category"]
        if expected not in known:
            msg = f"expected_category {expected!r} for {raw['name']!r} is not in 'categories'"
            raise ValueError(msg)
        txs.append(
            GoldenTransaction(
                name=raw["name"],
                amount=str(raw["amount"]),
                date=raw["date"],
                note=raw.get("note", ""),
                expected_category=expected,
                importance=raw.get("importance"),
                exclude=bool(raw.get("exclude", False)),
            )
        )
    return GoldenSet(categories=categories, ai_rules=data.get("ai_rules", []), transactions=txs)


class _MeteringTransport(httpx.AsyncBaseTransport):
    """Wraps the real transport to capture token usage, wall-clock, and the RAW
    (pre-snap) category the model returned per transaction name — none of which
    `categorize_transactions` exposes (its output is already snapped). Capturing
    here lets us measure raw-vs-snapped match without touching production code.

    Keyed by transaction name (unique within a golden set); the request prompt
    carries the names so we can align raw categories to rows across chunks.
    """

    def __init__(self, usage: Usage, raw_by_name: dict[str, str]) -> None:
        self._inner = httpx.AsyncHTTPTransport()
        self._usage = usage
        self._raw_by_name = raw_by_name

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        # Map this chunk's local index -> transaction name from the request.
        names_by_index: dict[int, str] = {}
        try:
            req_body = json.loads(request.content)
            prompt = req_body["messages"][1]["content"]
            txs = json.loads(prompt.split("Transactions JSON: ", 1)[1])
            names_by_index = {int(t["index"]): str(t["name"]) for t in txs}
        except (json.JSONDecodeError, KeyError, IndexError, ValueError, TypeError):
            pass

        start = time.perf_counter()
        response = await self._inner.handle_async_request(request)
        self._usage.seconds += time.perf_counter() - start
        self._usage.requests += 1
        # Read + replace the stream so callers can still consume the body.
        body = await response.aread()
        try:
            payload = json.loads(body)
            usage = payload.get("usage") or {}
            self._usage.prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
            self._usage.completion_tokens += int(usage.get("completion_tokens", 0) or 0)
            content = payload["choices"][0]["message"]["content"]
            for suggestion in json.loads(content)["categories"]:
                name = names_by_index.get(int(suggestion["index"]))
                if name is not None:
                    self._raw_by_name[name] = str(suggestion["category"]).strip()
        except (json.JSONDecodeError, KeyError, IndexError, ValueError, TypeError):
            pass
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=body,
            request=request,
        )


async def evaluate_model(gold: GoldenSet, model: str, api_key: str, chunk_size: int) -> Metrics:
    items = [
        BulkItem(
            name=t.name,
            category="uncategorized",
            amount=Decimal(t.amount),
            date=t.date,
            note=t.note,
        )
        for t in gold.transactions
    ]
    metrics = Metrics(model=model, total=len(items))
    metrics.exclude_truth = sum(1 for t in gold.transactions if t.exclude)
    # Raw (pre-snap) category the model returned, keyed by transaction name,
    # populated by the metering transport as responses arrive.
    raw_by_name: dict[str, str] = {}

    async with httpx.AsyncClient(
        transport=_MeteringTransport(metrics.usage, raw_by_name), timeout=120
    ) as client:
        try:
            result = await categorize_transactions(
                items,
                existing_categories=gold.categories,
                ai_rules=gold.ai_rules,
                api_key=api_key,
                model=model,
                chunk_size=chunk_size,
                client=client,
            )
        except Exception as exc:
            # Surface any failure (bad status, parse error) as a metric and keep
            # going so one broken candidate doesn't abort the whole comparison.
            print(f"  ERROR running {model}: {exc}", file=sys.stderr)
            metrics.parse_failures = len(items)
            return metrics

    known = {name for name, _ in gold.categories}
    for idx, (tx, out) in enumerate(zip(gold.transactions, result.items, strict=True)):
        # raw = what the model said before the production snap; out.category is
        # already snapped. Comparing the two reveals how much the snap is doing.
        raw = raw_by_name.get(tx.name, out.category)
        snapped = out.category
        # raw_match: the model produced the exact expected label on its own.
        if raw == tx.expected_category:
            metrics.raw_match += 1
        # snapped_match: counts as correct after the production snap normalises.
        if snapped == tx.expected_category:
            metrics.snapped_match += 1
        # new_category: model invented a label outside the known set (after snap).
        if snapped not in known:
            metrics.new_category += 1
            metrics.new_category_labels.add(snapped)
        # importance agreement (only where the golden set specifies it).
        if tx.importance is not None:
            metrics.importance_scored += 1
            if out.importance == tx.importance:
                metrics.importance_correct += 1
        # exclude accuracy.
        predicted_exclude = idx in result.excluded_indices
        if tx.exclude and predicted_exclude:
            metrics.exclude_tp += 1
        elif not tx.exclude and predicted_exclude:
            metrics.exclude_fp += 1
        elif tx.exclude and not predicted_exclude:
            metrics.exclude_fn += 1

    return metrics


def _pct(n: int, d: int) -> str:
    return f"{(100.0 * n / d):.0f}%" if d else "n/a"


def _cost(model: str, usage: Usage) -> str:
    price = PRICES.get(model)
    if price is None:
        return "n/a (price unknown)"
    in_price, out_price = price
    total = (usage.prompt_tokens / 1e6) * in_price + (usage.completion_tokens / 1e6) * out_price
    return f"${total:.5f}"


def print_report(results: list[Metrics]) -> None:
    print("\n=== Categorisation model evaluation ===\n")
    for m in results:
        print(f"Model: {m.model}  (n={m.total})")
        if m.parse_failures >= m.total and m.total:
            print("  RUN FAILED — see stderr above.\n")
            continue
        print(
            f"  category match (raw)     : {_pct(m.raw_match, m.total)} ({m.raw_match}/{m.total})"
        )
        print(
            f"  category match (snapped) : {_pct(m.snapped_match, m.total)} "
            f"({m.snapped_match}/{m.total})"
        )
        snap_rescue = m.snapped_match - m.raw_match
        print(f"  snap rescued             : {snap_rescue} (high => model won't reuse spelling)")
        print(
            f"  NEW categories invented  : {m.new_category} "
            f"{sorted(m.new_category_labels) if m.new_category_labels else ''}  <-- headline risk"
        )
        if m.importance_scored:
            print(
                f"  importance agreement     : {_pct(m.importance_correct, m.importance_scored)} "
                f"({m.importance_correct}/{m.importance_scored})"
            )
        print(
            f"  exclude  TP={m.exclude_tp} FN={m.exclude_fn} "
            f"FP={m.exclude_fp} (FP deletes a real tx!) of {m.exclude_truth} true excludes"
        )
        u = m.usage
        print(
            f"  tokens in/out            : {u.prompt_tokens}/{u.completion_tokens} "
            f"over {u.requests} request(s)"
        )
        print(f"  wall-clock               : {u.seconds:.2f}s")
        print(f"  est. cost (this run)     : {_cost(m.model, u)}\n")


async def _main_async(gold: GoldenSet, models: list[str], api_key: str, chunk_size: int) -> int:
    results: list[Metrics] = []
    for model in models:
        print(f"\nRunning {model} ...")
        results.append(await evaluate_model(gold, model, api_key, chunk_size))
    print_report(results)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--golden-set",
        default=str(Path(__file__).resolve().parent / "golden_set.json"),
        help="Path to the golden set JSON (default: scripts/golden_set.json).",
    )
    parser.add_argument(
        "--model",
        action="append",
        help="Model id to evaluate. Repeat to compare several. "
        "Defaults to the configured QUID_OPENROUTER_MODEL.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Override chunk size (default: QUID_OPENROUTER_CHUNK_SIZE).",
    )
    args = parser.parse_args()

    settings = get_settings()
    api_key = settings.openrouter_api_key
    if not api_key:
        print("QUID_OPENROUTER_API_KEY is not set.", file=sys.stderr)
        raise SystemExit(1)

    gold_path = Path(args.golden_set)
    if not gold_path.exists():
        print(
            f"Golden set not found at {gold_path}. "
            f"Copy scripts/golden_set.example.json to scripts/golden_set.json and edit it.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    gold = load_golden_set(gold_path)

    models = args.model or [settings.openrouter_model]
    print(
        f"Golden set: {gold_path} ({len(gold.transactions)} transactions, "
        f"{len(gold.categories)} categories, {len(gold.ai_rules)} rules)"
    )
    print(f"Models: {', '.join(models)}")

    chunk_size = args.chunk_size or settings.openrouter_chunk_size
    raise SystemExit(asyncio.run(_main_async(gold, models, api_key, chunk_size)))


if __name__ == "__main__":
    main()
