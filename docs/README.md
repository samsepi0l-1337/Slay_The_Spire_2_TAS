# Documentation Index

현재 문서는 Windows 실제 게임에서 replay 검증 가능한 Slay the Spire 2 TAS runtime v1을 기준으로 유지한다.

- [Architecture](architecture.md): TAS v1 실행 구조와 데이터 흐름.
- [Implemented work](implemented-work.md): 현재 코드로 구현된 범위와 검증 증거.
- [TAS runtime v1](tas-runtime.md): semantic movie, checkpoint, replay/verify CLI, ML experience gate, Windows passive hook canary.
- [Docker and Windows local execution](docker.md): Windows interactive desktop 실행 보조 경계.
- [V1 gaps](v1-gaps.md): 남은 gap과 acceptance 기준.

## Current Scope

포함:

- semantic movie + deterministic replay
- cold checkpoint(save hash + movie prefix hash + decision fingerprint)
- Windows passive-only hook canary scaffold
- 숫자키 hybrid combat input
- verified `TasExperience` data gate
- `tas-probe`, `tas-record`, `tas-replay`, `tas-verify`, `tas-search`

제외:

- mid-frame process memory savestate
- full simulation tick/RNG/time freeze
- input/time hook activation before canary is green
- anti-cheat, DRM, network, leaderboard bypass
- unverified `model_self` row를 기본 학습에 포함하는 흐름

## Verification

```bash
PYTHONPATH=src uv run --extra dev pytest
git diff --check
```
