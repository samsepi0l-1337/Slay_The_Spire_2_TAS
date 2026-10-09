"""Run the real fixture executable; no game assemblies or deployment required."""

import json
import socket
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "bridge/Sts2TelemetryBridge/Sts2TelemetryBridge.csproj"
DLL = PROJECT.parent / "bin/Release/net8.0/Sts2TelemetryBridge.dll"
FIXTURE = ROOT / "data/fixtures/telemetry-combat.json"


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            ["dotnet", "build", str(PROJECT), "-c", "Release"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    def test_invalid_configuration_fails_closed(self):
        for listen in ["invalid", "127.0.0.1:no", "0.0.0.0:28771", "127.0.0.1:0"]:
            with self.subTest(listen=listen):
                result = subprocess.run(
                    [
                        "dotnet",
                        str(DLL),
                        "pipe-serve",
                        "--fixture",
                        str(FIXTURE),
                        "--listen",
                        listen,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("pipe-serve", result.stderr)

    def test_fixture_round_trip_and_rejection(self):
        rejected = [
            ({"schema_version": 2}, "schema_version"),
            ({"schema_version": True}, "schema_version"),
            ({"run_id": ""}, "run_id"),
            ({"run_id": "stale-run"}, "run_id"),
            ({"expected_screen_id": "stale"}, "expected_screen_id"),
            ({"action": {"action_type": "unknown", "args": {}}}, "action_type"),
            ({"action": {"action_type": "play_card", "args": {}}}, "hand_slot"),
            (
                {"action": {"action_type": "play_card", "args": {"hand_slot": -1}}},
                "nonnegative",
            ),
            (
                {"action": {"action_type": "play_card", "args": {"hand_slot": True}}},
                "integer",
            ),
            (
                {"action": {"action_type": "play_card", "args": {"hand_slot": 1.5}}},
                "integer",
            ),
            (
                {"action": {"action_type": "play_card", "args": {"hand_slot": 99}}},
                "legal",
            ),
            (
                {"action": {"action_type": "end_turn", "args": {"hand_slot": 0}}},
                "unexpected",
            ),
            ({"action": {"action_type": "end_turn", "args": []}}, "objects"),
        ]
        for replacement, error in rejected:
            with self.subTest(replacement=replacement):
                self.round_trip(replacement, error)

    def round_trip(self, replacement, error):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        process = subprocess.Popen(
            [
                "dotnet",
                str(DLL),
                "pipe-serve",
                "--fixture",
                str(FIXTURE),
                "--listen",
                f"127.0.0.1:{port}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            ready = json.loads(process.stdout.readline())
            self.assertEqual(ready["transport"], "tcp")
            with (
                socket.create_connection(("127.0.0.1", port), timeout=5) as peer,
                peer.makefile("rw", encoding="utf-8") as stream,
            ):
                first = json.loads(stream.readline())
                snapshot = first["payload"]
                command = {
                    "run_id": snapshot.get("extras", {}).get("run_instance_id") or snapshot["seed"],
                    "schema_version": 1,
                    "expected_screen_id": snapshot["screen_id"],
                }
                for index, action in enumerate(snapshot["valid_actions"], start=1):
                    command["action"] = action
                    stream.write(json.dumps(command) + "\n")
                    stream.flush()
                    frame = json.loads(stream.readline())
                    self.assertEqual(frame["sequence"], first["sequence"] + index)
                    self.assertEqual(frame["payload"], snapshot)
                command.update(replacement)
                stream.write(json.dumps(command) + "\n")
                stream.flush()
                self.assertEqual(stream.readline(), "")
            self.assertEqual(process.wait(timeout=5), 2)
            self.assertIn(error, process.stderr.read())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
            process.stderr.close()


if __name__ == "__main__":
    unittest.main()
