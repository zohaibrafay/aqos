"""
AQOS - AI Quant Operating System
"""

from .version import Version

__version__ = Version.get_version()

__all__ = [
    "Version",
]