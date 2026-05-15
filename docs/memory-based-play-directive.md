# Memory Based Play Directive

이 문서는 사용자가 실제 게임 메모리/RAM 기준 플레이를 요구할 때의 별도 구현 지시서다. 현재 TAS runtime v1 acceptance와 분리하며, v1 문서의 semantic movie/replay 방향을 대체하지 않는다.

## 구현할 것

- Windows target process에 read-only로 attach하는 경계를 만든다.
- Slay the Spire 2 버전별 memory layout discovery tooling을 만든다.
- version-specific offset/signature registry를 관리한다.
- read-only memory snapshot을 stable schema로 저장한다.
- memory snapshot을 `StructuredGameState`로 변환한다.
- OCR/live state와 memory state를 cross-check하고 불일치 시 fail-closed 또는 diagnostic report를 남긴다.
- decision loop가 memory-derived state를 선택적으로 사용할 수 있게 한다.
- Windows-only acceptance test를 별도 gate로 둔다.

## 구현하지 않을 것

- game memory write 또는 mutation
- save memory patching
- RNG seed patching
- simulation tick/time hook
- input hook
- anti-cheat, DRM, network, leaderboard bypass
- 불명확한 offset을 추측으로 사용하는 동작
- memory-derived state를 v1 live replay acceptance와 자동으로 섞는 동작

## 구현 순서

1. read-only process attach boundary를 정의한다: target process, pid binding, permission failure, unsupported platform을 명확히 실패시킨다.
2. memory layout discovery tooling을 만든다: 후보 주소, 타입, confidence, game version, binary signature를 기록한다.
3. offset/signature registry를 만든다: game version과 branch별로 offset provenance와 validation rule을 저장한다.
4. memory snapshot schema를 만든다: player, cards, relics, potions, monsters, path/shop/event/rest 상태를 `StructuredGameState`와 매핑 가능한 형태로 저장한다.
5. OCR state와 memory state cross-check를 구현한다: 핵심 필드가 다르면 decision input으로 쓰지 않고 diagnostic evidence를 남긴다.
6. decision loop integration을 구현한다: `source_type=memory` 또는 `source_type=memory_cross_checked`로 관측 품질을 기록한다.
7. Windows-only acceptance test를 만든다: read-only attach, snapshot extraction, OCR cross-check, legal action generation까지 검증한다.

## Acceptance 기준

- 모든 process access는 read-only여야 한다.
- `WriteProcessMemory`, code patching, DLL-based memory mutation, time/RNG hook은 금지한다.
- memory snapshot은 game version/signature가 registry와 일치할 때만 decision input으로 사용할 수 있다.
- OCR cross-check가 configured critical field에서 실패하면 memory state는 gameplay action 실행에 쓰지 않는다.
- Windows 실제 게임 검증은 로그인된 local interactive session에서 실행된 결과만 acceptance evidence로 인정한다. SSH session은 파일 전송, 빌드, 로그 회수, 원격 진단에만 사용한다.

## 테스트 기준

- Unit: offset registry validation, snapshot schema parsing, strict type validation, unsupported version rejection.
- Fixture integration: recorded memory snapshot fixture를 `StructuredGameState`로 변환하고 legal action generation까지 확인한다.
- Cross-check: OCR state와 memory state 불일치 시 fail-closed evidence가 남는지 확인한다.
- Safety scan: mutation API token과 write path가 production memory reader에 없는지 검증한다.
- Windows acceptance: read-only process attach와 snapshot extraction을 local interactive session에서 검증한다.
- Full verification: `PYTHONPATH=src uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100`와 `git diff --check`.
