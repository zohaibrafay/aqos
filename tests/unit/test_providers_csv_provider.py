"""
Unit tests for AQOS local CSV OHLCV provider.
"""

from pathlib import Path

import pytest

from aqos.providers import (
    CsvOhlcvColumnMap,
    CsvOhlcvLoadRequest,
    HistoricalOhlcvAdapter,
    LocalCsvOhlcvProvider,
    build_csv_ohlcv_column_map,
    build_csv_ohlcv_load_request,
    build_historical_ohlcv_adapter,
    build_local_csv_ohlcv_provider,
    load_csv_ohlcv_into_adapter,
    normalize_csv_ohlcv_row,
    read_ohlcv_csv_rows,
    validate_csv_columns,
    validate_csv_file_path,
    write_ohlcv_csv_rows,
)


def write_sample_csv(path: Path) -> Path:
    path.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2026-01-01T00:00:00+00:00,2000,2020,1990,2010,100\n"
        "2026-01-01T01:00:00+00:00,2010,2030,2000,2025,120\n",
        encoding="utf-8",
    )
    return path


def test_csv_column_map_to_dict():
    column_map = CsvOhlcvColumnMap(
        timestamp=" time ",
        open=" o ",
        high=" h ",
        low=" l ",
        close=" c ",
        volume=" v ",
    )

    assert column_map.required_columns == ["time", "o", "h", "l", "c"]
    assert column_map.all_columns == ["time", "o", "h", "l", "c", "v"]
    assert column_map.to_dict() == {
        "timestamp": "time",
        "open": "o",
        "high": "h",
        "low": "l",
        "close": "c",
        "volume": "v",
    }


def test_csv_column_map_rejects_invalid_values():
    with pytest.raises(ValueError):
        CsvOhlcvColumnMap(timestamp="")

    with pytest.raises(ValueError):
        CsvOhlcvColumnMap(open="")

    with pytest.raises(ValueError):
        CsvOhlcvColumnMap(high="")

    with pytest.raises(ValueError):
        CsvOhlcvColumnMap(low="")

    with pytest.raises(ValueError):
        CsvOhlcvColumnMap(close="")

    with pytest.raises(ValueError):
        CsvOhlcvColumnMap(volume="")


def test_build_csv_ohlcv_column_map():
    column_map = build_csv_ohlcv_column_map(
        timestamp="date",
        open="o",
        high="h",
        low="l",
        close="c",
        volume="v",
    )

    assert isinstance(column_map, CsvOhlcvColumnMap)
    assert column_map.to_dict()["timestamp"] == "date"


def test_csv_ohlcv_load_request_to_dict(tmp_path):
    csv_path = write_sample_csv(tmp_path / "sample.csv")

    request = CsvOhlcvLoadRequest(
        file_path=f" {csv_path} ",
        symbol=" xauusd ",
        timeframe=" h1 ",
        provider_id=" csv-local ",
        quality=" validated ",
        delimiter=",",
        metadata={
            "source": "test",
        },
    )

    payload = request.to_dict()

    assert payload["file_path"] == str(csv_path)
    assert payload["symbol"] == "XAUUSD"
    assert payload["provider_id"] == "csv-local"
    assert payload["delimiter"] == ","
    assert payload["metadata"] == {
        "source": "test",
    }


def test_csv_ohlcv_load_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        CsvOhlcvLoadRequest(file_path="", symbol="XAUUSD", timeframe="H1")

    with pytest.raises(ValueError):
        CsvOhlcvLoadRequest(file_path="file.csv", symbol="bad symbol", timeframe="H1")

    with pytest.raises(ValueError):
        CsvOhlcvLoadRequest(file_path="file.csv", symbol="XAUUSD", timeframe="H1", provider_id="")

    with pytest.raises(ValueError):
        CsvOhlcvLoadRequest(file_path="file.csv", symbol="XAUUSD", timeframe="H1", column_map="bad")

    with pytest.raises(ValueError):
        CsvOhlcvLoadRequest(file_path="file.csv", symbol="XAUUSD", timeframe="H1", delimiter="::")

    with pytest.raises(ValueError):
        CsvOhlcvLoadRequest(file_path="file.csv", symbol="XAUUSD", timeframe="H1", metadata=[])


