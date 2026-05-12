import json
from pathlib import Path

from PIL import Image
import pytest

from sts2_tas import automation, cli, runtime
from sts2_tas.schema import AutomationAction, ChoiceOption, DecisionChoice, DecisionSnapshot


def _screen(path: Path) -> Path:
    Image.new("RGB", (1920, 1080), (15, 18, 24)).save(path)
    return path


def _ocr_fixture(path: Path) -> Path:
    path.write_text(
        json.dumps(
            [
                {"text": "타격", "box": [250, 260, 430, 330], "confidence": 0.99},
                {"text": "수비", "box": [760, 260, 940, 330], "confidence": 0.99},
                {"text": "넘기기", "box": [880, 930, 1040, 990], "confidence": 0.99},
            ]
        ),
        encoding="utf-8",
    )
    return path


def _snapshot(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "game_version": "0.105.1",
                "branch": "beta",
                "character": "ironclad",
                "ascension": 0,
                "floor": 1,
                "deck": ["strike"],
                "relics": ["burning_blood"],
                "hp": 70,
                "gold": 0,
                "options": [
                    {"id": "strike", "name": "Strike", "kind": "card", "tags": []},
                    {"id": "skip", "name": "Skip", "kind": "skip", "tags": []},
                ],
                "chosen": None,
                "skipped": False,
                "screenshot_path": "screen.png",
            }
        ),
        encoding="utf-8",
    )
    return path


def test_cli_parse_screen_writes_catalog_matched_options(tmp_path: Path) -> None:
    output = tmp_path / "parsed.json"

    exit_code = cli.main(
        [
            "parse-screen",
            "--screenshot",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / "ocr.json")),
            "--out",
            str(output),
        ]
    )

    parsed = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert [option["id"] for option in parsed["options"]] == ["strike", "defend", "skip"]


def test_cli_parse_screen_can_use_tesseract_provider(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "parsed.json"
    languages = []

    class Provider:
        def __init__(self, *, language: str) -> None:
            languages.append(language)

        def recognize(self, image_path: Path):
            return [
                cli.OcrToken(text="Strike", box=(250, 260, 430, 330), confidence=0.99),
                cli.OcrToken(text="Skip", box=(880, 930, 1040, 990), confidence=0.99),
            ]

    monkeypatch.setattr(cli, "TesseractOcrProvider", Provider)

    exit_code = cli.main(
        [
            "parse-screen",
            "--screenshot",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-provider",
            "tesseract",
            "--ocr-language",
            "eng+kor",
            "--out",
            str(output),
        ]
    )

    parsed = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert languages == ["eng+kor"]
    assert [option["id"] for option in parsed["options"]] == ["strike", "skip"]


def test_cli_parse_screen_requires_fixture_for_fixture_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ocr fixture"):
        cli.main(
            [
                "parse-screen",
                "--screenshot",
                str(_screen(tmp_path / "screen.png")),
                "--out",
                str(tmp_path / "parsed.json"),
            ]
        )


def test_cli_capture_live_appends_parsed_snapshot(tmp_path: Path) -> None:
    output = tmp_path / "captures.jsonl"

    exit_code = cli.main(
        [
            "capture-live",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / "ocr.json")),
            "--out",
            str(output),
            "--game-version",
            "0.105.1",
            "--branch",
            "beta",
            "--character",
            "ironclad",
            "--ascension",
            "0",
            "--floor",
            "1",
            "--hp",
            "70",
            "--gold",
            "0",
        ]
    )

    snapshot = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert exit_code == 0
    assert [option["id"] for option in snapshot["options"]] == ["strike", "defend", "skip"]


