"""Prepare teacher strike data and train a real ACT model; no ROS dependency."""
import argparse
import csv
import hashlib
import json
import random
import zipfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NAMES = ['joint1', 'joint2', 'joint4', 'joint3', 'gripper']


def prepare(args):
    cfg = json.loads((ROOT / 'configs/learning.json').read_text())
    output = ROOT / 'data/strike_raw'
    output.mkdir(parents=True, exist_ok=True)
    paths = [Path(x) for x in args.logs] if args.logs else sorted((ROOT / 'results').glob('preview_*.json'))[-1:]
    manifest = []
    for path in paths:
        records = json.loads(path.read_text())
        # Only the final strike. Never train on greeting, clap, reset or inference logs.
        records = [r for r in records if r['phase'] == 'strike_teacher_preview']
        if len(records) < cfg['chunk_size']:
            raise ValueError(f'No complete teacher strike in {path.name}')
        state = np.asarray([r['state'] for r in records], dtype=np.float32)
        action = np.asarray([r['command'] for r in records], dtype=np.float32)
        stamps = np.asarray([r['time'] for r in records], dtype=np.float64)
        stamps -= stamps[0]
        if state.shape != action.shape or state.shape[1] != 5 or not np.isfinite(state).all() or not np.isfinite(action).all():
            raise ValueError('Invalid state/action arrays')
        if not np.all(np.diff(stamps) > 0) or np.max(np.diff(stamps)) > 0.2:
            raise ValueError('Non-monotonic or sparse timestamps')
        if np.max(np.abs(action[-1] - [-2.2, 1.3, 0.15, -0.4, -0.5236])) > 0.02:
            raise ValueError('This log is not the current calibrated strike')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        dest = output / f'episode_{digest[:12]}.npz'
        np.savez_compressed(dest, state=state, action=action, time=stamps)
        manifest.append({'source_log': path.name, 'sha256': digest,
                         'samples': len(state), 'episode': dest.name,
                         'success_label': 'not automatically verified; teacher trajectory only'})
    (output / 'last_import.json').write_text(json.dumps(manifest, indent=2))
    print(f'Prepared {len(manifest)} teacher strike(s). These are not AI results.')


def convert(args):
    from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
    cfg = json.loads((ROOT / 'configs/learning.json').read_text())
    files = sorted((ROOT / 'data/strike_raw').glob('episode_*.npz'))
    if not files:
        raise RuntimeError('Run prepare first.')
    out = ROOT / 'data/strike_lerobot'
    if out.exists():
        raise RuntimeError('strike_lerobot already exists. Rename before rebuilding.')
    features = {key: {'dtype': 'float32', 'shape': (5,), 'names': NAMES}
                for key in ['observation.state', 'observation.environment_state', 'action']}
    episodes = []
    for path in files:
        with np.load(path) as ep:
            stamps, states, actions = ep['time'], ep['state'], ep['action']
        grid = np.arange(0, stamps[-1], 1/cfg['fps'])
        idx = np.maximum(np.searchsorted(stamps, grid, side='right') - 1, 0)
        if len(idx) < cfg['chunk_size']:
            raise ValueError(f'Episode too short: {path}')
        episodes.append((states[idx], actions[idx]))
    dataset = LeRobotDataset.create(repo_id=cfg['repo_id'], root=out, fps=cfg['fps'],
                                    robot_type='crane_plus', features=features, use_videos=False)
    for states, actions in episodes:
        for state, action in zip(states, actions):
            dataset.add_frame({'observation.state': state, 'observation.environment_state': state,
                               'action': action, 'task': 'Sweep the ball toward the fixed box.'})
        dataset.save_episode()
    all_actions = np.concatenate([a for _, a in episodes])
    (out / 'experiment.json').write_text(json.dumps({
        'teacher_episodes': len(episodes), 'joint_order': NAMES,
        'action_min': all_actions.min(axis=0).tolist(),
        'action_max': all_actions.max(axis=0).tolist(),
        'scope': 'Fixed ball/target positions; only strike is learned.',
        'config': cfg}, indent=2))
    print(f'Converted {len(episodes)} strike episodes -> {out}')


