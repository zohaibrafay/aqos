from __future__ import annotations

import ast
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def find_project_root() -> Path:
    current_file = Path(__file__).resolve()

    for parent in current_file.parents:
        if (parent / "src" / "aqos").exists():
            return parent

    raise RuntimeError(
        "Could not find AQOS project root. Expected a folder containing src/aqos."
    )


PROJECT_ROOT = find_project_root()
SRC_ROOT = PROJECT_ROOT / "src" / "aqos"
TESTS_ROOT = PROJECT_ROOT / "tests"
OUTPUT_DIR = PROJECT_ROOT / "tmp"
JSON_OUTPUT = OUTPUT_DIR / "aqos_codebase_reality_audit.json"
MD_OUTPUT = OUTPUT_DIR / "aqos_codebase_reality_audit.md"

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "tmp",
    "dist",
    "build",
    ".idea",
    ".vscode",
}

LOCAL_TOP_LEVEL_MODULES = {"aqos", "tests", "scripts"}


@dataclass(frozen=True)
class PythonFileAudit:
    path: str
    area: str
    lines_total: int
    lines_code: int
    classes: list[str]
    functions: list[str]
    imports: list[str]
    external_imports: list[str]
    has_pass: bool
    has_ellipsis: bool
    has_not_implemented_error: bool
    has_todo: bool
    classification: str
    reason: str


def is_ignored_path(path: Path) -> bool:
    return any(part in IGNORED_DIRS for part in path.parts)


def iter_python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []

    files: list[Path] = []
    for path in root.rglob("*.py"):
        if not is_ignored_path(path):
            files.append(path)
    return sorted(files)


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def count_code_lines(text: str) -> int:
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def get_area(path: Path) -> str:
    if SRC_ROOT in path.parents:
        try:
            relative_parts = path.relative_to(SRC_ROOT).parts
            return relative_parts[0] if relative_parts else "aqos"
        except ValueError:
            return "src"
    if TESTS_ROOT in path.parents:
        return "tests"
    return "project"


def top_level_import_name(name: str) -> str:
    return name.split(".", 1)[0]


def is_external_import(name: str) -> bool:
    top_name = top_level_import_name(name)

    if top_name in LOCAL_TOP_LEVEL_MODULES:
        return False

    if top_name in sys.stdlib_module_names:
        return False

    return True


def parse_python_file(path: Path) -> tuple[ast.AST | None, str | None]:
    text = read_text(path)
    try:
        return ast.parse(text), None
    except SyntaxError as exc:
        return None, f"{exc.__class__.__name__}: {exc}"


def collect_imports(tree: ast.AST) -> list[str]:
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(top_level_import_name(alias.name))

        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                continue
            if node.module:
                imports.add(top_level_import_name(node.module))

    return sorted(imports)


def collect_classes_and_functions(tree: ast.AST) -> tuple[list[str], list[str]]:
    classes: list[str] = []
    functions: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)

    return sorted(classes), sorted(functions)


def has_ast_node(tree: ast.AST, node_type: type[ast.AST]) -> bool:
    return any(isinstance(node, node_type) for node in ast.walk(tree))


def has_not_implemented_error(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise):
            exc = node.exc
            if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                if exc.func.id == "NotImplementedError":
                    return True
            if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
                return True
    return False


def classify_file(
    path: Path,
    code_lines: int,
    classes: list[str],
    functions: list[str],
    has_pass_stmt: bool,
    has_ellipsis_expr: bool,
    has_not_implemented: bool,
    parse_error: str | None,
) -> tuple[str, str]:
    name = path.name
    text = read_text(path)

    if parse_error:
        return "parse_error", parse_error

    normalized_path = path.relative_to(PROJECT_ROOT).as_posix()

    if normalized_path.startswith("src/aqos/scripts/"):
        return "tooling_script", "Executable AQOS maintenance or local verification script."

    if normalized_path == "src/aqos/cli/__main__.py":
        return "cli_entrypoint", "Python module entrypoint for AQOS CLI."

    if code_lines == 0:
        return "empty", "No executable code lines."

    if code_lines == 0:
        return "empty", "No executable code lines."

    if name == "__init__.py" and code_lines <= 2:
        return "empty_init", "__init__.py has little or no public export logic."

    if name == "constants.py" and "Final[" in text and "__all__" in text:
        return "constants_module", "Contains shared constants and public exports."

    if (
        "ABC" in text
        and "abstractmethod" in text
        and classes
        and functions
        and code_lines >= 20
    ):
        return "valid_contract", "Contains abstract interface/contract definitions used by AQOS."

    if code_lines <= 3 and not classes and not functions:
        return "tiny_file", "Very small file with almost no executable logic."

    if classes or functions:
        placeholder_signals = sum(
            [
                bool(has_pass_stmt),
                bool(has_ellipsis_expr),
                bool(has_not_implemented),
            ]
        )

        if placeholder_signals >= 2 and code_lines <= 80:
            return "abstraction_or_placeholder", "Contains class/function definitions but mostly placeholder behavior."

        if has_not_implemented and code_lines <= 120:
            return "abstraction_or_contract", "Uses NotImplementedError and may be contract-heavy."

        if len(functions) + len(classes) >= 1 and code_lines >= 20:
            return "implemented", "Contains executable class/function logic."

    if has_pass_stmt or has_ellipsis_expr or has_not_implemented:
        return "needs_review", "Contains placeholder-style code."

    return "implemented", "Contains executable code."


