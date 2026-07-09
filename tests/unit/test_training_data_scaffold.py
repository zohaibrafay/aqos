"""
Unit tests for AQOS training data package scaffold.
"""

import pytest

from aqos.training_data import (
    TrainingDataAssetType,
    TrainingDataConfig,
    TrainingDataHealth,
    TrainingDataIssue,
    TrainingDataResult,
    TrainingDatasetSplit,
    TrainingDataStatus,
    TrainingDataTimeframe,
    TrainingLabelTarget,
    build_training_data_config,
    build_training_data_health,
    build_training_data_issue,
    build_training_data_result,
    normalize_training_data_asset_type,
    normalize_training_data_status,
    normalize_training_data_timeframe,
    normalize_training_dataset_split,
    normalize_training_label_target,
    normalize_training_symbol,
    training_data_failure,
    training_data_success,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_non_negative_integer,
    validate_number,
    validate_positive_integer,
    validate_string,
    validate_training_data_issues,
    validate_training_label_targets,
)


def test_training_data_enum_values():
    assert TrainingDataStatus.READY.value == "ready"
    assert TrainingDataStatus.EMPTY.value == "empty"
    assert TrainingDataStatus.WARNING.value == "warning"
    assert TrainingDataStatus.ERROR.value == "error"

    assert TrainingDataAssetType.FOREX.value == "forex"
    assert TrainingDataAssetType.CRYPTO.value == "crypto"
    assert TrainingDataAssetType.COMMODITY.value == "commodity"
    assert TrainingDataAssetType.INDEX.value == "index"
    assert TrainingDataAssetType.STOCK.value == "stock"
    assert TrainingDataAssetType.UNKNOWN.value == "unknown"

    assert TrainingDataTimeframe.M1.value == "1m"
    assert TrainingDataTimeframe.M5.value == "5m"
    assert TrainingDataTimeframe.M15.value == "15m"
    assert TrainingDataTimeframe.M30.value == "30m"
    assert TrainingDataTimeframe.H1.value == "1h"
    assert TrainingDataTimeframe.H4.value == "4h"
    assert TrainingDataTimeframe.D1.value == "1d"
    assert TrainingDataTimeframe.W1.value == "1w"

    assert TrainingDatasetSplit.TRAIN.value == "train"
    assert TrainingDatasetSplit.VALIDATION.value == "validation"
    assert TrainingDatasetSplit.TEST.value == "test"
    assert TrainingDatasetSplit.WALK_FORWARD.value == "walk_forward"

    assert TrainingLabelTarget.FUTURE_RETURN.value == "future_return"
    assert TrainingLabelTarget.DIRECTION.value == "direction"
    assert TrainingLabelTarget.HIT_TP_BEFORE_SL.value == "hit_tp_before_sl"
    assert TrainingLabelTarget.VOLATILITY.value == "volatility"
    assert TrainingLabelTarget.EVENT_IMPACT.value == "event_impact"
    assert TrainingLabelTarget.RISK_LEVEL.value == "risk_level"


def test_training_data_normalizers():
    assert normalize_training_data_status(TrainingDataStatus.READY) == TrainingDataStatus.READY
    assert normalize_training_data_status(" WARNING ") == TrainingDataStatus.WARNING
    assert normalize_training_data_asset_type(TrainingDataAssetType.FOREX) == TrainingDataAssetType.FOREX
    assert normalize_training_data_asset_type(" CRYPTO ") == TrainingDataAssetType.CRYPTO
    assert normalize_training_data_timeframe(TrainingDataTimeframe.H1) == TrainingDataTimeframe.H1
    assert normalize_training_data_timeframe(" 1d ") == TrainingDataTimeframe.D1
    assert normalize_training_dataset_split(TrainingDatasetSplit.TRAIN) == TrainingDatasetSplit.TRAIN
    assert normalize_training_dataset_split(" TEST ") == TrainingDatasetSplit.TEST
    assert normalize_training_label_target(TrainingLabelTarget.DIRECTION) == TrainingLabelTarget.DIRECTION
    assert normalize_training_label_target(" VOLATILITY ") == TrainingLabelTarget.VOLATILITY

    with pytest.raises(ValueError):
        normalize_training_data_status("bad")

    with pytest.raises(ValueError):
        normalize_training_data_asset_type("bad")

    with pytest.raises(ValueError):
        normalize_training_data_timeframe("bad")

    with pytest.raises(ValueError):
        normalize_training_dataset_split("bad")

    with pytest.raises(ValueError):
        normalize_training_label_target("bad")


def test_training_symbol_normalizer():
    assert normalize_training_symbol(" xauusd ") == "XAUUSD"
    assert normalize_training_symbol("btc/usdt") == "BTC/USDT"
    assert normalize_training_symbol("eth-usdt") == "ETH-USDT"

    with pytest.raises(ValueError):
        normalize_training_symbol("")

    with pytest.raises(ValueError):
        normalize_training_symbol("bad symbol")

    with pytest.raises(ValueError):
        normalize_training_symbol("bad_symbol")


