#!/usr/bin/env bash
# Download the character sprite sheets the game needs.
#
# The sheets are not stored in this repository: run this once after cloning
# (and before building the Android APK). Maps are part of the repository and
# are not touched.
#
#   - Characters (everyone but Goku base / SSJ), the portraits and the
#     effects of the techniques of most characters come from the private
#     dbz-assets repository: set GH_TOKEN to a GitHub token that can read it.
#   - Goku base / SSJ, and the special technique effects (blasts, beams...)
#     come from spritedatabase.net.
#
# Usage: GH_TOKEN=... ./setup.sh [--force]
#   --force   download again even if the files are already there
#
# Environment:
#   GH_TOKEN        GitHub token with read access to the assets repository
#   ASSETS_REPO     owner/name of that repository (default Chakib08/dbz-assets)
#   ASSETS_BRANCH   its branch (default main)
#   ASSETS_URL      where to get assets.zip (default: raw.githubusercontent.com)

set -euo pipefail

SPRITE_DB="https://spritedatabase.net/files/gba/976/Sprite"
ASSETS_REPO="${ASSETS_REPO:-Chakib08/dbz-assets}"
ASSETS_BRANCH="${ASSETS_BRANCH:-main}"
ASSETS_URL="${ASSETS_URL:-https://raw.githubusercontent.com/$ASSETS_REPO/$ASSETS_BRANCH/assets.zip}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# spritedatabase.net: "<source URL> <destination, relative to the repository>"
SPRITE_DB_ASSETS=(
    # Goku (body and techniques)
    "$SPRITE_DB/Goku.gif               Graphics/assets/goku/base.png"
    "$SPRITE_DB/DBZBF_GokuSS1.png      Graphics/assets/goku/ssj.png"
    # Only used for the effects of the techniques (and the SSJ3 aura)
    "$SPRITE_DB/GokuSS3.png            Graphics/assets/effects/goku_ssj3.png"
    "$SPRITE_DB/Gohan.gif              Graphics/assets/effects/gohan_base.png"
    "$SPRITE_DB/VegetaSS.png           Graphics/assets/effects/vegeta_ssj.png"
)

# dbz-assets repository: "<path in the repository> <destination>"
REPO_ASSETS=(
    "goku/ssj3.png                     Graphics/assets/goku/ssj3.png"
    "gohan-schooler/base.png           Graphics/assets/gohan/base.png"
    "gohan-schooler/ssj.png            Graphics/assets/gohan/ssj.png"
    "vegeta-bf/base.png                Graphics/assets/vegeta/base.png"
    "vegeta-bf/ssj.png                 Graphics/assets/vegeta/ssj.png"
    "trunks-future-armor/base.png      Graphics/assets/trunks/base.png"
    "trunks-future-armor/ssj.png       Graphics/assets/trunks/ssj.png"
    "broly/base.png                    Graphics/assets/broly/base.png"
    "piccolo/base.png                  Graphics/assets/piccolo/base.png"
    # Piccolo without his weighted clothes: his power-up form
    "piccolo/no-weight.png             Graphics/assets/piccolo/ssj.png"
    "android17/base.png                Graphics/assets/android17/base.png"
    "android18/base.png                Graphics/assets/android18/base.png"
    "android13/base.png                Graphics/assets/android13/base.png"
    "android16/base.png                Graphics/assets/android16/base.png"
    "android19/base.png                Graphics/assets/android19/base.png"
    "android20/base.png                Graphics/assets/android20/base.png"
    "goten/base.png                    Graphics/assets/goten/base.png"
    "goten/ssj.png                     Graphics/assets/goten/ssj.png"
    "trunks-kid/base.png               Graphics/assets/kid_trunks/base.png"
    "trunks-kid/ssj.png                Graphics/assets/kid_trunks/ssj.png"
    "gotenks/base.png                  Graphics/assets/gotenks/base.png"
    "gotenks/ssj.png                   Graphics/assets/gotenks/ssj.png"
    "gotenks/ssj3.png                  Graphics/assets/gotenks/ssj3.png"
    "gohan-great-saiyaman/base.png     Graphics/assets/great_saiyaman/base.png"
    "gohan-great-saiyaman/ssj.png      Graphics/assets/great_saiyaman/ssj.png"
    "vegito/base.png                   Graphics/assets/vegito/base.png"
    "vegito/ssj.png                    Graphics/assets/vegito/ssj.png"
    "gogeta/ssj.png                    Graphics/assets/gogeta/ssj.png"
    "cell/imperfect.png                Graphics/assets/cell_imperfect/base.png"
    "cell/semi-perfect.png             Graphics/assets/cell_semi_perfect/base.png"
    "cell/perfect.png                  Graphics/assets/cell_perfect/base.png"
    "buu/base.png                      Graphics/assets/buu/base.png"
    "kid-buu/base.png                  Graphics/assets/kid_buu/base.png"
    "super-buu/base.png                Graphics/assets/super_buu/base.png"
    "super-buu/gotenks-absorbed.png    Graphics/assets/super_buu_gotenks/base.png"
    "super-buu/gohab-absorbed.png      Graphics/assets/super_buu_gohan/base.png"
    # Effects of the techniques of Trunks and Broly
    "effects/effects.png               Graphics/assets/effects/sfx.png"
    # Character portraits (character screens, dialog box)
    "portraits/bf/portraits-bf.png     Graphics/assets/portraits/bf.png"
    "portraits/log2/portrait-log2.png  Graphics/assets/portraits/log2.png"
    # Map pictures the arenas are cut from (tools/build_arenas.py)
    "maps/roshis-island.png               Graphics/assets/maps/roshis-island.png"
    "maps/papaya-island.png               Graphics/assets/maps/papaya-island.png"
    "maps/grand-kais-planet.png           Graphics/assets/maps/grand-kais-planet.png"
    "maps/kamis-lookout.png               Graphics/assets/maps/kamis-lookout.png"
    "maps/planet-of-the-kais.png          Graphics/assets/maps/planet-of-the-kais.png"
    "maps/diablo-desert.png               Graphics/assets/maps/diablo-desert.png"
    "maps/volcano.png                     Graphics/assets/maps/volcano.png"
    "maps/nataday-village.png             Graphics/assets/maps/nataday-village.png"
    "maps/southwest-forest.png            Graphics/assets/maps/southwest-forest.png"
    "maps/thieves-den.png                 Graphics/assets/maps/thieves-den.png"
    "maps/hfil.png                        Graphics/assets/maps/hfil.png"
    "maps/west-city.png                   Graphics/assets/maps/west-city.png"
    "maps/hercule-city.png                Graphics/assets/maps/hercule-city.png"
    "maps/cell-game-arena.png          Graphics/assets/maps/cell-game-arena.png"
)
# Written once the repository sheets are installed: older setups put other
# images at some of these paths, so their presence alone proves nothing
REPO_STAMP="Graphics/assets/.dbz-assets"

