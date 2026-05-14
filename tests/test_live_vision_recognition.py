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
            _token("Bash", (1270, 260, 1450, 330)),
            _token("Skip", (880, 930, 1040, 990)),
        ]
    )

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / "screen.png"), ocr_provider=provider)

    assert [(option.id, option.name, option.kind) for option in parsed.options] == [
        ("strike", "Strike", "card"),
        ("defend", "Defend", "card"),
        ("bash", "Bash", "card"),
        ("skip", "Skip", "skip"),
    ]


def test_parse_ocr_screen_matches_korean_card_catalog(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            _token("타격", (250, 260, 430, 330)),
            _token("수비", (760, 260, 940, 330)),
            _token("강타", (1270, 260, 1450, 330)),
            _token("넘기기", (880, 930, 1040, 990)),
        ]
    )

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / "screen.png"), ocr_provider=provider)

    assert [(option.id, option.name, option.kind) for option in parsed.options] == [
        ("strike", "Strike", "card"),
        ("defend", "Defend", "card"),
        ("bash", "Bash", "card"),
        ("skip", "Skip", "skip"),
    ]


def test_parse_ocr_screen_scales_reward_layout_from_reference_resolution(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            _token("Strike", (125, 130, 215, 165)),
            _token("Defend", (380, 130, 470, 165)),
            _token("Bash", (635, 130, 725, 165)),
            _token("Skip", (440, 465, 520, 495)),
        ]
    )

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / "half.png", size=(960, 540)), ocr_provider=provider)

    assert [option.id for option in parsed.options] == ["strike", "defend", "bash", "skip"]


def test_parse_ocr_screen_rejects_partial_card_reward_ocr(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            _token("Strike", (250, 260, 430, 330)),
            _token("Skip", (880, 930, 1040, 990)),
        ]
    )

    with pytest.raises(ValueError, match="unknown OCR screen layout"):
        recognition.parse_ocr_screen(_blank_screen(tmp_path / "screen.png"), ocr_provider=provider)


def test_parse_ocr_screen_disambiguates_duplicate_card_slots(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            _token("Strike", (250, 260, 430, 330)),
            _token("Strike", (760, 260, 940, 330)),
            _token("Strike", (1270, 260, 1450, 330)),
            _token("Skip", (880, 930, 1040, 990)),
        ]
    )

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / "screen.png"), ocr_provider=provider)

    assert [option.id for option in parsed.options] == ["strike_1", "strike_2", "strike_3", "skip"]


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
                "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
                "5\t1\t1\t1\t1\t1\t250\t260\t180\t70\t99.0\tStrike\n"
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


def test_tesseract_tsv_parser_adds_multiword_line_tokens() -> None:
    tokens = recognition._tokens_from_tsv(
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t760\t420\t90\t80\t96.0\tBurning\n"
        "5\t1\t1\t1\t1\t2\t860\t420\t80\t80\t94.0\tBlood\n"
    )

    assert recognition.OcrToken("Burning Blood", (760, 420, 940, 500), 0.95) in tokens


def test_tesseract_tsv_parser_splits_adjacent_multiword_options() -> None:
    tokens = recognition._tokens_from_tsv(
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t300\t420\t90\t80\t96.0\tBurning\n"
        "5\t1\t1\t1\t1\t2\t400\t420\t80\t80\t94.0\tBlood\n"
        "5\t1\t1\t1\t1\t3\t900\t420\t70\t80\t92.0\tTiny\n"
        "5\t1\t1\t1\t1\t4\t980\t420\t90\t80\t90.0\tHouse\n"
    )

    assert recognition.OcrToken("Burning Blood", (300, 420, 480, 500), 0.95) in tokens
    assert recognition.OcrToken("Tiny House", (900, 420, 1070, 500), 0.91) in tokens
    assert recognition.OcrToken("Burning Blood Tiny House", (300, 420, 1070, 500), 0.93) not in tokens


def test_parse_ocr_screen_matches_adjacent_multiword_relics_from_one_tsv_line(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        recognition._tokens_from_tsv(
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t300\t420\t90\t80\t96.0\tBurning\n"
            "5\t1\t1\t1\t1\t2\t400\t420\t80\t80\t94.0\tBlood\n"
            "5\t1\t1\t1\t1\t3\t900\t420\t70\t80\t92.0\tTiny\n"
            "5\t1\t1\t1\t1\t4\t980\t420\t90\t80\t90.0\tHouse\n"
        )
    )

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / "screen.png"), ocr_provider=provider)

    assert parsed.kind == "relic_choice"
    assert [option.id for option in parsed.options] == ["burning_blood", "tiny_house"]


def test_parse_ocr_screen_accepts_combat_state_without_reward_options(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            _token("HP 65/80", (80, 930, 220, 980)),
            _token("Energy 3/3", (420, 910, 540, 970)),
            _token("Hand Strike cost 1 attack", (250, 820, 430, 1010)),
            _token("Monster Jaw Worm 30/44 block 3 attack 7x1", (1270, 260, 1560, 570)),
        ]
    )

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / "combat.png"), ocr_provider=provider)

    assert parsed.kind == "combat"
    assert parsed.state_payload["player"]["hp"] == 65
    assert parsed.state_payload["cards"][0]["instance_id"] == "hand-0-strike"
    assert parsed.state_boxes["monster:jaw_worm:0"] == (1270, 260, 1560, 570)


def test_parse_ocr_screen_accepts_map_state_without_reward_options(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            _token(
                "Path node-a elite depth 1 elites 1 rests 0 shops 0 events 1 boss 5 forced",
                (700, 230, 820, 350),
            )
        ]
    )

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / "map.png"), ocr_provider=provider)

    assert parsed.kind == "map"
    assert parsed.state_payload["path_candidates"][0]["node_type"] == "elite"


def test_tesseract_tsv_parser_accepts_empty_output() -> None:
    assert recognition._tokens_from_tsv("") == []
