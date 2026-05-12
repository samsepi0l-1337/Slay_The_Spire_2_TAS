from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from PIL import Image

Box = tuple[int, int, int, int]
PixelPredicate = Callable[[tuple[int, int, int]], bool]


class DetectionKind(str, Enum):
    CARD_REWARD = "card_reward"
    RELIC_CHOICE = "relic_choice"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ScreenDetection:
    kind: DetectionKind
    option_boxes: list[Box]
    skip_box: Box | None


def detect_screen(image_path: Path) -> ScreenDetection:
    image = Image.open(image_path).convert("RGB")
    card_boxes = _components(image, _is_card_blue)
    relic_boxes = _components(image, _is_relic_gold)
    skip_boxes = _components(image, _is_skip_gray)

    if len(card_boxes) >= 3 and skip_boxes:
        return ScreenDetection(DetectionKind.CARD_REWARD, card_boxes[:3], skip_boxes[0])
    if relic_boxes:
        return ScreenDetection(DetectionKind.RELIC_CHOICE, relic_boxes, None)
    return ScreenDetection(DetectionKind.UNKNOWN, [], None)


def _components(image: Image.Image, predicate: PixelPredicate) -> list[Box]:
    width, height = image.size
    visited: set[tuple[int, int]] = set()
    boxes: list[Box] = []
    for y in range(height):
        for x in range(width):
            if (x, y) in visited or not predicate(image.getpixel((x, y))):
                continue
            boxes.append(_flood_box(image, x, y, predicate, visited))
    return sorted((box for box in boxes if _area(box) >= 900), key=lambda box: (box[0], box[1]))


def _flood_box(
    image: Image.Image,
    start_x: int,
    start_y: int,
    predicate: PixelPredicate,
    visited: set[tuple[int, int]],
) -> Box:
    width, height = image.size
    stack = [(start_x, start_y)]
    min_x = max_x = start_x
    min_y = max_y = start_y
    while stack:
        x, y = stack.pop()
        if (x, y) in visited or x < 0 or y < 0 or x >= width or y >= height:
            continue
        visited.add((x, y))
        if not predicate(image.getpixel((x, y))):
            continue
        min_x, max_x = min(min_x, x), max(max_x, x)
        min_y, max_y = min(min_y, y), max(max_y, y)
        stack.extend([(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)])
    return (min_x, min_y, max_x + 1, max_y + 1)


def _area(box: Box) -> int:
    return (box[2] - box[0]) * (box[3] - box[1])


def _is_card_blue(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return 35 <= red <= 70 and 70 <= green <= 115 and 145 <= blue <= 200


def _is_relic_gold(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return 160 <= red <= 210 and 115 <= green <= 165 and 30 <= blue <= 75


def _is_skip_gray(pixel: tuple[int, int, int]) -> bool:
    red, green, blue = pixel
    return 70 <= red <= 105 and 70 <= green <= 105 and 70 <= blue <= 105
