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
