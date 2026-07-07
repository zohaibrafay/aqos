"""
AQOS CLI executable entrypoint.

Allows running:

python -m aqos.cli version
python -m aqos.cli health
python -m aqos.cli run
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version

from aqos.api import API_SERVICE_NAME, API_VERSION
from aqos.cli.health import cli_api_health


def get_package_version() -> str:
    """Return installed AQOS package version."""
    try:
        return version("aqos")
    except PackageNotFoundError:
        return "0.1.0"


def add_output_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared output formatting arguments."""
    parser.add_argument(
        "--format",
        choices=[
            "text",
            "json",
            "pretty-json",
        ],
        default="text",
        help="Output format.",
    )

    parser.add_argument(
        "--metadata",
        action="store_true",
        help="Include response metadata.",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build AQOS CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="aqos",
        description="AQOS command-line interface.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
    )

    subparsers.add_parser(
        "version",
        help="Show AQOS CLI version.",
    )

    health_parser = subparsers.add_parser(
        "health",
        help="Show AQOS CLI health.",
    )
    add_output_arguments(health_parser)

    subparsers.add_parser(
        "run",
        help="Run AQOS CLI placeholder command.",
    )

    return parser


def handle_version() -> int:
    """Handle version command."""
    print(f"AQOS CLI version: {get_package_version()}")
    return 0


def handle_health(args: argparse.Namespace) -> int:
    """Handle health command."""
    cli_output = cli_api_health(
        output_format=args.format,
        include_metadata=args.metadata,
    )

    if args.format == "text":
        print("AQOS CLI health: healthy")
        print(f"service: {API_SERVICE_NAME}")
        print(f"api_version: {API_VERSION}")
        print("")
        print(cli_output.output)
    else:
        print(cli_output.output)

    return cli_output.exit_code


def handle_run() -> int:
    """Handle run command."""
    print("AQOS CLI run completed.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run AQOS CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        return handle_version()

    if args.command == "health":
        return handle_health(args)

    if args.command == "run":
        return handle_run()

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())