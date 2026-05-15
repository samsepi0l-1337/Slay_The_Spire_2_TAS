"""One-off remote verification: fixtures + live-learn-loop --max-steps 10. Not imported by package.

Set STS2_EXE to a full path of sts2-tas.exe to exercise the frozen build; otherwise uses .venv python -m sts2_tas.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image


def main() -> int:
    wd = Path(r"C:\Users\steep\sts2-tas-run")
    out = wd / "remote-smoke" / "verify-loop10"
    out.mkdir(parents=True, exist_ok=True)
    screen = out / "screen.png"
    Image.new("RGB", (1920, 1080), (15, 18, 24)).save(screen)

    def tok(t: str, box: tuple[int, int, int, int]) -> dict[str, object]:
        return {"text": t, "box": list(box), "confidence": 0.99}

    frame = [
        tok("Strike", (250, 260, 430, 330)),
        tok("Defend", (760, 260, 940, 330)),
        tok("Bash", (1270, 260, 1450, 330)),
        tok("Skip", (880, 930, 1040, 990)),
    ]
    frames = [frame for _ in range(10)]
    ocr = out / "ocr-seq.json"
    ocr.write_text(json.dumps(frames), encoding="utf-8")

    py = wd / ".venv" / "Scripts" / "python.exe"
    sts2_exe = os.environ.get("STS2_EXE", "").strip()
    subcmd = [
        "live-learn-loop",
        "--capture-fixture",
        str(screen),
        "--ocr-fixture-sequence",
        str(ocr),
        "--dataset",
        str(out / "dataset.jsonl"),
        "--policy",
        "first-legal",
        "--input-log",
        str(out / "inputs.jsonl"),
        "--max-steps",
        "10",
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
    if sts2_exe:
        cmd = [sts2_exe, *subcmd]
    else:
        cmd = [str(py), "-m", "sts2_tas", *subcmd]
    proc = subprocess.run(cmd, cwd=wd, check=False)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
