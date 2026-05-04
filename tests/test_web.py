"""Tests for browser-mode launch helpers."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ezproto.web import build_web_command


class WebCommandTests(unittest.TestCase):
    def test_build_web_command_uses_module_for_python_installs(self) -> None:
        self.assertEqual(
            build_web_command(),
            subprocess.list2cmdline([sys.executable, "-m", "ezproto"]),
        )

    def test_build_web_command_uses_executable_for_frozen_app(self) -> None:
        with mock.patch.object(sys, "frozen", True, create=True):
            self.assertEqual(
                build_web_command(),
                subprocess.list2cmdline([sys.executable]),
            )


if __name__ == "__main__":
    unittest.main()
