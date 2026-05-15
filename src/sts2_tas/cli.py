from __future__ import annotations

import argparse
import json
from pathlib import Path

from sts2_tas.bc import evaluate_behavioral_cloning, train_behavioral_cloning
from sts2_tas.dataset import JsonlTransitionWriter, TransitionRecord
from sts2_tas.env import Sts2Env
from sts2_tas.executor import MacroExecutor
from sts2_tas.heuristic import choose_action
from sts2_tas.rl import train_maskable_ppo_smoke
from sts2_tas.telemetry_schema import MacroAction, TelemetrySnapshot


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    result = args.func(args)
    if result is not None:
        print(json.dumps(result, sort_keys=True))
    return 0


def _bridge_smoke(args: argparse.Namespace) -> dict[str, int | str]:
    snapshot = _load_snapshot(args.fixture)
    return {"phase": snapshot.phase, "valid_actions": len(snapshot.valid_actions), "schema_version": snapshot.schema_version}


def _env_step(args: argparse.Namespace) -> dict[str, object]:
    env = Sts2Env(_load_snapshot(args.snapshot))
    observation, reward, terminated, truncated, info = env.step(args.action_index)
    return {"observation": observation, "reward": reward, "terminated": terminated, "truncated": truncated, "info": info}


def _collect_demo(args: argparse.Namespace) -> dict[str, object]:
    snapshot = _load_snapshot(args.snapshot)
    action = choose_action(snapshot)
    writer = JsonlTransitionWriter(args.output)
    writer.append(
        TransitionRecord(
            game_version=snapshot.game_version,
            mod_version=snapshot.mod_version,
            seed=snapshot.seed,
            timestamp=snapshot.timestamp,
            floor=snapshot.floor,
            phase=snapshot.phase,
            state_json=snapshot.to_dict(),
            valid_actions_json=[candidate.to_dict() for candidate in snapshot.valid_actions],
            chosen_action_json=action.to_dict(),
            reward=0.0,
            terminal=False,
            result="heuristic",
        )
    )
    return {"output": str(args.output), "chosen_action": action.to_dict()}


def _train_bc(args: argparse.Namespace) -> dict[str, object]:
    policy = train_behavioral_cloning(args.dataset, args.model)
    return {"algorithm": "behavioral-cloning", "states": len(policy.table), "model": str(args.model)}


def _train_ppo(args: argparse.Namespace) -> dict[str, object]:
    result = train_maskable_ppo_smoke(args.dataset, args.model, args.timesteps)
    return {**result, "model": str(args.model)}


def _evaluate_policy(args: argparse.Namespace) -> dict[str, object]:
    return evaluate_behavioral_cloning(args.dataset, args.model)


def _act(args: argparse.Namespace) -> dict[str, object]:
    action = MacroAction.from_dict(json.loads(args.action_json))
    executor = MacroExecutor(args.window_title, execute_enabled=args.execute)
    return executor.execute(action) if args.execute else executor.plan(action)


def _run_local(args: argparse.Namespace) -> dict[str, object]:
    writer = JsonlTransitionWriter(args.output)
    transitions = 0
    for _ in range(args.episodes):
        snapshot = _load_snapshot(args.snapshot)
        action = choose_action(snapshot)
        env = Sts2Env(snapshot, writer=writer)
        env.step(env.action_space.index_of(action))
        transitions += 1
    return {"episodes": args.episodes, "transitions": transitions, "output": str(args.output)}


def _load_snapshot(path: Path) -> TelemetrySnapshot:
    return TelemetrySnapshot.from_json(path.read_text())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sts2-tas")
    subcommands = parser.add_subparsers(required=True)
    _add_path_command(subcommands, "bridge-smoke", "fixture", _bridge_smoke)
    _add_path_command(subcommands, "env-step", "snapshot", _env_step).add_argument("--action-index", type=int, required=True)
    collect = _add_path_command(subcommands, "collect-demo", "snapshot", _collect_demo)
    collect.add_argument("--output", type=Path, required=True)
    train_bc = subcommands.add_parser("train-bc")
    train_bc.add_argument("--dataset", type=Path, required=True)
    train_bc.add_argument("--model", type=Path, required=True)
    train_bc.set_defaults(func=_train_bc)
    train_ppo = subcommands.add_parser("train-ppo")
    train_ppo.add_argument("--dataset", type=Path, required=True)
    train_ppo.add_argument("--model", type=Path, required=True)
    train_ppo.add_argument("--timesteps", type=int, default=128)
    train_ppo.set_defaults(func=_train_ppo)
    evaluate = subcommands.add_parser("evaluate-policy")
    evaluate.add_argument("--dataset", type=Path, required=True)
    evaluate.add_argument("--model", type=Path, required=True)
    evaluate.set_defaults(func=_evaluate_policy)
    act = subcommands.add_parser("act")
    act.add_argument("--action-json", required=True)
    act.add_argument("--window-title", default="Slay the Spire 2")
    act.add_argument("--execute", action="store_true")
    act.set_defaults(func=_act)
    run_local = _add_path_command(subcommands, "run-local", "snapshot", _run_local)
    run_local.add_argument("--episodes", type=int, default=1)
    run_local.add_argument("--output", type=Path, required=True)
    return parser


def _add_path_command(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    path_name: str,
    func: object,
) -> argparse.ArgumentParser:
    command = subcommands.add_parser(name)
    command.add_argument(f"--{path_name}", type=Path, required=True)
    command.set_defaults(func=func)
    return command


if __name__ == "__main__":
    raise SystemExit(main())
