"""Check model inference across the Python-process boundary; sends NO ROS commands."""
import math
import argparse
from pathlib import Path
from policy_client import PolicyClient

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description='Check ACT inference without moving the robot.')
parser.add_argument('--model', default=str(root / 'checkpoints/act_strike'))
args = parser.parse_args()
policy = PolicyClient(args.model)
try:
    state = [-1.15, 1.3, 0.15, -0.4, -0.5236]
    action = policy.action(state, lambda: None)
    assert len(action) == 5 and all(math.isfinite(x) for x in action)
    print('PASS: trained ACT weights loaded, current state sent, finite action received.')
    print('No ROS command sent. This checks inference, not ball-hit success.')
finally:
    policy.close()
