"""
AQOS training data base primitives.

This package prepares historical market data, news/macro events, labels,
pattern windows, and walk-forward datasets for AQOS ML model training.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class TrainingDataStatus(str, Enum):
    """Supported training data statuses."""

    READY = "ready"
    EMPTY = "empty"
    WARNING = "warning"
    ERROR = "error"


class TrainingDataAssetType(str, Enum):
    """Supported training data asset types."""

    FOREX = "forex"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    INDEX = "index"
    STOCK = "stock"
    UNKNOWN = "unknown"


class TrainingDataTimeframe(str, Enum):
    """Supported training data timeframes."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class TrainingDatasetSplit(str, Enum):
    """Supported dataset split names."""

    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
    WALK_FORWARD = "walk_forward"


class TrainingLabelTarget(str, Enum):
    """Supported label targets."""

    FUTURE_RETURN = "future_return"
    DIRECTION = "direction"
    HIT_TP_BEFORE_SL = "hit_tp_before_sl"
    VOLATILITY = "volatility"
    EVENT_IMPACT = "event_impact"
    RISK_LEVEL = "risk_level"


@dataclass(frozen=True)
class TrainingDataIssue:
    """Training data issue."""

    code: str
    message: str
    status: TrainingDataStatus | str = TrainingDataStatus.WARNING
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.code, "Issue code")
        validate_non_empty_string(self.message, "Issue message")
        normalize_training_data_status(self.status)
        validate_string(self.source, "Source")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert issue to dictionary."""
        return {
            "code": self.code.strip(),
            "message": self.message.strip(),
            "status": normalize_training_data_status(self.status).value,
            "source": self.source.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TrainingDataConfig:
    """Training data configuration."""

    dataset_id: str
    symbol: str
    asset_type: TrainingDataAssetType | str = TrainingDataAssetType.UNKNOWN
    timeframe: TrainingDataTimeframe | str = TrainingDataTimeframe.H1
    start_date: str = ""
    end_date: str = ""
    timezone: str = "UTC"
    label_targets: list[TrainingLabelTarget | str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.dataset_id, "Dataset ID")
        normalize_training_symbol(self.symbol)
        normalize_training_data_asset_type(self.asset_type)
        normalize_training_data_timeframe(self.timeframe)
        validate_string(self.start_date, "Start date")
        validate_string(self.end_date, "End date")
        validate_non_empty_string(self.timezone, "Timezone")
        validate_training_label_targets(self.label_targets)
        validate_metadata(self.metadata, "Metadata")

    @property
    def bounded(self) -> bool:
        """Return whether config has start and end date."""
        return bool(self.start_date.strip()) and bool(self.end_date.strip())

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "dataset_id": self.dataset_id.strip(),
            "symbol": normalize_training_symbol(self.symbol),
            "asset_type": normalize_training_data_asset_type(self.asset_type).value,
            "timeframe": normalize_training_data_timeframe(self.timeframe).value,
            "start_date": self.start_date.strip(),
            "end_date": self.end_date.strip(),
            "timezone": self.timezone.strip(),
            "bounded": self.bounded,
            "label_targets": [
                normalize_training_label_target(target).value
                for target in self.label_targets
            ],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TrainingDataHealth:
    """Training data health summary."""

    dataset_id: str
    status: TrainingDataStatus | str = TrainingDataStatus.READY
    row_count: int = 0
    feature_count: int = 0
    label_count: int = 0
    event_count: int = 0
    issue_count: int = 0
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.dataset_id, "Dataset ID")
        normalize_training_data_status(self.status)
        validate_non_negative_integer(self.row_count, "Row count")
        validate_non_negative_integer(self.feature_count, "Feature count")
        validate_non_negative_integer(self.label_count, "Label count")
        validate_non_negative_integer(self.event_count, "Event count")
        validate_non_negative_integer(self.issue_count, "Issue count")
        validate_non_empty_string(self.generated_at, "Generated at")
        validate_metadata(self.metadata, "Metadata")

    @property
    def healthy(self) -> bool:
        """Return whether dataset is healthy."""
        return normalize_training_data_status(self.status) == TrainingDataStatus.READY

    @property
    def has_rows(self) -> bool:
        """Return whether dataset has rows."""
        return self.row_count > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert health summary to dictionary."""
        return {
            "dataset_id": self.dataset_id.strip(),
            "status": normalize_training_data_status(self.status).value,
            "healthy": self.healthy,
            "row_count": self.row_count,
            "feature_count": self.feature_count,
            "label_count": self.label_count,
            "event_count": self.event_count,
            "issue_count": self.issue_count,
            "has_rows": self.has_rows,
            "generated_at": self.generated_at.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TrainingDataResult:
    """Training data operation result."""

    success: bool
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    issues: list[TrainingDataIssue] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_string(self.message, "Message")
        validate_metadata(self.data, "Data")
        validate_training_data_issues(self.issues)
        validate_metadata(self.metadata, "Metadata")

    @property
    def failed(self) -> bool:
        """Return whether result failed."""
        return not self.success

    @property
    def issue_count(self) -> int:
        """Return issue count."""
        return len(self.issues)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "failed": self.failed,
            "message": self.message.strip(),
            "data": dict(self.data),
            "issues": [issue.to_dict() for issue in self.issues],
            "issue_count": self.issue_count,
            "metadata": dict(self.metadata),
        }


