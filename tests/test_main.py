import io
import os
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import importlib.util

# src/main.py, not the launcher main.py at the project root
_spec = importlib.util.spec_from_file_location(
    "game_main", os.path.join(os.path.dirname(__file__), "..", "src", "main.py")
)
main = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(main)


class AndroidLogFile(io.IOBase):
    """What python-for-android puts in sys.stdout / sys.stderr: it writes to
    the Android log and has no file descriptor."""

    def writable(self):
        return True

    def write(self, text):
        return len(text)


class StartupTests(unittest.TestCase):
    def test_crash_traces_are_skipped_on_android_instead_of_crashing(self):
        with patch.object(sys, "stderr", AndroidLogFile()):
            with patch.object(main.faulthandler, "enable") as enable:
                self.assertFalse(main.enable_crash_traces())
        enable.assert_not_called()

    def test_crash_traces_are_on_with_a_real_terminal(self):
        with patch.object(main.faulthandler, "enable") as enable:
            with patch.object(sys, "stderr", sys.__stderr__):
                self.assertTrue(main.enable_crash_traces())
        enable.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()


class DesktopBuildTests(unittest.TestCase):
    """What the Windows build (PyInstaller, tools/build_desktop.py) relies on."""

    def test_the_game_folder_is_pyinstallers_data_folder_once_packaged(self):
        from utils.config import Config
        with patch.object(sys, "frozen", True, create=True), \
                patch.object(sys, "_MEIPASS", "/somewhere/_internal", create=True):
            self.assertEqual(Config.root_dir(), "/somewhere/_internal")
        project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertEqual(os.path.realpath(Config.root_dir()), os.path.realpath(project))

    def test_the_config_is_found_from_any_folder(self):
        from utils.config import Config
        here = os.getcwd()
        try:
            os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            Config.init()
        finally:
            os.chdir(here)
        self.assertEqual(Config.WIDTH, 1200)
        self.assertTrue(Config.CAPTION)

    def test_smoke_test_mode_plays_a_fight_and_quits(self):
        import subprocess
        project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = dict(os.environ, DBZ_SMOKE_TEST="arcade", DBZ_SMOKE_TEST_SECONDS="2",
                   SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
        result = subprocess.run([sys.executable, os.path.join(project, "src", "main.py")],
                                cwd=os.path.dirname(project), env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertIn("smoke test passed: story scene", result.stdout)


class IosTests(unittest.TestCase):
    """What the iOS app (kivy-ios, ios/) relies on in the game."""

    def test_the_game_knows_it_runs_on_ios(self):
        import game
        with patch.dict(os.environ, {"KIVY_BUILD": "ios"}):
            self.assertTrue(game.is_ios())
            self.assertTrue(game.is_mobile())
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("KIVY_BUILD", None)
            os.environ.pop("ANDROID_ARGUMENT", None)
            self.assertFalse(game.is_ios())
            self.assertFalse(game.is_mobile())

    def test_settings_go_to_the_apps_documents_folder(self):
        import settings
        from utils.config import Config
        Config.init()
        home = os.path.join(os.sep, "var", "mobile", "Containers", "Data", "Application", "X")
        with patch.dict(os.environ, {"KIVY_BUILD": "ios"}), \
                patch("settings.os.path.expanduser", return_value=home):
            os.environ.pop("ANDROID_PRIVATE", None)
            self.assertEqual(settings.settings_path(), os.path.join(home, "Documents", "user_settings.json"))

    def test_ios_is_landscape_only(self):
        """Set before SDL starts (pygame.init), which is when SDL reads it."""
        import game

        class Started(Exception):
            pass

        def init():
            seen.append(os.environ.get("SDL_IOS_ORIENTATIONS"))
            raise Started

        seen = []
        with patch.dict(os.environ, {"KIVY_BUILD": "ios"}):
            os.environ.pop("SDL_IOS_ORIENTATIONS", None)
            with patch("game.pygame.init", side_effect=init), self.assertRaises(Started):
                game.Game((1200, 540), "test", fullscreen=False)
        self.assertEqual(seen, ["LandscapeLeft LandscapeRight"])

    def test_the_ios_recipe_names_pygames_modules_for_kivy_ios(self):
        project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(project, "ios", "recipes", "pygame", "__init__.py")) as file:
            source = file.read()
        self.assertIn("PyInit_pygame_##mod_name", source)
        self.assertIn('version = "2.6.1"', source)
        with open(os.path.join(project, "requirements.txt")) as file:
            self.assertIn("pygame==2.6.1", file.read())  # the same pygame as on desktop

