#!/usr/bin/env bash
set -euo pipefail
ENV_ROOT="${PAI_TRAINING_DIR:-/home/ubuntu/pai_training}"
if [[ -e "$ENV_ROOT" ]]; then
  echo "Existing environment: $ENV_ROOT; left unchanged. Check environment.json for revisions."
  exit 0
fi
if [[ ! -x /home/ubuntu/.pixi/bin/pixi ]]; then
  echo 'Install pixi from https://pixi.sh first, then rerun this script.' >&2
  exit 1
fi
git clone https://github.com/matsuolab/pai_training.git "$ENV_ROOT"
git -C "$ENV_ROOT" checkout b4d6b5459066a80433475a83567504988875248a
git -C "$ENV_ROOT" submodule update --init --recursive
cd "$ENV_ROOT"
/home/ubuntu/.pixi/bin/pixi install
