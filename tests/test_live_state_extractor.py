from sts2_tas.live_state import extract_live_state
from sts2_tas.schema import OcrResult


def _token(text: str, box: tuple[int, int, int, int] = (0, 0, 10, 10)) -> OcrResult:
    return OcrResult(text=text, box=box, confidence=0.99)


def test_extract_live_state_reads_player_hand_monster_and_map_tokens() -> None:
    extraction = extract_live_state(
        [
            _token("HP 65/80"),
            _token("Energy 3/3"),
            _token("Block 5"),
            _token("Gold 99"),
            _token("Floor 7"),
            _token("Turn 2"),
            _token("Hand Strike cost 1 attack", (100, 800, 220, 980)),
            _token("Potion fire_potion slot 0 target used", (430, 920, 500, 990)),
            _token("Monster Jaw Worm 30/44 block 3 attack 7x1", (1200, 310, 1520, 620)),
            _token("Path node-a elite depth 1 elites 1 rests 0 shops 0 events 1 boss 5 forced", (700, 230, 820, 350)),
        ]
    )

    assert extraction.floor == 7
    assert extraction.state_payload["player"] == {
        "hp": 65,
        "max_hp": 80,
        "block": 5,
        "energy": 3,
        "turn": 2,
        "character_resource": {"gold": 99},
    }
    assert extraction.state_payload["cards"][0]["instance_id"] == "hand-0-strike"
    assert extraction.state_payload["cards"][0]["zone"] == "hand"
    assert extraction.state_payload["potions"][0]["potion_id"] == "fire_potion"
    assert extraction.state_payload["potions"][0]["usable"] is False
    assert extraction.state_payload["monsters"][0]["monster_id"] == "jaw_worm"
    assert extraction.state_payload["monsters"][0]["intent_type"] == "attack"
    assert extraction.state_payload["path_candidates"][0]["node_id"] == "node-a"
    assert extraction.state_boxes["card:hand-0-strike"] == (100, 800, 220, 980)
    assert extraction.state_boxes["potion:fire_potion:0"] == (430, 920, 500, 990)
    assert extraction.state_boxes["monster:jaw_worm:0"] == (1200, 310, 1520, 620)
    assert extraction.state_boxes["path:node-a"] == (700, 230, 820, 350)


def test_extract_live_state_records_missing_and_unknown_tokens() -> None:
    extraction = extract_live_state([_token("Unmapped Early Access Keyword")])

    assert "player.hp" in extraction.missing_fields
    assert "cards" in extraction.missing_fields
    assert extraction.unknown_tokens == ["Unmapped Early Access Keyword"]
