"""Bridge system-Python ROS control to the pixi Python ACT process."""
import json
import math
import os
import select
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PolicyClient:
    def __init__(self, model_path):
        model = Path(model_path).resolve()
        if not (model / 'model.safetensors').exists():
            raise RuntimeError(f'ACT weights missing: {model}. Train/import the model first.')
        self.config = json.loads((ROOT / 'configs/learning.json').read_text())
        self.process = subprocess.Popen(['bash', str(ROOT / 'scripts/act_server.sh'), str(model)],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        text=True, bufsize=1, start_new_session=True)
        try:
            message = self.receive(120)
            if not message.get('ready'):
                raise RuntimeError('Model process did not become ready')
            self.experiment = message['experiment']
            if self.experiment['joint_order'] != ['joint1', 'joint2', 'joint4', 'joint3', 'gripper']:
                raise RuntimeError('Checkpoint has incompatible joint order')
        except BaseException:
            self.close()
            raise

    def receive(self, timeout, spin=None):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if spin:
                spin()
            readable, _, _ = select.select([self.process.stdout], [], [], 0.005)
            if readable:
                line = self.process.stdout.readline()
                if not line:
                    raise RuntimeError('ACT process stopped; inspect its error above.')
                return json.loads(line)
            if self.process.poll() is not None:
                raise RuntimeError('ACT process failed.')
        raise TimeoutError('ACT inference timed out.')

    def action(self, state, spin):
        self.process.stdin.write(json.dumps({'state': state}) + '\n')
        self.process.stdin.flush()
        raw = self.receive(self.config['policy_wall_timeout_seconds'], spin)['action']
        if len(raw) != 5 or not all(math.isfinite(x) for x in raw):
            raise ValueError('Invalid model action')
        return raw

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()  # End the server's input loop normally.
        if self.process.poll() is None:
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGTERM)
                self.process.wait()
        if self.process.stdout:
            self.process.stdout.close()
