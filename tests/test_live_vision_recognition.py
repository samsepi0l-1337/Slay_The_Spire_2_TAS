from pathlib import Path

from PIL import Image
import pytest

from sts2_tas import recognition


def _blank_screen(path: Path, size: tuple[int, int] = (1920, 1080)) -> Path:
    Image.new("RGB", size, (15, 18, 24)).save(path)
    return path


def _token(text: str, box: tuple[int, int, int, int]) -> object:
    return recognition.OcrToken(text=text, box=box, confidence=0.99)


def test_parse_ocr_screen_matches_english_card_catalog(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            _token("Strike", (250, 260, 430, 330)),
            _token("Defend", (760, 260, 940, 330)),
            _token("Skip", (880, 930, 1040, 990)),
        ]
    )

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / "screen.png"), ocr_provider=provider)

    assert [(option.id, option.name, option.kind) for option in parsed.options] == [
        ("strike", "Strike", "card"),
        ("defend", "Defend", "card"),
        ("skip", "Skip", "skip"),
    ]


def test_parse_ocr_screen_matches_korean_card_catalog(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            _token("타격", (250, 260, 430, 330)),
            _token("수비", (760, 260, 940, 330)),
            _token("넘기기", (880, 930, 1040, 990)),
        ]
    )

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / "screen.png"), ocr_provider=provider)

    assert [(option.id, option.name, option.kind) for option in parsed.options] == [
        ("strike", "Strike", "card"),
        ("defend", "Defend", "card"),
        ("skip", "Skip", "skip"),
    ]


def test_parse_ocr_screen_scales_reward_layout_from_reference_resolution(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            _token("Strike", (125, 130, 215, 165)),
            _token("Defend", (380, 130, 470, 165)),
            _token("Skip", (440, 465, 520, 495)),
        ]
    )

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / "half.png", size=(960, 540)), ocr_provider=provider)

    assert [option.id for option in parsed.options] == ["strike", "defend", "skip"]


def test_parse_ocr_screen_rejects_unknown_layout(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider([_token("Strike", (10, 10, 110, 50))])

    with pytest.raises(ValueError, match="unknown OCR screen layout"):
        recognition.parse_ocr_screen(_blank_screen(tmp_path / "screen.png"), ocr_provider=provider)


def test_parse_ocr_screen_matches_relic_choice(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider([_token("Burning Blood", (760, 420, 980, 500))])

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / "screen.png"), ocr_provider=provider)

    assert parsed.kind == "relic_choice"
    assert [(option.id, option.name, option.kind) for option in parsed.options] == [
        ("burning_blood", "Burning Blood", "relic")
    ]


def test_parse_ocr_screen_ignores_unknown_catalog_text(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            _token("Mystery", (250, 260, 430, 330)),
            _token("Skip", (880, 930, 1040, 990)),
        ]
    )

    with pytest.raises(ValueError, match="unknown OCR screen layout"):
        recognition.parse_ocr_screen(_blank_screen(tmp_path / "screen.png"), ocr_provider=provider)


def test_tesseract_provider_parses_cli_tsv(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_run(command, *, capture_output, check, text):
        calls.append((command, capture_output, check, text))

        class Result:
            stdout = (
                "level\tleft\ttop\twidth\theight\tconf\ttext\n"
                "5\t250\t260\t180\t70\t99.0\tStrike\n"
            )

        return Result()

    monkeypatch.setattr(recognition.subprocess, "run", fake_run)

    provider = recognition.TesseractOcrProvider(language="eng+kor")
    tokens = provider.recognize(_blank_screen(tmp_path / "screen.png"))

    assert calls == [
        (
            ["tesseract", str(tmp_path / "screen.png"), "stdout", "-l", "eng+kor", "tsv"],
            True,
            True,
            True,
        )
    ]
    assert tokens == [_token("Strike", (250, 260, 430, 330))]


def test_tesseract_tsv_parser_accepts_empty_output() -> None:
    assert recognition._tokens_from_tsv("") == []
