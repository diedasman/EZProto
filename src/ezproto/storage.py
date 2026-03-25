"""JSON-backed storage for user profiles and app state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

USERS_DIRECTORY_NAME = "users"
APP_STATE_FILE_NAME = "app_state.json"
MAX_LOG_ENTRIES = 100
DEFAULT_THEME_NAME = "textual-dark"


@dataclass(slots=True)
class UserProfile:
    """A saved EZProto user profile."""

    name: str
    default_output_directory: str
    theme: str = DEFAULT_THEME_NAME
    last_generated_board_name: str = ""
    last_generated_board_details: dict[str, Any] = field(default_factory=dict)
    boards: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.name = self._clean_name(self.name)
        self.default_output_directory = self._clean_output_directory(
            self.default_output_directory
        )
        self.theme = (self.theme or DEFAULT_THEME_NAME).strip() or DEFAULT_THEME_NAME
        self.last_generated_board_name = self._clean_board_name(
            self.last_generated_board_name
        )
        self.last_generated_board_details = _clean_details(self.last_generated_board_details)
        self.boards = _clean_boards(self.boards)

        if not self.name:
            raise ValueError("User name is required.")
        if not self.default_output_directory:
            raise ValueError("Default output directory is required.")

    @property
    def slug(self) -> str:
        return slugify(self.name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "default_output_directory": self.default_output_directory,
            "theme": self.theme,
            "last_generated_board_name": self.last_generated_board_name,
            "last_generated_board_details": self.last_generated_board_details,
            "boards": self.boards,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserProfile:
        return cls(
            name=str(data.get("name", "")),
            default_output_directory=str(data.get("default_output_directory", "")),
            theme=str(data.get("theme", DEFAULT_THEME_NAME)),
            last_generated_board_name=str(data.get("last_generated_board_name", "")),
            last_generated_board_details=_clean_details(
                data.get("last_generated_board_details", {})
            ),
            boards=_clean_boards(data.get("boards", {})),
        )

    @staticmethod
    def _clean_name(value: str) -> str:
        return (value or "").strip()

    @staticmethod
    def _clean_output_directory(value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            return ""
        return str(Path(cleaned).expanduser())

    @staticmethod
    def _clean_board_name(value: str) -> str:
        return (value or "").strip()


@dataclass(slots=True)
class AppState:
    """Minimal persisted application state and event log."""

    last_user_slug: str = ""
    last_board_name: str = ""
    last_board_details: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_user_slug": self.last_user_slug,
            "last_board_name": self.last_board_name,
            "last_board_details": self.last_board_details,
            "events": self.events[-MAX_LOG_ENTRIES:],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppState:
        raw_events = data.get("events", [])
        events: list[dict[str, Any]] = []

        if isinstance(raw_events, list):
            for item in raw_events[-MAX_LOG_ENTRIES:]:
                if not isinstance(item, dict):
                    continue
                events.append(
                    {
                        "timestamp": str(item.get("timestamp", "")),
                        "user_slug": str(item.get("user_slug", "")),
                        "message": str(item.get("message", "")),
                        "board_name": str(item.get("board_name", "")),
                        "details": _clean_details(item.get("details", {})),
                    }
                )

        return cls(
            last_user_slug=str(data.get("last_user_slug", "")),
            last_board_name=str(data.get("last_board_name", "")),
            last_board_details=_clean_details(data.get("last_board_details", {})),
            events=events,
        )


def users_directory(base_path: Path | str = ".") -> Path:
    directory = Path(base_path).expanduser() / USERS_DIRECTORY_NAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def app_state_path(base_path: Path | str = ".") -> Path:
    return Path(base_path).expanduser() / APP_STATE_FILE_NAME


def list_user_profiles(base_path: Path | str = ".") -> list[UserProfile]:
    profiles: list[UserProfile] = []
    for path in users_directory(base_path).glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            profiles.append(UserProfile.from_dict(data))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return sorted(profiles, key=lambda profile: profile.name.lower())


def load_user_profile(user_slug: str, base_path: Path | str = ".") -> UserProfile | None:
    path = users_directory(base_path) / f"{user_slug}.json"
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    try:
        return UserProfile.from_dict(data)
    except ValueError:
        return None


def save_user_profile(profile: UserProfile, base_path: Path | str = ".") -> Path:
    path = users_directory(base_path) / f"{profile.slug}.json"
    path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
    return path.resolve()


def load_app_state(base_path: Path | str = ".") -> AppState:
    path = app_state_path(base_path)
    if not path.exists():
        return AppState()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppState()

    if not isinstance(data, dict):
        return AppState()

    return AppState.from_dict(data)


def save_app_state(state: AppState, base_path: Path | str = ".") -> Path:
    path = app_state_path(base_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
    return path.resolve()


def update_app_state(
    base_path: Path | str = ".",
    *,
    last_user_slug: str | None = None,
    message: str | None = None,
    user_slug: str | None = None,
    board_name: str | None = None,
    details: dict[str, Any] | None = None,
) -> AppState:
    state = load_app_state(base_path)

    if last_user_slug is not None:
        state.last_user_slug = last_user_slug
    if board_name is not None:
        state.last_board_name = str(board_name)
    if details is not None:
        state.last_board_details = _clean_details(details)

    if message:
        state.events.append(
            {
                "timestamp": _timestamp(),
                "user_slug": user_slug or last_user_slug or "",
                "message": message,
                "board_name": board_name or "",
                "details": _clean_details(details or {}),
            }
        )
        state.events = state.events[-MAX_LOG_ENTRIES:]

    save_app_state(state, base_path)
    return state


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower())
    return cleaned.strip("_") or "user"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def current_timestamp() -> str:
    return _timestamp()


def _clean_boards(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}

    cleaned: dict[str, dict[str, Any]] = {}
    for board_name, details in value.items():
        cleaned[str(board_name)] = _clean_details(details)
    return cleaned


def _clean_details(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, (str, int, float, bool)) or item is None:
            cleaned[str(key)] = item
        elif isinstance(item, list):
            cleaned[str(key)] = [
                sub_item
                for sub_item in item
                if isinstance(sub_item, (str, int, float, bool)) or sub_item is None
            ]
        elif isinstance(item, dict):
            cleaned[str(key)] = _clean_details(item)
    return cleaned
