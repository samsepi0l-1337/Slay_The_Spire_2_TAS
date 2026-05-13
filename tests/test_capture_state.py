import json
from pathlib import Path

import pytest

from sts2_tas.capture_state import _player_value, load_captured_game_state


def test_load_captured_game_state_uses_full_state_json(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "player": {
                    "hp": 50,
                    "max_hp": 80,
                    "block": 7,
                    "energy": 2,
                    "turn": 3,
                    "strength": 1,
                    "dexterity": 2,
                    "vulnerable": 0,
                    "weak": 1,
                    "frail": 0,
                    "artifact": 1,
                    "poison": 0,
                    "regen": 2,
                    "intangible": 0,
                    "character_resource": {"stance": "neutral"},
                },
                "cards": [
                    {
                        "instance_id": "hand-strike",
                        "card_id": "strike",
                        "zone": "hand",
                        "upgraded": True,
                        "base_cost": 1,
                        "current_cost": 0,
                        "type": "attack",
                        "rarity": "basic",
                        "tags": ["attack"],
                    }
                ],
                "relics": [{"relic_id": "burning_blood", "obtained_order": 0, "counter": 1, "cooldown": 0}],
                "potions": [{"potion_id": "fire_potion", "slot": 0, "requires_target": True, "usable": True}],
                "monsters": [
                    {
                        "monster_id": "jaw_worm",
                        "slot_index": 0,
                        "hp": 20,
                        "max_hp": 44,
                        "block": 3,
                        "intent_type": "attack",
                        "intent_damage": 11,
                        "hit_count": 1,
                        "buffs": ["strength:2"],
                        "debuffs": ["weak:1"],
                    }
                ],
                "path_candidates": [
                    {
                        "node_id": "n2",
                        "node_type": "elite",
                        "depth": 1,
                        "elite_count_ahead": 2,
                        "rest_count_ahead": 1,
                        "shop_count_ahead": 0,
                        "event_count_ahead": 1,
                        "boss_distance": 8,
                        "forced_elite": True,
                    }
                ],
                "missing_fields": ["draw_pile_order"],
                "unknown_tokens": ["new_keyword"],
            }
        ),
        encoding="utf-8",
    )

    captured = load_captured_game_state(
        state_json=state_path,
        deck=[],
        relics=[],
        hp=1,
        gold=99,
        max_hp=None,
        block=None,
        energy=None,
        turn=None,
        strength=None,
        dexterity=None,
        vulnerable=None,
        weak=None,
        frail=None,
        artifact=None,
        poison=None,
        regen=None,
        intangible=None,
    )

    assert captured.player.hp == 50
    assert captured.player.character_resource == {"stance": "neutral", "gold": 99}
    assert captured.cards[0].zone == "hand"
    assert captured.relics[0].counter == 1
    assert captured.potions[0].requires_target is True
    assert captured.monsters[0].intent_damage == 11
    assert captured.path_candidates[0].forced_elite is True
    assert captured.missing_fields == ["draw_pile_order"]
    assert captured.unknown_tokens == ["new_keyword"]


def test_load_captured_game_state_records_missing_defaulted_fields() -> None:
    captured = load_captured_game_state(
        state_json=None,
        deck=["strike"],
        relics=["burning_blood"],
        hp=70,
        gold=0,
        max_hp=80,
        block=0,
        energy=3,
        turn=1,
        strength=0,
        dexterity=0,
        vulnerable=0,
        weak=0,
        frail=0,
        artifact=0,
        poison=0,
        regen=0,
        intangible=0,
    )

    assert captured.player.max_hp == 80
    assert captured.cards[0].type == "unknown"
    assert captured.relics[0].counter is None
    assert "cards.metadata" in captured.missing_fields
    assert "relics.counters" in captured.missing_fields
    assert "monsters" in captured.missing_fields


def test_load_captured_game_state_handles_empty_and_invalid_payload(tmp_path: Path) -> None:
    invalid_state = tmp_path / "state.json"
    invalid_state.write_text("[]", encoding="utf-8")

    empty = load_captured_game_state(
        state_json=None,
        deck=[],
        relics=[],
        hp=70,
        gold=0,
        max_hp=None,
        block=None,
        energy=None,
        turn=None,
        strength=None,
        dexterity=None,
        vulnerable=None,
        weak=None,
        frail=None,
        artifact=None,
        poison=None,
        regen=None,
        intangible=None,
    )

    assert "player.max_hp" in empty.missing_fields
    assert "cards" in empty.missing_fields
    assert "relics" in empty.missing_fields
    with pytest.raises(ValueError, match="state json"):
        load_captured_game_state(
            state_json=invalid_state,
            deck=[],
            relics=[],
            hp=70,
            gold=0,
            max_hp=None,
            block=None,
            energy=None,
            turn=None,
            strength=None,
            dexterity=None,
            vulnerable=None,
            weak=None,
            frail=None,
            artifact=None,
            poison=None,
            regen=None,
            intangible=None,
        )


def test_player_value_rejects_missing_required_value() -> None:
    with pytest.raises(ValueError, match="player.hp"):
        _player_value({}, "hp", None, [])
