"""Exercise installed CLI processes and the real C# fixture producer."""

import json
import queue
import socket
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data/fixtures/telemetry-combat.json"
PROJECT = ROOT / "bridge/Sts2TelemetryBridge/Sts2TelemetryBridge.csproj"


def test_fixture_cli_pipeline(tmp_path: Path) -> None:
    def run(*args: str) -> dict:
        result = subprocess.run(
            [sys.executable, "-m", "sts2_tas.cli", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        return json.loads(result.stdout)

    assert run("bridge-smoke", "--fixture", str(FIXTURE))["valid_actions"] == 3
    dataset, model, qstar, log = (tmp_path / name for name in ("demo.jsonl", "bc.json", "qstar.json", "run.jsonl"))
    run("collect-demo", "--snapshot", str(FIXTURE), "--output", str(dataset))
    assert json.loads(dataset.read_text())["chosen_action"]["action_type"] == "play_card"
    run("train-bc", "--dataset", str(dataset), "--model", str(model))
    assert run("evaluate-policy", "--dataset", str(dataset), "--model", str(model))["accuracy"] == 1.0
    result = run(
        "run-qstar", "--snapshot", str(FIXTURE), "--model", str(qstar), "--output", str(log), "--search-depth", "1"
    )
    assert result["transitions"] > 0
    assert model.is_file() and qstar.is_file()
    assert all(
        json.loads(line)["chosen_action"]["action_type"] in {"play_card", "end_turn"}
        for line in log.read_text().splitlines()
    )


def test_cli_subprocess_invalid_input_has_nonzero_exit(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "sts2_tas.cli", "bridge-smoke", "--fixture", str(tmp_path / "missing.json")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert "missing.json" in result.stderr
    assert "Traceback" not in result.stderr


def test_csharp_fixture_producer_to_python_live_cli(tmp_path: Path) -> None:
    subprocess.run(["dotnet", "build", str(PROJECT), "-c", "Release"], cwd=ROOT, check=True, timeout=120)
    dll = PROJECT.parent / "bin/Release/net8.0/Sts2TelemetryBridge.dll"
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    server = subprocess.Popen(
        ["dotnet", str(dll), "pipe-serve", "--fixture", str(FIXTURE), "--listen", f"127.0.0.1:{port}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    ready = queue.Queue()
    thread = threading.Thread(target=lambda: ready.put(server.stdout.readline()), daemon=True)
    thread.start()
    model, output = tmp_path / "live.json", tmp_path / "live.jsonl"
    try:
        assert json.loads(ready.get(timeout=15))["transport"] == "tcp"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "sts2_tas.cli",
                "run-live",
                "--transport",
                f"tcp:127.0.0.1:{port}",
                "--model",
                str(model),
                "--output",
                str(output),
                "--search-depth",
                "1",
                "--max-steps",
                "1",
                "--execute",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        summary = json.loads(result.stdout)
        assert summary["commands"] == summary["transitions"] == 1
        assert model.is_file()
        assert json.loads(output.read_text())["result"] == "live"
        stdout, stderr = server.communicate(timeout=15)
        assert server.returncode == 0, (stdout, stderr)
    finally:
        if server.poll() is None:
            server.kill()
            server.communicate(timeout=15)
        thread.join(timeout=1)
