#!/usr/bin/env bash
set -eo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_ROOT="${PAI_TRAINING_DIR:-/home/ubuntu/pai_training}"
cd "$ENV_ROOT"
exec "${PIXI_BIN:-/home/ubuntu/.pixi/bin/pixi}" run python "$ROOT/scripts/act_server.py" "$@"
