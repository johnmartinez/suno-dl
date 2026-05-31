#!/usr/bin/env bash
# install.sh — install suno-dl on macOS or Linux.
#
# Three steps:
#   1. pip install -r requirements.txt --break-system-packages
#   2. chmod +x suno-dl.py
#   3. ln -sf "$(pwd)/suno-dl.py" /usr/local/bin/suno-dl
#
# Step 3 needs write access to /usr/local/bin. On most macOS / Linux
# installs you'll want to run this with sudo:
#
#     sudo bash install.sh
#
# After install, `suno-dl --help` should work from any directory.

set -euo pipefail

cd "$(dirname "$0")"

echo "[1/3] Installing Python dependencies..."
pip install -r requirements.txt --break-system-packages

echo "[2/3] Marking suno-dl.py executable..."
chmod +x suno-dl.py

echo "[3/3] Symlinking to /usr/local/bin/suno-dl..."
ln -sf "$(pwd)/suno-dl.py" /usr/local/bin/suno-dl

echo
echo "Installed. Verify with:"
echo "    suno-dl --help"
echo
echo "Then export your Suno session cookie (see README) and run:"
echo "    suno-dl --output-dir ~/Music/suno"
