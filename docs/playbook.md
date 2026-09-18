# STS2 Ironclad run playbook (ML-usable)

Verified against MegaCrit AutoSlay handlers and the public STS2 CLI mod (ForceClick / PlayCardAction / NEventRoom.Proceed). These are the same macros the live TAS emits, so Q* can learn `(phase, screen_id, extras) -> action_type`.

| Screen | When | Click | ML? |
| --- | --- | --- | --- |
| Main Continue | Saved run exists | Never Continue (Silent save). `AbandonRun` then confirm popup | No (UI) |
| Main Singleplayer | After abandon / no save | `SingleplayerButton` ForceClick even if disabled, then `StandardButton` | No |
| Character | New run | `NCharacterSelectButton` IRONCLAD then enabled `ConfirmButton` | No (always Ironclad) |
| Neow / event | After embark or event node | Ancient: ForceClick `%DialogueHitbox` until last line. Then click non-proceed `OptionButtons[i]`. Grid/deck overlays (`NDeckTransformSelectScreen`, `NDeckCardSelectScreen`, `NCardGridSelectionScreen`): Press one `NCardHolder`, then preview `_previewConfirmButton` / `NConfirmButton`. Do not keep Pressing the same holder. | Yes: option index vs gold/HP |
| Map | After event/rewards close | `NMapScreen.TravelToMapCoord` first travelable | Yes: node type (combat/elite/rest/shop/treasure) |
| Combat | Fight | Q* among `play_card`; skip Hemokinesis/Bloodletting/Offering when HP≤20; `end_turn` only if no cards. If `NPlayerHand.IsInCardSelection` (Armaments etc.), Press the hand holder then `%SelectModeConfirmButton` instead of `PlayCardAction`. | Yes: Q* |
| Rewards | After combat or event loot | Enabled `NRewardButton` (gold/potion), `NCardHolder` Pressed, or skip (`NCardRewardAlternativeButton` / `NChoiceSelectionSkipButton` 넘어가기) as `choose_reward` slot 1. Then `NProceedButton`. | Yes: card id vs skip |
| Rest | Campfire | Click `NRestSiteButton` or await `ChooseLocalOption` then `AfterSelectingOption` (HEAL if enabled). When `ProceedButton` is enabled, ForceClick it. Do not re-invoke option 0 while waiting. | Yes: HEAL vs SMITH by HP |
| Treasure | Chest | `ProceedButton` (skip or take) | Yes: relic vs skip |
| Shop | Merchant | `ProceedButton` (leave; no buy until gold model exists) | Later |
| Game over | Death / run summary | `NGameOverContinueButton` then Singleplayer Ironclad. Leftover game-over UI must not block Singleplayer. | No (UI; start next run) |
| Act 3 boss dead | Victory extras | stop `until-clear` | Label for Q* |

Q* already trains on `phase`, `screen_id`, HP, energy, card damage, enemy HP. Adding `extras.room` (event/rest/shop/treasure) is enough to reuse this table as features. Combat decisions are already Q*; UI screens are scripted macros so the learner is not blocked on Neow/proceed. The Windows launcher waits for `\\.\pipe\sts2-tas` without connecting, so the TAS client is the only pipe peer.
