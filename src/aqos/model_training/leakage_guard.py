from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


DEFAULT_LEAKAGE_COLUMN_NAMES = frozenset(
    {
        "future_close",
        "future_return",
        "future_max_high_return",
        "future_max_low_return",
        "buy_take_profit_hit",
        "buy_stop_loss_hit",
        "sell_take_profit_hit",
        "sell_stop_loss_hit",
        "take_profit_hit",
        "stop_loss_hit",
        "trade_quality_score",
    }
)

DEFAULT_LEAKAGE_PREFIXES = (
    "future_",
)


@dataclass(frozen=True)
class LeakageCheckResult:
    valid: bool
    leaked_columns: tuple[str, ...]

    def raise_if_invalid(self) -> None:
        if self.valid:
            return

        raise ValueError(
            "Model feature columns contain future/outcome leakage columns: "
            f"{list(self.leaked_columns)}"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "leaked_columns": list(self.leaked_columns),
        }


def find_leakage_columns(
    columns: Iterable[str],
    blocked_names: frozenset[str] = DEFAULT_LEAKAGE_COLUMN_NAMES,
    blocked_prefixes: tuple[str, ...] = DEFAULT_LEAKAGE_PREFIXES,
) -> tuple[str, ...]:
    leaked: list[str] = []

    for column in columns:
        normalized = str(column).strip()

        if normalized in blocked_names:
            leaked.append(normalized)
            continue

        if any(normalized.startswith(prefix) for prefix in blocked_prefixes):
            leaked.append(normalized)

    return tuple(dict.fromkeys(leaked))


def check_feature_columns_for_leakage(
    feature_columns: Iterable[str],
) -> LeakageCheckResult:
    leaked_columns = find_leakage_columns(feature_columns)

    return LeakageCheckResult(
        valid=not leaked_columns,
        leaked_columns=leaked_columns,
    )


def raise_if_feature_columns_have_leakage(
    feature_columns: Iterable[str],
) -> None:
    check_feature_columns_for_leakage(feature_columns).raise_if_invalid()


def drop_leakage_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    leaked_columns = find_leakage_columns(dataframe.columns)

    if not leaked_columns:
        return dataframe.copy()

    return dataframe.drop(columns=list(leaked_columns))


__all__ = [
    "DEFAULT_LEAKAGE_COLUMN_NAMES",
    "DEFAULT_LEAKAGE_PREFIXES",
    "LeakageCheckResult",
    "check_feature_columns_for_leakage",
    "drop_leakage_columns",
    "find_leakage_columns",
    "raise_if_feature_columns_have_leakage",
]