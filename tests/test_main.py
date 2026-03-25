"""Tests for the EZProto CLI entry point."""

from __future__ import annotations

import io
import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ezproto.__main__ import main, run_update_command
from ezproto.updater import UpdateError, UpdateResult


class MainEntryPointTests(unittest.TestCase):
    def test_main_runs_update_subcommand(self) -> None:
        with mock.patch("ezproto.__main__.run_update_command", return_value=0) as runner:
            exit_code = main(["update"])

        self.assertEqual(exit_code, 0)
        runner.assert_called_once_with()

    def test_main_runs_app_when_no_subcommand_is_given(self) -> None:
        app_instance = mock.Mock()

        with mock.patch("ezproto.app.ProtoboardApp", return_value=app_instance) as app_class:
            exit_code = main([])

        self.assertEqual(exit_code, 0)
        app_class.assert_called_once_with()
        app_instance.run.assert_called_once_with()


class RunUpdateCommandTests(unittest.TestCase):
    def test_run_update_command_reports_success(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch(
            "ezproto.__main__.update_installation",
            return_value=UpdateResult(
                repository_root=Path("C:/EZProto"),
                updated=True,
                previous_revision="1234567",
                current_revision="89abcde",
            ),
        ):
            exit_code = run_update_command(stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("EZProto updated successfully.", stdout.getvalue())

    def test_run_update_command_reports_failures(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch(
            "ezproto.__main__.update_installation",
            side_effect=UpdateError("boom"),
        ):
            exit_code = run_update_command(stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("EZProto update failed: boom", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
