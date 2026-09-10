# AGENTS.md

## Communication

- 한국어로 짧게 답한다. 결과 먼저, 근거는 로그/응답 코드/실패 값 중심으로만 쓴다.
- 추측하지 않는다. 불확실하면 확인하고, 확인 못 한 내용은 확인 못 했다고 말한다.
- tool first. 긴 설명보다 실행, 검증, 결과를 우선한다.

## Work Rules

- 단일 사용 추상화, 미래 확장용 추상화, 의미 없는 wrapper는 만들지 않는다.
- 파일은 350~400줄 이하로 유지한다.
- 큰 함수에는 분기를 계속 쌓지 않는다.
- Functional Programming, SOLID, DRY, KISS, YAGNI, Clean Code principles, TDD를 따른다.
- 파일을 하나하나 생성하지 말고, 명령어를 사용 가능한 것은 사용해서 작업한다.
- test coverage를 100% 유지한다.
- test 진행후 전체 파일을 검토하여 누락된 부분이 있는지 확인한다.
- 코드를 수정한 후에는 documentat를 업데이트한다.
- 작업이 끝나면 PR commit & push 하고, comments에 `@codex review` + review 해야하는 사항들을 작성한다.
- test에는 e2e test를 포함한다.
- windows ssh 연결을 사용하여 테스트를 진행한다.

## Documentation

- 수정하거나 작성하기 전에 관련 영역 문서를 먼저 확인한다.
- 전체 문서 인덱스: `docs/README.md`
- 코드 수정 시 관련 문서도 업데이트한다.

## Module Ownership

- `src/sts2_tas/telemetry_schema.py`: `TelemetrySnapshot`, `ValidAction`, `MacroAction`, `MacroActionCommand`, run record validation.
- `src/sts2_tas/telemetry_client.py`: named pipe/WebSocket transport, reconnect, frame ordering, corrupt-frame rejection.
- `src/sts2_tas/env.py`: Gymnasium `Sts2Env`, `reset(seed)`, `step(action)`, `action_masks()`.
- `src/sts2_tas/action_space.py`: deterministic macro-action flatten/unflatten and valid action masks.
- `src/sts2_tas/executor.py`: dry-run/native macro-action executor with target-window guard and `--execute` gate.
- `src/sts2_tas/heuristic.py`: combat/reward/map/shop/event/rest baseline policy.
- `src/sts2_tas/bc.py`: behavioral cloning training and inference.
- `src/sts2_tas/rl.py`: MaskablePPO training and evaluation.
- `src/sts2_tas/qstar.py`: Q* search over legal macros, online TD weight updates, and the play loop.
- `src/sts2_tas/dataset.py`: JSONL first transition logging with SQLite/Parquet-compatible records.
- `bridge/Sts2TelemetryBridge/`: Godot 4 C#/.NET bridge, checked-in `.sln`/`.csproj`, Harmony bootstrap, patch point config, named pipe/WebSocket transport.
- `.github/workflows/windows-exe.yml`: Windows executable workflow for the new CLI surface and bridge smoke fixtures.

## Project

- PR comment에는 `@codex review`, 문제, 원인, 수정 범위, 검증 결과, UI 변경 시 스크린샷을 포함한다.