def test_cli_act_dry_run_reports_action_without_input_events(tmp_path: Path, capsys) -> None:
    input_log = tmp_path / "inputs.jsonl"

    exit_code = cli.main(
        [
            "act",
            "--snapshot",
            str(_snapshot(tmp_path / "snapshot.json")),
            "--choice",
            "pick:strike",
            "--input-log",
            str(input_log),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output == {"dry_run": True, "action": "pick", "option_id": "strike"}
    assert not input_log.exists()


def test_cli_act_execute_writes_input_event(tmp_path: Path) -> None:
    input_log = tmp_path / "inputs.jsonl"

    exit_code = cli.main(
        [
            "act",
            "--snapshot",
            str(_snapshot(tmp_path / "snapshot.json")),
            "--choice",
            "pick:strike",
            "--input-log",
            str(input_log),
            "--execute",
        ]
    )

    event = json.loads(input_log.read_text(encoding="utf-8").splitlines()[0])
    assert exit_code == 0
    assert event == {"action": "pick", "option_id": "strike"}


def test_cli_save_state_backup_and_restore_round_trip(tmp_path: Path) -> None:
    save_file = tmp_path / "runs" / "autosave.sav"
    save_file.parent.mkdir()
    save_file.write_text("before", encoding="utf-8")
    backup_dir = tmp_path / "backups"

    backup_code = cli.main(["save-state", "backup", "--save", str(save_file), "--backup-dir", str(backup_dir)])
    save_file.write_text("after", encoding="utf-8")
    restore_code = cli.main(["save-state", "restore", "--save", str(save_file), "--backup-dir", str(backup_dir)])

    assert backup_code == 0
    assert restore_code == 0
    assert save_file.read_text(encoding="utf-8") == "before"


def test_cli_run_loop_records_seed_episode(tmp_path: Path) -> None:
    episodes = tmp_path / "episodes.jsonl"

    exit_code = cli.main(
        [
            "run-loop",
            "--seeds",
            "7",
            "--capture-fixture",
            str(_screen(tmp_path / "screen.png")),
            "--ocr-fixture",
            str(_ocr_fixture(tmp_path / "ocr.json")),
            "--episodes-out",
            str(episodes),
            "--max-steps",
            "1",
        ]
    )

    episode = json.loads(episodes.read_text(encoding="utf-8").splitlines()[0])
    assert exit_code == 0
    assert episode["seed"] == 7
    assert episode["steps"] == 1
    assert episode["choices"] == [{"action": "pick", "option_id": "strike"}]


def test_cli_evaluate_seeds_writes_summary(tmp_path: Path) -> None:
    episodes = tmp_path / "episodes.jsonl"
    episodes.write_text(
        "\n".join(
            [
                json.dumps({"seed": 7, "steps": 3, "victory": True}),
                json.dumps({"seed": 8, "steps": 2, "victory": False}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary = tmp_path / "summary.json"

    exit_code = cli.main(["evaluate-seeds", "--episodes", str(episodes), "--out", str(summary)])

    assert exit_code == 0
    assert json.loads(summary.read_text(encoding="utf-8")) == {
        "episodes": 2,
        "victories": 1,
        "win_rate": 0.5,
        "average_steps": 2.5,
    }


def test_plan_action_rejects_missing_pick_option(tmp_path: Path) -> None:
    snapshot = DecisionSnapshot.from_json(_snapshot(tmp_path / "snapshot.json").read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="not present"):
        automation.plan_action(snapshot, DecisionChoice(action="pick", option_id="bash"), dry_run=True)


def test_plan_action_rejects_skip_without_skip_option() -> None:
    snapshot = DecisionSnapshot(
        game_version="0.105.1",
        branch="beta",
        character="ironclad",
        ascension=0,
        floor=1,
        deck=[],
        relics=[],
        hp=70,
        gold=0,
        options=[ChoiceOption(id="strike", name="Strike", kind="card", tags=[])],
        chosen=None,
        skipped=False,
        screenshot_path=Path("screen.png"),
    )

    with pytest.raises(ValueError, match="skip option"):
        automation.plan_action(snapshot, DecisionChoice(action="skip"), dry_run=True)


def test_apply_action_requires_controller_for_execute() -> None:
    action = AutomationAction(action="pick", option_id="strike", dry_run=False)

    with pytest.raises(ValueError, match="input controller"):
        automation.apply_action(action, None)


def test_save_state_rejects_missing_save_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="save file"):
        runtime.backup_save(tmp_path / "missing.sav", tmp_path / "backups")


def test_save_state_rejects_missing_backup(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="backup file"):
        runtime.restore_save(tmp_path / "autosave.sav", tmp_path / "backups")
