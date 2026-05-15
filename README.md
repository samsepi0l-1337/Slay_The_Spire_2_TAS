# StS2 TAS

telemetry-driven ML automation research stack for Slay the Spire 2.

The project direction is now Python ML core + Gymnasium + C# Godot/Harmony telemetry bridge + macro-action executor. The model never learns raw mouse coordinates. It chooses macro actions such as `play_card(hand_slot=2, target_slot=0)`, `end_turn`, or `choose_reward(choice_slot=1)`, and the executor translates those actions into guarded window-relative input.

This stack is for single-player local research only. Do not use it for online co-op, Steam Leaderboards, public matchmaking, anti-cheat bypass, game result mutation, or memory writes. Real OS input is gated by `--execute`; dry-run and structured logs remain the default workflow.

## Quick Start

Python stays pinned to 3.14 for this repository.

```bash
uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
uv run sts2-tas bridge-smoke --fixture data/fixtures/telemetry/combat.json --out data/bridge-smoke.json
uv run sts2-tas env-step --snapshot data/fixtures/telemetry/combat.json --action end_turn
uv run sts2-tas collect-demo --transport pipe --dataset data/demo.jsonl --policy heuristic --max-steps 100
uv run sts2-tas train-bc --dataset data/demo.jsonl --model models/bc.pt --epochs 20
uv run sts2-tas train-ppo --dataset data/demo.jsonl --model models/ppo.zip --total-timesteps 10000
uv run sts2-tas evaluate-policy --model models/bc.pt --episodes data/eval.jsonl --out data/eval-summary.json
uv run sts2-tas act --snapshot data/fixtures/telemetry/combat.json --action play_card:hand_slot=0,target_slot=0 --input-log data/input-plan.jsonl
uv run sts2-tas run-local --transport pipe --policy models/bc.pt --dataset data/local-run.jsonl --max-steps 100
uv run sts2-tas act --transport pipe --policy models/bc.pt --input-backend native --target-process SlayTheSpire2 --execute
```

The command names above are the target public contract for the rewrite. Until the implementation catches up, docs and tests should treat old TAS/movie/replay/checkpoint commands as retired compatibility debt.

## Architecture

```text
[Slay the Spire 2]
        |
        v
[C# Godot/Harmony Telemetry Bridge]
        |
        v
[Python Gymnasium Environment + ML]
        |
        v
[Macro-action Executor]
```

The bridge exports structured state and valid actions. Python validates each telemetry frame, flattens valid actions into a maskable action space, computes reward and episode logs, trains BC or MaskablePPO policies, then asks the executor to apply selected macro actions when execution is explicitly enabled.

## Data

Minimum run rows include `run_id`, `game_version`, `mod_version`, `seed`, `timestamp`, `floor`, `phase`, `state_json`, `valid_actions_json`, `chosen_action_json`, `reward`, `terminal`, `result`, and optional `screenshot_path`. JSONL is the first storage target; SQLite and Parquet are planned for larger experiments.

## Stack

- Python: `gymnasium`, `torch`, `stable-baselines3`, `sb3-contrib`, `pydantic`, `numpy`, `pandas`, `pillow`, `mlflow`
- Input and vision fallback: `pyautogui`, `pynput`, `mss`, `opencv-python`
- Bridge: Godot 4 C#/.NET, Harmony, checked-in `.sln` and `.csproj`
- Packaging: Docker, Windows executable workflow, `uv.lock`

## Docs

- [docs/README.md](docs/README.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/implemented-work.md](docs/implemented-work.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/docker.md](docs/docker.md)