def train(args):
    import torch
    from lerobot.common.datasets.lerobot_dataset import LeRobotDataset, LeRobotDatasetMetadata
    from lerobot.common.datasets.utils import dataset_to_policy_features
    from lerobot.common.policies.act.configuration_act import ACTConfig
    from lerobot.common.policies.act.modeling_act import ACTPolicy
    from lerobot.configs.types import FeatureType
    cfg = json.loads((ROOT / 'configs/learning.json').read_text())
    random.seed(cfg['seed'])
    np.random.seed(cfg['seed'])
    torch.manual_seed(cfg['seed'])
    torch.set_num_threads(2)
    if args.device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('Select a GPU runtime in Colab. CPU is only for short checks.')
    steps = args.steps if args.steps is not None else cfg['training_steps']
    if steps < 1:
        raise ValueError('steps must be positive')
    output = ROOT / 'checkpoints' / args.run_name
    if output.exists():
        raise RuntimeError('Model directory exists; choose a new --run-name.')
    data_root = ROOT / 'data/strike_lerobot'
    meta = LeRobotDatasetMetadata(cfg['repo_id'], root=data_root)
    # Most non-base joints barely move during a level sweep. Do not amplify
    # numerical sensor noise by dividing observations by a near-zero std.
    for key in ['observation.state', 'observation.environment_state']:
        meta.stats[key]['std'] = np.maximum(np.asarray(meta.stats[key]['std']), 0.01).astype(np.float32)
    features = dataset_to_policy_features(meta.features)
    inputs = {k: v for k, v in features.items() if v.type != FeatureType.ACTION}
    outputs = {k: v for k, v in features.items() if v.type == FeatureType.ACTION}
    act = ACTConfig(input_features=inputs, output_features=outputs,
                    pretrained_backbone_weights=None,
                    **{k: cfg[k] for k in ['chunk_size', 'n_action_steps', 'dim_model', 'n_heads',
                                          'dim_feedforward', 'n_encoder_layers', 'n_decoder_layers',
                                          'n_vae_encoder_layers']})
    policy = ACTPolicy(act, dataset_stats=meta.stats).to(args.device)
    policy.train()
    dataset = LeRobotDataset(cfg['repo_id'], root=data_root, delta_timestamps={
        'action': [i/cfg['fps'] for i in range(cfg['chunk_size'])]})
    loader = torch.utils.data.DataLoader(dataset, batch_size=cfg['batch_size'],
                                         shuffle=True, num_workers=0)
    if not len(loader):
        raise RuntimeError('Empty training dataset')
    optimizer = torch.optim.AdamW(policy.parameters(), lr=cfg['learning_rate'])
    output.mkdir(parents=True)
    step = 0
    with (output / 'loss.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['step', 'loss'])
        while step < steps:
            for batch in loader:
                batch = {k: v.to(args.device) for k, v in batch.items() if isinstance(v, torch.Tensor)}
                # The model predicts actions; the loss measures their difference from teacher actions.
                loss, _ = policy.forward(batch)
                if not torch.isfinite(loss):
                    raise RuntimeError('Non-finite loss')
                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(policy.parameters(), 1)
                optimizer.step()
                value = float(loss.detach().cpu())
                writer.writerow([step, value])
                if step % 50 == 0:
                    print(f'step={step} loss={value:.5f}', flush=True)
                    f.flush()
                step += 1
                if step >= steps:
                    break
    policy.save_pretrained(output)
    experiment = json.loads((data_root / 'experiment.json').read_text())
    experiment.update(training_steps=steps, device=args.device,
                      observation_std_floor=0.01,
                      status='trained; Gazebo task success is not yet evaluated')
    (output / 'experiment.json').write_text(json.dumps(experiment, indent=2))
    print(f'Saved ACT model: {output}')


def export(args):
    if not (ROOT / 'data/strike_lerobot/experiment.json').exists():
        raise RuntimeError('Convert data first')
    out = ROOT.parent / 'ball_strike_colab.zip'
    if out.exists():
        raise RuntimeError('Rename the previous ball_strike_colab.zip before exporting')
    paths = [ROOT / 'scripts/strike_learning.py', ROOT / 'configs/learning.json',
             ROOT / 'constraints-colab.txt', ROOT / 'environment.json']
    paths += [p for p in (ROOT / 'data/strike_lerobot').rglob('*') if p.is_file()]
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in paths:
            z.write(path, Path(ROOT.name) / path.relative_to(ROOT))
    print(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['prepare', 'convert', 'train', 'export'])
    p.add_argument('--logs', nargs='+')
    p.add_argument('--device', choices=['cpu', 'cuda'], default='cuda')
    p.add_argument('--steps', type=int)
    p.add_argument('--run-name', default='act_strike')
    args = p.parse_args()
    globals()[args.command](args)


if __name__ == '__main__':
    main()
