#!/usr/bin/env python3
"""Copy what the iOS app runs into one folder, for `toolchain create`.

kivy-ios copies that folder into the app as "YourApp" and runs its main.py:
the project's launcher main.py (it puts src/ on the path), the code, and
Config/, Graphics/ (with the downloaded sprite sheets) and Sounds/.

    python3 ios/stage_app.py <folder>
"""

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDERS = ("src", "Config", "Graphics", "Sounds")
FILES = ("main.py",)
# Not needed in the app (the full-size icon picture, caches, the players'
# own settings)
IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc", "android_icon.png", "user_settings.json", ".git*")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    target = os.path.abspath(sys.argv[1])
    if not os.path.isdir(os.path.join(ROOT, "Graphics", "assets", "goku")):
        sys.exit("No sprite sheets: run ./setup.sh first")
    shutil.rmtree(target, ignore_errors=True)
    os.makedirs(target)
    for folder in FOLDERS:
        shutil.copytree(os.path.join(ROOT, folder), os.path.join(target, folder), ignore=IGNORED)
    for name in FILES:
        shutil.copy2(os.path.join(ROOT, name), target)
    print(f"App files in {target}")


if __name__ == "__main__":
    main()
