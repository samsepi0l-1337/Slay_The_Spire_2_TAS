from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
import subprocess
from typing import Callable, Protocol

from PIL import Image

from .live_state import LiveStateExtraction, extract_live_state
from .schema import OcrResult, ParsedScreen, RecognizedOption

Box = tuple[int, int, int, int]
PixelPredicate = Callable[[tuple[int, int, int]], bool]
OcrToken = OcrResult
REFERENCE_RESOLUTION = (1920, 1080)
MIN_OCR_OPTION_CONFIDENCE = 0.60


class OcrProvider(Protocol):
    def recognize(self, image_path: Path) -> list[OcrToken]:  # pragma: no cover
        ...


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    name: str
    kind: str
    aliases: tuple[str, ...]
    tags: tuple[str, ...] = ()


CATALOG = (
    CatalogEntry("strike", "Strike", "card", ("strike", "\ud0c0\uaca9"), ("attack",)),
    CatalogEntry("defend", "Defend", "card", ("defend", "\uc218\ube44"), ("skill",)),
    CatalogEntry("bash", "Bash", "card", ("bash", "\uac15\ud0c0"), ("attack",)),
    CatalogEntry("burning_blood", "Burning Blood", "relic", ("burning blood", "\ud0c0\uc624\ub974\ub294 \ud53c")),
    CatalogEntry("tiny_house", "Tiny House", "relic", ("tiny house", "\uc791\uc740 \uc9d1")),
    CatalogEntry("skip", "Skip", "skip", ("skip", "\ub118\uae30\uae30")),
    CatalogEntry("single_player", "Single Player", "select_single_player", ("single player", "\uc2f1\uae00 \ud50c\ub808\uc774")),
    CatalogEntry("standard", "Standard", "select_mode", ("standard", "\ud45c\uc900", "\uc77c\ubc18")),
    CatalogEntry("ironclad", "Ironclad", "select_character", ("ironclad", "\uc544\uc774\uc5b8\ud074\ub798\ub4dc")),
    CatalogEntry("new_run", "New Run", "restart_run", ("new run", "play again", "retry", "\uc0c8 \ub7f0", "\ub2e4\uc2dc \uc2dc\uc791")),
)


class DetectionKind(str, Enum):
    CARD_REWARD = "card_reward"
    RELIC_CHOICE = "relic_choice"
    MAIN_MENU = "main_menu"
    MODE_SELECT = "mode_select"
    CHARACTER_SELECT = "character_select"
    VICTORY = "victory"
    GAME_OVER = "game_over"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ScreenDetection:
    kind: DetectionKind
    option_boxes: list[Box]
    skip_box: Box | None


@dataclass(frozen=True)
class FakeOcrProvider:
    tokens: list[OcrToken]

    def recognize(self, image_path: Path) -> list[OcrToken]:
        return self.tokens


@dataclass(frozen=True)
class TesseractOcrProvider:
    language: str = "eng"
    binary: str = "tesseract"

    def recognize(self, image_path: Path) -> list[OcrToken]:
        result = subprocess.run(
            [self.binary, str(image_path), "stdout", "-l", self.language, "tsv"],
            capture_output=True,
            check=True,
            text=True,
        )
        return _tokens_from_tsv(result.stdout)


def parse_ocr_screen(image_path: Path, ocr_provider: OcrProvider) -> ParsedScreen:
    image = Image.open(image_path)
    width, height = image.size
    tokens = ocr_provider.recognize(image_path)
    extraction = extract_live_state(tokens)
    options = [
        option
        for token in tokens
        if (option := _recognized_option(token, (width, height))) is not None
    ]
    non_skip = sorted((option for option in options if option.kind != "skip"), key=lambda option: option.box[0])
    skip = sorted((option for option in options if option.kind == "skip"), key=lambda option: option.box[0])
    cards = [option for option in non_skip if option.kind == "card"]
    terminal_kind = _terminal_kind(tokens)
    if terminal_kind is not None:
        restarts = [option for option in non_skip if option.kind == "restart_run"]
        if restarts:
            return _parsed(terminal_kind.value, _slot_ids(restarts), image_path, (width, height), extraction)
    menu_kind = _menu_kind(non_skip)
    if menu_kind is not None:
        return _parsed(menu_kind.value, _slot_ids(non_skip), image_path, (width, height), extraction)
    if len(cards) == 3 and len(cards) == len(non_skip) and skip:
        return _parsed(
            DetectionKind.CARD_REWARD.value,
            [*_slot_ids(cards), skip[0]],
            image_path,
            (width, height),
            extraction,
        )
    if non_skip and all(option.kind == "relic" for option in non_skip):
        return _parsed(DetectionKind.RELIC_CHOICE.value, _slot_ids(non_skip), image_path, (width, height), extraction)
    if extraction.state_payload.get("path_candidates"):
        return _parsed("map", [], image_path, (width, height), extraction)
    if extraction.state_payload.get("cards") or extraction.state_payload.get("monsters"):
        return _parsed("combat", [], image_path, (width, height), extraction)
    raise ValueError(f"unknown OCR screen layout for {image_path}")


def _parsed(
    kind: str,
    options: list[RecognizedOption],
    image_path: Path,
    resolution: tuple[int, int],
    extraction: LiveStateExtraction,
) -> ParsedScreen:
    return ParsedScreen(
        kind,
        options,
        image_path,
        resolution,
        state_payload=extraction.state_payload,
        state_boxes=extraction.state_boxes,
        missing_fields=extraction.missing_fields,
        unknown_tokens=extraction.unknown_tokens,
    )


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


