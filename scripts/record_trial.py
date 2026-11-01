"""Record the Gazebo window during one real ACT trial (no playback)."""
import os
import re
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare_window():
    from Xlib import X, display, protocol
    d = display.Display(os.environ.get('DISPLAY', ':0'))
    root = d.screen().root
    size = root.get_geometry()
    tree = subprocess.check_output(['xwininfo', '-root', '-tree'], text=True)
    match = re.search(r'(0x[0-9a-f]+) "Gazebo":', tree)
    if not match:
        raise RuntimeError('Open Gazebo before recording.')
    wid = int(match[1], 16)
    def event(name, data):
        root.send_event(protocol.event.ClientMessage(
            window=wid, client_type=d.intern_atom(name), data=(32, data)),
            event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
        d.flush()
    event('_NET_WM_STATE', [1, d.intern_atom('_NET_WM_STATE_FULLSCREEN'), 0, 0, 0])
    event('_NET_ACTIVE_WINDOW', [1, X.CurrentTime, 0, 0, 0])
    time.sleep(2)
    d.close()
    return wid, f'{size.width}x{size.height}'


def main():
    os.environ.setdefault('DISPLAY', ':0')
    wid, screen_size = prepare_window()
    out = ROOT / 'videos' / time.strftime('act_trial_%Y%m%d_%H%M%S')
    out.mkdir(parents=True, exist_ok=False)
    recorder = None
    run = None
    with (out / 'trial.log').open('w') as log, (out / 'capture.log').open('w') as capture:
        try:
            run = subprocess.Popen(['bash', str(ROOT / 'scripts/ai.sh')],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, bufsize=1, start_new_session=True)
            for line in run.stdout:
                print(line, end='', flush=True)
                log.write(line)
                log.flush()
                # Exclude model loading; capture all actual robot motion.
                if 'AI mode: fixed greeting/setup' in line and recorder is None:
                    recorder = subprocess.Popen([
                        'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'warning',
                        '-f', 'x11grab', '-framerate', '10', '-draw_mouse', '0',
                        '-video_size', screen_size, '-i', os.environ['DISPLAY'],
                        '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                        '-c:v', 'libx264', '-threads', '1', '-preset', 'ultrafast', '-crf', '20',
                        '-pix_fmt', 'yuv420p', str(out / 'gazebo_raw.mp4')],
                        stdout=capture, stderr=capture)
                    time.sleep(1)
                    if recorder.poll() is not None:
                        raise RuntimeError('Capture failed; inspect capture.log')
                    print('RECORDING GAZEBO', flush=True)
            code = run.wait()
            if code:
                raise RuntimeError(f'Trial failed: exit {code}; recording retained.')
        finally:
            if run is not None and run.poll() is None:
                os.killpg(run.pid, signal.SIGINT)
                try:
                    run.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(run.pid, signal.SIGTERM)
            if recorder is not None and recorder.poll() is None:
                recorder.send_signal(signal.SIGINT)
                recorder.wait(timeout=20)
            print(f'Recording folder: {out}', flush=True)


if __name__ == '__main__':
    main()
