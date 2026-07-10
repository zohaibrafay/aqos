from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src" / "aqos"

IGNORED_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def is_ignored(path: Path) -> bool:
    return any(part in IGNORED_DIR_NAMES for part in path.parts)


def has_real_content(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    return bool(text.strip())


def test_aqos_has_no_empty_python_files() -> None:
    empty_files = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in SRC_ROOT.rglob("*.py")
        if not is_ignored(path) and not has_real_content(path)
    ]

    assert empty_files == [], (
        "AQOS should not contain empty Python files. "
        "Delete empty placeholders or replace them with real working logic. "
        f"Empty files: {empty_files}"
    )