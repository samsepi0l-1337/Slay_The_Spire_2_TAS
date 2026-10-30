import json
import os
import socket
import threading
from io import StringIO
from pathlib import Path

import pytest

from sts2_tas.cli import main
from sts2_tas.live import (
    _connect_pipe,
    command_sender,
    connect_transport,
    frame_stream,
)
from sts2_tas.telemetry_client import TelemetryFrameReader
from sts2_tas.telemetry_schema import MacroAction, TelemetrySnapshot

FIXTURE = Path(__file__).parent / "fixtures" / "telemetry-combat.json"


def load_snapshot() -> TelemetrySnapshot:
    return TelemetrySnapshot.from_json(FIXTURE.read_text())


def test_telemetry_frame_reader_accepts_utf8_bom() -> None:
    snapshot = load_snapshot()
    payload = "\ufeff" + json.dumps({"sequence": 1, "payload": snapshot.to_dict()})
    assert TelemetryFrameReader().accept_json(payload).sequence == 1


def test_frame_stream_skips_invalid_snapshots() -> None:
    snapshot = load_snapshot()
    bad = json.dumps({"sequence": 1, "payload": {**snapshot.to_dict(), "valid_actions": [], "phase": "combat"}})
    good = json.dumps({"sequence": 2, "payload": snapshot.to_dict()})
    frames = list(frame_stream(StringIO(bad + "\n" + good + "\n")))
    assert len(frames) == 1
    assert frames[0].phase == "combat"


def test_frame_stream_and_command_sender_round_trip() -> None:
    snapshot = load_snapshot()
    reader = StringIO(json.dumps({"sequence": 1, "payload": snapshot.to_dict()}) + "\n\n")
    writer = StringIO()

    frames = list(frame_stream(reader))
    assert frames[0].phase == "combat"
    assert command_sender(writer, execute=False) is None
    sender = command_sender(writer, execute=True)
    assert sender is not None
    sender(MacroAction("end_turn", {}), snapshot.screen_id, snapshot.seed)
    assert json.loads(writer.getvalue())["action"]["action_type"] == "end_turn"


def test_connect_transport_tcp_and_rejects_unknown_and_posix_pipes() -> None:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    def serve() -> None:
        conn, _ = listener.accept()
        conn.sendall(b"ok\n")
        conn.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    reader, writer = connect_transport(f"tcp:127.0.0.1:{port}")
    assert reader.readline() == "ok\n"
    writer.close()
    reader.close()
    listener.close()

    with pytest.raises(ValueError, match="unsupported transport"):
        connect_transport("udp:x")
    with pytest.raises(ValueError, match="named pipes require Windows"):
        _connect_pipe("sts2-tas", 1.0, platform="posix")
    if os.name == "nt":
        with pytest.raises(OSError):
            connect_transport("pipe:sts2-tas-missing", timeout_s=0.2)
    else:
        with pytest.raises(ValueError, match="named pipes require Windows"):
            connect_transport("pipe:sts2-tas")


def test_connect_pipe_retries_then_succeeds_and_times_out(tmp_path: Path) -> None:
    handle = (tmp_path / "pipe.txt").open("w+", encoding="utf-8")
    attempts = {"n": 0}

    def opener(path: str, *args: object, **kwargs: object):
        del path, args, kwargs
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise OSError("busy")
        return handle

    reader, writer = _connect_pipe(
        "sts2-tas", 1.0, platform="nt", opener=opener, sleeper=lambda _: None, clock=lambda: 0.0
    )
    assert reader is handle
    assert writer is handle

    def fail(*args: object, **kwargs: object):
        del args, kwargs
        raise OSError("missing")

    ticks = iter([0.0, 0.5, 1.0])
    with pytest.raises(OSError, match="missing"):
        _connect_pipe("sts2-tas", 1.0, platform="nt", opener=fail, sleeper=lambda _: None, clock=lambda: next(ticks))


def test_run_live_cli_over_tcp(tmp_path: Path, capsys) -> None:
    snapshot = load_snapshot()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    payload = json.dumps({"sequence": 1, "payload": snapshot.to_dict()}) + "\n"

    received = []

    def serve() -> None:
        conn, _ = listener.accept()
        conn.sendall(payload.encode("utf-8"))
        # Match transport startup budget while Torch initializes the first policy.
        conn.settimeout(30)
        try:
            received.append(json.loads(conn.recv(4096).decode("utf-8")))
        except OSError:
            pass
        conn.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    model = tmp_path / "qstar.json"
    output = tmp_path / "live.jsonl"
    assert (
        main(
            [
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
                "2",
                "--until-clear",
                "--command-delay",
                "0",
                "--command-cooldown",
                "0",
                "--execute",
            ]
        )
        == 0
    )
    listener.close()
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert received[0]["expected_screen_id"] == snapshot.screen_id
    result = json.loads(capsys.readouterr().out)
    assert result["algorithm"] == "qstar-live"
    assert result["commands"] == 1


def test_tcp_close_streams_releases_connection_end_to_end():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    reader, writer = connect_transport(f"tcp:127.0.0.1:{listener.getsockname()[1]}")
    peer, _ = listener.accept()
    peer.settimeout(1)
    try:
        writer.write("round-trip\n")
        writer.flush()
        assert peer.recv(4096) == b"round-trip\n"
        writer.close()
        reader.close()
        assert peer.recv(4096) == b""
    finally:
        writer.close()
        reader.close()
        peer.close()
        listener.close()


def test_bracketed_ipv6_transport_round_trip():
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as listener:
        listener.bind(("::1", 0))
        listener.listen(1)
        reader, writer = connect_transport(f"tcp:[::1]:{listener.getsockname()[1]}")
        peer, _ = listener.accept()
        with peer, reader, writer:
            peer.sendall(b"ipv6-loopback\n")
            assert reader.readline() == "ipv6-loopback\n"
