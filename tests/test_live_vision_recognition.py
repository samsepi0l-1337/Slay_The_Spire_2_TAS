from pathlib import Path

from PIL import Image
import pytest

from sts2_tas import recognition


def _blank_screen(path: Path, size: tuple[int, int] = (1920, 1080)) -> Path:
    Image.new("RGB", size, (15, 18, 24)).save(path)
    return path


def _neow_choice_screen(path: Path) -> Path:
    image = Image.new("RGB", (1920, 1080), (10, 35, 55))
    pixels = image.load()
    for box in ((470, 740, 1450, 835), (470, 835, 1450, 930), (470, 930, 1450, 1030)):
        for x in range(box[0], box[2]):
            for y in range(box[1], box[3]):
                pixels[x, y] = (18, 105, 140)
    image.save(path)
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


def test_parse_ocr_screen_matches_korean_continue_menu(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider([_token("계속", (700, 650, 850, 720))])

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / "menu.png"), ocr_provider=provider)

    assert parsed.kind == "main_menu"
    assert [(option.id, option.name, option.kind) for option in parsed.options] == [
        ("continue", "Continue", "continue_run")
    ]


def test_parse_ocr_screen_matches_korean_map_legend(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider([_token("범례", (1669, 331, 1739, 374))])

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / "map.png"), ocr_provider=provider)

    assert parsed.kind == "map"


def test_parse_ocr_screen_detects_neow_choice_panels_without_readable_option_text(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider([_token("턴 종료", (1711, 850, 1775, 928))])

    parsed = recognition.parse_ocr_screen(_neow_choice_screen(tmp_path / "neow.png"), ocr_provider=provider)

    assert parsed.kind == "event"
    assert parsed.state_payload == {
        "event_options": [
            {"option_id": "neow_option_1", "label": "Neow option 1"},
            {"option_id": "neow_option_2", "label": "Neow option 2"},
            {"option_id": "neow_option_3", "label": "Neow option 3"},
        ]
    }
    assert parsed.state_boxes == {
        "event_option:neow_option_1": (470, 740, 1450, 835),
        "event_option:neow_option_2": (470, 835, 1450, 930),
        "event_option:neow_option_3": (470, 930, 1450, 1030),
    }
    assert parsed.field_confidence == {"event_options": 0.99}
    assert "event_options" not in parsed.missing_fields


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


def test_ocr_token_report_records_discarded_and_fuzzy_candidates(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            recognition.OcrToken("Strike", (250, 260, 430, 330), 0.59),
            recognition.OcrToken("Defend", (760, 900, 940, 970), 0.99),
            recognition.OcrToken("Striek", (1270, 260, 1450, 330), 0.99),
            recognition.OcrToken("Mystery", (880, 930, 1040, 990), 0.99),
            recognition.OcrToken("Striking", (300, 600, 430, 660), 0.99),
            recognition.OcrToken("   ", (450, 600, 520, 660), 0.99),
        ]
    )

    report = recognition.build_ocr_token_report(
        _blank_screen(tmp_path / "screen.png"),
        ocr_provider=provider,
    ).to_dict()

    assert report["unknown_tokens"] == [
        {"text": "Striek", "box": [1270, 260, 1450, 330], "confidence": 0.99},
        {"text": "Mystery", "box": [880, 930, 1040, 990], "confidence": 0.99},
        {"text": "Striking", "box": [300, 600, 430, 660], "confidence": 0.99},
        {"text": "   ", "box": [450, 600, 520, 660], "confidence": 0.99},
    ]
    assert report["low_confidence_catalog_candidates"] == [
        {
            "token": {"text": "Strike", "box": [250, 260, 430, 330], "confidence": 0.59},
            "entry_id": "strike",
            "entry_name": "Strike",
            "entry_kind": "card",
            "matched_alias": "strike",
        }
    ]
    assert report["layout_rejected_catalog_candidates"] == [
        {
            "token": {"text": "Defend", "box": [760, 900, 940, 970], "confidence": 0.99},
            "entry_id": "defend",
            "entry_name": "Defend",
            "entry_kind": "card",
            "matched_alias": "defend",
        }
    ]
    assert report["fuzzy_candidates"] == [
        {
            "token": {"text": "Striek", "box": [1270, 260, 1450, 330], "confidence": 0.99},
            "entry_id": "strike",
            "entry_name": "Strike",
            "entry_kind": "card",
            "alias": "strike",
            "reason": "edit_distance",
            "distance": 2,
        },
        {
            "token": {"text": "Striking", "box": [300, 600, 430, 660], "confidence": 0.99},
            "entry_id": "strike",
            "entry_name": "Strike",
            "entry_kind": "card",
            "alias": "strike",
            "reason": "prefix",
        },
    ]


