#!/usr/bin/env python3
"""Build the desktop game (Windows .exe; also works on Linux and macOS)
with PyInstaller, into dist/<NAME>/: the program and, in its _internal
folder, Config/, Graphics/ and Sounds/ (Config.root_dir finds them there).

    pip install -r requirements.txt pyinstaller pillow
    ./setup.sh                      # the sprite sheets
    python tools/build_desktop.py

Pillow turns the PNG icon into the .ico Windows wants. Run the result with
dist/<NAME>/<NAME>(.exe); zip the whole folder to share it.
"""

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "DragonBallZTrunksHope"
DATA = ("Config", "Graphics", "Sounds")
ICON = os.path.join("Graphics", "android", "icon.png")
# Not needed by the game (the full-size icon picture, the online server)
EXCLUDED_FILES = (os.path.join("Graphics", "android_icon.png"),)


def main():
    import PyInstaller.__main__

    os.chdir(ROOT)
    missing = [folder for folder in DATA if not os.path.isdir(folder)]
    if missing:
        sys.exit(f"missing: {missing}")
    if not os.path.isdir(os.path.join("Graphics", "assets", "goku")):
        sys.exit("No sprite sheets: run ./setup.sh first")

    args = [
        os.path.join("src", "main.py"),
        "--name", NAME,
        "--noconfirm",
        "--clean",
        "--windowed",           # no console window behind the game
        "--paths", "src",
        "--distpath", "dist",
        "--workpath", os.path.join("build", "pyinstaller"),
        "--specpath", os.path.join("build", "pyinstaller"),
    ]
    for folder in DATA:
        args += ["--add-data", f"{os.path.join(ROOT, folder)}{os.pathsep}{folder}"]
    try:
        import PIL  # noqa: F401  (converts the PNG icon)
        args += ["--icon", os.path.join(ROOT, ICON)]
    except ImportError:
        print("Pillow not installed: building without an icon")
    PyInstaller.__main__.run(args)

    data = os.path.join("dist", NAME, "_internal")
    for path in EXCLUDED_FILES:
        target = os.path.join(data, path)
        if os.path.exists(target):
            os.remove(target)
    # The player's own settings must not ship with the game
    settings = os.path.join(data, "user_settings.json")
    if os.path.exists(settings):
        os.remove(settings)
    shutil.rmtree(os.path.join(data, "Graphics", "assets", ".git"), ignore_errors=True)
    print(f"Built dist/{NAME}/")


if __name__ == "__main__":
    main()
