"""Load the actual trained ACT weights and predict commands. No ROS imports."""
import contextlib
import json
import sys
from pathlib import Path


def main():
    import torch
    # LeRobot emits loading messages; reserve stdout for the JSON protocol.
    with contextlib.redirect_stdout(sys.stderr):
        from lerobot.common.policies.act.modeling_act import ACTPolicy
        model = Path(sys.argv[1]).resolve()
        if not (model / 'experiment.json').exists():
            raise RuntimeError('Missing strike training provenance')
        experiment = json.loads((model / 'experiment.json').read_text())
        torch.set_num_threads(2)
        policy = ACTPolicy.from_pretrained(model).to('cpu')
        policy.eval()
        policy.reset()
    print(json.dumps({'ready': True, 'experiment': experiment}), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        if request.get('reset'):
            policy.reset()
            print(json.dumps({'reset': True}), flush=True)
            continue
        state = torch.tensor(request['state'], dtype=torch.float32).unsqueeze(0)
        if tuple(state.shape) != (1, 5) or not torch.isfinite(state).all():
            raise ValueError('Invalid observation')
        observation = {'observation.state': state, 'observation.environment_state': state}
        with torch.inference_mode():
            # THIS is the AI replacement: the learned network predicts the action.
            action = policy.select_action(observation)
        values = action.cpu().numpy().reshape(-1)
        if len(values) != 5 or not torch.isfinite(action).all():
            raise ValueError('Invalid model output')
        print(json.dumps({'action': values.tolist()}), flush=True)


if __name__ == '__main__':
    main()