force=false
case "${1:-}" in
    "") ;;
    --force) force=true ;;
    -h|--help) sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
esac

if ! command -v curl >/dev/null 2>&1; then
    echo "error: curl is required" >&2
    exit 1
fi
fetch() { curl --fail --silent --show-error --location --retry 3 --output "$2" "$1"; }

# The first bytes tell PNG and GIF images apart from an HTML error page
is_image() {
    local magic
    magic="$(head -c 4 "$1" | od -An -tx1 | tr -d ' \n')"
    [[ "$magic" == "89504e47" || "$magic" == "47494638" ]]
}

# Moves a checked image into place in one step, so an interrupted run never
# leaves a broken image behind
install_image() {
    local source="$1" target="$2"
    if ! is_image "$source"; then
        return 1
    fi
    mkdir -p "$(dirname "$target")"
    cp "$source" "$target.part"
    mv "$target.part" "$target"
}

downloaded=0
skipped=0
failed=0

# ---- spritedatabase.net --------------------------------------------------------
# Older setups kept the spritedatabase sheets where the repository ones go
# now: move them to the effects folder instead of downloading them again
migrate() {
    local old="$ROOT/$1" new="$ROOT/$2"
    if [[ -s "$old" && ! -e "$new" && ! -e "$ROOT/$REPO_STAMP" ]]; then
        mkdir -p "$(dirname "$new")"
        mv "$old" "$new"
    fi
}
migrate Graphics/assets/goku/ssj3.png Graphics/assets/effects/goku_ssj3.png
migrate Graphics/assets/gohan/base.png Graphics/assets/effects/gohan_base.png
migrate Graphics/assets/vegeta/ssj.png Graphics/assets/effects/vegeta_ssj.png

for entry in "${SPRITE_DB_ASSETS[@]}"; do
    read -r url destination <<<"$entry"
    target="$ROOT/$destination"
    if [[ -s "$target" && "$force" == false ]]; then
        skipped=$((skipped + 1))
        continue
    fi
    mkdir -p "$(dirname "$target")"
    echo "Downloading $destination"
    if fetch "$url" "$target.part" && is_image "$target.part"; then
        mv "$target.part" "$target"
        downloaded=$((downloaded + 1))
    else
        rm -f "$target.part"
        echo "  failed: $url" >&2
        failed=$((failed + 1))
    fi
