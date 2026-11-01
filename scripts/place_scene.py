"""Validate the anchored arm location, or print configured ball coordinates."""
import argparse
import json
import math
import subprocess
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ball_position(cfg):
    x, y, z = cfg['robot']['position']
    dx, dy, dz = cfg['ball']['offset_from_robot']
    yaw = cfg['robot']['yaw']
    return [x + math.cos(yaw)*dx - math.sin(yaw)*dy,
            y + math.sin(yaw)*dx + math.cos(yaw)*dy, z + dz]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--ball-position', action='store_true')
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    cfg = json.loads((ROOT / 'configs/scene.json').read_text())
    ball = ball_position(cfg)
    radius = 0.04
    table = cfg['table']
    for value, bounds in zip(ball[:2], [table['x_bounds'], table['y_bounds']]):
        if not bounds[0] + radius <= value <= bounds[1] - radius:
            raise ValueError('Ball starts too close to table edge')
    if args.ball_position:
        print(' '.join(str(v) for v in ball))
        return
    if args.check:
        print(json.dumps({'robot': cfg['robot'], 'ball_position': ball}))
        return
    robot = cfg['robot']
    result = subprocess.run(['ign', 'model', '-m', robot['name'], '--pose'],
                            text=True, capture_output=True, timeout=20, check=True)
    match = re.search(r'\[\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*\]\s*\n\s*\[\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)', result.stdout)
    if not match:
        raise RuntimeError('Cannot read robot pose. Start Gazebo with scripts/front_center.launch.py.')
    values = [float(x) for x in match.groups()]
    if any(abs(a-b) > 0.015 for a, b in zip(values[:3], robot['position'])) or abs(values[5]-robot['yaw']) > 0.015:
        raise RuntimeError('Robot is at old position. Stop old Gazebo launch, then run: ros2 launch /workspace/submission_ball_strike/scripts/front_center.launch.py')
    print(f'Arm location verified: {values[:3]}; planned ball at {ball}')


if __name__ == '__main__':
    main()
