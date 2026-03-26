"""Tests for EZProto's self-update helpers."""

from __future__ import annotations

import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ezproto.updater import UpdateError, UpdateResult, find_repository_root, update_installation


class UpdateInstallationTests(unittest.TestCase):
    def test_update_refuses_dirty_checkout(self) -> None:
        repository_root = Path("C:/EZProto")

        with mock.patch("ezproto.updater._require_git", return_value="git"):
            with mock.patch(
                "ezproto.updater.find_repository_root",
                return_value=repository_root,
            ):
                with mock.patch(
                    "ezproto.updater._git_output",
                    return_value=" M src/ezproto/app.py",
                ):
                    with self.assertRaisesRegex(UpdateError, "local changes"):
                        update_installation()

    def test_update_skips_reinstall_when_repo_is_current(self) -> None:
        repository_root = Path("C:/EZProto")

        with mock.patch("ezproto.updater._require_git", return_value="git"):
            with mock.patch(
                "ezproto.updater.find_repository_root",
                return_value=repository_root,
            ):
                with mock.patch(
                    "ezproto.updater._git_output",
                    side_effect=["", "", "abc1234", "abc1234"],
                ):
                    with mock.patch(
                        "ezproto.updater._run_command",
                        return_value="Already up to date.",
                    ) as run_command:
                        result = update_installation()

        self.assertEqual(
            result,
            UpdateResult(
                repository_root=repository_root,
                updated=False,
                previous_revision="abc1234",
                current_revision="abc1234",
            ),
        )
        run_command.assert_called_once_with(
            ["git", "-C", str(repository_root), "pull", "--ff-only"],
            description="download the latest EZProto changes",
        )

    def test_update_ignores_untracked_user_output(self) -> None:
        repository_root = Path("C:/EZProto")

        with mock.patch("ezproto.updater._require_git", return_value="git"):
            with mock.patch(
                "ezproto.updater.find_repository_root",
                return_value=repository_root,
            ):
                with mock.patch(
                    "ezproto.updater._git_output",
                    side_effect=[
                        "?? Demo Board/\n?? output/test1/\n",
                        "?? Demo Board/\n?? output/test1/\n",
                        "abc1234",
                        "abc1234",
                    ],
                ):
                    with mock.patch(
                        "ezproto.updater._run_command",
                        return_value="Already up to date.",
                    ) as run_command:
                        result = update_installation()

        self.assertFalse(result.updated)
        self.assertEqual(result.previous_revision, "abc1234")
        self.assertEqual(result.current_revision, "abc1234")
        run_command.assert_called_once_with(
            ["git", "-C", str(repository_root), "pull", "--ff-only"],
            description="download the latest EZProto changes",
        )

    def test_update_restores_generated_metadata_before_pulling(self) -> None:
        repository_root = Path("C:/EZProto")

        with mock.patch("ezproto.updater._require_git", return_value="git"):
            with mock.patch(
                "ezproto.updater.find_repository_root",
                return_value=repository_root,
            ):
                with mock.patch(
                    "ezproto.updater._git_output",
                    side_effect=[
                        " M src/ezproto.egg-info/SOURCES.txt\n M src/ezproto.egg-info/requires.txt\n",
                        "",
                        "abc1234",
                        "abc1234",
                    ],
                ):
                    with mock.patch(
                        "ezproto.updater._run_command",
                        return_value="Already up to date.",
                    ) as run_command:
                        result = update_installation()

        self.assertFalse(result.updated)
        self.assertEqual(run_command.call_count, 2)
        self.assertEqual(
            run_command.call_args_list[0],
            mock.call(
                [
                    "git",
                    "-C",
                    str(repository_root),
                    "restore",
                    "--source=HEAD",
                    "--staged",
                    "--worktree",
                    "--",
                    "src/ezproto.egg-info/SOURCES.txt",
                    "src/ezproto.egg-info/requires.txt",
                ],
                description="reset generated packaging metadata",
            ),
        )
        self.assertEqual(
            run_command.call_args_list[1],
            mock.call(
                ["git", "-C", str(repository_root), "pull", "--ff-only"],
                description="download the latest EZProto changes",
            ),
        )

    def test_update_reinstalls_after_new_commit_is_pulled(self) -> None:
        repository_root = Path("C:/EZProto")

        with mock.patch("ezproto.updater._require_git", return_value="git"):
            with mock.patch(
                "ezproto.updater.find_repository_root",
                return_value=repository_root,
            ):
                with mock.patch(
                    "ezproto.updater._git_output",
                    side_effect=["", "", "oldrev1", "newrev2"],
                ):
                    with mock.patch(
                        "ezproto.updater._run_command",
                        return_value="",
                    ) as run_command:
                        result = update_installation()

        self.assertTrue(result.updated)
        self.assertEqual(result.previous_revision, "oldrev1")
        self.assertEqual(result.current_revision, "newrev2")
        self.assertEqual(run_command.call_count, 2)
        self.assertEqual(
            run_command.call_args_list[0],
            mock.call(
                ["git", "-C", str(repository_root), "pull", "--ff-only"],
                description="download the latest EZProto changes",
            ),
        )
        self.assertEqual(
            run_command.call_args_list[1],
            mock.call(
                [sys.executable, "-m", "pip", "install", "-e", str(repository_root)],
                description="refresh the EZProto installation",
            ),
        )


class FindRepositoryRootTests(unittest.TestCase):
    def test_find_repository_root_reports_non_git_installs_cleanly(self) -> None:
        with mock.patch("ezproto.updater._require_git", return_value="git"):
            with mock.patch(
                "ezproto.updater._run_command",
                side_effect=UpdateError("not a git checkout"),
            ):
                with self.assertRaisesRegex(
                    UpdateError,
                    "Automatic updates are only available",
                ):
                    find_repository_root()


if __name__ == "__main__":
    unittest.main()