done

# ---- dbz-assets repository -------------------------------------------------------
repo_complete() {
    [[ -e "$ROOT/$REPO_STAMP" ]] || return 1
    local entry path destination
    for entry in "${REPO_ASSETS[@]}"; do
        read -r path destination <<<"$entry"
        [[ -s "$ROOT/$destination" ]] || return 1
    done
}

if repo_complete && [[ "$force" == false ]]; then
    skipped=$((skipped + ${#REPO_ASSETS[@]}))
elif [[ -z "${GH_TOKEN:-}" ]]; then
    echo "error: GH_TOKEN is not set: the character sheets of $ASSETS_REPO cannot be downloaded" >&2
    echo "  Run: GH_TOKEN=<token with read access to $ASSETS_REPO> ./setup.sh" >&2
    failed=$((failed + ${#REPO_ASSETS[@]}))
else
    work="$(mktemp -d)"
    trap 'rm -rf "$work"' EXIT
    archive="$work/assets.zip"
    echo "Downloading the character sheets from $ASSETS_REPO"
    # The assets.zip release of the repository, else the whole repository
    # as an archive (same files, inside one top folder)
    if ! curl --fail --silent --show-error --location --retry 3 \
            -H "Authorization: Bearer $GH_TOKEN" \
            -o "$archive" \
            "$ASSETS_URL" 2>/dev/null; then
        curl --fail --silent --show-error --location --retry 3 \
            -H "Authorization: Bearer $GH_TOKEN" \
            -H "Accept: application/vnd.github+json" \
            -o "$archive" \
            "https://api.github.com/repos/$ASSETS_REPO/zipball/$ASSETS_BRANCH" || rm -f "$archive"
    fi

    if [[ ! -s "$archive" ]]; then
        echo "  failed: cannot download $ASSETS_REPO" >&2
        echo "  GitHub answers \"not found\" when the token cannot see the repository: in the" >&2
        echo "  token's settings, give it access to $ASSETS_REPO (Repository access: Only select" >&2
        echo "  repositories) with the Contents: Read-only permission." >&2
        failed=$((failed + ${#REPO_ASSETS[@]}))
    else
        mkdir -p "$work/files"
        if command -v unzip >/dev/null 2>&1; then
            unzip -q "$archive" -d "$work/files"
        else
            python3 -m zipfile -e "$archive" "$work/files"
        fi
        repo_failed=0
        for entry in "${REPO_ASSETS[@]}"; do
            read -r path destination <<<"$entry"
            # The file, whatever top folder the archive puts it in
            found="$(find "$work/files" -type f -path "*/$path" -print -quit)"
            if [[ -n "$found" ]] && install_image "$found" "$ROOT/$destination"; then
                echo "Installed $destination"
                downloaded=$((downloaded + 1))
            else
                echo "  failed: $path not found in $ASSETS_REPO" >&2
                repo_failed=$((repo_failed + 1))
            fi
        done
        failed=$((failed + repo_failed))
        if [[ "$repo_failed" -eq 0 ]]; then
            date -u +%Y-%m-%dT%H:%M:%SZ > "$ROOT/$REPO_STAMP"
        fi
    fi
fi

# ---- Arenas: maps built from the map pictures ---------------------------------------
# tools/build_arenas.py needs pygame: the project's Python if it has it,
# else a small environment of its own (.setup-env)
PYTHON="${PYTHON:-python3}"
if [[ -d "$ROOT/Graphics/assets/maps" ]]; then
    if ! "$PYTHON" -c "import pygame" >/dev/null 2>&1; then
        if [[ ! -x "$ROOT/.setup-env/bin/python" ]]; then
            echo "Installing pygame for building the arenas (.setup-env)"
            python3 -m venv "$ROOT/.setup-env" && "$ROOT/.setup-env/bin/python" -m pip install -q pygame==2.6.1 \
                || rm -rf "$ROOT/.setup-env"
        fi
        PYTHON="$ROOT/.setup-env/bin/python"
    fi
    arena_force=""
    [[ "$force" == true ]] && arena_force="--force"
    if SDL_VIDEODRIVER=dummy "$PYTHON" "$ROOT/tools/build_arenas.py" $arena_force; then
        echo "Arenas built in Graphics/assets/arenas"
    else
        echo "  failed: building the arenas" >&2
        failed=$((failed + 1))
    fi
fi

echo "Done: $downloaded downloaded, $skipped already present, $failed failed."
[[ "$failed" -eq 0 ]]
