"""
Unit tests for AQOS Version Management.
"""

from aqos.version import (
    Version,
    APP_NAME,
    FULL_NAME,
    VERSION,
    RELEASE_STAGE,
    AUTHOR,
    DESCRIPTION,
)


def test_app_name():
    assert Version.get_app_name() == APP_NAME


def test_full_name():
    assert Version.get_full_name() == FULL_NAME


def test_version():
    assert Version.get_version() == VERSION


def test_release_stage():
    assert Version.get_release_stage() == RELEASE_STAGE


def test_full_version():
    assert Version.get_full_version() == f"{APP_NAME} v{VERSION}"


def test_banner_contains_application_name():
    banner = Version.get_banner()

    assert APP_NAME in banner


def test_banner_contains_full_name():
    banner = Version.get_banner()

    assert FULL_NAME in banner


def test_banner_contains_version():
    banner = Version.get_banner()

    assert VERSION in banner


def test_banner_contains_stage():
    banner = Version.get_banner()

    assert RELEASE_STAGE in banner


def test_banner_contains_author():
    banner = Version.get_banner()

    assert AUTHOR in banner


def test_description_is_not_empty():
    assert DESCRIPTION.strip() != ""