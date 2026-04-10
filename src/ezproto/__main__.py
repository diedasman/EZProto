"""Application entry point."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence, TextIO

from ezproto import __version__
from ezproto.updater import UpdateError, update_installation
from ezproto.web import DEFAULT_WEB_HOST, DEFAULT_WEB_PORT, run_web_app


def parse_port(value: str) -> int:
    """Validate a TCP port argument for browser mode."""

    try:
        port = int(value)
    except ValueError as exc:  # pragma: no cover - argparse formatting path
        raise argparse.ArgumentTypeError("Port must be an integer.") from exc

    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 1 and 65535.")
    return port


def build_parser() -> argparse.ArgumentParser:
    """Create the EZProto command-line parser."""

    parser = argparse.ArgumentParser(prog="ezproto")
    parser.add_argument(
        "--web",
        action="store_true",
        help="Serve the Textual app in a local browser instead of the terminal",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_WEB_HOST,
        help=f"Host to bind in web mode (default: {DEFAULT_WEB_HOST})",
    )
    parser.add_argument(
        "--port",
        type=parse_port,
        default=DEFAULT_WEB_PORT,
        help=f"Port to bind in web mode (default: {DEFAULT_WEB_PORT})",
    )
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

    if args.web:
        run_web_app(host=args.host, port=args.port)
        return 0

    from ezproto.app import ProtoboardApp

    ProtoboardApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
