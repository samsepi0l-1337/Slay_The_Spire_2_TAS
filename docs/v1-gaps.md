# v1 Gaps

현재 v1은 OCR 기반 screen automation과 entity/action ranker 학습 경계를 구현한다. 아래 항목은 아직 구현하지 않은 범위다.

## Deferred Scope

- Steam/Godot 내부 메모리나 runtime state를 직접 읽지 않는다. OCR과 명시 `--state-json` 입력이 현재 상태 소스다.
- 실제 게임 E2E smoke, OS 권한 설정, target-window activation 검증은 자동 테스트에서 수행하지 않는다.
- Quartz/PyObjC targeted PID input delivery는 dependency를 추가하지 않고 향후 확장점으로 남겼다.
- simulator-backed self-play, PPO, GNN map encoder 같은 reinforcement learning 경로는 구현하지 않았다.
- 온라인/co-op/leaderboard 자동화는 제외한다.