def test_build_csv_ohlcv_load_request(tmp_path):
    csv_path = write_sample_csv(tmp_path / "sample.csv")

    request = build_csv_ohlcv_load_request(
        file_path=str(csv_path),
        symbol="xauusd",
        timeframe="h1",
    )

    assert isinstance(request, CsvOhlcvLoadRequest)
    assert request.to_dict()["symbol"] == "XAUUSD"


def test_validate_csv_file_path(tmp_path):
    csv_path = write_sample_csv(tmp_path / "sample.csv")

    assert validate_csv_file_path(str(csv_path)) == csv_path

    with pytest.raises(FileNotFoundError):
        validate_csv_file_path(str(tmp_path / "missing.csv"))

    with pytest.raises(ValueError):
        validate_csv_file_path(str(tmp_path))


def test_validate_csv_columns():
    column_map = CsvOhlcvColumnMap()

    assert validate_csv_columns(
        fieldnames=["timestamp", "open", "high", "low", "close", "volume"],
        column_map=column_map,
    ) == ["timestamp", "open", "high", "low", "close", "volume"]

    with pytest.raises(ValueError):
        validate_csv_columns(fieldnames=None, column_map=column_map)

    with pytest.raises(ValueError):
        validate_csv_columns(fieldnames=["timestamp"], column_map=column_map)

    with pytest.raises(ValueError):
        validate_csv_columns(fieldnames=["timestamp"], column_map="bad")


def test_normalize_csv_ohlcv_row():
    row = normalize_csv_ohlcv_row(
        row={
            "timestamp": " 2026-01-01T00:00:00+00:00 ",
            "open": "2000",
            "high": "2020",
            "low": "1990",
            "close": "2010",
            "volume": "100",
        },
        column_map=CsvOhlcvColumnMap(),
    )

    assert row == {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "open": 2000.0,
        "high": 2020.0,
        "low": 1990.0,
        "close": 2010.0,
        "volume": 100.0,
    }

    no_volume = normalize_csv_ohlcv_row(
        row={
            "timestamp": "2026-01-01T00:00:00+00:00",
            "open": "2000",
            "high": "2020",
            "low": "1990",
            "close": "2010",
        },
        column_map=CsvOhlcvColumnMap(),
    )

    assert no_volume["volume"] == 0.0

    with pytest.raises(ValueError):
        normalize_csv_ohlcv_row(row=[], column_map=CsvOhlcvColumnMap())

    with pytest.raises(ValueError):
        normalize_csv_ohlcv_row(row={}, column_map="bad")

    with pytest.raises(KeyError):
        normalize_csv_ohlcv_row(row={}, column_map=CsvOhlcvColumnMap())


def test_read_ohlcv_csv_rows(tmp_path):
    csv_path = write_sample_csv(tmp_path / "sample.csv")

    rows = read_ohlcv_csv_rows(
        file_path=str(csv_path),
    )

    assert len(rows) == 2
    assert rows[0]["timestamp"] == "2026-01-01T00:00:00+00:00"
    assert rows[0]["close"] == 2010.0

    with pytest.raises(ValueError):
        read_ohlcv_csv_rows(
            file_path=str(csv_path),
            delimiter="::",
        )


def test_read_ohlcv_csv_rows_with_custom_columns(tmp_path):
    csv_path = tmp_path / "custom.csv"
    csv_path.write_text(
        "date,o,h,l,c,v\n"
        "2026-01-01T00:00:00+00:00,2000,2020,1990,2010,100\n",
        encoding="utf-8",
    )

    rows = read_ohlcv_csv_rows(
        file_path=str(csv_path),
        column_map=CsvOhlcvColumnMap(
            timestamp="date",
            open="o",
            high="h",
            low="l",
            close="c",
            volume="v",
        ),
    )

    assert len(rows) == 1
    assert rows[0]["close"] == 2010.0


def test_write_ohlcv_csv_rows(tmp_path):
    csv_path = tmp_path / "nested" / "out.csv"

    result_path = write_ohlcv_csv_rows(
        file_path=str(csv_path),
        rows=[
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "open": 2000,
                "high": 2020,
                "low": 1990,
                "close": 2010,
                "volume": 100,
            }
        ],
    )

    assert result_path == csv_path
    assert csv_path.exists()

    rows = read_ohlcv_csv_rows(file_path=str(csv_path))

    assert len(rows) == 1
    assert rows[0]["close"] == 2010.0

    with pytest.raises(ValueError):
        write_ohlcv_csv_rows(file_path="", rows=[])

    with pytest.raises(ValueError):
        write_ohlcv_csv_rows(file_path=str(csv_path), rows="bad")

    with pytest.raises(ValueError):
        write_ohlcv_csv_rows(file_path=str(csv_path), rows=[], delimiter="::")

    with pytest.raises(KeyError):
        write_ohlcv_csv_rows(file_path=str(csv_path), rows=[{}])


