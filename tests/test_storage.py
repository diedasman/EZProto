"""Storage tests for EZProto user profiles and app state."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ezproto.storage import (
    DEFAULT_THEME_NAME,
    UserProfile,
    list_user_profiles,
    load_app_state,
    load_user_profile,
    save_user_profile,
    update_app_state,
)


class UserProfileStorageTests(unittest.TestCase):
    def test_user_profiles_round_trip_as_json_files(self) -> None:
        profile = UserProfile(
            name="Dirk User",
            default_output_directory="C:/Boards",
            theme="gruvbox",
            last_generated_board_name="Demo Board",
            last_generated_board_details={
                "summary": "3 x 2 grid",
                "output_file": "C:/Boards/Demo Board/Demo_Board.kicad_pcb",
            },
            boards={
                "Demo Board": {
                    "summary": "3 x 2 grid",
                    "output_file": "C:/Boards/Demo Board/Demo_Board.kicad_pcb",
                }
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            saved_path = save_user_profile(profile, temp_dir)

            self.assertTrue(saved_path.exists())
            self.assertEqual(saved_path.name, "dirk_user.json")

            loaded = load_user_profile("dirk_user", temp_dir)

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.name, "Dirk User")
            self.assertEqual(loaded.default_output_directory, "C:\\Boards")
            self.assertEqual(loaded.theme, "gruvbox")
            self.assertEqual(loaded.last_generated_board_name, "Demo Board")
            self.assertIn("Demo Board", loaded.boards)
            self.assertEqual(
                loaded.last_generated_board_details["summary"],
                "3 x 2 grid",
            )

    def test_list_user_profiles_ignores_invalid_json_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            save_user_profile(
                UserProfile(
                    name="Beta User",
                    default_output_directory="C:/Boards",
                    theme=DEFAULT_THEME_NAME,
                ),
                temp_dir,
            )
            invalid_path = Path(temp_dir) / "users" / "broken.json"
            invalid_path.write_text("{not-valid-json", encoding="utf-8")

            profiles = list_user_profiles(temp_dir)

            self.assertEqual([profile.name for profile in profiles], ["Beta User"])


class AppStateTests(unittest.TestCase):
    def test_update_app_state_tracks_last_user_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state = update_app_state(
                temp_dir,
                last_user_slug="dirk_user",
                message="Created user.",
                user_slug="dirk_user",
                board_name="Demo Board",
                details={
                    "summary": "3 x 2 grid",
                    "output_file": "C:/Boards/Demo Board/Demo_Board.kicad_pcb",
                },
            )

            self.assertEqual(state.last_user_slug, "dirk_user")
            self.assertEqual(state.last_board_name, "Demo Board")
            self.assertEqual(state.last_board_details["summary"], "3 x 2 grid")
            self.assertEqual(len(state.events), 1)
            self.assertEqual(state.events[0]["message"], "Created user.")
            self.assertEqual(state.events[0]["board_name"], "Demo Board")

            loaded_state = load_app_state(temp_dir)
            self.assertEqual(loaded_state.last_user_slug, "dirk_user")
            self.assertEqual(loaded_state.events[0]["user_slug"], "dirk_user")
            self.assertEqual(loaded_state.last_board_name, "Demo Board")

            raw = json.loads((Path(temp_dir) / "app_state.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["last_user_slug"], "dirk_user")
            self.assertEqual(raw["last_board_name"], "Demo Board")


if __name__ == "__main__":
    unittest.main()
