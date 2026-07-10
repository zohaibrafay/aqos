from __future__ import annotations


def parse_major_minor(version: str) -> tuple[int, int]:
    parts = version.split(".")
    return int(parts[0]), int(parts[1])


def test_ml_dependencies_are_available() -> None:
    import joblib
    import numpy
    import pandas
    import sklearn

    assert numpy.__version__
    assert pandas.__version__
    assert sklearn.__version__
    assert joblib.__version__


def test_numpy_version_is_pinned_below_known_joblib_warning_range() -> None:
    import numpy

    major, minor = parse_major_minor(numpy.__version__)

    assert (major, minor) < (2, 5)