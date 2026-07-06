"""
Integration tests for AQOS Data Pipeline.
"""

from pathlib import Path

import pandas as pd

from aqos.data import DataPipeline


def test_pipeline(tmp_path: Path):

    csv_file = tmp_path / "market.csv"

    dataframe = pd.DataFrame(
        {
            "timestamp": [
                "2026-01-01 00:00:00",
                "2026-01-01 01:00:00",
            ],
            "open": [100, 101],
            "high": [102, 103],
            "low": [99, 100],
            "close": [101, 102],
            "volume": [1000, 1200],
        }
    )

    dataframe.to_csv(csv_file, index=False)

    pipeline = DataPipeline()

    result = pipeline.run(csv_file)

    assert len(result) == 2
    assert result["timestamp"].is_monotonic_increasing