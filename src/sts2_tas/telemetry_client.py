from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, TextIO

from sts2_tas.telemetry_schema import TelemetrySnapshot, ValidationError


@dataclass(frozen=True)
class TelemetryFrame:
    sequence: int
    payload: TelemetrySnapshot


class TelemetryFrameReader:
    def __init__(self) -> None:
        self.last_sequence: int | None = None

    def accept_json(self, text: str) -> TelemetryFrame:
        try:
            frame = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"corrupt frame: {exc.msg}") from exc
        if not isinstance(frame, dict):
            raise ValidationError("frame must be an object")
        sequence = frame.get("sequence")
        if not isinstance(sequence, int):
            raise ValidationError("frame sequence must be an integer")
        if self.last_sequence is not None and sequence == self.last_sequence:
            raise ValidationError(f"duplicate frame sequence: {sequence}")
        if self.last_sequence is not None and sequence < self.last_sequence:
            raise ValidationError(f"out of order frame sequence: {sequence}")
        payload = TelemetrySnapshot.from_dict(frame.get("payload", {}))
        self.last_sequence = sequence
        return TelemetryFrame(sequence, payload)


class TelemetryStreamClient:
    def __init__(self, connect: Callable[[], TextIO]) -> None:
        self._connect = connect
        self._stream: TextIO | None = None
        self._reader = TelemetryFrameReader()
        self.connect_attempts = 0
        self.reconnect_attempts = 0

    def next_frame(self) -> TelemetryFrame:
        while True:
            line = self._current_stream().readline()
            if line == "":
                self._reconnect()
                continue
            if line.strip() == "":
                continue
            return self._reader.accept_json(line)

    def _current_stream(self) -> TextIO:
        if self._stream is None:
            self._stream = self._open_stream()
        return self._stream

    def _reconnect(self) -> None:
        if self._stream is not None:
            self._stream.close()
        self._stream = None
        self.reconnect_attempts += 1

    def _open_stream(self) -> TextIO:
        self.connect_attempts += 1
        return self._connect()