def audit_python_file(path: Path) -> PythonFileAudit:
    text = read_text(path)
    tree, parse_error = parse_python_file(path)

    lines_total = len(text.splitlines())
    lines_code = count_code_lines(text)
    area = get_area(path)

    classes: list[str] = []
    functions: list[str] = []
    imports: list[str] = []
    external_imports: list[str] = []
    has_pass_stmt = False
    has_ellipsis_expr = "..." in text
    has_not_implemented = "NotImplementedError" in text

    if tree is not None:
        classes, functions = collect_classes_and_functions(tree)
        imports = collect_imports(tree)
        external_imports = sorted({item for item in imports if is_external_import(item)})
        has_pass_stmt = has_ast_node(tree, ast.Pass)
        has_ellipsis_expr = any(
            isinstance(node, ast.Constant) and node.value is Ellipsis
            for node in ast.walk(tree)
        ) or has_ellipsis_expr
        has_not_implemented = has_not_implemented_error(tree) or has_not_implemented

    has_todo = "TODO" in text or "todo" in text or "FIXME" in text or "fixme" in text

    classification, reason = classify_file(
        path=path,
        code_lines=lines_code,
        classes=classes,
        functions=functions,
        has_pass_stmt=has_pass_stmt,
        has_ellipsis_expr=has_ellipsis_expr,
        has_not_implemented=has_not_implemented,
        parse_error=parse_error,
    )

    return PythonFileAudit(
        path=relative(path),
        area=area,
        lines_total=lines_total,
        lines_code=lines_code,
        classes=classes,
        functions=functions,
        imports=imports,
        external_imports=external_imports,
        has_pass=has_pass_stmt,
        has_ellipsis=has_ellipsis_expr,
        has_not_implemented_error=has_not_implemented,
        has_todo=has_todo,
        classification=classification,
        reason=reason,
    )


def read_requirements() -> list[str]:
    candidates = [
        PROJECT_ROOT / "requirements.txt",
        PROJECT_ROOT / "requirements-dev.txt",
        PROJECT_ROOT / "pyproject.toml",
    ]

    existing: list[str] = []
    for path in candidates:
        if path.exists():
            existing.append(relative(path))

    return existing


def extract_declared_dependencies() -> list[str]:
    dependencies: set[str] = set()

    requirements_path = PROJECT_ROOT / "requirements.txt"
    if requirements_path.exists():
        for line in read_text(requirements_path).splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            package = (
                stripped.split("==")[0]
                .split(">=")[0]
                .split("<=")[0]
                .split("~=")[0]
                .split(">")[0]
                .split("<")[0]
                .strip()
            )
            if package:
                dependencies.add(package)

    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    if pyproject_path.exists():
        text = read_text(pyproject_path)
        for raw_line in text.splitlines():
            line = raw_line.strip().strip(",").strip('"').strip("'")
            if ">=" in line or "==" in line:
                package = (
                    line.split("==")[0]
                    .split(">=")[0]
                    .split("<=")[0]
                    .split("~=")[0]
                    .split(">")[0]
                    .split("<")[0]
                    .strip()
                    .strip('"')
                    .strip("'")
                )
                if package and not package.startswith("["):
                    dependencies.add(package)

    return sorted(dependencies)


def normalize_package_name(name: str) -> str:
    mapping = {
        "yaml": "PyYAML",
        "dotenv": "python-dotenv",
        "sklearn": "scikit-learn",
        "cv2": "opencv-python",
        "PIL": "Pillow",
    }
    return mapping.get(name, name)


def module_path_from_src_file(path_text: str) -> str | None:
    if not path_text.startswith("src/aqos/") or not path_text.endswith(".py"):
        return None

    module = path_text.removeprefix("src/").removesuffix(".py").replace("/", ".")
    if module.endswith(".__init__"):
        module = module.removesuffix(".__init__")

    return module


