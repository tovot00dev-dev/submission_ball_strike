#!/usr/bin/env bash
# Remove only the book's example cube in the current Gazebo world.
set -euo pipefail
ign service -s /world/default/remove \
  --reqtype ignition.msgs.Entity --reptype ignition.msgs.Boolean \
  --timeout 5000 --req 'name: "wood_cube_5cm", type: MODEL'
