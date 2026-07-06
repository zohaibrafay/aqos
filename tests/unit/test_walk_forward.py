"""
Unit tests for WalkForwardValidator.
"""

import pytest

from aqos.evaluation import WalkForwardSplit, WalkForwardValidator


def test_walk_forward_split():
    validator = WalkForwardValidator(
        train_size=4,
        test_size=2,
        step_size=2,
    )

    splits = validator.split(
        data=[
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
        ]
    )

    assert len(splits) == 3

    first = splits[0]

    assert isinstance(first, WalkForwardSplit)
    assert first.train_start == 0
    assert first.train_end == 4
    assert first.test_start == 4
    assert first.test_end == 6
    assert first.train_data == [1, 2, 3, 4]
    assert first.test_data == [5, 6]


def test_default_step_size_uses_test_size():
    validator = WalkForwardValidator(
        train_size=4,
        test_size=2,
    )

    splits = validator.split(
        data=[
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
        ]
    )

    assert len(splits) == 3
    assert splits[1].train_start == 2
    assert splits[1].test_start == 6


def test_custom_step_size():
    validator = WalkForwardValidator(
        train_size=3,
        test_size=2,
        step_size=1,
    )

    splits = validator.split(
        data=[
            1,
            2,
            3,
            4,
            5,
            6,
        ]
    )

    assert len(splits) == 2
    assert splits[0].train_data == [1, 2, 3]
    assert splits[0].test_data == [4, 5]
    assert splits[1].train_data == [2, 3, 4]
    assert splits[1].test_data == [5, 6]


def test_single_split():
    validator = WalkForwardValidator(
        train_size=3,
        test_size=2,
    )

    splits = validator.split(
        data=[
            1,
            2,
            3,
            4,
            5,
        ]
    )

    assert len(splits) == 1
    assert splits[0].train_data == [1, 2, 3]
    assert splits[0].test_data == [4, 5]


def test_invalid_train_size():
    with pytest.raises(ValueError):
        WalkForwardValidator(
            train_size=0,
            test_size=2,
        )


def test_invalid_test_size():
    with pytest.raises(ValueError):
        WalkForwardValidator(
            train_size=4,
            test_size=0,
        )


def test_invalid_step_size():
    with pytest.raises(ValueError):
        WalkForwardValidator(
            train_size=4,
            test_size=2,
            step_size=0,
        )


def test_empty_data():
    validator = WalkForwardValidator(
        train_size=4,
        test_size=2,
    )

    with pytest.raises(ValueError):
        validator.split([])


def test_insufficient_data():
    validator = WalkForwardValidator(
        train_size=4,
        test_size=2,
    )

    with pytest.raises(ValueError):
        validator.split(
            data=[
                1,
                2,
                3,
                4,
                5,
            ]
        )