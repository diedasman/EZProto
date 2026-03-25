"""Application entry point."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence, TextIO

from ezproto import __version__
from ezproto.updater import UpdateError, update_installation


def build_parser() -> argparse.ArgumentParser:
    """Create the EZProto command-line parser."""

    parser = argparse.ArgumentParser(prog="ezproto")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "update",
        help="Update EZProto from its installed git checkout",
    )
    return parser


def run_update_command(
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Update EZProto and report the result to the terminal."""

    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    try:
        result = update_installation()
    except UpdateError as error:
        print(f"EZProto update failed: {error}", file=stderr)
        return 1

    if result.updated:
        print(
            "EZProto updated successfully.\n"
            f"Repository: {result.repository_root}\n"
            f"Revision: {result.previous_revision[:7]} -> {result.current_revision[:7]}",
            file=stdout,
        )
        return 0

    print(
        "EZProto is already up to date.\n"
        f"Repository: {result.repository_root}\n"
        f"Revision: {result.current_revision[:7]}",
        file=stdout,
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Textual protoboard generator or a CLI subcommand."""

    args = build_parser().parse_args(argv)
    if args.command == "update":
        return run_update_command()

    from ezproto.app import ProtoboardApp

    ProtoboardApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
