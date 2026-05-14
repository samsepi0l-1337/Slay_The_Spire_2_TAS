from __future__ import annotations

from pathlib import Path
from statistics import fmean

from .capture_state import CapturedGameState
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
    enriched_state = _state_with_reward_cards(captured_state, parsed.options)
    return _game_step(
        game_version=game_version,
        branch=branch,
        character=character,
        ascension=ascension,
        floor=floor,
        captured_state=enriched_state,
        decision_context=parsed.kind,
        actions=[
            ActionCandidate(
                action_type=_action_type(option.kind),
                option_id=option.id,
                screen_box=option.box,
                legal=True,
            )
            for option in parsed.options
        ],
        source_type=source_type,
        ocr_confidence=confidence,
        screenshot_path=parsed.screenshot_path,
        outcome=_outcome_from_parsed_screen(parsed.kind, floor=floor, hp=captured_state.player.hp),
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
        state=StructuredGameState(
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
