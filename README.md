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
- **Attacking**: Press **A** or the on-screen **A** button. Each press is one move of the combo: a punch, another punch, a kick, another kick, then round again (holding does not repeat). You and the enemies strike at the same pace, at most once every 0.4 seconds, so mash the button to keep the combo going.
- **Special technique**: Press **D** or the on-screen **KI** button to charge and fire an energy beam in the direction you face. It costs 30 KI.
- **Super Saiyan**: Press **S** or the on-screen **SSJ** button to transform (needs 20 KI), and again to go back. While transformed you deal 50% more damage and take half, but KI drains instead of regenerating; you revert when it runs out.
- **Talking to NPCs**: Press **T** or the on-screen **T** button while near an NPC.
- **Full screen**: The game opens full screen at the display's own resolution (always on Android). On desktop, press **F11** to switch between full screen and a window, or set `"fullscreen": false` in `Config/config.json` to start in a window.
- **Quit**: Press **Esc** (or the Android back button), or tap the **X** button in the top-right corner, then confirm with **Yes** / Enter. While the question is open the game is paused.
- **Menu**: Select Start or Options with the keyboard or tap. Options shows the control guide; press Esc or tap to return.
- **Enemies**: Each enemy has a health bar and name above its head. Enemies are tough (they only take 60% of each hit) and flinch at most once every 1.8 seconds, so they keep fighting back. A Saiyan enemy such as Vegeta turns Super Saiyan when his health drops to half: the bar's frame turns gold, he hits 50% harder and takes half damage.
- **Combat resources**: The HUD shows HP and KI (mana). Attacks cost KI, which regenerates over time; nearby hostile NPCs pursue and attack back.