def test_ocr_fuzzy_candidates_handles_empty_and_prefix_only_text() -> None:
    assert recognition._fuzzy_candidates(recognition.OcrToken("", (0, 0, 1, 1), 0.99)) == []

    candidates = recognition._fuzzy_candidates(recognition.OcrToken("strike plus", (0, 0, 1, 1), 0.99))

    assert [(candidate.entry.id, candidate.reason, candidate.distance) for candidate in candidates] == [
        ("strike", "prefix", None)
    ]


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
            [
                "tesseract",
                str(tmp_path / "screen.png"),
                "stdout",
                "-l",
                "eng+kor",
                "-c",
                "tessedit_create_tsv=1",
            ],
            True,
            True,
            True,
        )
    ]
    assert tokens == [_token("Strike", (250, 260, 430, 330))]


def test_tesseract_provider_passes_tessdata_dir(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_run(command, *, capture_output, check, text):
        calls.append((command, capture_output, check, text))

        class Result:
            stdout = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"

        return Result()

    monkeypatch.setattr(recognition.subprocess, "run", fake_run)

    provider = recognition.TesseractOcrProvider(
        language="eng+kor",
        tessdata_dir=tmp_path / "tessdata",
        page_segmentation_mode=12,
    )
    provider.recognize(_blank_screen(tmp_path / "screen.png"))

    assert calls[0][0] == [
        "tesseract",
        str(tmp_path / "screen.png"),
        "stdout",
        "-l",
        "eng+kor",
        "--tessdata-dir",
        str(tmp_path / "tessdata"),
        "--psm",
        "12",
        "-c",
        "tessedit_create_tsv=1",
    ]


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


def test_parse_ocr_screen_matches_split_game_over_from_tesseract_tsv(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        recognition._tokens_from_tsv(
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t760\t160\t190\t90\t96.0\tGame\n"
            "5\t1\t1\t1\t1\t2\t970\t160\t190\t90\t94.0\tOver\n"
            "5\t1\t1\t1\t2\t1\t810\t780\t130\t70\t96.0\tNew\n"
            "5\t1\t1\t1\t2\t2\t960\t780\t150\t70\t94.0\tRun\n"
        )
    )

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / "game-over.png"), ocr_provider=provider)

    assert parsed.kind == "game_over"
    assert [option.id for option in parsed.options] == ["new_run"]


@pytest.mark.parametrize(
    ("title_tokens", "expected_kind"),
    [
        (["승리"], "victory"),
        (["게임", "오버"], "game_over"),
    ],
)
def test_parse_ocr_screen_matches_korean_terminal_aliases(
    tmp_path: Path,
    title_tokens: list[str],
    expected_kind: str,
) -> None:
    tokens = [
        recognition.OcrToken(text=text, box=(760 + index * 140, 160, 880 + index * 140, 250), confidence=0.99)
        for index, text in enumerate(title_tokens)
    ]
    tokens.append(recognition.OcrToken("다시 시작", (810, 780, 1110, 850), 0.99))
    provider = recognition.FakeOcrProvider(tokens)

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / "terminal-kr.png"), ocr_provider=provider)

    assert parsed.kind == expected_kind
    assert [option.id for option in parsed.options] == ["new_run"]


def test_parse_ocr_screen_ignores_low_confidence_terminal_title(tmp_path: Path) -> None:
    provider = recognition.FakeOcrProvider(
        [
            recognition.OcrToken("Game Over", (760, 160, 1160, 250), 0.30),
            recognition.OcrToken("New Run", (810, 780, 1110, 850), 0.99),
        ]
    )

    with pytest.raises(ValueError, match="unknown OCR screen layout"):
        recognition.parse_ocr_screen(_blank_screen(tmp_path / "low-terminal.png"), ocr_provider=provider)


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


@pytest.mark.parametrize(
    ("token_text", "expected_kind", "payload_key"),
    [
        ("Shop item Strike Plus card price 75 card strike", "shop", "shop_items"),
        ("Event option Take gold", "event", "event_options"),
        ("Rest option Smith", "rest", "rest_options"),
    ],
)
def test_parse_ocr_screen_accepts_shop_event_and_rest_state_without_reward_options(
    tmp_path: Path,
    token_text: str,
    expected_kind: str,
    payload_key: str,
) -> None:
    provider = recognition.FakeOcrProvider([_token(token_text, (700, 430, 1120, 520))])

    parsed = recognition.parse_ocr_screen(_blank_screen(tmp_path / f"{expected_kind}.png"), ocr_provider=provider)

    assert parsed.kind == expected_kind
    assert parsed.state_payload[payload_key]


def test_tesseract_tsv_parser_accepts_empty_output() -> None:
    assert recognition._tokens_from_tsv("") == []
