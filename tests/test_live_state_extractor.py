from sts2_tas.live_state import extract_live_state
from sts2_tas.schema import OcrResult


def _token(text: str, box: tuple[int, int, int, int] = (0, 0, 10, 10)) -> OcrResult:
    return OcrResult(text=text, box=box, confidence=0.99)


def _token_with_confidence(
    text: str,
    confidence: float,
    box: tuple[int, int, int, int] = (0, 0, 10, 10),
) -> OcrResult:
    return OcrResult(text=text, box=box, confidence=confidence)


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


def test_extract_live_state_records_field_confidence_for_extracted_fields() -> None:
    extraction = extract_live_state(
        [
            _token_with_confidence("HP 65/80", 0.91),
            _token_with_confidence("Energy 3/3", 0.88),
            _token_with_confidence("Block 5", 0.83),
            _token_with_confidence("Gold 99", 0.82),
            _token_with_confidence("Turn 2", 0.87),
            _token_with_confidence("Hand Strike cost 1 attack", 0.79),
            _token_with_confidence("Monster Jaw Worm 30/44 block 3 attack 7x1", 0.78),
            _token_with_confidence("Path node-a elite depth 1 elites 1 rests 0 shops 0 events 1 boss 5", 0.77),
            _token_with_confidence("Potion fire_potion slot 0 target used", 0.76),
        ]
    )

    assert extraction.field_confidence == {
        "player.hp": 0.91,
        "player.max_hp": 0.91,
        "player.energy": 0.88,
        "player.block": 0.83,
        "player.character_resource.gold": 0.82,
        "player.turn": 0.87,
        "cards": 0.79,
        "monsters": 0.78,
        "path_candidates": 0.77,
        "potions": 0.76,
    }


def test_extract_live_state_reads_shop_event_and_rest_options() -> None:
    extraction = extract_live_state(
        [
            _token_with_confidence("Shop item Strike Plus card price 75 card strike", 0.92, (100, 100, 260, 220)),
            _token_with_confidence("Shop item Remove Slot remove price 100 target defend", 0.91, (320, 100, 480, 220)),
            _token_with_confidence("Leave shop", 0.90, (1700, 930, 1880, 1010)),
            _token_with_confidence("Event option Take gold", 0.89, (500, 720, 1500, 780)),
            _token_with_confidence("Rest option Rest", 0.88, (690, 430, 830, 570)),
            _token_with_confidence("Rest option Smith", 0.87, (1000, 430, 1140, 570)),
        ]
    )

    assert extraction.state_payload["shop_items"] == [
        {"item_id": "strike_plus", "item_type": "card", "price": 75, "card_id": "strike"},
        {"item_id": "remove_slot", "item_type": "remove", "price": 100, "target_card_id": "defend"},
    ]
    assert extraction.state_payload["event_options"] == [{"option_id": "take_gold", "label": "Take gold"}]
    assert extraction.state_payload["rest_options"] == [{"option_id": "rest"}, {"option_id": "smith"}]
    assert extraction.state_boxes["shop_item:strike_plus"] == (100, 100, 260, 220)
    assert extraction.state_boxes["shop_item:remove_slot"] == (320, 100, 480, 220)
    assert extraction.state_boxes["leave_shop"] == (1700, 930, 1880, 1010)
    assert extraction.state_boxes["event_option:take_gold"] == (500, 720, 1500, 780)
    assert extraction.state_boxes["rest_option:rest"] == (690, 430, 830, 570)
    assert extraction.state_boxes["rest_option:smith"] == (1000, 430, 1140, 570)
    assert extraction.field_confidence["shop_items"] == 0.92
    assert extraction.field_confidence["event_options"] == 0.89
    assert extraction.field_confidence["rest_options"] == 0.88


def test_extract_live_state_marks_unavailable_shop_event_and_rest_options() -> None:
    extraction = extract_live_state(
        [
            _token_with_confidence("Shop item Tiny House relic price 150 sold", 0.92),
            _token_with_confidence("Event option Take gold unavailable", 0.91),
            _token_with_confidence("Rest option Smith disabled", 0.90),
        ]
    )

    assert extraction.state_payload["shop_items"][0]["purchasable"] is False
    assert extraction.state_payload["event_options"][0]["available"] is False
    assert extraction.state_payload["rest_options"][0]["available"] is False


def test_extract_live_state_records_missing_and_unknown_tokens() -> None:
    extraction = extract_live_state([_token("Unmapped Early Access Keyword")])

    assert "player.hp" in extraction.missing_fields
    assert "cards" in extraction.missing_fields
    assert extraction.unknown_tokens == ["Unmapped Early Access Keyword"]
