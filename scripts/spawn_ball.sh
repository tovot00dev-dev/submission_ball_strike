#!/usr/bin/env bash
# Spawn one dynamic 8cm sphere. Optional arguments: x y z (world meters).
set -eo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source /opt/ros/humble/setup.bash
read -r BALL_X BALL_Y BALL_Z < <(/usr/bin/python3 "$ROOT/scripts/place_scene.py" --ball-position)
ros2 run ros_gz_sim create -world default -name strike_ball \
  -allow_renaming false -file "$ROOT/assets/strike_ball.sdf" \
  -x "${1:-$BALL_X}" -y "${2:-$BALL_Y}" -z "${3:-$BALL_Z}"
