#!/usr/bin/env bash
# Download the character and dialog sprite sheets the game needs.
#
# The sheets are not stored in this repository: run this once after cloning
# (and before building the Android APK). Maps are part of the repository and
# are not touched.
#
# Usage: ./setup.sh [--force]
#   --force   download again even if a file is already there

set -euo pipefail

SPRITE_DB="https://spritedatabase.net/files/gba/976/Sprite"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# One line per file: "<source URL> <destination, relative to the repository>"
ASSETS=(
    # Goku
    "$SPRITE_DB/Goku.gif               Graphics/assets/goku/base.png"
    "$SPRITE_DB/DBZBF_GokuSS1.png      Graphics/assets/goku/ssj.png"
    "$SPRITE_DB/GokuSS3.png            Graphics/assets/goku/ssj3.png"
    # Gohan
    "$SPRITE_DB/Gohan.gif              Graphics/assets/gohan/base.png"
    # Vegeta (only a Super Saiyan sheet exists, so he is always one)
    "$SPRITE_DB/VegetaSS.png           Graphics/assets/vegeta/ssj.png"
)

force=false
case "${1:-}" in
    "") ;;
    --force) force=true ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
esac

if command -v curl >/dev/null 2>&1; then
    fetch() { curl --fail --silent --show-error --location --retry 3 --output "$2" "$1"; }
elif command -v wget >/dev/null 2>&1; then
    fetch() { wget --quiet --tries=3 --output-document="$2" "$1"; }
else
    echo "error: curl or wget is required" >&2
    exit 1
fi

# The first bytes tell PNG and GIF images apart from an HTML error page
is_image() {
    local magic
    magic="$(head -c 4 "$1" | od -An -tx1 | tr -d ' \n')"
    [[ "$magic" == "89504e47" || "$magic" == "47494638" ]]
}

downloaded=0
skipped=0
failed=0
for entry in "${ASSETS[@]}"; do
    read -r url destination <<<"$entry"
    target="$ROOT/$destination"

    if [[ -s "$target" && "$force" == false ]]; then
        skipped=$((skipped + 1))
        continue
    fi

    mkdir -p "$(dirname "$target")"
    partial="$target.part"
    echo "Downloading $destination"
    if fetch "$url" "$partial" && is_image "$partial"; then
        # Written in one step, so an interrupted download never leaves a
        # broken image behind
        mv "$partial" "$target"
        downloaded=$((downloaded + 1))
    else
        rm -f "$partial"
        echo "  failed: $url" >&2
        failed=$((failed + 1))
    fi
done

echo "Done: $downloaded downloaded, $skipped already present, $failed failed."
[[ "$failed" -eq 0 ]]
