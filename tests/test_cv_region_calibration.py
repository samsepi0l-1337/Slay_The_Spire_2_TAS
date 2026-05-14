import json
from pathlib import Path

from PIL import Image, ImageDraw

from sts2_tas import cli
from sts2_tas.cv_calibration import load_region_calibration
from sts2_tas.recognition import DetectionKind, FakeOcrProvider, OcrToken, detect_screen, parse_ocr_screen


def _screen(path: Path, *, size: tuple[int, int] = (1000, 600)) -> Path:
    Image.new("RGB", size, (15, 18, 24)).save(path)
    return path


def _calibration(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "reference_resolution": [1000, 600],
                "regions": {
                    "card": [[850, 70, 990, 190], [20, 10, 170, 110], [420, 310, 580, 440]],
                    "skip": [[40, 510, 210, 570]],
                    "relic": [[320, 220, 680, 360]],
                    "menu": [[0, 0, 1000, 600]],
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_parse_ocr_screen_uses_calibrated_regions_instead_of_default_layout(tmp_path: Path) -> None:
    calibration = load_region_calibration(_calibration(tmp_path / "regions.json"))
    provider = FakeOcrProvider(
        [
            OcrToken("Strike", (880, 90, 960, 150), 0.99),
            OcrToken("Defend", (40, 20, 140, 80), 0.99),
            OcrToken("Bash", (450, 330, 550, 390), 0.99),
            OcrToken("Skip", (70, 520, 190, 560), 0.99),
        ]
    )

    parsed = parse_ocr_screen(_screen(tmp_path / "screen.png"), provider, calibration=calibration)

    assert parsed.kind == "card_reward"
    assert [option.id for option in parsed.options] == ["defend", "bash", "strike", "skip"]


def test_detect_screen_uses_calibrated_cv_regions_to_ignore_decoy_components(tmp_path: Path) -> None:
    image = Image.new("RGB", (1000, 600), (15, 18, 24))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 200, 120, 330), fill=(48, 90, 170))
    draw.rectangle((850, 70, 990, 190), fill=(48, 90, 170))
    draw.rectangle((20, 10, 170, 110), fill=(48, 90, 170))
    draw.rectangle((420, 310, 580, 440), fill=(48, 90, 170))
    draw.rectangle((40, 510, 210, 570), fill=(88, 88, 88))
    image_path = tmp_path / "cv.png"
    image.save(image_path)

    detection = detect_screen(image_path, calibration=load_region_calibration(_calibration(tmp_path / "regions.json")))

    assert detection.kind is DetectionKind.CARD_REWARD
    assert detection.option_boxes == [(20, 10, 171, 111), (420, 310, 581, 441), (850, 70, 991, 191)]
    assert detection.skip_box == (40, 510, 211, 571)


def test_cli_parse_screen_accepts_region_calibration_file(tmp_path: Path) -> None:
    screenshot = _screen(tmp_path / "screen.png")
    fixture = tmp_path / "ocr.json"
    output = tmp_path / "parsed.json"
    fixture.write_text(
        json.dumps(
            [
                {"text": "Strike", "box": [880, 90, 960, 150], "confidence": 0.99},
                {"text": "Defend", "box": [40, 20, 140, 80], "confidence": 0.99},
                {"text": "Bash", "box": [450, 330, 550, 390], "confidence": 0.99},
                {"text": "Skip", "box": [70, 520, 190, 560], "confidence": 0.99},
            ]
        ),
        encoding="utf-8",
    )

    exit_code = cli.main(
        [
            "parse-screen",
            "--screenshot",
            str(screenshot),
            "--ocr-fixture",
            str(fixture),
            "--region-calibration",
            str(_calibration(tmp_path / "regions.json")),
            "--out",
            str(output),
        ]
    )

    parsed = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert parsed["kind"] == "card_reward"
