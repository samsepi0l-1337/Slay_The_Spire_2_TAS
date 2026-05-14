from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .schema import Box


@dataclass(frozen=True)
class RegionCalibration:
    reference_resolution: tuple[int, int]
    regions: dict[str, tuple[Box, ...]]

    def scaled_regions(self, name: str, resolution: tuple[int, int]) -> tuple[Box, ...]:
        return tuple(_scale_box(box, self.reference_resolution, resolution) for box in self.regions.get(name, ()))

    def contains_center(self, name: str, box: Box, resolution: tuple[int, int]) -> bool:
        center_x = (box[0] + box[2]) / 2
        center_y = (box[1] + box[3]) / 2
        return any(left <= center_x <= right and top <= center_y <= bottom for left, top, right, bottom in self.scaled_regions(name, resolution))


def load_region_calibration(path: Path) -> RegionCalibration:
    payload = json.loads(path.read_text(encoding="utf-8"))
    reference = tuple(payload["reference_resolution"])
    regions = {
        name: tuple(tuple(box) for box in boxes)
        for name, boxes in payload["regions"].items()
    }
    return RegionCalibration(reference_resolution=reference, regions=regions)


def _scale_box(box: Box, reference: tuple[int, int], resolution: tuple[int, int]) -> Box:
    ref_width, ref_height = reference
    width, height = resolution
    return (
        round(box[0] * width / ref_width),
        round(box[1] * height / ref_height),
        round(box[2] * width / ref_width),
        round(box[3] * height / ref_height),
    )
