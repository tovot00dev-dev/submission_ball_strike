"""Crop a recorded Gazebo trial and add factual labels without retiming."""
import subprocess
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description='Crop a 932x635 Gazebo recording using the demonstration layout.')
parser.add_argument('source', type=Path, help='Raw MP4 from record_trial.py; this layout expects the scene at the left.')
parser.add_argument('--output', type=Path, default=ROOT / 'videos/task_demo.mp4')
args = parser.parse_args()
source = args.source
target = args.output
target.parent.mkdir(parents=True, exist_ok=True)
filters = (
    'crop=512:460:0:174,scale=768:690,pad=768:800:0:70:black,'
    "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
    "text='CRANE+ V2 - ACT imitation learning':fontsize=25:fontcolor=white:x=20:y=12,"
    "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
    "text='Fixed greeting + learned strike / Fixed scene':fontsize=19:fontcolor=white:x=20:y=44,"
    "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
    "text='Gazebo screen recording - no speed change':fontsize=19:fontcolor=white:x=20:y=771"
)
subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source),
                '-vf', filters, '-c:v', 'libx264', '-threads', '1', '-preset', 'fast',
                '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                str(target)], check=True)
print(target)
