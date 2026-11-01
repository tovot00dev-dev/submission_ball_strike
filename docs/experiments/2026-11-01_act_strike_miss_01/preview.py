"""Slow, ball-free scripted motion preview. NOT trained AI; Gazebo only."""
import argparse
import json
import math
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate(cfg):
    if cfg['fps'] <= 0 or len(cfg['joint_names']) != 5:
        raise ValueError('Invalid fps or joint ordering')
    if not math.isfinite(cfg.get('hold_seconds', 0)) or cfg.get('hold_seconds', 0) < 0:
        raise ValueError('Invalid hold duration')
    prev = None
    for frame in cfg['keyframes']:
        positions = frame['positions']
        if len(positions) != 5 or frame['seconds'] <= 0:
            raise ValueError('Invalid keyframe')
        for value, bounds in zip(positions, cfg['limits_degrees']):
            if not math.isfinite(value) or not math.radians(bounds[0]) <= value <= math.radians(bounds[1]):
                raise ValueError('Joint target exceeds URDF limit')
        # Cubic smoothstep peak speed is 1.5 * displacement / duration.
        if prev is not None and any(1.5 * abs(a - b) / frame['seconds'] > cfg['max_velocity_rad_s']
                                    for a, b in zip(positions, prev)):
            raise ValueError('Trajectory exceeds configured velocity limit')
        prev = positions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Validate only, no ROS or movement')
    parser.add_argument('--no-ball', action='store_true', help='Run motion only; leave the existing scene unchanged')
    parser.add_argument('--controller', choices=['teacher', 'ai'], default='teacher')
    parser.add_argument('--model', default=str(ROOT / 'checkpoints/act_strike'))
    args = parser.parse_args()
    cfg = json.loads((ROOT / 'configs/motion_preview.json').read_text())
    validate(cfg)
    if args.check:
        print('PASS: keyframe joint limits and interpolation speeds. Collision/contact NOT checked.')
        print(' -> '.join(f['phase'] for f in cfg['keyframes']))
        return
    # Load weights BEFORE moving anything. There is no teacher fallback in AI mode.
    policy = None
    if args.controller == 'ai':
        from policy_client import PolicyClient
        policy = PolicyClient(args.model)
        print('AI mode: fixed greeting/setup, trained ACT controls ONLY the strike.', flush=True)
    import rclpy
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    from sensor_msgs.msg import JointState
    from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
    rclpy.init()
    node = Node('ball_strike_scripted_preview', parameter_overrides=[Parameter('use_sim_time', value=True)])
    names = cfg['joint_names']
    latest = {'position': None, 'time': None}

    def now():
        return node.get_clock().now().nanoseconds / 1e9

    def update(msg):
        lookup = dict(zip(msg.name, msg.position))
        if all(n in lookup for n in names):
            latest.update(position=[lookup[n] for n in names], time=now())

    subscription = node.create_subscription(JointState, '/joint_states', update, 10)
    topics = ['/crane_plus_arm_controller/joint_trajectory', '/crane_plus_gripper_controller/joint_trajectory']
    pubs = [node.create_publisher(JointTrajectory, t, 10) for t in topics]

    def check_connection():
        if any(node.count_publishers(t) > 1 for t in topics):
            raise RuntimeError('Stop teleop and all other motion publishers before preview.')
        if latest['time'] is None or now() - latest['time'] > 0.5:
            raise RuntimeError('Joint state stale; check Gazebo.')

    def run_with_ros(command, timeout):
        # Spawning a Gazebo model takes real time. Keep draining clock/state
        # subscriptions while the child process runs, otherwise queued messages
        # can trigger a false stale-state error before the strike.
        process = subprocess.Popen(command)
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                rclpy.spin_once(node, timeout_sec=0.01)
                if time.monotonic() > deadline:
                    raise TimeoutError(f'Command timed out: {command}')
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, command)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)

    def send(positions):
        for pub, js, values in zip(pubs, [names[:4], names[4:]], [positions[:4], positions[4:]]):
            msg = JointTrajectory()
            msg.joint_names = js
            pt = JointTrajectoryPoint()
            pt.positions = [float(v) for v in values]
            pt.time_from_start.nanosec = 100_000_000
            msg.points = [pt]
            pub.publish(msg)

    log = []
    trace = None
    try:
        wall = time.monotonic()
        while latest['position'] is None or now() == 0 or not all(p.get_subscription_count() for p in pubs):
            rclpy.spin_once(node, timeout_sec=0.05)
            if time.monotonic() - wall > 20:
                raise RuntimeError('Gazebo clock, joint states, or controllers missing.')
        check_connection()
        if not args.no_ball:
            # Do not let the greeting or preparation touch the demonstration ball.
            run_with_ros(['bash', str(ROOT / 'scripts/remove_ball.sh')], timeout=15)
        run_with_ros(['/usr/bin/python3', str(ROOT / 'scripts/place_scene.py')], timeout=25)
        # Refresh joint messages after the model placement request.
        rclpy.spin_once(node, timeout_sec=0.1)
        previous = list(latest['position'])
        for value, bounds in zip(previous, cfg['limits_degrees']):
            if not math.isfinite(value) or not math.radians(bounds[0]) <= value <= math.radians(bounds[1]):
                raise RuntimeError('Initial measured joint state outside configured limits.')
        from world_trace import WorldTrace
        (ROOT / 'results').mkdir(exist_ok=True)
        trace = WorldTrace(ROOT / 'results' / f'world_{time.time_ns()}.csv')
        for frame in cfg['keyframes']:
            if frame['phase'] == 'strike_teacher_preview' and not args.no_ball:
                print('Spawning ball after windup, immediately before strike.', flush=True)
                run_with_ros(['bash', str(ROOT / 'scripts/spawn_ball.sh')], timeout=30)
                # Let the ball settle and refresh joint state before moving.
                settle_start, settle_wall = now(), time.monotonic()
                while now() - settle_start < 0.5:
                    rclpy.spin_once(node, timeout_sec=0.01)
                    if time.monotonic() - settle_wall > 20:
                        raise RuntimeError('Simulation clock stopped while placing ball.')
                check_connection()
            if frame['phase'] == 'strike_teacher_preview' and policy is not None:
                # The old target/smoothstep trajectory below is NOT used in this branch.
                print('strike_ai: using trained ACT predictions, no teacher interpolation.', flush=True)
                begin, wall = now(), time.monotonic()
                last_command = list(latest['position'])
                step_count = 0
                while now() - begin < frame['seconds'] + cfg.get('hold_seconds', 0):
                    check_connection()
                    state = list(latest['position'])
                    raw = policy.action(state, lambda: rclpy.spin_once(node, timeout_sec=0.001))
                    command = []
                    for i, value in enumerate(raw):
                        low = max(math.radians(cfg['limits_degrees'][i][0]),
                                  policy.experiment['action_min'][i] - 0.08)
                        high = min(math.radians(cfg['limits_degrees'][i][1]),
                                   policy.experiment['action_max'][i] + 0.08)
                        delta = policy.config['max_command_delta_per_tick']
                        command.append(max(last_command[i]-delta,
                                           min(last_command[i]+delta, max(low, min(high, value)))))
                    send(command)
                    log.append({'time': now(), 'phase': 'strike_ai', 'state': state,
                                'raw_action': raw, 'command': command,
                                'limited': any(abs(a-b)>1e-6 for a,b in zip(raw, command))})
                    step_count += 1
                    last_command = command
                    tick = now()
                    while now() - tick < 1/cfg['fps']:
                        rclpy.spin_once(node, timeout_sec=0.005)
                        if time.monotonic() - wall > 120:
                            raise RuntimeError('AI strike clock stopped or inference too slow.')
                print(f'ACT strike completed: {step_count} model predictions.', flush=True)
                continue
            target = frame['positions']
            duration = max(frame['seconds'], max(1.5 * abs(a-b) / cfg['max_velocity_rad_s']
                                                  for a, b in zip(previous, target)) + 0.05)
            start, wall = now(), time.monotonic()
            print(frame['phase'], flush=True)
            sent_end = False
            while not sent_end:
                rclpy.spin_once(node, timeout_sec=0.01)
                check_connection()
                u = min(1.0, max(0.0, (now() - start) / duration))
                smooth = u*u*(3-2*u)
                command = [a + (b-a)*smooth for a, b in zip(previous, target)]
                send(command)
                log.append({'time': now(), 'phase': frame['phase'],
                            'state': list(latest['position']), 'command': command})
                step_start = now()
                while now() - step_start < 1/cfg['fps']:
                    rclpy.spin_once(node, timeout_sec=0.01)
                    if time.monotonic() - wall > duration*100 + 20:
                        raise RuntimeError('Simulation stopped or extremely slow.')
                sent_end = now() - start >= duration + cfg.get('hold_seconds', 0)
            previous = list(target)
        print('Observing the rolling ball for four simulation seconds.', flush=True)
        observe_start, observe_wall = now(), time.monotonic()
        while now() - observe_start < 4.0:
            rclpy.spin_once(node, timeout_sec=0.01)
            if time.monotonic() - observe_wall > 60:
                raise RuntimeError('Simulation stopped during observation.')
        print(f'Trial complete: controller={args.controller}. Task success must be evaluated separately.')
    finally:
        if policy is not None:
            policy.close()
        if trace is not None:
            trace.close()
        result = ROOT / 'results'
        result.mkdir(exist_ok=True)
        (result / f'preview_{time.time_ns()}.json').write_text(json.dumps(log))
        (result / f'run_config_{time.time_ns()}.json').write_text(json.dumps({
            'controller': args.controller, 'model': args.model if policy else None,
            'motion_config': cfg,
            'scene': json.loads((ROOT / 'configs/scene.json').read_text())}, indent=2))
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
