"""
Guard tests keeping paper trading simulated and paper-only.

Paper trading must never reach a real venue, and no real-execution path may
depend on it. These are structural checks over the source itself, so they fail
the moment an import sneaks in rather than waiting for a runtime surprise.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from aqos.accounts.models import AccountType
from aqos.paper_trading.eligibility import check_account_is_paper


PAPER_TRADING_DIR = Path(__file__).resolve().parents[2] / "src" / "aqos" / "paper_trading"

SRC_DIR = Path(__file__).resolve().parents[2] / "src" / "aqos"

#: Libraries that would let paper trading reach a real venue or the network.
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "aiohttp",
        "boto3",
        "binance",
        "ccxt",
        "ftplib",
        "http",
        "httpx",
        "ib_insync",
        "MetaTrader5",
        "oandapyV20",
        "paramiko",
        "requests",
        "smtplib",
        "socket",
        "ssl",
        "telnetlib",
        "urllib",
        "urllib3",
        "websocket",
        "websockets",
        "xmlrpc",
    }
)


def paper_trading_modules() -> tuple[Path, ...]:
    return tuple(sorted(PAPER_TRADING_DIR.glob("*.py")))


def imported_roots(path: Path) -> set[str]:
    """Every top-level module name imported by one file."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # A relative import cannot reach a third-party venue library.
                continue

            if node.module:
                roots.add(node.module.split(".")[0])

    return roots


def test_the_package_has_modules_to_check() -> None:
    """A guard that silently checks nothing is worse than no guard."""

    modules = paper_trading_modules()

    assert len(modules) >= 7
    assert {path.name for path in modules} >= {
        "contracts.py",
        "eligibility.py",
        "execution_service.py",
        "memory_broker.py",
        "models.py",
        "repositories.py",
        "simulator.py",
        "validation.py",
    }


@pytest.mark.parametrize(
    "module_path",
    paper_trading_modules(),
    ids=lambda path: path.name,
)
def test_paper_trading_imports_no_broker_or_network_library(
    module_path: Path,
) -> None:
    forbidden = imported_roots(module_path) & FORBIDDEN_IMPORT_ROOTS

    assert not forbidden, (
        f"{module_path.name} imports {sorted(forbidden)}; paper trading is "
        "simulated entirely inside AQOS and must never reach a real venue."
    )


def test_no_real_execution_module_depends_on_paper_trading() -> None:
    """
    Paper trading stays a leaf.

    If a live or broker path imported it, a simulated fill could end up on a
    real execution route by accident.
    """

    importers: list[str] = []

    for path in SRC_DIR.rglob("*.py"):
        if PAPER_TRADING_DIR in path.parents:
            continue

        if "aqos.paper_trading" in path.read_text(encoding="utf-8"):
            importers.append(str(path.relative_to(SRC_DIR)))

    assert importers == []


def test_the_paper_only_rule_refuses_every_non_paper_account_type() -> None:
    """Every account type except paper must be refused, including new ones."""

    class FakeAccount:
        def __init__(self, account_type: AccountType) -> None:
            self.account_type = account_type
            self.broker = type("B", (), {"value": "none"})()

    for account_type in AccountType:
        reason = check_account_is_paper(FakeAccount(account_type))

        if account_type == AccountType.PAPER:
            assert reason is None
        else:
            assert reason is not None
            assert reason.code.value == "account_not_paper"
