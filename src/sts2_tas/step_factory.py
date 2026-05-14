from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from statistics import fmean

from .actions import generate_legal_actions
from .capture_state import CapturedGameState, overlay_captured_game_state
from .recognition import DetectionKind, ScreenDetection
from .schema import (
    ActionCandidate,
    CardInstance,
    GameStep,
    ObservationQuality,
    ParsedScreen,
    StepOutcome,
    StructuredGameState,
)


def game_step_from_detection(
    *,
    detection: ScreenDetection,
    game_version: str,
    branch: str,
    character: str,
    ascension: int,
    floor: int,
    captured_state: CapturedGameState,
    screenshot_path: Path,
) -> GameStep:
    if detection.kind is DetectionKind.UNKNOWN:
        raise ValueError(f"unknown screen layout for {screenshot_path}")
    return _game_step(
        game_version=game_version,
        branch=branch,
        character=character,
        ascension=ascension,
        floor=floor,
        captured_state=captured_state,
        decision_context=detection.kind.value,
        actions=_actions_from_detection(detection),
        source_type="screen",
        ocr_confidence=1.0,
        screenshot_path=screenshot_path,
    )


def game_step_from_parsed_screen(
    *,
    parsed: ParsedScreen,
    game_version: str,
    branch: str,
    character: str,
    ascension: int,
    floor: int,
    captured_state: CapturedGameState,
    source_type: str,
) -> GameStep:
    confidence = fmean(option.confidence for option in parsed.options) if parsed.options else 0.0
    extracted_state = overlay_captured_game_state(
        captured_state,
        parsed.state_payload,
        missing_fields=parsed.missing_fields,
        unknown_tokens=parsed.unknown_tokens,
    )
    effective_floor = _parsed_floor(parsed, floor)
    enriched_state = _state_with_reward_cards(extracted_state, parsed.options)
    state = _structured_state(
        game_version=game_version,
        branch=branch,
        character=character,
        ascension=ascension,
        floor=effective_floor,
        captured_state=enriched_state,
        decision_context=parsed.kind,
    )
    return _game_step(
        game_version=game_version,
        branch=branch,
        character=character,
        ascension=ascension,
        floor=effective_floor,
        captured_state=enriched_state,
        decision_context=parsed.kind,
        actions=_actions_from_parsed_screen(parsed, state),
        source_type=source_type,
        ocr_confidence=confidence,
        screenshot_path=parsed.screenshot_path,
        outcome=_outcome_from_parsed_screen(parsed.kind, floor=effective_floor, hp=enriched_state.player.hp),
    )


def _game_step(
    *,
    game_version: str,
    branch: str,
    character: str,
    ascension: int,
    floor: int,
    captured_state: CapturedGameState,
    decision_context: str,
    actions: list[ActionCandidate],
    source_type: str,
    ocr_confidence: float,
    screenshot_path: Path,
    outcome: StepOutcome | None = None,
) -> GameStep:
    catalog_version = f"{game_version}:{branch}"
    return GameStep(
        state=_structured_state(
            game_version=game_version,
            branch=branch,
            character=character,
            ascension=ascension,
            floor=floor,
            captured_state=captured_state,
            decision_context=decision_context,
        ),
        actions=actions,
        chosen_action_id=None,
        outcome=outcome,
        observation=ObservationQuality(
            source_type=source_type,
            ocr_confidence=ocr_confidence,
            game_version=game_version,
            branch=branch,
            catalog_version=catalog_version,
            missing_fields=captured_state.missing_fields,
            unknown_tokens=captured_state.unknown_tokens,
        ),
        screenshot_path=screenshot_path,
    )


def _structured_state(
    *,
    game_version: str,
    branch: str,
    character: str,
    ascension: int,
    floor: int,
    captured_state: CapturedGameState,
    decision_context: str,
) -> StructuredGameState:
    catalog_version = f"{game_version}:{branch}"
    return StructuredGameState(
        game_version=game_version,
        branch=branch,
        catalog_version=catalog_version,
        character=character,
        ascension=ascension,
        floor=floor,
        decision_context=decision_context,
        player=captured_state.player,
        cards=captured_state.cards,
        relics=captured_state.relics,
        potions=captured_state.potions,
        monsters=captured_state.monsters,
        path_candidates=captured_state.path_candidates,
    )


