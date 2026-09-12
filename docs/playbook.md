# STS2 Ironclad run playbook (ML-usable)

Verified against MegaCrit AutoSlay handlers and the public STS2 CLI mod (ForceClick / PlayCardAction / NEventRoom.Proceed). These are the same macros the live TAS emits, so Q* can learn `(phase, screen_id, extras) -> action_type`.

| Screen | When | Click | ML? |
| --- | --- | --- | --- |
| Main Continue | Saved run exists | Never Continue (Silent save). `AbandonRun` then confirm popup | No (UI) |
| Main Singleplayer | After abandon / no save | `SingleplayerButton` ForceClick even if disabled, then `StandardButton` | No |
| Character | New run | `NCharacterSelectButton` IRONCLAD then enabled `ConfirmButton` | No (always Ironclad) |
| Neow / event | After embark or event node | Dialogue `NAncientDialogueHitbox`, then `NEventOptionButton` ForceClick, then `NEventRoom.Proceed()` when finished | Yes: option index vs gold/HP |
| Map | Between rooms | `NMapScreen.TravelToMapCoord` first travelable | Yes: node type (combat/elite/rest/shop/treasure) |
| Combat | Fight | Q* among `play_card`; `end_turn` only if no cards | Yes: Q* |
| Rewards | After combat | Enabled `NRewardButton`, `NCardHolder` Pressed, then enabled `NProceedButton` | Yes: card id vs skip |
| Rest | Campfire | `ChooseLocalOption(0)` HEAL, then `ProceedButton` | Yes: HEAL vs SMITH by HP |
| Treasure | Chest | `ProceedButton` (skip or take) | Yes: relic vs skip |
| Shop | Merchant | `ProceedButton` (leave; no buy until gold model exists) | Later |
| Game over | Death / run summary | `NGameOverContinueButton` then Singleplayer Ironclad | No (UI; start next run) |
| Act 3 boss dead | Victory extras | stop `until-clear` | Label for Q* |

Q* already trains on `phase`, `screen_id`, HP, energy, card damage, enemy HP. Adding `extras.room` (event/rest/shop/treasure) is enough to reuse this table as features. Combat decisions are already Q*; UI screens are scripted macros so the learner is not blocked on Neow/proceed.
