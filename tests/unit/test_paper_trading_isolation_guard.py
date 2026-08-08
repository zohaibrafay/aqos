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
        "commands.py",
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


#: Paper modules that only read persisted history.
#:
#: Importing one cannot cause a fill: they query rows the simulator already
#: wrote. A read-only API needs these to show a user their own paper history.
PAPER_READ_ONLY_MODULES = frozenset(
    {
        "aqos.paper_trading.contracts",
        "aqos.paper_trading.history",
        "aqos.paper_trading.models",
        "aqos.paper_trading.repositories",
        "aqos.paper_trading.sessions",
        "aqos.paper_trading.session_service",
    }
)

#: Paper modules that can actually execute something.
#:
#: These place orders, fill them, move balances and decide eligibility. Nothing
#: outside the package may import them: that is the boundary which keeps a
#: simulated fill from reaching a real execution route.
PAPER_EXECUTION_MODULES = frozenset(
    {
        "aqos.paper_trading.eligibility",
        "aqos.paper_trading.execution_service",
        "aqos.paper_trading.memory_broker",
        "aqos.paper_trading.simulator",
        "aqos.paper_trading.validation",
    }
)

#: The one module outside callers may use to cause paper activity.
#:
#: Sprint 060 opened paper mutation over HTTP. Rather than letting the API
#: import the execution service — which would let a transport layer choose its
#: own safety rails — it imports this, which takes plain values and always runs
#: the same gate. Widening this set is how the boundary would be lost, so it
#: stays exactly one module.
PAPER_COMMAND_MODULES = frozenset({"aqos.paper_trading.commands"})

#: Packages allowed to read persisted paper history.
#:
#: Only the read-only HTTP layer. Anything live, broker-facing or
#: execution-facing stays out entirely, read-only or not.
PAPER_READ_ONLY_CONSUMERS = ("aqos/http_api",)

#: Packages allowed to issue paper commands.
#:
#: The same HTTP layer, and nothing else. A live or broker-facing package that
#: could issue a paper command could book simulated activity from a real path.
PAPER_COMMAND_CONSUMERS = ("aqos/http_api",)

#: Packages that must never touch paper trading at all.
EXECUTION_FACING_PACKAGES = (
    "aqos/brokers",
    "aqos/execution_policy",
    "aqos/providers",
    "aqos/news_providers",
)


def imported_modules(path: Path) -> set[str]:
    """
    Every module this file imports, by dotted name.

    Parsed rather than grepped: a mention in a docstring or a comment is not a
    dependency, and only a real import can create one.
    """

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            modules.add(node.module)

    return modules


def paper_imports(path: Path) -> set[str]:
    return {
        module
        for module in imported_modules(path)
        if module == "aqos.paper_trading"
        or module.startswith("aqos.paper_trading.")
    }


def source_modules_outside_paper_trading() -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(SRC_DIR.rglob("*.py"))
        if PAPER_TRADING_DIR not in path.parents
    )


def test_the_module_split_covers_the_whole_package() -> None:
    """
    Every paper module is classified.

    A new module that is neither read-only nor execution would otherwise fall
    through the guard unnoticed.
    """

    classified = (
        PAPER_READ_ONLY_MODULES | PAPER_EXECUTION_MODULES | PAPER_COMMAND_MODULES
    )
    actual = {
        f"aqos.paper_trading.{path.stem}"
        for path in paper_trading_modules()
        if path.stem != "__init__"
    }

    assert actual == classified


def test_the_module_sets_do_not_overlap() -> None:
    assert not (PAPER_READ_ONLY_MODULES & PAPER_EXECUTION_MODULES)
    assert not (PAPER_READ_ONLY_MODULES & PAPER_COMMAND_MODULES)
    assert not (PAPER_EXECUTION_MODULES & PAPER_COMMAND_MODULES)


def test_the_command_boundary_is_exactly_one_module() -> None:
    """
    One door in, not a corridor of them.

    Every module added here is another place a caller could reach past the
    gate, so growing this set has to be a deliberate, visible act.
    """

    assert PAPER_COMMAND_MODULES == {"aqos.paper_trading.commands"}


def test_the_command_boundary_owns_the_execution_internals() -> None:
    """
    The boundary is only a boundary if it is the one importing the internals.

    If ``commands`` delegated to something outside the package, or reached the
    execution service indirectly, callers would be relying on a door that does
    not lead anywhere.
    """

    commands = PAPER_TRADING_DIR / "commands.py"

    assert commands.exists()
    assert "aqos.paper_trading.execution_service" in imported_modules(commands)


def test_no_module_outside_paper_trading_imports_execution_internals() -> None:
    """
    The boundary that matters: nothing outside may execute paper trades.

    Importing the simulator, the broker or the execution service from elsewhere
    is what could put a simulated fill on a real execution route.
    """

    offenders: list[str] = []

    for path in source_modules_outside_paper_trading():
        forbidden = paper_imports(path) & PAPER_EXECUTION_MODULES

        if forbidden:
            offenders.append(f"{path.relative_to(SRC_DIR)} -> {sorted(forbidden)}")

    assert offenders == []


def test_the_package_root_counts_as_execution() -> None:
    """
    ``import aqos.paper_trading`` re-exports the execution surface.

    Importing the package itself would hand a caller the simulator and the
    execution service, so it is forbidden exactly like importing them directly.
    """

    offenders: list[str] = []

    for path in source_modules_outside_paper_trading():
        if "aqos.paper_trading" in paper_imports(path):
            offenders.append(str(path.relative_to(SRC_DIR)))

    assert offenders == []


