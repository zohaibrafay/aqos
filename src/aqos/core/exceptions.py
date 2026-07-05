"""
AQOS Exception Framework

Defines the custom exception hierarchy used across AQOS.
"""

from __future__ import annotations


class AQOSException(Exception):
    """
    Base exception for all AQOS-specific errors.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


class ConfigurationError(AQOSException):
    """Raised when configuration loading or validation fails."""


class ValidationError(AQOSException):
    """Raised when validation fails."""


class DataError(AQOSException):
    """Raised when data processing fails."""


class FeatureError(AQOSException):
    """Raised when feature engineering fails."""


class ModelError(AQOSException):
    """Raised when model operations fail."""


class MemoryError(AQOSException):
    """Raised when memory subsystem fails."""


class StrategyError(AQOSException):
    """Raised when strategy generation fails."""


class RiskError(AQOSException):
    """Raised when risk management fails."""


class AgentError(AQOSException):
    """Raised when an agent fails."""


class InfrastructureError(AQOSException):
    """Raised for infrastructure-related failures."""