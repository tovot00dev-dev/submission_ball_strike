"""Read Gazebo world model poses without modifying the simulation."""
import csv
import re
import subprocess
import threading


class WorldTrace:
    def __init__(self, path):
        self.file = path.open('w', newline='')
        self.writer = csv.writer(self.file)
        self.writer.writerow(['sim_seconds', 'model', 'x', 'y', 'z'])
        self.last = {}
        self.error = None
        self.process = subprocess.Popen(['ign', 'topic', '-e', '-t', '/world/default/dynamic_pose/info'],
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        text=True, bufsize=1)
        self.thread = threading.Thread(target=self.read, daemon=True)
        self.thread.start()

    def read(self):
        stamp = 0.0
        block, depth, kind = [], 0, None
        try:
            for line in self.process.stdout:
                if kind is None:
                    if line.startswith('header {'):
                        kind = 'header'
                    elif line.startswith('pose {'):
                        kind = 'pose'
                    else:
                        continue
                    block, depth = [], 0
                block.append(line)
                depth += line.count('{') - line.count('}')
                if depth != 0:
                    continue
                text = ''.join(block)
                if kind == 'header':
                    sec = re.search(r'\bsec:\s*(\d+)', text)
                    nsec = re.search(r'\bnsec:\s*(\d+)', text)
                    stamp = (int(sec[1]) if sec else 0) + (int(nsec[1]) if nsec else 0) / 1e9
                else:
                    name = re.search(r'name:\s*"([^"]+)"', text)
                    pos = re.search(r'position\s*\{([^}]*)\}', text)
                    if name and pos and name[1] in ('strike_ball', 'wood_cube_5cm'):
                        if stamp - self.last.get(name[1], -1) >= 0.02:
                            xyz = []
                            for axis in 'xyz':
                                value = re.search(r'\b'+axis+r':\s*([-+\deE.]+)', pos[1])
                                xyz.append(float(value[1]) if value else 0.0)
                            self.writer.writerow([stamp, name[1], *xyz])
                            self.last[name[1]] = stamp
                kind = None
        except Exception as exc:
            self.error = repr(exc)

    def close(self):
        self.process.terminate()
        self.process.wait(timeout=5)
        self.thread.join(timeout=5)
        self.file.close()
        if self.error:
            print(f'World trace warning: {self.error}')
