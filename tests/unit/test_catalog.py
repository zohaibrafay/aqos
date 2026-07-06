from pathlib import Path

import pytest

from aqos.data import DataCatalog


def test_register_dataset():

    catalog = DataCatalog()

    catalog.register("gold", "datasets/gold.csv")

    assert catalog.exists("gold")


def test_get_dataset():

    catalog = DataCatalog()

    catalog.register("gold", "datasets/gold.csv")

    path = catalog.get("gold")

    assert isinstance(path, Path)


def test_list_dataset():

    catalog = DataCatalog()

    catalog.register("gold", "datasets/gold.csv")
    catalog.register("eurusd", "datasets/eurusd.csv")

    assert catalog.list() == ["eurusd", "gold"]


def test_missing_dataset():

    catalog = DataCatalog()

    with pytest.raises(KeyError):
        catalog.get("unknown")