def test_training_data_validators():
    assert validate_string("", "Field") == ""
    assert validate_string("value", "Field") == "value"
    assert validate_non_empty_string(" value ", "Field") == "value"
    assert validate_metadata({"a": 1}) == {"a": 1}
    assert validate_number(1, "Value") == 1.0
    assert validate_number(-1.5, "Value") == -1.5
    assert validate_non_negative_integer(0, "Count") == 0
    assert validate_positive_integer(1, "Count") == 1
    assert validate_non_negative_float(0, "Value") == 0.0
    assert validate_training_label_targets(["direction", TrainingLabelTarget.VOLATILITY]) == [
        "direction",
        TrainingLabelTarget.VOLATILITY,
    ]

    with pytest.raises(ValueError):
        validate_string(123, "Field")

    with pytest.raises(ValueError):
        validate_non_empty_string("", "Field")

    with pytest.raises(ValueError):
        validate_metadata([])

    with pytest.raises(ValueError):
        validate_number(True, "Value")

    with pytest.raises(ValueError):
        validate_number("1", "Value")

    with pytest.raises(ValueError):
        validate_non_negative_integer(-1, "Count")

    with pytest.raises(ValueError):
        validate_non_negative_integer(True, "Count")

    with pytest.raises(ValueError):
        validate_positive_integer(0, "Count")

    with pytest.raises(ValueError):
        validate_non_negative_float(-1, "Value")

    with pytest.raises(ValueError):
        validate_training_label_targets("bad")

    with pytest.raises(ValueError):
        validate_training_label_targets(["bad"])


