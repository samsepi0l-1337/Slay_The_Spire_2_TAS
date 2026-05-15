from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .tas_movie import TasMovie

CheckpointFormat = Literal["tas_movie_v1"]


@dataclass(frozen=True)
class TasCheckpoint:
    run_id: str
    movie: TasMovie
    save_path: Path
    save_hash: str
    movie_prefix_length: int
    movie_prefix_hash: str
    screen_hash: str
    state_fingerprint: str
    format: CheckpointFormat = "tas_movie_v1"

    def __post_init__(self) -> None:
        if not self.run_id:
            raise ValueError("run_id is required")
        if self.movie_prefix_length < 0 or self.movie_prefix_length > len(self.movie.frames):
            raise ValueError("movie_prefix_length is out of range")
        if len(self.save_hash) != 64:
            raise ValueError("save_hash must be a sha256 hexdigest")
        if not self.movie_prefix_hash:
            raise ValueError("movie_prefix_hash is required")
        if not self.screen_hash:
            raise ValueError("screen_hash is required")
        if not self.state_fingerprint:
            raise ValueError("state_fingerprint is required")

    @classmethod
    def from_movie_and_save(
        cls,
        *,
        run_id: str,
        movie: TasMovie,
        save_path: Path,
        state_fingerprint: str,
        screen_hash: str,
        movie_prefix_length: int | None = None,
    ) -> TasCheckpoint:
        if movie_prefix_length is None:
            movie_prefix_length = len(movie.frames)
        return cls(
            run_id=run_id,
            movie=movie,
            save_path=save_path,
            save_hash=cls.compute_save_hash(save_path),
            movie_prefix_length=movie_prefix_length,
            movie_prefix_hash=movie.prefix_hash(movie_prefix_length),
            state_fingerprint=state_fingerprint,
            screen_hash=screen_hash,
        )

    @staticmethod
    def compute_save_hash(path: Path) -> str:
        digest = hashlib.sha256()
        digest.update(path.read_bytes())
        return digest.hexdigest()

    def validate_save(self, save_path: Path | None = None) -> bool:
        target = save_path or self.save_path
        try:
            actual = self.compute_save_hash(target)
        except FileNotFoundError:
            return False
        return actual == self.save_hash

    def validate_movie_prefix_hash(self) -> bool:
        return self.movie_prefix_hash == self.movie.prefix_hash(self.movie_prefix_length)

    def validate_screen_state_fingerprints(self) -> bool:
        if self.movie_prefix_length <= 0:
            return False
        checkpoint_frame = self.movie.frames[self.movie_prefix_length - 1]
        return checkpoint_frame.screen_hash == self.screen_hash and checkpoint_frame.state_fingerprint == self.state_fingerprint

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["movie"] = self.movie.to_dict()
        data["save_path"] = str(self.save_path)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TasCheckpoint:
        return cls(
            run_id=str(data["run_id"]),
            movie=TasMovie.from_dict(data["movie"]),
            save_path=Path(data["save_path"]),
            save_hash=str(data["save_hash"]),
            movie_prefix_length=int(data["movie_prefix_length"]),
            movie_prefix_hash=str(data["movie_prefix_hash"]),
            screen_hash=str(data["screen_hash"]),
            state_fingerprint=str(data["state_fingerprint"]),
            format=str(data.get("format", "tas_movie_v1")),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, payload: str) -> TasCheckpoint:
        return cls.from_dict(json.loads(payload))