def find_possible_unused_modules(files: list[PythonFileAudit], all_python_text: str) -> list[dict[str, Any]]:
    possible_unused: list[dict[str, Any]] = []

    for item in files:
        module_path = module_path_from_src_file(item.path)
        if not module_path:
            continue

        if item.path.endswith("__init__.py"):
            continue

        if item.path.startswith("src/aqos/scripts/"):
            continue

        if item.path == "src/aqos/cli/__main__.py":
            continue

        if item.classification in {"tooling_script", "cli_entrypoint"}:
            continue

        short_import = module_path.replace("aqos.", "", 1)

        references = all_python_text.count(module_path) + all_python_text.count(short_import)

        if references <= 1:
            possible_unused.append(
                {
                    "path": item.path,
                    "module": module_path,
                    "classification": item.classification,
                    "reason": "Heuristic: module path appears rarely in project source/tests.",
                }
            )

    return possible_unused


def build_audit() -> dict[str, Any]:
    src_files = iter_python_files(SRC_ROOT)
    test_files = iter_python_files(TESTS_ROOT)
    script_files = iter_python_files(PROJECT_ROOT / "scripts")

    all_files = sorted(set(src_files + test_files + script_files))
    audited_files = [audit_python_file(path) for path in all_files]

    all_python_text = "\n".join(read_text(path) for path in all_files)

    classification_counts = Counter(item.classification for item in audited_files)
    area_counts = Counter(item.area for item in audited_files)

    file_name_counts = Counter(Path(item.path).name for item in audited_files)
    duplicate_file_names = {
        name: count for name, count in file_name_counts.items() if count > 1 and name != "__init__.py"
    }

    class_name_to_paths: dict[str, list[str]] = defaultdict(list)
    for item in audited_files:
        for class_name in item.classes:
            class_name_to_paths[class_name].append(item.path)

    duplicate_classes = {
        name: paths for name, paths in class_name_to_paths.items() if len(paths) > 1
    }

    external_imports = sorted(
        {
            external
            for item in audited_files
            for external in item.external_imports
        }
    )

    declared_dependencies = extract_declared_dependencies()
    declared_dependency_names = {normalize_package_name(item).lower() for item in declared_dependencies}
    inferred_dependency_names = {normalize_package_name(item).lower() for item in external_imports}

    possible_missing_dependencies = sorted(
        item
        for item in inferred_dependency_names
        if item not in declared_dependency_names
        and item not in {"pytest"}
    )

    files_with_placeholder_code = [
        asdict(item)
        for item in audited_files
        if item.has_pass or item.has_ellipsis or item.has_not_implemented_error
    ]

    possible_unused_modules = find_possible_unused_modules(audited_files, all_python_text)

    keep_files = [
        item.path for item in audited_files if item.classification == "implemented"
    ]

    review_files = [
    item.path
    for item in audited_files
    if item.classification
    in {
        "abstraction_or_placeholder",
        "abstraction_or_contract",
        "needs_review",
        "tiny_file",
        "parse_error",
    }
]

    empty_files = [
        item.path
        for item in audited_files
        if item.classification in {"empty", "empty_init"}
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(PROJECT_ROOT),
        "src_root_exists": SRC_ROOT.exists(),
        "tests_root_exists": TESTS_ROOT.exists(),
        "summary": {
            "total_python_files": len(audited_files),
            "src_python_files": len(src_files),
            "test_python_files": len(test_files),
            "script_python_files": len(script_files),
            "classification_counts": dict(sorted(classification_counts.items())),
            "area_counts": dict(sorted(area_counts.items())),
            "total_code_lines": sum(item.lines_code for item in audited_files),
            "total_classes": sum(len(item.classes) for item in audited_files),
            "total_functions": sum(len(item.functions) for item in audited_files),
        },
        "dependencies": {
            "dependency_files_found": read_requirements(),
            "declared_dependencies": declared_dependencies,
            "external_imports_detected": external_imports,
            "possible_missing_dependencies": possible_missing_dependencies,
        },
        "duplicates": {
            "duplicate_file_names": duplicate_file_names,
            "duplicate_class_names": duplicate_classes,
        },
        "action_lists": {
            "keep_or_use": keep_files,
            "review_or_upgrade": review_files,
            "empty_or_init_files": empty_files,
            "possible_unused_modules": possible_unused_modules,
        },
        "placeholder_code_files": files_with_placeholder_code,
        "files": [asdict(item) for item in audited_files],
    }


