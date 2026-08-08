"""
Guard tests keeping notifications inside this machine.

A notification package is where an external provider SDK usually arrives first,
and with it a credential, a network call and a delivery record nobody can
verify. These are structural checks over the source so that arrival fails a
test rather than shipping.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from aqos.notifications import (
    NotificationChannel,
    build_delivery_backends,
    is_supported_channel,
)
from aqos.notifications.types import DeliveryStatus


SRC_DIR = Path(__file__).resolve().parents[2] / "src" / "aqos"

NOTIFICATIONS_DIR = SRC_DIR / "notifications"

#: Libraries that would let a notification leave this machine.
#:
#: Nothing in this package should reach a network, a mail server or a vendor.
#: Delivery is a row in a table until a sprint deliberately makes it more.
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "aiohttp",
        "boto3",
        "botocore",
        "email",
        "firebase_admin",
        "ftplib",
        "http",
        "httpx",
        "mailgun",
        "onesignal",
        "postmarker",
        "pusher",
        "requests",
        "sendgrid",
        "slack_sdk",
        "smtplib",
        "socket",
        "ssl",
        "telegram",
        "twilio",
        "urllib",
        "urllib3",
        "websocket",
        "websockets",
    }
)

#: Builtins that turn data into code.
FORBIDDEN_BUILTIN_CALLS = frozenset({"eval", "exec", "__import__"})

#: Ways a module could import by name or start a process.
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


def notification_modules() -> tuple[Path, ...]:
    return tuple(sorted(NOTIFICATIONS_DIR.glob("*.py")))


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            roots.add(node.module.split(".")[0])

    return roots


def dynamic_calls(path: Path) -> set[str]:
    """
    Calls that could run something chosen at runtime.

    Bare names are checked against the builtins and attribute calls against the
    dynamic-import names, so ``re.compile`` is not mistaken for the ``compile``
    builtin.
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


def test_the_package_has_modules_to_check() -> None:
    """A guard that silently checks nothing is worse than no guard."""

    names = {path.name for path in notification_modules()}

    assert {
        "types.py",
        "models.py",
        "repositories.py",
        "preferences.py",
        "templates.py",
        "service.py",
        "delivery.py",
    } <= names


@pytest.mark.parametrize(
    "module_path",
    notification_modules(),
    ids=lambda path: path.name,
)
def test_it_imports_no_delivery_provider(module_path: Path) -> None:
    forbidden = imported_roots(module_path) & FORBIDDEN_IMPORT_ROOTS

    assert not forbidden, (
        f"{module_path.name} imports {sorted(forbidden)}; notifications are "
        "stored in this database and nothing here may reach a network or a "
        "provider."
    )


@pytest.mark.parametrize(
    "module_path",
    notification_modules(),
    ids=lambda path: path.name,
)
def test_it_runs_no_code_it_was_handed(module_path: Path) -> None:
    """
    Templates are text, not programs.

    A notification body is assembled from caller data, so a dynamic call
    anywhere on this path would turn a message into an execution route.
    """

    forbidden = dynamic_calls(module_path)

    assert not forbidden, (
        f"{module_path.name} calls {sorted(forbidden)}; nothing on the "
        "notification path may execute code chosen at runtime."
    )


def test_no_module_reads_a_credential() -> None:
    offenders: list[str] = []

    for path in notification_modules():
        text = path.read_text(encoding="utf-8")

        # Matched as assignments and lookups rather than as words: several
        # modules name these in prose precisely to say they are excluded.
        if any(
            fragment in text
            for fragment in (
                "SMTP_",
                "smtp_host",
                "api_key=",
                "SENDGRID",
                "getenv(\"AQOS_EMAIL",
                "password=",
            )
        ):
            offenders.append(path.name)

    assert offenders == []


def test_it_writes_no_filesystem_path_into_a_notification() -> None:
    for path in notification_modules():
        text = path.read_text(encoding="utf-8")

        assert "/srv/" not in text
        assert "C:\\\\" not in text


def test_the_dynamic_call_guard_would_catch_a_violation(tmp_path) -> None:
    offender = tmp_path / "sneaky.py"
    offender.write_text(
        "import importlib\n"
        "def render(name):\n"
        "    return importlib.import_module(name)\n",
        encoding="utf-8",
    )

    assert dynamic_calls(offender) == {"import_module"}


def test_the_import_guard_would_catch_a_violation(tmp_path) -> None:
    offender = tmp_path / "mailer.py"
    offender.write_text("import smtplib\n", encoding="utf-8")

    assert imported_roots(offender) & FORBIDDEN_IMPORT_ROOTS == {"smtplib"}


def test_nothing_unsupported_can_report_a_delivery() -> None:
    """
    Stated as behaviour, not only as structure.

    Every backend is asked to deliver, and only the channel this deployment
    actually supports is allowed to say it did.
    """

    for channel, backend in build_delivery_backends().items():
        outcome = backend.deliver("notification_1")

        if outcome.status is DeliveryStatus.SENT:
            assert is_supported_channel(channel), (
                f"{channel.value} reported a delivery it cannot make."
            )


def test_email_and_push_never_report_sent() -> None:
    backends = build_delivery_backends()

    for channel in (NotificationChannel.EMAIL, NotificationChannel.PUSH):
        assert backends[channel].deliver("n").status is not DeliveryStatus.SENT


def test_the_package_exports_what_it_declares() -> None:
    import aqos.notifications as package

    missing = [name for name in package.__all__ if not hasattr(package, name)]

    assert missing == []
    assert package.__all__ == sorted(package.__all__)
