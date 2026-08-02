from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aqos.accounts.models import AccountStatus, AccountType, TradingAccount
from aqos.paper_trading.contracts import (
    OPENING_PAPER_ACTIONS,
    PaperAction,
    PaperExecutionRequest,
    PaperOrderType,
    PaperRejectionReason,
    SUPPORTED_PAPER_ORDER_TYPES,
)


AQOS_PAPER_VALIDATION_VERSION = "1.0"

#: Order types that must carry a price. A market order takes the current price;
#: a limit or stop order without one has no trigger at all.
PRICE_REQUIRED_ORDER_TYPES = (PaperOrderType.LIMIT, PaperOrderType.STOP)


@dataclass(frozen=True)
class PaperValidationResult:
    """The outcome of validating a paper execution request."""

    accepted: bool
    rejection_reason: PaperRejectionReason | None = None
    rejection_message: str | None = None

    def __post_init__(self) -> None:
        if not self.accepted and self.rejection_reason is None:
            raise ValueError("A rejected validation must carry a reason.")

    @classmethod
    def accept(cls) -> "PaperValidationResult":
        return cls(accepted=True)

    @classmethod
    def reject(
        cls,
        reason: PaperRejectionReason,
        message: str,
    ) -> "PaperValidationResult":
        return cls(
            accepted=False,
            rejection_reason=reason,
            rejection_message=message,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "rejection_reason": (
                self.rejection_reason.value if self.rejection_reason else None
            ),
            "rejection_message": self.rejection_message,
        }


def validate_paper_account(account: TradingAccount) -> PaperValidationResult:
    """
    Check the account is one the paper broker may act on.

    Paper trading only ever touches paper accounts: routing a paper order at a
    live or funded account would put simulated fills against real capital.
    """

    if account.account_type != AccountType.PAPER:
        return PaperValidationResult.reject(
            PaperRejectionReason.ACCOUNT_NOT_PAPER,
            f"The paper broker only accepts paper accounts, not "
            f"{account.account_type.value}.",
        )

    if account.status != AccountStatus.ACTIVE:
        return PaperValidationResult.reject(
            PaperRejectionReason.ACCOUNT_NOT_ACTIVE,
            f"Account status is {account.status.value}.",
        )

    return PaperValidationResult.accept()


def validate_paper_execution_request(
    request: PaperExecutionRequest,
    account: TradingAccount,
) -> PaperValidationResult:
    """Validate a request against the account it targets."""

    if request.account_id != account.account_id:
        return PaperValidationResult.reject(
            PaperRejectionReason.MISSING_REQUIRED_FIELD,
            "Request and account refer to different accounts.",
        )

    if request.user_id != account.user_id:
        return PaperValidationResult.reject(
            PaperRejectionReason.MISSING_REQUIRED_FIELD,
            "Request and account refer to different users.",
        )

    account_result = validate_paper_account(account)

    if not account_result.accepted:
        return account_result

    if request.quantity <= 0:
        return PaperValidationResult.reject(
            PaperRejectionReason.INVALID_QUANTITY,
            f"Quantity must be positive, got {request.quantity}.",
        )

    if request.order_type not in SUPPORTED_PAPER_ORDER_TYPES:
        return PaperValidationResult.reject(
            PaperRejectionReason.UNSUPPORTED_ORDER_TYPE,
            f"Unsupported order type: {request.order_type.value}.",
        )

    if request.action not in tuple(PaperAction):
        return PaperValidationResult.reject(
            PaperRejectionReason.UNSAFE_ACTION,
            f"Unsupported action: {request.action}.",
        )

    if (
        request.order_type in PRICE_REQUIRED_ORDER_TYPES
        and request.requested_price is None
    ):
        return PaperValidationResult.reject(
            PaperRejectionReason.MISSING_REQUIRED_FIELD,
            f"A {request.order_type.value} order requires a requested price.",
        )

    for field_name, value in (
        ("requested_price", request.requested_price),
        ("stop_loss", request.stop_loss),
        ("take_profit", request.take_profit),
    ):
        if value is not None and value <= 0:
            return PaperValidationResult.reject(
                PaperRejectionReason.INVALID_PRICE,
                f"{field_name} must be positive, got {value}.",
            )

    if request.action in OPENING_PAPER_ACTIONS:
        stop_result = validate_protective_prices(request)

        if not stop_result.accepted:
            return stop_result

    return PaperValidationResult.accept()


def validate_protective_prices(
    request: PaperExecutionRequest,
) -> PaperValidationResult:
    """
    Check stop loss and take profit sit on the correct side of the entry.

    A stop above the entry on a long position would close the trade instantly at
    a loss, which is never what the caller meant.
    """

    reference = request.requested_price

    if reference is None:
        return PaperValidationResult.accept()

    if request.action == PaperAction.BUY:
        if request.stop_loss is not None and request.stop_loss >= reference:
            return PaperValidationResult.reject(
                PaperRejectionReason.INVALID_PRICE,
                "A long stop loss must be below the entry price.",
            )

        if request.take_profit is not None and request.take_profit <= reference:
            return PaperValidationResult.reject(
                PaperRejectionReason.INVALID_PRICE,
                "A long take profit must be above the entry price.",
            )

    if request.action == PaperAction.SELL:
        if request.stop_loss is not None and request.stop_loss <= reference:
            return PaperValidationResult.reject(
                PaperRejectionReason.INVALID_PRICE,
                "A short stop loss must be above the entry price.",
            )

        if request.take_profit is not None and request.take_profit >= reference:
            return PaperValidationResult.reject(
                PaperRejectionReason.INVALID_PRICE,
                "A short take profit must be below the entry price.",
            )

    return PaperValidationResult.accept()


__all__ = [
    "AQOS_PAPER_VALIDATION_VERSION",
    "PRICE_REQUIRED_ORDER_TYPES",
    "PaperValidationResult",
    "validate_paper_account",
    "validate_paper_execution_request",
    "validate_protective_prices",
]
