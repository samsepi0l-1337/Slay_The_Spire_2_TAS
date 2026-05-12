from pathlib import Path

from PIL import Image, ImageDraw

from sts2_tas.recognition import DetectionKind, detect_screen


def _card_reward_image(path: Path) -> Path:
    image = Image.new("RGB", (900, 600), (15, 18, 24))
    draw = ImageDraw.Draw(image)
    for left in (120, 350, 580):
        draw.rectangle((left, 120, left + 150, 360), fill=(48, 90, 170))
    draw.rectangle((380, 500, 520, 550), fill=(88, 88, 88))
    image.save(path)
    return path


def _relic_choice_image(path: Path) -> Path:
    image = Image.new("RGB", (900, 600), (15, 18, 24))
    draw = ImageDraw.Draw(image)
    for left in (260, 420, 580):
        draw.rectangle((left, 220, left + 80, 300), fill=(185, 142, 50))
    image.save(path)
    return path


def test_detects_card_reward_fixture_with_skip_button(tmp_path: Path) -> None:
    detection = detect_screen(_card_reward_image(tmp_path / "card.png"))

    assert detection.kind is DetectionKind.CARD_REWARD
    assert len(detection.option_boxes) == 3
    assert detection.skip_box is not None


def test_detects_relic_choice_fixture(tmp_path: Path) -> None:
    detection = detect_screen(_relic_choice_image(tmp_path / "relic.png"))

    assert detection.kind is DetectionKind.RELIC_CHOICE
    assert len(detection.option_boxes) == 3
    assert detection.skip_box is None


def test_unknown_fixture_is_stable(tmp_path: Path) -> None:
    image_path = tmp_path / "unknown.png"
    Image.new("RGB", (320, 200), (15, 18, 24)).save(image_path)

    first = detect_screen(image_path)
    second = detect_screen(image_path)

    assert first == second
    assert first.kind is DetectionKind.UNKNOWN
