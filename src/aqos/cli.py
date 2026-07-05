"""
AQOS Command Line Interface.
"""

from __future__ import annotations

import argparse

from aqos.core import Bootstrap, HealthCheck
from aqos.version import Version


def main() -> None:
    parser = argparse.ArgumentParser(prog="aqos")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("version", help="Show AQOS version")
    subparsers.add_parser("health", help="Run health check")
    subparsers.add_parser("run", help="Start AQOS")

    args = parser.parse_args()

    if args.command == "version":
        print(Version.get_version())
        return

    bootstrap = Bootstrap()
    bootstrap.initialize()

    if args.command == "health":
        health = HealthCheck(bootstrap)
        print(health.status())

    elif args.command == "run":
        print("AQOS is running.")

    bootstrap.shutdown()


if __name__ == "__main__":
    main()