def validate_string(value: str, field_name: str) -> str:
    """Validate string."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    return value


def validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate non-empty string."""
    validate_string(value, field_name)

    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_metadata(value: dict[str, Any], field_name: str = "Metadata") -> dict[str, Any]:
    """Validate metadata dictionary."""
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dictionary.")

    return value


def validate_number(value: int | float, field_name: str) -> float:
    """Validate number."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field_name} must be a number.")

    return float(value)


def validate_non_negative_integer(value: int, field_name: str) -> int:
    """Validate non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value


def validate_positive_integer(value: int, field_name: str) -> int:
    """Validate positive integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")

    return value


def validate_non_negative_float(value: int | float, field_name: str) -> float:
    """Validate non-negative float."""
    validate_number(value, field_name)

    if value < 0:
        raise ValueError(f"{field_name} must be a non-negative number.")

    return float(value)


def normalize_training_symbol(symbol: str) -> str:
    """Normalize training symbol."""
    normalized = validate_non_empty_string(symbol, "Symbol").upper()

    if not normalized.replace("/", "").replace("-", "").isalnum():
        raise ValueError("Symbol must be alphanumeric and may include '/' or '-'.")

    return normalized


def normalize_training_data_status(
    status: TrainingDataStatus | str,
) -> TrainingDataStatus:
    """Normalize training data status."""
    if isinstance(status, TrainingDataStatus):
        return status

    normalized = validate_non_empty_string(status, "Training data status").lower()

    try:
        return TrainingDataStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TrainingDataStatus)
        raise ValueError(
            f"Invalid training data status '{status}'. Valid statuses: {valid}.",
        ) from exc


def normalize_training_data_asset_type(
    asset_type: TrainingDataAssetType | str,
) -> TrainingDataAssetType:
    """Normalize training data asset type."""
    if isinstance(asset_type, TrainingDataAssetType):
        return asset_type

    normalized = validate_non_empty_string(asset_type, "Asset type").lower()

    try:
        return TrainingDataAssetType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TrainingDataAssetType)
        raise ValueError(
            f"Invalid asset type '{asset_type}'. Valid asset types: {valid}.",
        ) from exc


def normalize_training_data_timeframe(
    timeframe: TrainingDataTimeframe | str,
) -> TrainingDataTimeframe:
    """Normalize training data timeframe."""
    if isinstance(timeframe, TrainingDataTimeframe):
        return timeframe

    normalized = validate_non_empty_string(timeframe, "Timeframe").lower()

    try:
        return TrainingDataTimeframe(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TrainingDataTimeframe)
        raise ValueError(
            f"Invalid timeframe '{timeframe}'. Valid timeframes: {valid}.",
        ) from exc


def normalize_training_dataset_split(
    split: TrainingDatasetSplit | str,
) -> TrainingDatasetSplit:
    """Normalize training dataset split."""
    if isinstance(split, TrainingDatasetSplit):
        return split

    normalized = validate_non_empty_string(split, "Dataset split").lower()

    try:
        return TrainingDatasetSplit(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TrainingDatasetSplit)
        raise ValueError(
            f"Invalid dataset split '{split}'. Valid splits: {valid}.",
        ) from exc


def normalize_training_label_target(
    target: TrainingLabelTarget | str,
) -> TrainingLabelTarget:
    """Normalize training label target."""
    if isinstance(target, TrainingLabelTarget):
        return target

    normalized = validate_non_empty_string(target, "Label target").lower()

    try:
        return TrainingLabelTarget(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TrainingLabelTarget)
        raise ValueError(
            f"Invalid label target '{target}'. Valid targets: {valid}.",
        ) from exc


def validate_training_label_targets(
    targets: list[TrainingLabelTarget | str],
) -> list[TrainingLabelTarget | str]:
    """Validate label targets."""
    if not isinstance(targets, list):
        raise ValueError("Label targets must be a list.")

    for target in targets:
        normalize_training_label_target(target)

    return targets


def validate_training_data_issues(
    issues: list[TrainingDataIssue],
) -> list[TrainingDataIssue]:
    """Validate training data issues."""
    if not isinstance(issues, list):
        raise ValueError("Issues must be a list.")

    for issue in issues:
        if not isinstance(issue, TrainingDataIssue):
            raise ValueError("Issues must contain TrainingDataIssue objects.")

    return issues


def build_training_data_issue(
    *,
    code: str,
    message: str,
    status: TrainingDataStatus | str = TrainingDataStatus.WARNING,
    source: str = "",
    metadata: dict[str, Any] | None = None,
) -> TrainingDataIssue:
    """Build training data issue."""
    return TrainingDataIssue(
        code=code,
        message=message,
        status=status,
        source=source,
        metadata=metadata or {},
    )


def build_training_data_config(
    *,
    dataset_id: str,
    symbol: str,
    asset_type: TrainingDataAssetType | str = TrainingDataAssetType.UNKNOWN,
    timeframe: TrainingDataTimeframe | str = TrainingDataTimeframe.H1,
    start_date: str = "",
    end_date: str = "",
    timezone: str = "UTC",
    label_targets: list[TrainingLabelTarget | str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> TrainingDataConfig:
    """Build training data config."""
    return TrainingDataConfig(
        dataset_id=dataset_id,
        symbol=symbol,
        asset_type=asset_type,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        timezone=timezone,
        label_targets=label_targets or [],
        metadata=metadata or {},
    )


def build_training_data_health(
    *,
    dataset_id: str,
    status: TrainingDataStatus | str = TrainingDataStatus.READY,
    row_count: int = 0,
    feature_count: int = 0,
    label_count: int = 0,
    event_count: int = 0,
    issue_count: int = 0,
    generated_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TrainingDataHealth:
    """Build training data health."""
    health_kwargs: dict[str, Any] = {
        "dataset_id": dataset_id,
        "status": status,
        "row_count": row_count,
        "feature_count": feature_count,
        "label_count": label_count,
        "event_count": event_count,
        "issue_count": issue_count,
        "metadata": metadata or {},
    }

    if generated_at is not None:
        health_kwargs["generated_at"] = generated_at

    return TrainingDataHealth(**health_kwargs)


def build_training_data_result(
    *,
    success: bool,
    message: str = "",
    data: dict[str, Any] | None = None,
    issues: list[TrainingDataIssue] | None = None,
    metadata: dict[str, Any] | None = None,
) -> TrainingDataResult:
    """Build training data result."""
    return TrainingDataResult(
        success=success,
        message=message,
        data=data or {},
        issues=issues or [],
        metadata=metadata or {},
    )


def training_data_success(
    *,
    message: str = "",
    data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> TrainingDataResult:
    """Build successful training data result."""
    return build_training_data_result(
        success=True,
        message=message,
        data=data or {},
        metadata=metadata or {},
    )


def training_data_failure(
    *,
    message: str,
    code: str = "training_data_error",
    source: str = "",
    metadata: dict[str, Any] | None = None,
) -> TrainingDataResult:
    """Build failed training data result."""
    return build_training_data_result(
        success=False,
        message=message,
        issues=[
            build_training_data_issue(
                code=code,
                message=message,
                status=TrainingDataStatus.ERROR,
                source=source,
            ),
        ],
        metadata=metadata or {},
    )