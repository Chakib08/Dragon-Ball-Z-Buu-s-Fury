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