def test_training_data_issue_to_dict():
    issue = TrainingDataIssue(
        code=" missing_rows ",
        message=" Missing historical rows ",
        status=" WARNING ",
        source=" importer ",
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert issue.to_dict() == {
        "code": "missing_rows",
        "message": "Missing historical rows",
        "status": "warning",
        "source": "importer",
        "metadata": {
            "symbol": "XAUUSD",
        },
    }


def test_training_data_issue_rejects_invalid_values():
    with pytest.raises(ValueError):
        TrainingDataIssue(code="", message="Message")

    with pytest.raises(ValueError):
        TrainingDataIssue(code="code", message="")

    with pytest.raises(ValueError):
        TrainingDataIssue(code="code", message="Message", status="bad")

    with pytest.raises(ValueError):
        TrainingDataIssue(code="code", message="Message", source=123)

    with pytest.raises(ValueError):
        TrainingDataIssue(code="code", message="Message", metadata=[])


def test_build_training_data_issue():
    issue = build_training_data_issue(
        code="ok",
        message="Dataset ready.",
        status="ready",
    )

    assert isinstance(issue, TrainingDataIssue)
    assert issue.code == "ok"


def test_training_data_config_to_dict():
    config = TrainingDataConfig(
        dataset_id=" xauusd-h1-10y ",
        symbol=" xauusd ",
        asset_type=" forex ",
        timeframe=" 1h ",
        start_date="2016-01-01",
        end_date="2026-01-01",
        timezone=" UTC ",
        label_targets=["direction", TrainingLabelTarget.FUTURE_RETURN],
        metadata={
            "source": "test",
        },
    )

    payload = config.to_dict()

    assert config.bounded is True
    assert payload == {
        "dataset_id": "xauusd-h1-10y",
        "symbol": "XAUUSD",
        "asset_type": "forex",
        "timeframe": "1h",
        "start_date": "2016-01-01",
        "end_date": "2026-01-01",
        "timezone": "UTC",
        "bounded": True,
        "label_targets": ["direction", "future_return"],
        "metadata": {
            "source": "test",
        },
    }


def test_training_data_config_builder_and_unbounded():
    config = build_training_data_config(
        dataset_id="btc-1h",
        symbol="BTCUSDT",
        asset_type="crypto",
        timeframe="1h",
    )

    assert isinstance(config, TrainingDataConfig)
    assert config.bounded is False
    assert config.symbol == "BTCUSDT"


def test_training_data_config_rejects_invalid_values():
    with pytest.raises(ValueError):
        TrainingDataConfig(dataset_id="", symbol="XAUUSD")

    with pytest.raises(ValueError):
        TrainingDataConfig(dataset_id="dataset", symbol="bad symbol")

    with pytest.raises(ValueError):
        TrainingDataConfig(dataset_id="dataset", symbol="XAUUSD", asset_type="bad")

    with pytest.raises(ValueError):
        TrainingDataConfig(dataset_id="dataset", symbol="XAUUSD", timeframe="bad")

    with pytest.raises(ValueError):
        TrainingDataConfig(dataset_id="dataset", symbol="XAUUSD", start_date=123)

    with pytest.raises(ValueError):
        TrainingDataConfig(dataset_id="dataset", symbol="XAUUSD", end_date=123)

    with pytest.raises(ValueError):
        TrainingDataConfig(dataset_id="dataset", symbol="XAUUSD", timezone="")

    with pytest.raises(ValueError):
        TrainingDataConfig(dataset_id="dataset", symbol="XAUUSD", label_targets="bad")

    with pytest.raises(ValueError):
        TrainingDataConfig(dataset_id="dataset", symbol="XAUUSD", metadata=[])


def test_training_data_health_to_dict():
    health = TrainingDataHealth(
        dataset_id=" dataset ",
        status=" READY ",
        row_count=100,
        feature_count=20,
        label_count=3,
        event_count=5,
        issue_count=0,
        generated_at="2026-01-01T00:00:00+00:00",
        metadata={
            "source": "test",
        },
    )

    payload = health.to_dict()

    assert health.healthy is True
    assert health.has_rows is True
    assert payload["dataset_id"] == "dataset"
    assert payload["status"] == "ready"
    assert payload["row_count"] == 100
    assert payload["feature_count"] == 20
    assert payload["label_count"] == 3
    assert payload["event_count"] == 5
    assert payload["generated_at"] == "2026-01-01T00:00:00+00:00"


def test_training_data_health_builder_and_rejections():
    health = build_training_data_health(
        dataset_id="dataset",
        status="empty",
        generated_at="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(health, TrainingDataHealth)
    assert health.healthy is False
    assert health.has_rows is False

    with pytest.raises(ValueError):
        TrainingDataHealth(dataset_id="")

    with pytest.raises(ValueError):
        TrainingDataHealth(dataset_id="dataset", status="bad")

    with pytest.raises(ValueError):
        TrainingDataHealth(dataset_id="dataset", row_count=-1)

    with pytest.raises(ValueError):
        TrainingDataHealth(dataset_id="dataset", feature_count=-1)

    with pytest.raises(ValueError):
        TrainingDataHealth(dataset_id="dataset", label_count=-1)

    with pytest.raises(ValueError):
        TrainingDataHealth(dataset_id="dataset", event_count=-1)

    with pytest.raises(ValueError):
        TrainingDataHealth(dataset_id="dataset", issue_count=-1)

    with pytest.raises(ValueError):
        TrainingDataHealth(dataset_id="dataset", generated_at="")

    with pytest.raises(ValueError):
        TrainingDataHealth(dataset_id="dataset", metadata=[])


def test_training_data_result_to_dict():
    issue = build_training_data_issue(
        code="warning",
        message="Small dataset.",
    )
    result = TrainingDataResult(
        success=True,
        message=" Done ",
        data={
            "rows": 100,
        },
        issues=[issue],
        metadata={
            "source": "test",
        },
    )

    payload = result.to_dict()

    assert result.failed is False
    assert result.issue_count == 1
    assert payload["success"] is True
    assert payload["failed"] is False
    assert payload["message"] == "Done"
    assert payload["data"] == {"rows": 100}
    assert payload["issue_count"] == 1


def test_training_data_result_builders():
    success = training_data_success(
        message="Dataset ready.",
        data={
            "rows": 100,
        },
    )
    failure = training_data_failure(
        message="Dataset failed.",
        code="dataset_failed",
        source="test",
    )
    custom = build_training_data_result(
        success=True,
        message="Custom result.",
    )

    assert isinstance(success, TrainingDataResult)
    assert success.success is True
    assert success.data == {"rows": 100}

    assert failure.failed is True
    assert failure.issues[0].code == "dataset_failed"
    assert failure.issues[0].status == TrainingDataStatus.ERROR

    assert custom.success is True


def test_training_data_result_rejects_invalid_values():
    issue = build_training_data_issue(
        code="issue",
        message="Issue",
    )

    with pytest.raises(ValueError):
        TrainingDataResult(success="yes")

    with pytest.raises(ValueError):
        TrainingDataResult(success=True, message=123)

    with pytest.raises(ValueError):
        TrainingDataResult(success=True, data=[])

    with pytest.raises(ValueError):
        TrainingDataResult(success=True, issues="bad")

    with pytest.raises(ValueError):
        TrainingDataResult(success=True, issues=["bad"])

    with pytest.raises(ValueError):
        TrainingDataResult(success=True, metadata=[])

    assert validate_training_data_issues([issue]) == [issue]


def test_training_data_exports_are_sorted_and_exist():
    import aqos.training_data as training_data

    assert training_data.__all__ == sorted(training_data.__all__)

    for export_name in training_data.__all__:
        assert hasattr(training_data, export_name), export_name