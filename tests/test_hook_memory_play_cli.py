from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from sts2_tas import cli


def _screen(path: Path) -> Path:
    Image.new("RGB", (1920, 1080), (15, 18, 24)).save(path)
    return path


def _ocr_fixture(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
                {"text": "HP 70 / 80", "box": [20, 20, 160, 60], "confidence": 0.99},
                {"text": "Energy 3", "box": [20, 70, 160, 110], "confidence": 0.99},
                {"text": "Strike", "box": [250, 260, 430, 330], "confidence": 0.99},
                {"text": "Defend", "box": [760, 260, 940, 330], "confidence": 0.99},
                {"text": "Bash", "box": [1270, 260, 1450, 330], "confidence": 0.99},
                {"text": "Skip", "box": [880, 930, 1040, 990], "confidence": 0.99},
            ]
        ),
        encoding="utf-8",
    )
    return path


def _hook_jsonl(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "sts2-hook-canary.v1",
                "event_type": "present_frame",
                "frame_counter": 7,
                "timestamp_utc": "2026-05-15T00:00:00Z",
                "process_id": 1234,
                "target_pid": 1234,
                "session_nonce": "nonce-1",
                "thread_id": 5678,
                "passive_only": True,
                "foreground": True,
                "window": {"process_name": "SlayTheSpire2.exe", "client_width": 1920, "client_height": 1080},
                "capture": {"mode": "hash_only", "frame_hash": "sha256:frame"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _registry(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "signatures": [
                    {
                        "game_version": "0.105.1",
                        "branch": "beta",
                        "binary_signature": "sha256:abc",
                        "offsets": {"player.hp": 16, "player.energy": 24},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _snapshot(path: Path, *, hp: int = 70) -> Path:
    path.write_text(
        json.dumps(
            {
                "game_version": "0.105.1",
                "branch": "beta",
                "binary_signature": "sha256:abc",
                "state_payload": {
                    "player": {
                        "hp": hp,
                        "max_hp": 80,
                        "block": 0,
                        "energy": 3,
                        "turn": 1,
                        "character_resource": {"gold": 0},
                    }
                },
                "target_pid": 1234,
                "target_process": "SlayTheSpire2",
            }
        ),
        encoding="utf-8",
    )
    return path


def _base_args(tmp_path: Path) -> list[str]:
    return [
        "hook-memory-play",
        "--capture-fixture",
        str(_screen(tmp_path / "screen.png")),
        "--ocr-fixture",
        str(_ocr_fixture(tmp_path / "ocr.json")),
        "--hook-jsonl",
        str(_hook_jsonl(tmp_path / "hook.jsonl")),
        "--hook-session-nonce",
        "nonce-1",
        "--hook-target-pid",
        "1234",
        "--memory-registry",
        str(_registry(tmp_path / "registry.json")),
        "--memory-snapshot",
        str(_snapshot(tmp_path / "memory.json")),
        "--memory-critical-fields",
        "player.hp,player.energy",
        "--choice",
        "pick:strike",
        "--input-log",
        str(tmp_path / "inputs.jsonl"),
        "--game-version",
        "0.105.1",
        "--branch",
        "beta",
        "--character",
        "ironclad",
        "--ascension",
        "0",
        "--floor",
        "1",
        "--hp",
        "70",
        "--gold",
        "0",
    ]


def test_hook_memory_play_cross_checked_memory_executes_jsonl_action(tmp_path: Path, capsys) -> None:
    args = [*_base_args(tmp_path), "--execute"]

    assert cli.main(args) == 0

    report = json.loads(capsys.readouterr().out)
    input_row = json.loads((tmp_path / "inputs.jsonl").read_text(encoding="utf-8"))
    assert report["state_source"] == "memory_cross_checked"
    assert report["memory_usable"] is True
    assert report["hook"]["frame_counter"] == 7
    assert report["action"]["success"] is True
    assert report["step"]["state"]["player"]["hp"] == 70
    assert input_row["input_plan"] == {"kind": "click", "x": 340, "y": 295}


def test_hook_memory_play_fails_closed_when_memory_cross_check_mismatches(tmp_path: Path, capsys) -> None:
    args = _base_args(tmp_path)
    snapshot_index = args.index("--memory-snapshot") + 1
    args[snapshot_index] = str(_snapshot(tmp_path / "memory-mismatch.json", hp=69))
    args.append("--execute")

    assert cli.main(args) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["memory_usable"] is False
    assert report["fail_closed_reason"] == "memory_ocr_mismatch"
    assert report["mismatches"] == {"player.hp": [70, 69]}
    assert not (tmp_path / "inputs.jsonl").exists()


def test_hook_memory_play_rejects_empty_hook_stream(tmp_path: Path) -> None:
    hook_path = tmp_path / "empty-hook.jsonl"
    hook_path.write_text("", encoding="utf-8")
    args = _base_args(tmp_path)
    args[args.index("--hook-jsonl") + 1] = str(hook_path)

    try:
        cli.main(args)
    except ValueError as error:
        assert "no events" in str(error)
    else:  # pragma: no cover
        raise AssertionError("expected empty hook stream to fail")


def test_hook_memory_play_rejects_native_backend_without_execute(tmp_path: Path) -> None:
    args = [*_base_args(tmp_path), "--input-backend", "native"]

    try:
        cli.main(args)
    except ValueError as error:
        assert "native input backend requires --execute" in str(error)
    else:  # pragma: no cover
        raise AssertionError("expected native dry-run to fail")


def test_hook_memory_play_rejects_native_execute_without_target_process(tmp_path: Path) -> None:
    args = [*_base_args(tmp_path), "--input-backend", "native", "--execute"]

    try:
        cli.main(args)
    except ValueError as error:
        assert "native input backend requires --target-process" in str(error)
    else:  # pragma: no cover
        raise AssertionError("expected native execute without target-process to fail")


def test_hook_memory_play_rejects_empty_memory_critical_fields(tmp_path: Path) -> None:
    args = _base_args(tmp_path)
    args[args.index("--memory-critical-fields") + 1] = ""

    try:
        cli.main(args)
    except ValueError as error:
        assert "memory-critical-fields" in str(error)
    else:  # pragma: no cover
        raise AssertionError("expected empty critical fields to fail")


def test_hook_memory_play_fails_closed_when_snapshot_pid_mismatches_hook(tmp_path: Path, capsys) -> None:
    snapshot_path = tmp_path / "memory-pid-mismatch.json"
    payload = json.loads(_snapshot(snapshot_path).read_text(encoding="utf-8"))
    payload["target_pid"] = 999
    snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
    args = _base_args(tmp_path)
    args[args.index("--memory-snapshot") + 1] = str(snapshot_path)
    args.append("--execute")

    assert cli.main(args) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["memory_usable"] is False
    assert report["fail_closed_reason"] == "memory_hook_binding_mismatch"
    assert not (tmp_path / "inputs.jsonl").exists()


def test_memory_snapshot_cli_reads_registry_offsets_with_read_only_reader(tmp_path: Path, capsys, monkeypatch) -> None:
    class Reader:
        def __init__(self, pid: int) -> None:
            assert pid == 1234

        def process_identity(self):
            from sts2_tas.memory_play import ProcessIdentity

            return ProcessIdentity(pid=1234, process_name="SlayTheSpire2", executable_path=None, binary_signature="sha256:abc")

        def read_int32(self, address: int) -> int:
            return {16: 70, 24: 3}[address]

        def close(self) -> None:
            return None

    monkeypatch.setattr("sts2_tas.cli.WindowsReadOnlyProcessMemoryReader", Reader)
    out = tmp_path / "snapshot.json"

    assert cli.main(
        [
            "memory-snapshot",
            "--target-process",
            "SlayTheSpire2",
            "--pid",
            "1234",
            "--platform-name",
            "Windows",
            "--memory-registry",
            str(_registry(tmp_path / "registry.json")),
            "--game-version",
            "0.105.1",
            "--branch",
            "beta",
            "--binary-signature",
            "sha256:abc",
            "--out",
            str(out),
        ]
    ) == 0

    report = json.loads(capsys.readouterr().out)
    snapshot = json.loads(out.read_text(encoding="utf-8"))
    assert report == {"access_mode": "read-only", "memory_snapshot": str(out)}
    assert snapshot["target_pid"] == 1234
    assert snapshot["target_process"] == "SlayTheSpire2"
    assert snapshot["state_payload"] == {"player": {"energy": 3, "hp": 70}}
