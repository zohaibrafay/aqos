"""
Guard tests keeping backtesting historical and keeping the API out of it.

A backtest reads files, writes files and runs a simulation. Sprint 061 made it
reachable over HTTP, which means a request is now one step away from all three
— so the boundary is checked structurally, not trusted.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from aqos.backtesting.commands import (
    DATASET_NAME_PATTERN,
    SUPPORTED_STRATEGIES,
    BacktestDatasetError,
    normalize_dataset_name,
)


SRC_DIR = Path(__file__).resolve().parents[2] / "src" / "aqos"

BACKTESTING_DIR = SRC_DIR / "backtesting"

HTTP_API_DIR = SRC_DIR / "http_api"

#: Libraries that would let a backtest reach a live venue or the network.
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "aiohttp",
        "binance",
        "boto3",
        "ccxt",
        "ftplib",
        "httpx",
        "ib_insync",
        "MetaTrader5",
        "oandapyV20",
        "paramiko",
        "requests",
        "smtplib",
        "socket",
        "telnetlib",
        "urllib",
        "urllib3",
        "websocket",
        "websockets",
        "xmlrpc",
    }
)

#: Builtins that turn data into code.
#:
#: Matched only when called bare, because that is the only way the builtin is
#: reached. ``re.compile`` is an attribute call and compiles a pattern, not a
#: program, so flagging it would be a false alarm that trains people to ignore
#: this guard.
FORBIDDEN_BUILTIN_CALLS = frozenset({"eval", "exec", "compile", "__import__"})

#: Ways a module could import by name or start a process.
#:
#: Matched however they are called. A backtest that could do any of these would
#: turn "which strategy?" into "which code?", which is the difference between a
#: simulation and a remote shell.
FORBIDDEN_DYNAMIC_CALLS = frozenset(
    {
        "import_module",
        "load_module",
        "system",
        "popen",
        "spawn",
        "check_output",
        "check_call",
        "Popen",
    }
)

#: Backtesting modules the API may import.
#:
#: The command boundary, plus the read-only registry the Sprint 056 endpoints
#: serve from. Everything else — the runner, the simulator, the data loader,
#: the adapters — stays private.
BACKTEST_API_ALLOWED_MODULES = frozenset(
    {
        "aqos.backtesting.commands",
        "aqos.backtesting.registry",
    }
)

#: The single command boundary.
BACKTEST_COMMAND_MODULES = frozenset({"aqos.backtesting.commands"})


def python_files(directory: Path) -> tuple[Path, ...]:
    return tuple(sorted(directory.glob("*.py")))


def imported_modules(path: Path) -> set[str]:
    """Every module this file imports, by dotted name."""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            modules.add(node.module)

    return modules


def imported_roots(path: Path) -> set[str]:
    return {module.split(".")[0] for module in imported_modules(path)}


def dynamic_calls(path: Path) -> set[str]:
    """
    Every call this file makes that could run code chosen at runtime.

    Bare calls are checked against the builtins and attribute calls against the
    dynamic-import and subprocess names, so ``re.compile`` is not mistaken for
    the ``compile`` builtin.
    """

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_BUILTIN_CALLS | FORBIDDEN_DYNAMIC_CALLS:
                found.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in FORBIDDEN_DYNAMIC_CALLS:
                found.add(node.func.attr)

    return found


def backtesting_imports(path: Path) -> set[str]:
    return {
        module
        for module in imported_modules(path)
        if module == "aqos.backtesting"
        or module.startswith("aqos.backtesting.")
    }


def test_the_package_has_modules_to_check() -> None:
    """A guard that silently checks nothing is worse than no guard."""

    names = {path.name for path in python_files(BACKTESTING_DIR)}

    assert {"commands.py", "runner.py", "registry.py", "simulator.py"} <= names


@pytest.mark.parametrize(
    "module_path",
    python_files(BACKTESTING_DIR),
    ids=lambda path: path.name,
)
def test_backtesting_imports_no_broker_or_network_library(
    module_path: Path,
) -> None:
    forbidden = imported_roots(module_path) & FORBIDDEN_IMPORT_ROOTS

    assert not forbidden, (
        f"{module_path.name} imports {sorted(forbidden)}; a backtest replays "
        "stored history and must never reach a venue or the network."
    )


@pytest.mark.parametrize(
    "module_path",
    (*python_files(BACKTESTING_DIR), *python_files(HTTP_API_DIR)),
    ids=lambda path: f"{path.parent.name}/{path.name}",
)
def test_nothing_runs_code_it_was_handed(module_path: Path) -> None:
    """
    No dynamic import, evaluation or subprocess anywhere on this path.

    A request names a strategy and a dataset. Neither may ever become something
    the process imports, evaluates or executes.
    """

    forbidden = dynamic_calls(module_path)

    assert not forbidden, (
        f"{module_path.name} calls {sorted(forbidden)}; nothing on the "
        "backtest path may execute code chosen at runtime."
    )


def test_the_api_reaches_backtesting_only_through_approved_modules() -> None:
    """
    The API may issue commands and read the registry. Nothing else.

    Importing the runner would let a transport layer build its own
    ``BacktestRunnerConfig`` — including its ``data_path``, which is exactly
    the parameter the command boundary exists to keep out of a request.
    """

    offenders: list[str] = []

    for path in python_files(HTTP_API_DIR):
        forbidden = backtesting_imports(path) - BACKTEST_API_ALLOWED_MODULES

        if forbidden:
            offenders.append(f"{path.name} -> {sorted(forbidden)}")

    assert offenders == []


def test_the_api_imports_no_runner_or_simulator() -> None:
    """Said bluntly, because this is the one that matters."""

    private = {
        "aqos.backtesting.runner",
        "aqos.backtesting.simulator",
        "aqos.backtesting.data_loader",
        "aqos.backtesting.strategy_runner",
        "aqos.backtesting.model_runner",
        "aqos.backtesting.cli",
    }
    offenders: list[str] = []

    for path in python_files(HTTP_API_DIR):
        forbidden = backtesting_imports(path) & private

        if forbidden:
            offenders.append(f"{path.name} -> {sorted(forbidden)}")

    assert offenders == []


def test_the_command_boundary_is_exactly_one_module() -> None:
    assert BACKTEST_COMMAND_MODULES == {"aqos.backtesting.commands"}


def test_the_command_boundary_owns_the_runner() -> None:
    """The boundary is only a boundary if it is the one calling the runner."""

    commands = BACKTESTING_DIR / "commands.py"

    assert commands.exists()
    assert "aqos.backtesting.runner" in imported_modules(commands)


def test_an_api_module_importing_the_runner_would_be_caught(tmp_path) -> None:
    """The guard fails on a real violation rather than only passing."""

    offender = tmp_path / "routes_sneaky.py"
    offender.write_text(
        "from aqos.backtesting.runner import run_backtest_from_csv\n",
        encoding="utf-8",
    )

    assert backtesting_imports(offender) - BACKTEST_API_ALLOWED_MODULES == {
        "aqos.backtesting.runner"
    }


def test_a_dynamic_import_would_be_caught(tmp_path) -> None:
    offender = tmp_path / "dynamic.py"
    offender.write_text(
        "import importlib\n"
        "def load(name):\n"
        "    return importlib.import_module(name)\n",
        encoding="utf-8",
    )

    assert dynamic_calls(offender) == {"import_module"}


def test_evaluating_a_string_would_be_caught(tmp_path) -> None:
    offender = tmp_path / "evaluator.py"
    offender.write_text("def run(src):\n    return eval(src)\n", encoding="utf-8")

    assert dynamic_calls(offender) == {"eval"}


def test_compiling_a_regex_is_not_a_violation(tmp_path) -> None:
    """
    The guard has to tell a pattern from a program.

    A guard that cried wolf over ``re.compile`` would be switched off, and then
    it would not catch the thing it exists for.
    """

    innocent = tmp_path / "patterns.py"
    innocent.write_text(
        "import re\nPATTERN = re.compile(r'^[a-z]+$')\n",
        encoding="utf-8",
    )

    assert dynamic_calls(innocent) == set()


class TestDatasetNamesCannotBePaths:
    @pytest.mark.parametrize(
        "name",
        [
            "../etc/passwd",
            "/etc/passwd",
            "C:\\Windows\\win.ini",
            "sub/dir",
            "sub\\dir",
            "..",
            ".",
            "data.csv",
            "with space",
            "with;semicolon",
            "$(whoami)",
            "",
            "   ",
            "x" * 200,
        ],
    )
    def test_anything_that_is_not_a_bare_name_is_refused(
        self,
        name: str,
    ) -> None:
        """
        The pattern is the whole defence.

        A name that cannot express a path cannot escape the configured
        directory, so this is checked before anything is resolved rather than
        after.
        """

        with pytest.raises(BacktestDatasetError):
            normalize_dataset_name(name)

    @pytest.mark.parametrize("name", ["xauusd_h1", "EURUSD-M15", "d1", "a" * 64])
    def test_a_plain_name_is_accepted(self, name: str) -> None:
        assert normalize_dataset_name(name) == name

    def test_the_pattern_anchors_both_ends(self) -> None:
        """An unanchored pattern would match a path that merely contains one."""

        assert DATASET_NAME_PATTERN.pattern.startswith("^")
        assert DATASET_NAME_PATTERN.pattern.endswith("$")


class TestStrategiesAreAFixedList:
    def test_the_supported_strategies_are_named(self) -> None:
        assert SUPPORTED_STRATEGIES == ("csv_signal_strategy",)

    def test_no_strategy_name_looks_like_an_import_path(self) -> None:
        """
        A dotted name would suggest something is imported by name somewhere.

        Nothing here resolves a strategy by import, and the names are kept
        plain so no future reader assumes otherwise.
        """

        for name in SUPPORTED_STRATEGIES:
            assert "." not in name
            assert "/" not in name
            assert ":" not in name
