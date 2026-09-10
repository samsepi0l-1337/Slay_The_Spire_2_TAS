import json
from pathlib import Path

path = Path("models/qstar-live.jsonl")
with path.open("rb") as handle:
    handle.seek(0, 2)
    size = handle.tell()
    handle.seek(max(size - 20000, 0))
    line = handle.read().decode("utf-8", errors="replace").splitlines()[-1]
data = json.loads(line)
print("chosen", data.get("chosen_action"))
print("phase", data.get("phase"), "floor", data.get("floor"))
state = data.get("state") or {}
print("screen", state.get("screen_id"), "player", state.get("player"))
print("enemies", state.get("enemies"))
print("hand", state.get("hand"))
print("valid", state.get("valid_actions"))
