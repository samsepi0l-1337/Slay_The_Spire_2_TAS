# V1 Gaps

현재 문서는 Windows Slay the Spire 2 TAS runtime 방향성에 맞춘 남은 gap만 추적한다. v1 TAS acceptance 기준과 직접 연결되지 않는 예전 자동화 세부 항목은 제외한다.

## Current Baseline

구현되어 있는 것은 TAS artifact와 정적 검증 경계다.

- `TasMovie`, `TasFrame`, `PhysicalInput`
- `TasCheckpoint`
- `TasExperience`
- numeric-key combat input mapping
- passive-only Windows hook scaffold
- static `tas-replay --verify`
- static `tas-verify --runs N`
- verified-label `train --label-policy verified`

아직 구현되어 있지 않은 것은 Windows 실제 게임을 대상으로 한 live replay acceptance다.

## P0 Gaps

- Live replay backend: `tas-replay --verify`는 아직 Windows target process에 입력을 보내고 frame/state drift를 재측정하지 않는다. 현재는 저장된 `.sts2movie`를 읽어 hash/fingerprint 존재와 stored outcome을 검사한다.
- Five-run acceptance: `tas-verify --runs 5`는 아직 실제 5회 게임 replay가 아니다. 같은 movie의 static verification을 N회 반복한다. Gate 5는 live backend가 붙은 뒤에만 TAS-grade acceptance로 인정한다.
- Real recording: `tas-record`는 movie metadata와 파일 구조를 만든다. live gameplay에서 semantic action, physical input, screen hash, state fingerprint를 채우는 recorder는 남아 있다.
- Checkpoint replay: `tas-search`는 save hash와 prefix hash를 검증하지만 실제 save restore, movie prefix replay, decision fingerprint 도달 확인을 수행하지 않는다.
- Native canary attach: `native/sts2_tas_hook/`는 passive scaffold다. Detours/Present attach, frame hash 수집, IPC transport, Python consumer 연결은 남아 있다.

## P1 Gaps

- Gate 5 report semantics: static verifier 출력에는 `acceptance_source=static_movie` 같은 구분자가 필요하다. live Windows 검증 결과와 fixture/static 검증 결과가 섞이면 안 된다.
- Drift evidence: replay drift가 발생했을 때 frame number, last semantic action, before/after screenshot, state fingerprint를 저장하는 report format이 필요하다.
- Target boundary: `--target-process`가 지정된 live capture는 visible target window가 없으면 전체 화면 fallback 없이 fail-closed 한다. 남은 gap은 실제 입력 실행에서 `--target-process` 없이는 fail-closed 하도록 강제하고, process name selector와 window title helper를 분리하는 것이다.
- Checkpoint negative path: checkpoint 검증 실패 시 branch movie를 acceptance 산출물처럼 쓰지 않도록 CLI 경로와 테스트를 잠가야 한다.
- Hook IPC trust boundary: named pipe에는 session nonce, ACL, target pid binding 같은 검증 경계가 필요하다.
- Foreground metadata: hook scaffold의 foreground-window metadata는 target-bound metadata로 바뀌어야 한다.

## P2 Gaps

- ML JSONL strict types: `TasExperience.from_dict()`는 문자열 `"false"` 같은 truthy 값을 boolean으로 받아들이지 않도록 strict parsing이 필요하다.
- Numeric slot edges: `hand-10-*`, `hand-99-*`, `hand-01-*`, invalid target box에 대한 fail-closed 테스트가 필요하다.
- Click box validation: zero-area, inverted, negative, out-of-bounds screen box를 실행 전에 거부해야 한다.
- Windows task wording: scheduled task wrapper 문구는 hidden/elevated execution이 아니라 explicit interactive local run boundary를 드러내도록 정리해야 한다.

## Acceptance Boundary

TAS-grade acceptance는 아래 조건이 모두 충족된 뒤에만 주장한다.

- Windows target process가 확인된 상태에서 replay가 실제 입력을 보낸다.
- replay마다 live frame hash와 state fingerprint를 새로 수집한다.
- 같은 movie가 5회 모두 victory에 도달한다.
- drift 0건, unclassified screen 0건, target-window mismatch 0건이다.
- fallback probe/static verifier 결과는 acceptance evidence에 포함하지 않는다.
