# Implemented Work

현재 코드 기준으로 구현된 TAS v1 범위만 정리한다.

## CLI

- `tas-probe`
  - passive probe JSONL을 기록한다.
  - native hook이 없으면 `hook_attached=false`, `mode=python_fallback`, `tas_grade=false`를 명시한다.
- `tas-record`
  - `.sts2movie` 파일 계약과 metadata를 생성한다.
- `tas-replay --verify`
  - movie를 읽고 frame count, victory, drift count, unclassified screen count, target mismatch count를 출력한다.
- `tas-verify --runs N`
  - 같은 movie 검증을 N회 반복하고 victory/drift aggregate를 출력한다.
- `tas-search`
  - `TasCheckpoint`의 save hash, movie prefix hash, screen/state fingerprint를 검증하고 prefix movie를 쓴다.
- `train --label-policy verified`
  - `TasExperience` JSONL에서 기본 supervised 후보 row 수를 검증한다.
- 기존 `train --model --character`
  - `GameStep` 기반 Torch 학습 경로로 유지한다.

## Data Model

- `TasMovie`
  - ordered `TasFrame` 목록, game version, branch, target process, stable prefix hash를 제공한다.
- `TasFrame`
  - semantic action, physical input, screen hash, state fingerprint, decision context, source policy, label source, outcome reference를 저장한다.
- `PhysicalInput`
  - `key_tap`, `click`, `wait` 입력을 표현한다.
- `TasCheckpoint`
  - save file SHA-256, movie prefix hash/length, screen hash, state fingerprint를 저장한다.
- `TasExperience`
  - movie frame, run id, state fingerprint, legal actions, selected action, behavior policy, label source, changed ack, terminal return, failure/no-op/drift markers를 저장한다.

## Input Runtime

- combat `play_card`는 `source_card_id=hand-N-*`를 숫자키로 변환한다.
- targeted card는 keypress 뒤 target click을 하나의 sequence로 만든다.
- non-target card는 keypress만 만든다.
- combat `end_turn`은 `E` keypress다.
- non-combat action은 shortcut이 검증되기 전까지 screen box click을 유지한다.
- Windows native backend는 keypress+click sequence를 하나의 guarded PowerShell script로 생성한다.
- target window가 지정되면 input 직전에 process/title/bounds를 다시 확인하고 mismatch면 실패한다.

## Native Hook Scaffold

`native/sts2_tas_hook/`에 다음 scaffold가 있다.

- `CMakeLists.txt`
- `README.md`
- `ipc_contract.md`
- `sts2_tas_hook.cpp`

계약:

- x64 Windows
- Detours 기반 future Present hook
- frame counter
- foreground/window metadata
- optional screenshot/hash
- passive-only
- no input hook
- no time hook

현재 빌드, 주입, 실제 hook attach는 구현하지 않았다.

## Documentation

- `docs/architecture.md`: 현재 v1 구조만 유지한다.
- `docs/tas-runtime.md`: CLI, movie, checkpoint, ML gate, hook boundary를 설명한다.
- `docs/README.md`: 현재 방향성의 인덱스와 scope만 유지한다.

## Verification Evidence

로컬 macOS/Python 3.14 환경에서 확인한 범위:

```bash
PYTHONPATH=src uv run --extra dev pytest
git diff --check
```

통과 기준:

- unit: movie/checkpoint/experience/input mapping
- integration: TAS CLI, existing CLI, native input backend, live loop regression
- asset: Windows hook scaffold token/contract

## Not Implemented

- real Windows hook build/injection
- SlayTheSpire2 process attach
- live frame screenshot hash from Present
- real movie recording from live gameplay
- real physical replay against the game
- save restore + prefix replay on Windows
- `tas-verify --runs 5` live victory acceptance
- `TasExperience` to Torch tensor training integration
