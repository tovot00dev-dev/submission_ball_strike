#!/usr/bin/env bash
set -euo pipefail
ign service -s /world/default/remove \
  --reqtype ignition.msgs.Entity --reptype ignition.msgs.Boolean \
  --timeout 5000 --req 'name: "strike_ball", type: MODEL'
