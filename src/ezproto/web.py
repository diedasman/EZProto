"""Browser-mode launch helpers for EZProto."""

from __future__ import annotations

import subprocess
import sys
import threading
import webbrowser

DEFAULT_WEB_HOST = "localhost"
DEFAULT_WEB_PORT = 8000


def build_web_command() -> str:
    """Build the command textual-serve uses to launch the app subprocess."""

    return subprocess.list2cmdline([sys.executable, "-m", "ezproto"])


def build_browser_url(host: str, port: int) -> str:
    """Build the user-facing browser URL for the served app."""

    browse_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    return f"http://{browse_host}:{port}/"


def run_web_app(
    host: str = DEFAULT_WEB_HOST,
    port: int = DEFAULT_WEB_PORT,
    *,
    open_browser: bool = True,
) -> None:
    """Serve EZProto in a browser with textual-serve."""

    try:
        from textual_serve.server import Server
    except ImportError as exc:  # pragma: no cover - depends on installed extras
        raise RuntimeError(
            "Browser mode requires `textual-serve`. Reinstall EZProto dependencies and try again."
        ) from exc

    command = build_web_command()
    launch_url = build_browser_url(host, port)

    print(f"EZProto Web serving the Textual app on http://{host}:{port}/")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(launch_url)).start()
        print(f"Opening {launch_url}")

    Server(command=command, host=host, port=port, title="EZProto").serve()
