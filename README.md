# Dragon-Ball-Z-Buu-s-Fury
Dragon Ball Z Buu's Fury (Fan remake in python) powered by pygame

## Disclaimer
This game is a fan-made project and is not affiliated with or endorsed by Akira Toriyama, Toei Animation, Funimation, Shueisha, Webfoot Technologies, or Atari. Dragon Ball Z and all related characters and elements are trademarks of their respective owners. This project is intended for non-commercial use only and is a tribute to the original "Dragon Ball Z: Buu's Fury" game. Please support the official releases.


## Description
The purpose of this repository is to reproduce Dragon Ball Z Buu's Fury from Game Boy Advance, i started the latter to improve my python coding skills firstly, and to remake one of my favorite childhood games from GBA


## Prerequisites
Install pip if it's not already installed and install the requirements using pip
`$ pip3 install -r requirements.txt`

Application settings are stored in `Config/config.json`.

Launch the game
`cd Dragon-Ball-Z-Buu-s-Fury/`
`python3 src/main.py`

## Android APK

The **Build Android APK** GitHub Actions workflow builds a debug APK on pushes to `main`, pull requests targeting `main`, and manual runs. Download the `android-apk` artifact from the completed workflow run. Pushing a version tag such as `v1.0.0` also attaches the APK to a GitHub Release.

To build locally, install [Buildozer](https://buildozer.readthedocs.io/) and run:

```sh
buildozer android debug
```

## Game Mechanics

### Controls

- **Choose a character**: Select Goku, Goten, Vegeta, or Gohan from the character screen after choosing Start. Use Left/Right and Enter, or tap a character.
- **Movement**: Use the arrow keys, or the on-screen D-pad on a touch device. Diagonal movement is supported.
- **Running**: Hold Space while moving, or hold the on-screen **R** button.
- **Attacking**: Press **A** or the on-screen **A** button.
- **Talking to NPCs**: Press **T** or the on-screen **T** button while near an NPC.
- **Menu**: Select Start or Options with the keyboard or tap. Options shows the control guide; press Esc or tap to return.