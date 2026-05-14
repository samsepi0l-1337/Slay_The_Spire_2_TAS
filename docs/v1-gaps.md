# v1 Status And Gaps

v1 now includes a reproducible data pipeline plus guarded live-vision automation boundaries. The default remains dry-run unless `--execute` is explicitly provided.

## Machine Learning

Implemented:

- PyTorch entity/action behavior-cloning ranker with value head
- legal action masking for torch policy logits
- per-character model training
- deterministic save/load/recommend flow
- seed episode JSONL logging
- win-rate evaluation across seeds

Not implemented:

- PPO or other neural reinforcement learning loops
- GNN map encoder
- simulator-backed self-play
- automatic patch-to-patch card/relic metadata migration

## Screen Recognition

Implemented:

- deterministic color-region detection for stable or synthetic screenshots
- card reward, skip button, and relic choice layout detection
- provider-based OCR token parsing
- English/Korean card, relic, and skip catalog matching
- resolution-independent reward layout checks

Not implemented:

- animation/frame timing stabilization
- full-card art/template matching
- direct Steam or Godot state introspection

## screen automation

Implemented:

- dry-run action planning from parsed options
- `live-step` fixture or Pillow screen capture into OCR, recommendation/manual choice, and one planned action
- `--execute` gated input event logging
- `--input-backend native` execution adapter for local OS input plans
- option-box center click planning for picks and skip-button clicks
- macOS target-window activation plus same-script window identity/bounds verification before native input
- Windows target-window detection plus PowerShell/user32 native click input
- explicit save-state backup and restore
- seed run-loop episode generation

Not implemented:

- OS permission provisioning for live screen capture
- Quartz/PyObjC targeted PID input delivery
- direct game process reset hooks
- online/co-op or leaderboard automation

Future platform-native screen automation must stay behind `--execute`, require local-only single-player mode, and keep dry-run logging before any click or key is sent.
