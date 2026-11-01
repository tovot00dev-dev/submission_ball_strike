#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source /opt/ros/humble/setup.bash
source /home/ubuntu/airobot_ws/install/setup.bash
exec /usr/bin/python3 "$ROOT/scripts/preview.py" "$@"
