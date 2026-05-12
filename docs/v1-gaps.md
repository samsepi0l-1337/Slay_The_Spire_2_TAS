# v1 Gaps

v1 intentionally builds a reproducible data and recommendation pipeline before controlling the game.

## Machine Learning

Implemented:

- supervised tabular candidate ranking
- per-character model training
- deterministic save/load/recommend flow

Not implemented:

- OCR for actual card/relic text extraction
- template matching against the full live game UI
- reinforcement learning
- self-play or simulator-driven rollouts
- win-rate evaluation across seeds
- automatic patch-to-patch card/relic metadata migration

## Screen Recognition

Implemented:

- deterministic color-region detection for stable or synthetic screenshots
- card reward, skip button, and relic choice layout detection

Not implemented:

- robust live-game screen parser
- multi-resolution UI handling
- non-English UI parsing
- animation/frame timing stabilization
- direct Steam or Godot state introspection

## screen automation

Not implemented:

- mouse click execution
- keyboard routing
- window focus management
- save-state control
- run reset loops
- online/co-op or leaderboard automation

Future screen automation should start behind an explicit `--execute` flag, require local-only single-player mode, and include dry-run logging before any click is sent.