def test_build_local_csv_ohlcv_provider():
    provider = build_local_csv_ohlcv_provider(
        provider_id="csv-provider",
        name="CSV Provider",
        metadata={
            "source": "test",
        },
    )

    assert isinstance(provider, LocalCsvOhlcvProvider)
    assert provider.provider_id == "csv-provider"
    assert isinstance(provider.get_adapter(), HistoricalOhlcvAdapter)
    assert provider.metadata == {
        "source": "test",
    }


def test_local_csv_provider_rejects_invalid_values():
    with pytest.raises(ValueError):
        LocalCsvOhlcvProvider(provider_config="bad")

    with pytest.raises(ValueError):
        LocalCsvOhlcvProvider(adapter="bad")

    with pytest.raises(ValueError):
        LocalCsvOhlcvProvider(metadata=[])


def test_local_csv_provider_load_file(tmp_path):
    csv_path = write_sample_csv(tmp_path / "sample.csv")
    provider = build_local_csv_ohlcv_provider(provider_id="csv-local")

    batch = provider.load_file(
        file_path=str(csv_path),
        symbol="xauusd",
        timeframe="h1",
        quality="validated",
        metadata={
            "dataset": "demo",
        },
    )

    assert batch.provider_id == "csv-local"
    assert batch.to_dict()["symbol"] == "XAUUSD"
    assert batch.count == 2
    assert batch.metadata["dataset"] == "demo"
    assert batch.metadata["row_count"] == 2
    assert provider.get_adapter().count() == 1
    assert provider.get_adapter().latest_candle(symbol="XAUUSD", timeframe="H1").close == 2025.0


def test_local_csv_provider_load_rejects_wrong_provider_id(tmp_path):
    csv_path = write_sample_csv(tmp_path / "sample.csv")
    provider = build_local_csv_ohlcv_provider(provider_id="csv-local")

    request = build_csv_ohlcv_load_request(
        file_path=str(csv_path),
        symbol="XAUUSD",
        timeframe="H1",
        provider_id="other",
    )

    with pytest.raises(ValueError):
        provider.load(request)

    with pytest.raises(ValueError):
        provider.load("bad")


def test_local_csv_provider_export_batch(tmp_path):
    csv_path = write_sample_csv(tmp_path / "sample.csv")
    export_path = tmp_path / "export.csv"
    provider = build_local_csv_ohlcv_provider(provider_id="csv-local")
    batch = provider.load_file(
        file_path=str(csv_path),
        symbol="XAUUSD",
        timeframe="H1",
    )

    output_path = provider.export_batch(
        batch=batch,
        file_path=str(export_path),
    )

    assert output_path == export_path
    assert export_path.exists()
    assert len(read_ohlcv_csv_rows(file_path=str(export_path))) == 2


def test_load_csv_ohlcv_into_adapter(tmp_path):
    csv_path = write_sample_csv(tmp_path / "sample.csv")
    adapter = build_historical_ohlcv_adapter(provider_id="csv-local")

    batch = load_csv_ohlcv_into_adapter(
        adapter=adapter,
        file_path=str(csv_path),
        symbol="XAUUSD",
        timeframe="H1",
    )

    assert batch.count == 2
    assert adapter.count() == 1

    with pytest.raises(ValueError):
        load_csv_ohlcv_into_adapter(
            adapter="bad",
            file_path=str(csv_path),
            symbol="XAUUSD",
            timeframe="H1",
        )


def test_csv_provider_exports_exist():
    import aqos.providers as providers

    expected_exports = [
        "CsvOhlcvColumnMap",
        "CsvOhlcvLoadRequest",
        "LocalCsvOhlcvProvider",
        "build_csv_ohlcv_column_map",
        "build_csv_ohlcv_load_request",
        "build_local_csv_ohlcv_provider",
        "load_csv_ohlcv_into_adapter",
        "normalize_csv_ohlcv_row",
        "read_ohlcv_csv_rows",
        "validate_csv_columns",
        "validate_csv_file_path",
        "write_ohlcv_csv_rows",
    ]

    for export_name in expected_exports:
        assert hasattr(providers, export_name), export_name