from __future__ import annotations

import json

import pandas as pd
import pytest

from aqos.model_training import (
    DatasetQualityConfig,
    DatasetQualitySeverity,
    build_dataset_quality_report,
    build_target_distribution,
    build_target_ratios,
    write_dataset_quality_report,
)


def build_quality_dataset() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
            "high": [1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5],
            "low": [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5],
            "close": [1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1],
            "volume": [100, 110, 120, 130, 140, 150, 160, 170],
            "return_1": [0.0, 0.1, 0.05, -0.03, 0.02, -0.01, 0.04, -0.02],
            "future_return": [0.1, 0.2, 0.1, -0.1, 0.0, 0.2, -0.2, 0.1],
            "trade_quality_score": [0.1, 0.3, 0.2, -0.1, 0.0, 0.2, -0.2, 0.1],
            "target": ["buy", "sell", "hold", "buy", "sell", "hold", "buy", "sell"],
        }
    )


def test_build_target_distribution_counts_labels() -> None:
    distribution = build_target_distribution(build_quality_dataset(), "target")

    assert distribution == {
        "buy": 3,
        "hold": 2,
        "sell": 3,
    }


def test_build_target_ratios_calculates_percentages() -> None:
    ratios = build_target_ratios({"buy": 2, "sell": 2})

    assert ratios == {
        "buy": 0.5,
        "sell": 0.5,
    }


def test_build_dataset_quality_report_returns_valid_report_for_good_dataset() -> None:
    report = build_dataset_quality_report(build_quality_dataset())

    assert report.valid is True
    assert report.rows == 8
    assert report.target_column == "target"
    assert report.target_distribution == {
        "buy": 3,
        "hold": 2,
        "sell": 3,
    }
    assert "future_return" not in report.feature_columns
    assert "trade_quality_score" not in report.feature_columns
    assert report.leakage_columns == ()
    assert report.errors == ()


def test_build_dataset_quality_report_warns_about_class_imbalance() -> None:
    dataset = build_quality_dataset()
    dataset["target"] = ["buy", "buy", "buy", "buy", "buy", "buy", "buy", "sell"]

    report = build_dataset_quality_report(
        dataset,
        config=DatasetQualityConfig(max_majority_class_ratio=0.8),
    )

    assert report.valid is True
    assert report.majority_class == "buy"
    assert report.majority_class_ratio == 0.875
    assert any(issue.code == "quality_class_imbalance" for issue in report.warnings)


def test_build_dataset_quality_report_warns_about_constant_features() -> None:
    dataset = build_quality_dataset()
    dataset["volume"] = 100

    report = build_dataset_quality_report(dataset)

    assert report.valid is True
    assert "volume" in report.constant_feature_columns
    assert any(issue.code == "quality_constant_feature" for issue in report.warnings)


def test_build_dataset_quality_report_is_invalid_for_missing_target() -> None:
    dataset = build_quality_dataset().drop(columns=["target"])

    report = build_dataset_quality_report(dataset)

    assert report.valid is False
    assert any(issue.severity == DatasetQualitySeverity.ERROR for issue in report.errors)
    assert any(issue.code == "schema_missing_required_column" for issue in report.errors)


def test_dataset_quality_report_raise_if_invalid() -> None:
    report = build_dataset_quality_report(build_quality_dataset().drop(columns=["target"]))

    with pytest.raises(ValueError, match="Dataset quality check failed"):
        report.raise_if_invalid()


def test_write_dataset_quality_report_writes_json(tmp_path) -> None:
    report = build_dataset_quality_report(build_quality_dataset())
    output_path = tmp_path / "reports" / "quality.json"

    written_path = write_dataset_quality_report(output_path, report)
    payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert written_path == output_path
    assert payload["valid"] is True
    assert payload["rows"] == 8
    assert payload["target_distribution"]["buy"] == 3