def _recognized_option(token: OcrToken, resolution: tuple[int, int]) -> RecognizedOption | None:
    if token.confidence < MIN_OCR_OPTION_CONFIDENCE:
        return None
    entry = _catalog_match(token.text)
    if entry is None or not _in_layout_region(token, entry.kind, resolution):
        return None
    return RecognizedOption(
        id=entry.id,
        name=entry.name,
        kind=entry.kind,  # type: ignore[arg-type]
        box=token.box,
        confidence=token.confidence,
        source_text=token.text,
        tags=list(entry.tags),
    )


def _slot_ids(options: list[RecognizedOption]) -> list[RecognizedOption]:
    counts: dict[str, int] = {}
    for option in options:
        counts[option.id] = counts.get(option.id, 0) + 1
    indexes: dict[str, int] = {}
    slotted: list[RecognizedOption] = []
    for option in options:
        if counts[option.id] == 1:
            slotted.append(option)
            continue
        indexes[option.id] = indexes.get(option.id, 0) + 1
        slotted.append(replace(option, id=f"{option.id}_{indexes[option.id]}"))
    return slotted


def _catalog_match(text: str) -> CatalogEntry | None:
    normalized = _normalize_text(text)
    for entry in CATALOG:
        if normalized in {_normalize_text(alias) for alias in entry.aliases}:
            return entry
    return None


def _terminal_kind(tokens: list[OcrToken]) -> DetectionKind | None:
    normalized = {_normalize_text(token.text) for token in tokens}
    if normalized & {"victory", "victory!", "clear", "run clear"}:
        return DetectionKind.VICTORY
    if normalized & {"game over", "defeat", "defeated"}:
        return DetectionKind.GAME_OVER
    return None


def _menu_kind(options: list[RecognizedOption]) -> DetectionKind | None:
    kinds = {option.kind for option in options}
    if "select_single_player" in kinds:
        return DetectionKind.MAIN_MENU
    if "select_mode" in kinds:
        return DetectionKind.MODE_SELECT
    if "select_character" in kinds:
        return DetectionKind.CHARACTER_SELECT
    return None


def _normalize_text(text: str) -> str:
    return " ".join(text.casefold().strip().split())


def _in_layout_region(token: OcrToken, kind: str, resolution: tuple[int, int]) -> bool:
    width, height = resolution
    center_x = (token.box[0] + token.box[2]) / 2 / width
    center_y = (token.box[1] + token.box[3]) / 2 / height
    if kind == "skip":
        return 0.35 <= center_x <= 0.65 and center_y >= 0.75
    if kind == "card":
        return 0.05 <= center_x <= 0.95 and 0.10 <= center_y <= 0.55
    if kind in {"select_single_player", "select_mode", "select_character", "restart_run"}:
        return 0.05 <= center_x <= 0.95 and 0.10 <= center_y <= 0.90
    return 0.05 <= center_x <= 0.95 and 0.10 <= center_y <= 0.70


def _tokens_from_tsv(payload: str) -> list[OcrToken]:
    lines = [line for line in payload.splitlines() if line.strip()]
    if not lines:
        return []
    headers = lines[0].split("\t")
    tokens: list[OcrToken] = []
    line_tokens: dict[tuple[str, str, str, str], list[OcrToken]] = {}
    for line in lines[1:]:
        row = dict(zip(headers, line.split("\t"), strict=False))
        text = row.get("text", "").strip()
        if row.get("level") == "5" and text:
            left = int(row["left"])
            top = int(row["top"])
            width = int(row["width"])
            height = int(row["height"])
            confidence = float(row["conf"])
            token = OcrToken(
                text=text,
                box=(left, top, left + width, top + height),
                confidence=confidence / 100 if confidence > 1 else confidence,
            )
            tokens.append(token)
            key = (
                row.get("page_num", ""),
                row.get("block_num", ""),
                row.get("par_num", ""),
                row.get("line_num", ""),
            )
            if all(key):
                line_tokens.setdefault(key, []).append(token)
    tokens.extend(_compound_line_tokens(line_tokens))
    return tokens


def _compound_line_tokens(line_tokens: dict[tuple[str, str, str, str], list[OcrToken]]) -> list[OcrToken]:
    compounds: list[OcrToken] = []
    for tokens in line_tokens.values():
        if len(tokens) < 2:
            continue
        ordered = sorted(tokens, key=lambda token: token.box[0])
        compounds.extend(_catalog_span_tokens(ordered))
    return compounds


def _catalog_span_tokens(tokens: list[OcrToken]) -> list[OcrToken]:
    compounds: list[OcrToken] = []
    for start in range(len(tokens)):
        for end in range(start + 2, len(tokens) + 1):
            span = tokens[start:end]
            text = " ".join(token.text for token in span)
            if _catalog_match(text) is None:
                continue
            compounds.append(_merge_tokens(span, text))
    return compounds


def _merge_tokens(tokens: list[OcrToken], text: str) -> OcrToken:
    return OcrToken(
        text=text,
        box=(
            min(token.box[0] for token in tokens),
            min(token.box[1] for token in tokens),
            max(token.box[2] for token in tokens),
            max(token.box[3] for token in tokens),
        ),
        confidence=sum(token.confidence for token in tokens) / len(tokens),
    )
