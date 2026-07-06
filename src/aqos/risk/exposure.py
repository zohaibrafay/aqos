"""
Exposure risk.

Calculates position exposure and validates exposure limits.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ExposureRecord:
    """
    Represents exposure for a single position.
    """

    symbol: str
    position_size: float
    price: float
    exposure: float


@dataclass(slots=True)
class ExposureManager:
    """
    Exposure risk manager.
    """

    max_exposure_percent: float = 1.0

    def __post_init__(self) -> None:
        """
        Validate exposure configuration.
        """

        if self.max_exposure_percent <= 0:
            raise ValueError(
                "Max exposure percent must be greater than zero."
            )

        if self.max_exposure_percent > 1:
            raise ValueError(
                "Max exposure percent cannot be greater than 1."
            )

    def calculate(
        self,
        position_size: float,
        price: float,
    ) -> float:
        """
        Calculate position exposure.
        """

        if position_size <= 0:
            raise ValueError("Position size must be greater than zero.")

        if price <= 0:
            raise ValueError("Price must be greater than zero.")

        return position_size * price

    def exposure_percent(
        self,
        exposure: float,
        account_balance: float,
    ) -> float:
        """
        Calculate exposure as a percentage of account balance.
        """

        if exposure < 0:
            raise ValueError("Exposure cannot be negative.")

        if account_balance <= 0:
            raise ValueError("Account balance must be greater than zero.")

        return exposure / account_balance

    def is_within_limit(
        self,
        exposure: float,
        account_balance: float,
    ) -> bool:
        """
        Check whether exposure is within the configured limit.
        """

        percent = self.exposure_percent(
            exposure=exposure,
            account_balance=account_balance,
        )

        return percent <= self.max_exposure_percent

    def create_record(
        self,
        symbol: str,
        position_size: float,
        price: float,
    ) -> ExposureRecord:
        """
        Create an exposure record.
        """

        if not symbol:
            raise ValueError("Symbol cannot be empty.")

        exposure = self.calculate(
            position_size=position_size,
            price=price,
        )

        return ExposureRecord(
            symbol=symbol,
            position_size=position_size,
            price=price,
            exposure=exposure,
        )

    def total_exposure(
        self,
        records: list[ExposureRecord],
    ) -> float:
        """
        Calculate total exposure from exposure records.
        """

        if not records:
            return 0.0

        return sum(record.exposure for record in records)


__all__ = [
    "ExposureManager",
    "ExposureRecord",
]