#!/usr/bin/env bash
# =============================================================================
# setup.sh -- one-time setup for the archive-based-tracking pipeline.
#
# It will:
#   1. install the Python dependencies,
#   2. download the EasyList + EasyPrivacy filter lists (for tracker detection),
#   3. clone DuckDuckGo's Tracker Radar (for domain -> organization mapping).
#
# Usage:
#   bash setup.sh
# =============================================================================
set -euo pipefail

sudo apt update
sudo apt install python3-pip
echo "==> Installing Python dependencies"
python -m pip install -r requirements.txt

echo "==> Downloading EasyList filter lists"
mkdir -p tracker_list
curl -fsSL -o tracker_list/easylist.txt    https://easylist.to/easylist/easylist.txt
curl -fsSL -o tracker_list/easyprivacy.txt https://easylist.to/easylist/easyprivacy.txt

echo "==> Cloning DuckDuckGo Tracker Radar (organization mapping)"
if [ ! -d "tracker-radar" ]; then
  git clone --depth 1 https://github.com/duckduckgo/tracker-radar.git
else
  echo "    tracker-radar already present, skipping clone"
fi

echo "==> Setup complete."
echo "    Next: edit input.csv and config.yaml, then run the four stages."
