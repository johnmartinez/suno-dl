#!/usr/bin/env bash
# install.sh — install suno-dl on macOS or Linux.
#
# Three steps:
#   1. pip install -r requirements.txt --break-system-packages
#   2. chmod +x suno-dl.py
#   3. ln -sf "$(pwd)/suno-dl.py" /usr/local/bin/suno-dl
#
# Run this as your regular user — NOT with sudo. Step 3 needs write access
# to /usr/local/bin; if you don't have it, the script will invoke `sudo`
# just for that single command. Running the whole script as root would
# install the Python packages into the system site-packages instead of
# your user site, which isn't what you want.
#
# After install, `suno-dl --help` should work from any directory.

set -euo pipefail

cd "$(dirname "$0")"

LINK_TARGET="/usr/local/bin/suno-dl"
LINK_DIR="$(dirname "$LINK_TARGET")"

echo "[1/3] Installing Python dependencies..."
pip install -r requirements.txt --break-system-packages

echo "[2/3] Marking suno-dl.py executable..."
chmod +x suno-dl.py

echo "[3/3] Symlinking to $LINK_TARGET..."
if [ -w "$LINK_DIR" ]; then
    ln -sf "$(pwd)/suno-dl.py" "$LINK_TARGET"
else
    echo "    $LINK_DIR is not writable by $(id -un); requesting sudo for the symlink only."
    if ! command -v sudo >/dev/null 2>&1; then
        echo "    error: sudo not found. Re-run as root, or symlink suno-dl.py" >&2
        echo "    into a directory on your \$PATH that you own (see README)." >&2
        exit 1
    fi
    sudo ln -sf "$(pwd)/suno-dl.py" "$LINK_TARGET"
fi

echo
echo "Installed. Verify with:"
echo "    suno-dl --help"
echo
echo "Then export your Suno session cookie (see README) and run:"
echo "    suno-dl --output-dir ~/Music/suno"
