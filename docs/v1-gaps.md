# v1 Status And Gaps

v1 now includes a reproducible data pipeline plus guarded live-vision automation boundaries. The default remains dry-run unless `--execute` is explicitly provided.

## Machine Learning

Implemented:

- supervised tabular candidate ranking
- per-character model training
- deterministic save/load/recommend flow
- seed episode JSONL logging
- win-rate evaluation across seeds

Not implemented:

- neural reinforcement learning
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
- explicit save-state backup and restore
- seed run-loop episode generation

Not implemented:

- window focus management
- OS permission provisioning for live screen capture
- Windows native click injection
- direct game process reset hooks
- online/co-op or leaderboard automation

Future platform-native screen automation must stay behind `--execute`, require local-only single-player mode, and keep dry-run logging before any click or key is sent.