def _state_with_reward_cards(captured_state: CapturedGameState, options) -> CapturedGameState:
    reward_cards = [
        CardInstance(
            instance_id=f"reward-{index}-{option.id}",
            card_id=_canonical_option_id(option.id),
            zone="reward",
            upgraded=False,
            base_cost=None,
            current_cost=None,
            type=_card_type(option.tags),
            rarity="unknown",
            tags=list(option.tags),
        )
        for index, option in enumerate(options)
        if option.kind == "card"
    ]
    if not reward_cards:
        return captured_state
    return CapturedGameState(
        player=captured_state.player,
        cards=[*captured_state.cards, *reward_cards],
        relics=captured_state.relics,
        potions=captured_state.potions,
        monsters=captured_state.monsters,
        path_candidates=captured_state.path_candidates,
        missing_fields=captured_state.missing_fields,
        unknown_tokens=captured_state.unknown_tokens,
    )


def _actions_from_detection(detection: ScreenDetection) -> list[ActionCandidate]:
    if detection.kind is DetectionKind.CARD_REWARD:
        actions = [
            ActionCandidate(action_type="pick_card", option_id=f"card_{index}", screen_box=box)
            for index, box in enumerate(detection.option_boxes, start=1)
        ]
        if detection.skip_box is not None:
            actions.append(ActionCandidate(action_type="skip_reward", option_id="skip", screen_box=detection.skip_box))
        return actions
    return [
        ActionCandidate(action_type="pick_relic", option_id=f"relic_{index}", screen_box=box)
        for index, box in enumerate(detection.option_boxes, start=1)
    ]


def _actions_from_parsed_screen(parsed: ParsedScreen, state: StructuredGameState) -> list[ActionCandidate]:
    fallback = [
        ActionCandidate(
            action_type=_action_type(option.kind),
            option_id=option.id,
            screen_box=option.box,
            legal=True,
        )
        for option in parsed.options
    ]
    generated = generate_legal_actions(state)
    if not generated:
        return fallback
    return [_with_screen_binding(action, parsed, fallback) for action in generated]


def _with_screen_binding(
    action: ActionCandidate,
    parsed: ParsedScreen,
    fallback: list[ActionCandidate],
) -> ActionCandidate:
    boxes = parsed.state_boxes or {}
    if action.action_type == "pick_card" and action.target_card_id is not None:
        option_id, screen_box = _reward_option_binding(action.target_card_id, fallback)
        return replace(action, option_id=option_id, screen_box=screen_box)
    if action.action_type == "skip_reward":
        skip = next((candidate for candidate in fallback if candidate.action_type == "skip_reward"), None)
        return replace(action, option_id="skip", screen_box=None if skip is None else skip.screen_box)
    if action.action_type == "choose_path" and action.path_node_id is not None:
        return replace(action, screen_box=boxes.get(f"path:{action.path_node_id}"))
    if action.action_type == "play_card" and action.source_card_id is not None:
        return replace(action, screen_box=boxes.get(f"card:{action.source_card_id}"))
    if action.action_type == "use_potion" and action.source_potion_id is not None:
        return replace(action, screen_box=boxes.get(f"potion:{action.source_potion_id}"))
    return action


def _reward_option_binding(target_card_id: str, fallback: list[ActionCandidate]) -> tuple[str | None, tuple[int, int, int, int] | None]:
    for index, candidate in enumerate((item for item in fallback if item.action_type == "pick_card")):
        if target_card_id.startswith(f"reward-{index}-"):
            return candidate.option_id, candidate.screen_box
    return None, None


def _action_type(kind: str) -> str:
    if kind == "card":
        return "pick_card"
    if kind == "relic":
        return "pick_relic"
    if kind == "skip":
        return "skip_reward"
    if kind in {"select_single_player", "select_mode", "select_character", "restart_run"}:
        return kind
    raise ValueError(f"unsupported recognized option kind: {kind}")


def _outcome_from_parsed_screen(kind: str, *, floor: int, hp: int) -> StepOutcome | None:
    if kind == DetectionKind.VICTORY.value:
        return StepOutcome(victory=True, floor_reached=floor, hp_remaining=hp, terminal=True)
    if kind == DetectionKind.GAME_OVER.value:
        return StepOutcome(victory=False, floor_reached=floor, hp_remaining=hp, terminal=True)
    return None


def _parsed_floor(parsed: ParsedScreen, fallback: int) -> int:
    payload = parsed.state_payload or {}
    meta = payload.get("_meta", {})
    if isinstance(meta, dict) and "floor" in meta:
        return int(meta["floor"])
    return fallback


def _card_type(tags: list[str]) -> str:
    for card_type in ("attack", "skill", "power", "curse", "status"):
        if card_type in tags:
            return card_type
    return "unknown"


def _canonical_option_id(option_id: str) -> str:
    base, separator, suffix = option_id.rpartition("_")
    if separator and suffix.isdigit():
        return base
    return option_id
