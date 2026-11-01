#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE='airobotbook/ros2-desktop-ai-robot-book-humble@sha256:b58ec74c019aacd9ce4818fa25fc5a9e0a1f22f8c9cd1f5260994bf15cd9eb63'
if docker container inspect pai_ros2 >/dev/null 2>&1; then
  echo 'pai_ros2 already exists. Use the existing container or choose another name manually.' >&2
  exit 1
fi
docker run -d --name pai_ros2 \
  -p 127.0.0.1:6080:80 -p 127.0.0.1:9090:9090 -p 127.0.0.1:9876:9876 \
  --shm-size=512m -v "$ROOT:/workspace/submission_ball_strike" "$IMAGE"
