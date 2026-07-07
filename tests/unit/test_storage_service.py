"""
Unit tests for StorageService.
"""

import pytest

from aqos.services import StorageRecord, StorageService


def test_save_record():
    service = StorageService()

    record = service.save(
        key="run-1",
        value={"profit": 100.0},
        namespace="experiments",
        metadata={"symbol": "XAUUSD"},
    )

    assert isinstance(record, StorageRecord)
    assert record.key == "run-1"
    assert record.namespace == "experiments"
    assert record.value["profit"] == 100.0
    assert record.metadata["symbol"] == "XAUUSD"
    assert service.count() == 1


def test_save_default_namespace():
    service = StorageService()

    record = service.save(
        key="config",
        value={"mode": "test"},
    )

    assert record.namespace == "default"
    assert service.exists("config") is True


def test_get_record():
    service = StorageService()

    service.save(
        key="run-1",
        value={"profit": 100.0},
        namespace="experiments",
    )

    record = service.get(
        key="run-1",
        namespace="experiments",
    )

    assert record is not None
    assert record.key == "run-1"


def test_get_missing_record():
    service = StorageService()

    record = service.get(
        key="missing",
        namespace="experiments",
    )

    assert record is None


def test_get_required_missing_record():
    service = StorageService()

    with pytest.raises(ValueError):
        service.get_required(
            key="missing",
            namespace="experiments",
        )


def test_load_value():
    service = StorageService()

    service.save(
        key="run-1",
        value={"profit": 100.0},
        namespace="experiments",
    )

    value = service.load(
        key="run-1",
        namespace="experiments",
    )

    assert value == {"profit": 100.0}


def test_load_returns_copy():
    service = StorageService()

    service.save(
        key="run-1",
        value={"profit": 100.0},
        namespace="experiments",
    )

    value = service.load(
        key="run-1",
        namespace="experiments",
    )

    value["profit"] = 999.0

    original = service.load(
        key="run-1",
        namespace="experiments",
    )

    assert original["profit"] == 100.0


def test_exists_true():
    service = StorageService()

    service.save(
        key="run-1",
        value={"profit": 100.0},
        namespace="experiments",
    )

    assert service.exists(
        key="run-1",
        namespace="experiments",
    ) is True


def test_exists_false():
    service = StorageService()

    assert service.exists(
        key="run-1",
        namespace="experiments",
    ) is False


def test_save_without_overwrite_raises_for_existing_record():
    service = StorageService()

    service.save(
        key="run-1",
        value={"profit": 100.0},
        namespace="experiments",
    )

    with pytest.raises(ValueError):
        service.save(
            key="run-1",
            value={"profit": 200.0},
            namespace="experiments",
            overwrite=False,
        )


def test_save_with_overwrite_updates_value():
    service = StorageService()

    service.save(
        key="run-1",
        value={"profit": 100.0},
        namespace="experiments",
    )

    service.save(
        key="run-1",
        value={"profit": 200.0},
        namespace="experiments",
    )

    value = service.load(
        key="run-1",
        namespace="experiments",
    )

    assert value["profit"] == 200.0


def test_list_records():
    service = StorageService()

    service.save("run-b", {"profit": 200.0}, "experiments")
    service.save("run-a", {"profit": 100.0}, "experiments")

    records = service.list()

    assert len(records) == 2


def test_list_records_by_namespace():
    service = StorageService()

    service.save("run-1", {"profit": 100.0}, "experiments")
    service.save("model-1", {"accuracy": 0.8}, "models")

    records = service.list(namespace="experiments")

    assert len(records) == 1
    assert records[0].namespace == "experiments"


def test_list_keys():
    service = StorageService()

    service.save("run-b", {"profit": 200.0}, "experiments")
    service.save("run-a", {"profit": 100.0}, "experiments")

    assert service.list_keys("experiments") == [
        "run-a",
        "run-b",
    ]


def test_list_namespaces():
    service = StorageService()

    service.save("run-1", {"profit": 100.0}, "experiments")
    service.save("model-1", {"accuracy": 0.8}, "models")

    assert service.list_namespaces() == [
        "experiments",
        "models",
    ]


def test_update_metadata():
    service = StorageService()

    service.save(
        key="run-1",
        value={"profit": 100.0},
        namespace="experiments",
        metadata={"symbol": "XAUUSD"},
    )

    record = service.update_metadata(
        key="run-1",
        namespace="experiments",
        metadata={"timeframe": "H1"},
    )

    assert record.metadata["symbol"] == "XAUUSD"
    assert record.metadata["timeframe"] == "H1"


def test_update_metadata_missing_record():
    service = StorageService()

    with pytest.raises(ValueError):
        service.update_metadata(
            key="missing",
            namespace="experiments",
            metadata={"symbol": "XAUUSD"},
        )


def test_update_metadata_empty_metadata():
    service = StorageService()

    service.save(
        key="run-1",
        value={"profit": 100.0},
        namespace="experiments",
    )

    with pytest.raises(ValueError):
        service.update_metadata(
            key="run-1",
            namespace="experiments",
            metadata={},
        )


def test_count_by_namespace():
    service = StorageService()

    service.save("run-1", {"profit": 100.0}, "experiments")
    service.save("run-2", {"profit": 200.0}, "experiments")
    service.save("model-1", {"accuracy": 0.8}, "models")

    assert service.count("experiments") == 2
    assert service.count("models") == 1
    assert service.count() == 3


def test_remove_record():
    service = StorageService()

    service.save(
        key="run-1",
        value={"profit": 100.0},
        namespace="experiments",
    )

    service.remove(
        key="run-1",
        namespace="experiments",
    )

    assert service.exists(
        key="run-1",
        namespace="experiments",
    ) is False
    assert service.count() == 0


def test_clear_namespace():
    service = StorageService()

    service.save("run-1", {"profit": 100.0}, "experiments")
    service.save("model-1", {"accuracy": 0.8}, "models")

    service.clear_namespace("experiments")

    assert service.count("experiments") == 0
    assert service.count("models") == 1


def test_clear_storage():
    service = StorageService()

    service.save("run-1", {"profit": 100.0}, "experiments")
    service.save("model-1", {"accuracy": 0.8}, "models")

    service.clear()

    assert service.count() == 0


def test_empty_key():
    service = StorageService()

    with pytest.raises(ValueError):
        service.save(
            key="",
            value={"profit": 100.0},
            namespace="experiments",
        )


def test_empty_namespace():
    service = StorageService()

    with pytest.raises(ValueError):
        service.save(
            key="run-1",
            value={"profit": 100.0},
            namespace="",
        )


def test_list_with_empty_namespace():
    service = StorageService()

    with pytest.raises(ValueError):
        service.list(namespace="")


def test_clear_empty_namespace():
    service = StorageService()

    with pytest.raises(ValueError):
        service.clear_namespace("")