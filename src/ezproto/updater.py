"""Helpers for updating an editable EZProto installation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Sequence


class UpdateError(RuntimeError):
    """Raised when EZProto cannot update itself safely."""


@dataclass(slots=True)
class UpdateResult:
    """Outcome of an EZProto update attempt."""

    repository_root: Path
    updated: bool
    previous_revision: str
    current_revision: str


def update_installation() -> UpdateResult:
    """Update EZProto from the git checkout backing the current install."""

    git_executable = _require_git()
    repository_root = find_repository_root(git_executable)
    _ensure_clean_checkout(git_executable, repository_root)

    previous_revision = _git_output(
        git_executable,
        repository_root,
        "rev-parse",
        "HEAD",
    ).strip()

    _run_command(
        [git_executable, "-C", str(repository_root), "pull", "--ff-only"],
        description="download the latest EZProto changes",
    )

    current_revision = _git_output(
        git_executable,
        repository_root,
        "rev-parse",
        "HEAD",
    ).strip()

    if current_revision == previous_revision:
        return UpdateResult(
            repository_root=repository_root,
            updated=False,
            previous_revision=previous_revision,
            current_revision=current_revision,
        )

    _run_command(
        [sys.executable, "-m", "pip", "install", "-e", str(repository_root)],
        description="refresh the EZProto installation",
    )

    return UpdateResult(
        repository_root=repository_root,
        updated=True,
        previous_revision=previous_revision,
        current_revision=current_revision,
    )


def find_repository_root(git_executable: str | None = None) -> Path:
    """Locate the git checkout that backs the installed EZProto package."""

    git_executable = git_executable or _require_git()
    package_directory = Path(__file__).resolve().parent

    try:
        root = _run_command(
            [
                git_executable,
                "-C",
                str(package_directory),
                "rev-parse",
                "--show-toplevel",
            ],
            description="locate the EZProto git checkout",
        ).strip()
    except UpdateError as error:
        raise UpdateError(
            "Automatic updates are only available for EZProto installs that come "
            "from a git checkout. Reinstall from the repository, then run "
            "`ezproto update`."
        ) from error

    repository_root = Path(root)
    if not (repository_root / "pyproject.toml").exists():
        raise UpdateError(
            f"Found a git checkout at {repository_root}, but it does not look like EZProto."
        )

    return repository_root


def _require_git() -> str:
    git_executable = shutil.which("git")
    if git_executable is None:
        raise UpdateError(
            "Git is required to update EZProto. Install Git and try `ezproto update` again."
        )
    return git_executable


def _ensure_clean_checkout(git_executable: str, repository_root: Path) -> None:
    status_output = _git_output(
        git_executable,
        repository_root,
        "status",
        "--porcelain",
    )
    tracked_changes = [
        line
        for line in status_output.splitlines()
        if line.strip() and not line.startswith("??")
    ]
    if tracked_changes:
        raise UpdateError(
            "Update cancelled because the EZProto checkout has local changes. "
            "Commit or stash them before running `ezproto update`."
        )


def _git_output(git_executable: str, repository_root: Path, *args: str) -> str:
    return _run_command(
        [git_executable, "-C", str(repository_root), *args],
        description="inspect the EZProto git checkout",
    )


def _run_command(command: Sequence[str], *, description: str) -> str:
    try:
        completed = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise UpdateError(f"Unable to {description}: {error}") from error

    if completed.returncode == 0:
        return completed.stdout

    message = (completed.stderr or completed.stdout).strip() or "No output."
    raise UpdateError(f"Unable to {description}: {message}")