def write_json_report(audit: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")


def write_markdown_report(audit: dict[str, Any]) -> None:
    summary = audit["summary"]
    dependencies = audit["dependencies"]
    action_lists = audit["action_lists"]
    duplicates = audit["duplicates"]

    lines: list[str] = []
    lines.append("# AQOS Codebase Reality Audit")
    lines.append("")
    lines.append(f"Generated at: `{audit['generated_at']}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total Python files: `{summary['total_python_files']}`")
    lines.append(f"- Source Python files: `{summary['src_python_files']}`")
    lines.append(f"- Test Python files: `{summary['test_python_files']}`")
    lines.append(f"- Script Python files: `{summary['script_python_files']}`")
    lines.append(f"- Total code lines: `{summary['total_code_lines']}`")
    lines.append(f"- Total classes: `{summary['total_classes']}`")
    lines.append(f"- Total functions: `{summary['total_functions']}`")
    lines.append("")
    lines.append("## Classification Counts")
    lines.append("")
    for name, count in summary["classification_counts"].items():
        lines.append(f"- {name}: `{count}`")

    lines.append("")
    lines.append("## Dependencies")
    lines.append("")
    lines.append("Declared dependencies:")
    for item in dependencies["declared_dependencies"] or ["None detected"]:
        lines.append(f"- `{item}`")

    lines.append("")
    lines.append("External imports detected:")
    for item in dependencies["external_imports_detected"] or ["None detected"]:
        lines.append(f"- `{item}`")

    lines.append("")
    lines.append("Possible missing dependencies:")
    for item in dependencies["possible_missing_dependencies"] or ["None detected"]:
        lines.append(f"- `{item}`")

    lines.append("")
    lines.append("## Empty / Init Files")
    lines.append("")
    for item in action_lists["empty_or_init_files"][:100] or ["None detected"]:
        lines.append(f"- `{item}`")

    lines.append("")
    lines.append("## Review Or Upgrade Files")
    lines.append("")
    for item in action_lists["review_or_upgrade"][:150] or ["None detected"]:
        lines.append(f"- `{item}`")

    lines.append("")
    lines.append("## Possible Unused Modules")
    lines.append("")
    for item in action_lists["possible_unused_modules"][:150] or ["None detected"]:
        if isinstance(item, dict):
            lines.append(f"- `{item['path']}` — {item['reason']}")
        else:
            lines.append(f"- `{item}`")

    lines.append("")
    lines.append("## Duplicate File Names")
    lines.append("")
    duplicate_file_names = duplicates["duplicate_file_names"]
    if duplicate_file_names:
        for name, count in duplicate_file_names.items():
            lines.append(f"- `{name}` appears `{count}` times")
    else:
        lines.append("- None detected")

    lines.append("")
    lines.append("## Duplicate Class Names")
    lines.append("")
    duplicate_class_names = duplicates["duplicate_class_names"]
    if duplicate_class_names:
        for name, paths in duplicate_class_names.items():
            lines.append(f"- `{name}`")
            for path in paths:
                lines.append(f"  - `{path}`")
    else:
        lines.append("- None detected")

    lines.append("")
    lines.append("## Next Action")
    lines.append("")
    lines.append("Use this audit to decide which files should be kept, upgraded, connected, or removed before adding the next ML training modules.")

    MD_OUTPUT.write_text("\n".join(lines), encoding="utf-8")


def print_console_summary(audit: dict[str, Any]) -> None:
    summary = audit["summary"]
    action_lists = audit["action_lists"]
    dependencies = audit["dependencies"]

    print("AQOS Codebase Reality Audit")
    print("=" * 32)
    print(f"Total Python files: {summary['total_python_files']}")
    print(f"Source Python files: {summary['src_python_files']}")
    print(f"Test Python files: {summary['test_python_files']}")
    print(f"Total code lines: {summary['total_code_lines']}")
    print("")
    print("Classification counts:")
    for name, count in summary["classification_counts"].items():
        print(f"  - {name}: {count}")

    print("")
    print(f"Empty/init files: {len(action_lists['empty_or_init_files'])}")
    print(f"Review/upgrade files: {len(action_lists['review_or_upgrade'])}")
    print(f"Possible unused modules: {len(action_lists['possible_unused_modules'])}")
    print(f"Possible missing dependencies: {len(dependencies['possible_missing_dependencies'])}")

    print("")
    print(f"JSON report: {JSON_OUTPUT.relative_to(PROJECT_ROOT)}")
    print(f"Markdown report: {MD_OUTPUT.relative_to(PROJECT_ROOT)}")


def main() -> int:
    if not SRC_ROOT.exists():
        print(f"ERROR: AQOS source root not found: {SRC_ROOT}")
        return 1

    audit = build_audit()
    write_json_report(audit)
    write_markdown_report(audit)
    print_console_summary(audit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())