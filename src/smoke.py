"""Progress notes of a smoke test (DBZ_SMOKE_TEST, see main.py), for the
build pipelines: printed, and on iOS also written to the app's Documents
folder (smoke_test.log), where the pipeline reads them from the simulator
(an app's output does not always reach the console).

Nothing here imports pygame: the first note is written before the game's
code (and pygame) is imported, so a failing import shows too.
"""

import os
import time
import traceback

LOG_ENV = "DBZ_SMOKE_TEST_LOG"


def active():
    return bool(os.environ.get("DBZ_SMOKE_TEST"))


def log_path():
    """Where the notes go: DBZ_SMOKE_TEST_LOG, else on iOS the app's
    Documents folder, else nowhere (printed only)."""
    if os.environ.get(LOG_ENV):
        return os.environ[LOG_ENV]
    if os.environ.get("KIVY_BUILD") == "ios":
        return os.path.join(os.path.expanduser("~"), "Documents", "smoke_test.log")
    return None


def report(message):
    if not active():
        return
    print(message, flush=True)
    path = log_path()
    if path is None:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as file:
            file.write(f"{time.strftime('%H:%M:%S')} {message}\n")
    except OSError:
        pass


def report_error():
    """The exception being handled, with its traceback."""
    report("error:\n" + traceback.format_exc())