def test_only_approved_consumers_read_paper_history() -> None:
    """Read-only paper history is for the read-only API layer and nothing else."""

    offenders: list[str] = []

    for path in source_modules_outside_paper_trading():
        if not paper_imports(path) & PAPER_READ_ONLY_MODULES:
            continue

        relative = path.relative_to(SRC_DIR).as_posix()

        if not any(
            relative.startswith(f"{consumer.removeprefix('aqos/')}/")
            for consumer in PAPER_READ_ONLY_CONSUMERS
        ):
            offenders.append(relative)

    assert offenders == []


def test_only_approved_consumers_issue_paper_commands() -> None:
    """The command boundary is for the HTTP layer and nothing else."""

    offenders: list[str] = []

    for path in source_modules_outside_paper_trading():
        if not paper_imports(path) & PAPER_COMMAND_MODULES:
            continue

        relative = path.relative_to(SRC_DIR).as_posix()

        if not any(
            relative.startswith(f"{consumer.removeprefix('aqos/')}/")
            for consumer in PAPER_COMMAND_CONSUMERS
        ):
            offenders.append(relative)

    assert offenders == []


def test_the_http_layer_reaches_paper_trading_only_through_approved_modules() -> None:
    """
    The API may read history and issue commands. Nothing else.

    Stated from the API's side as well as from paper trading's, because this is
    the rule that keeps a transport layer from assembling its own execution
    path out of the internals.
    """

    allowed = PAPER_READ_ONLY_MODULES | PAPER_COMMAND_MODULES
    offenders: list[str] = []

    for path in source_modules_outside_paper_trading():
        relative = path.relative_to(SRC_DIR).as_posix()

        if not relative.startswith("http_api/"):
            continue

        forbidden = paper_imports(path) - allowed

        if forbidden:
            offenders.append(f"{relative} -> {sorted(forbidden)}")

    assert offenders == []


def test_the_http_layer_imports_no_execution_internal() -> None:
    """
    Said separately and bluntly, because this is the one that matters.

    The simulator, the broker, the execution service, the eligibility gate and
    the validation rules are all unreachable from the API.
    """

    offenders: list[str] = []

    for path in source_modules_outside_paper_trading():
        relative = path.relative_to(SRC_DIR).as_posix()

        if not relative.startswith("http_api/"):
            continue

        forbidden = paper_imports(path) & PAPER_EXECUTION_MODULES

        if forbidden:
            offenders.append(f"{relative} -> {sorted(forbidden)}")

    assert offenders == []


def test_an_api_module_reaching_the_execution_service_would_be_caught(
    tmp_path,
) -> None:
    """The guard fails on a real violation rather than only passing."""

    offender = tmp_path / "routes_sneaky.py"
    offender.write_text(
        "from aqos.paper_trading.execution_service import "
        "PaperExecutionService\n"
        "from aqos.paper_trading.simulator import PaperMarketBar\n",
        encoding="utf-8",
    )

    forbidden = paper_imports(offender) & PAPER_EXECUTION_MODULES

    assert forbidden == {
        "aqos.paper_trading.execution_service",
        "aqos.paper_trading.simulator",
    }


def test_a_command_import_is_recognised_as_approved(tmp_path) -> None:
    caller = tmp_path / "routes_paper_actions.py"
    caller.write_text(
        "from aqos.paper_trading.commands import PaperCommandService\n",
        encoding="utf-8",
    )

    imports = paper_imports(caller)

    assert imports & PAPER_COMMAND_MODULES == {"aqos.paper_trading.commands"}
    assert not imports & PAPER_EXECUTION_MODULES


def test_execution_facing_packages_import_nothing_from_paper_trading() -> None:
    """
    Broker and execution-policy code stays completely clear of the simulator.

    Read-only or not: a live path has no business reading simulated history.
    """

    offenders: list[str] = []

    for path in source_modules_outside_paper_trading():
        relative = path.relative_to(SRC_DIR).as_posix()

        if not any(
            relative.startswith(package.removeprefix("aqos/"))
            for package in EXECUTION_FACING_PACKAGES
        ):
            continue

        if paper_imports(path):
            offenders.append(relative)

    assert offenders == []


def test_a_docstring_mention_is_not_a_dependency() -> None:
    """
    The guard parses imports, so prose about the boundary is not a violation.

    The previous text search flagged any file that merely named the package,
    including one documenting this very rule.
    """

    source = (
        '"""A module that only talks about aqos.paper_trading."""\n'
        "# aqos.paper_trading.simulator is mentioned here too\n"
        "value = 'aqos.paper_trading.execution_service'\n"
    )
    tree = ast.parse(source)
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

    assert modules == set()


def test_a_forbidden_import_would_still_be_caught(tmp_path) -> None:
    """The guard must actually fail on a real violation, not just pass."""

    offender = tmp_path / "live_executor.py"
    offender.write_text(
        "from aqos.paper_trading.execution_service import "
        "PaperExecutionService\n",
        encoding="utf-8",
    )

    assert paper_imports(offender) & PAPER_EXECUTION_MODULES == {
        "aqos.paper_trading.execution_service"
    }


def test_a_read_only_import_is_recognised_as_such(tmp_path) -> None:
    reader = tmp_path / "reader.py"
    reader.write_text(
        "from aqos.paper_trading.history import PaperHistoryService\n",
        encoding="utf-8",
    )

    imports = paper_imports(reader)

    assert imports & PAPER_READ_ONLY_MODULES == {"aqos.paper_trading.history"}
    assert not imports & PAPER_EXECUTION_MODULES


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
