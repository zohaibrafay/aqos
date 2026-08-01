from __future__ import annotations

import json

import pandas as pd
import pytest

from aqos.backtesting.cli import run_backtesting_cli


def build_model_backtest_cli_args(
    data_path,
    output_dir,
    model_path,
    extra: list[str] | None = None,
) -> list[str]:
    return [
        "model-backtest",
        "--data-path",
        str(data_path),
        "--output-dir",
        str(output_dir),
        "--model-path",
        str(model_path),
        "--symbol",
        "XAUUSD",
        "--timeframe",
        "H1",
        "--strategy-name",
        "sprint_037_model_backtest_smoke",
        "--warmup-bars",
        "5",
        "--model-stop-loss-points",
        "4",
        "--model-take-profit-points",
        "6",
        "--fixed-quantity",
        "1",
        "--point-value",
        "1",
        "--max-open-positions",
        "1",
        *(extra or []),
    ]


def test_model_backtesting_cli_end_to_end_smoke(
    promoted_backtest_model_files,
    backtest_model_data_path,
    tmp_path,
    capsys,
) -> None:
    output_dir = tmp_path / "model_backtest_cli_output"

    exit_code = run_backtesting_cli(
        build_model_backtest_cli_args(
            data_path=backtest_model_data_path,
            output_dir=output_dir,
            model_path=promoted_backtest_model_files["model_path"],
            extra=[
                "--model-metadata-path",
                str(promoted_backtest_model_files["metadata_path"]),
                "--promotion-registry-path",
                str(promoted_backtest_model_files["registry_path"]),
                "--required-stage",
                "paper_trading",
            ],
        )
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    model_report_path = output_dir / "model_backtest_report.json"
    predictions_path = output_dir / "model_backtest_predictions.csv"
    trades_path = output_dir / "model_backtest_trades.csv"
    equity_path = output_dir / "model_backtest_equity_curve.csv"
    orders_path = output_dir / "model_backtest_orders.csv"
    signals_path = output_dir / "model_backtest_signals.csv"

    assert exit_code == 0

    assert model_report_path.exists()
    assert predictions_path.exists()
    assert trades_path.exists()
    assert equity_path.exists()
    assert orders_path.exists()
    assert signals_path.exists()

    assert payload["gate_decision"]["status"] == "approved"
    assert payload["gate_decision"]["allowed"] is True
    assert payload["model_identity"]["model_id"] == (
        promoted_backtest_model_files["model_id"]
    )
    assert payload["model_identity"]["promotion_stage"] == "paper_trading"
    assert payload["prediction_rows"] == 80

    strategy_backtest = payload["strategy_backtest"]

    assert strategy_backtest["data_load"]["loaded_rows"] == 80
    assert strategy_backtest["run_config"]["strategy_name"] == (
        "sprint_037_model_backtest_smoke"
    )
    assert strategy_backtest["metrics"]["metadata"]["adapter_type"] == "ml_model"
    assert strategy_backtest["metrics"]["total_trades"] > 0
    assert strategy_backtest["final_state"]["open_position_count"] == 0

    predictions = pd.read_csv(predictions_path)
    trades = pd.read_csv(trades_path)

    assert len(predictions) == 80
    assert predictions.iloc[0]["adapter_status"] == "skipped"
    assert predictions.iloc[10]["predicted_label"] in {"buy", "sell"}
    assert predictions.iloc[10]["model_version"] == (
        promoted_backtest_model_files["model_version"]
    )
    assert len(trades) == strategy_backtest["metrics"]["total_trades"]

    report = json.loads(model_report_path.read_text(encoding="utf-8"))

    assert report["config"]["gate_config"]["required_stage"] == "paper_trading"
    assert report["config"]["adapter_config"]["warmup_bars"] == 5


def test_model_backtesting_cli_rejects_unpromoted_model(
    unpromoted_backtest_model_files,
    backtest_model_data_path,
    tmp_path,
) -> None:
    output_dir = tmp_path / "rejected_model_backtest_output"

    with pytest.raises(ValueError, match="Backtest model promotion gate rejected"):
        run_backtesting_cli(
            build_model_backtest_cli_args(
                data_path=backtest_model_data_path,
                output_dir=output_dir,
                model_path=unpromoted_backtest_model_files["model_path"],
                extra=[
                    "--model-metadata-path",
                    str(unpromoted_backtest_model_files["metadata_path"]),
                    "--promotion-registry-path",
                    str(unpromoted_backtest_model_files["registry_path"]),
                    "--required-stage",
                    "paper_trading",
                ],
            )
        )

    assert not (output_dir / "model_backtest_report.json").exists()


def test_model_backtesting_cli_requires_override_to_disable_gate(
    promoted_backtest_model_files,
    backtest_model_data_path,
    tmp_path,
) -> None:
    with pytest.raises(ValueError, match="allow_unpromoted_model must be enabled"):
        run_backtesting_cli(
            build_model_backtest_cli_args(
                data_path=backtest_model_data_path,
                output_dir=tmp_path / "disabled_gate_output",
                model_path=promoted_backtest_model_files["model_path"],
                extra=["--disable-promotion-gate"],
            )
        )


def test_model_backtesting_cli_runs_with_explicit_override(
    unpromoted_backtest_model_files,
    backtest_model_data_path,
    tmp_path,
    capsys,
) -> None:
    output_dir = tmp_path / "override_model_backtest_output"

    exit_code = run_backtesting_cli(
        build_model_backtest_cli_args(
            data_path=backtest_model_data_path,
            output_dir=output_dir,
            model_path=unpromoted_backtest_model_files["model_path"],
            extra=[
                "--model-metadata-path",
                str(unpromoted_backtest_model_files["metadata_path"]),
                "--promotion-registry-path",
                str(unpromoted_backtest_model_files["registry_path"]),
                "--allow-unpromoted-model",
            ],
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["gate_decision"]["status"] == "overridden"
    assert payload["gate_decision"]["override_applied"] is True
    assert payload["gate_decision"]["reasons"]


def test_model_backtesting_cli_blocks_shorts_when_requested(
    promoted_backtest_model_files,
    backtest_model_data_path,
    tmp_path,
    capsys,
) -> None:
    output_dir = tmp_path / "long_only_model_backtest_output"

    exit_code = run_backtesting_cli(
        build_model_backtest_cli_args(
            data_path=backtest_model_data_path,
            output_dir=output_dir,
            model_path=promoted_backtest_model_files["model_path"],
            extra=[
                "--model-metadata-path",
                str(promoted_backtest_model_files["metadata_path"]),
                "--promotion-registry-path",
                str(promoted_backtest_model_files["registry_path"]),
                "--no-short",
            ],
        )
    )

    payload = json.loads(capsys.readouterr().out)
    predictions = pd.read_csv(output_dir / "model_backtest_predictions.csv")

    assert exit_code == 0
    assert payload["config"]["adapter_config"]["allow_short"] is False
    assert set(predictions["action"].unique()) <= {"buy", "hold"}
    assert "sell" in set(predictions["predicted_label"].dropna().unique())
