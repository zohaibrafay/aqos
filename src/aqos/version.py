"""
AQOS Version Management

This module provides version and application metadata for AQOS.

It intentionally contains no external dependencies and acts as the
single source of truth for application identity.
"""

# ============================================================================
# Application Metadata (Single Source of Truth)
# ============================================================================

APP_NAME = "AQOS"
FULL_NAME = "AI Quant Operating System"

VERSION = "0.1.0"
RELEASE_STAGE = "Development"

AUTHOR = "Zohaib Hussain"

COPYRIGHT = "Copyright (c) 2026 AQOS"

DESCRIPTION = (
    "A research-driven AI Quantitative Research Platform "
    "for financial market intelligence."
)


# ============================================================================
# Version Helper
# ============================================================================

class Version:
    """
    Provides access to AQOS application metadata.

    This class contains only static methods because version information
    is global application metadata and does not require object instances.
    """

    @staticmethod
    def get_app_name() -> str:
        """Return the application name."""
        return APP_NAME

    @staticmethod
    def get_full_name() -> str:
        """Return the full application name."""
        return FULL_NAME

    @staticmethod
    def get_version() -> str:
        """Return the application version."""
        return VERSION

    @staticmethod
    def get_release_stage() -> str:
        """Return the current release stage."""
        return RELEASE_STAGE

    @staticmethod
    def get_full_version() -> str:
        """Return application name with version."""
        return f"{APP_NAME} v{VERSION}"

    @staticmethod
    def get_banner() -> str:
        """Return the AQOS startup banner."""

        return (
            "\n"
            "============================================================\n"
            f"{FULL_NAME}\n"
            f"Application : {APP_NAME}\n"
            f"Version     : {VERSION}\n"
            f"Stage       : {RELEASE_STAGE}\n"
            f"Author      : {AUTHOR}\n"
            "============================================================"
        )