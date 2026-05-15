# V1 Implementation Directive

이 문서는 `docs/v1-gaps.md`의 gap을 실제 구현 지시서로 분리한다. 대상은 Windows interactive desktop에서 실제 Slay the Spire 2를 replay 검증 가능한 TAS runtime v1로 만드는 작업이다.

## 구현할 것

- `tas-replay --verify --live`는 Windows target process를 찾고, movie의 `PhysicalInput`을 실제 native 입력으로 replay하며, 각 frame의 live screen hash와 state fingerprint를 다시 수집한다.
- `tas-verify --runs N --live`는 같은 movie를 실제 Windows 게임에서 N회 replay하고 victory, drift, unclassified screen, target-window mismatch를 aggregate한다.
- `tas-record --live`는 live gameplay의 semantic action, physical input, screen hash, state fingerprint, decision context, source policy, label source를 채운 `TasFrame`을 기록한다.
- `tas-search`는 checkpoint save restore, movie prefix replay, decision fingerprint 도달 확인을 수행한다.
- `native/sts2_tas_hook/`는 passive-only Windows canary로 Detours `IDXGISwapChain::Present` attach, frame counter, target-bound window metadata, optional frame hash, named-pipe JSONL IPC, Python consumer를 제공한다.
- static/live report를 분리한다. static 검증은 `acceptance_source=static_movie`, live Windows 검증은 `acceptance_source=live_windows_replay`를 출력한다.
- replay drift evidence는 frame number, last semantic action, expected/actual screen hash, expected/actual state fingerprint, before/after screenshot path, target window metadata를 남긴다.
- 실제 native execute 경로는 `--target-process`를 필수로 하고, target window mismatch나 click box 오류를 입력 전에 fail-closed 한다.
- `TasExperience` JSONL boolean은 strict bool만 허용하고, combat numeric slot과 click box edge를 fail-closed로 검증한다.

## 구현하지 않을 것

- mid-frame process memory savestate
- gameplay memory write 또는 mutation
- simulation tick freeze
- RNG/time hook
- input hook 활성화
- anti-cheat, DRM, network, leaderboard bypass
- Python fallback 또는 static verifier 결과를 TAS-grade acceptance evidence로 승격하는 동작

## 구현 순서

1. P2/P1 안전성 gap을 먼저 잠근다: strict bool, numeric slot edge, click box validation, target-process execute boundary, checkpoint negative path, Windows task wording.
2. report schema를 정리한다: `acceptance_source`, `tas_grade`, drift evidence, static/live 구분을 추가한다.
3. `PhysicalInput` replay adapter를 구현한다: movie frame input을 native backend command/controller로 변환한다.
4. fake hook/IPC 기반 live replay harness를 만든다: 실제 Windows hook 없이 replay, drift, mismatch, no-op을 테스트할 수 있게 한다.
5. checkpoint restore/replay adapter를 구현한다: save backup, restore, prefix replay, fingerprint 확인을 atomic하게 처리한다.
6. Windows Detours passive hook을 구현한다: target pid binding, nonce, ACL, Present frame event, optional frame hash, Python reader를 연결한다.
7. Windows 5-run live acceptance를 구현한다: local interactive session에서 5회 victory, drift 0, unclassified 0, target mismatch 0일 때만 TAS-grade로 인정한다.

## Acceptance 기준

- `tas-replay --verify` static output은 항상 `acceptance_source=static_movie`이며 TAS-grade acceptance가 아니다.
- `tas-replay --verify --live`는 `acceptance_source=live_windows_replay`이고 target process/window가 확인된 상태에서 실제 입력을 보낸다.
- `tas-verify --runs 5 --live`는 5회 모두 victory, drift 0, unclassified screen 0, target-window mismatch 0일 때만 `tas_grade=true`를 출력한다.
- hook이 실패하면 fallback event는 진단용으로만 기록하고 `tas_grade=false`를 유지한다.
- Windows 실제 게임 검증은 로그인된 local interactive session에서 실행된 결과만 acceptance evidence로 인정한다. SSH session은 파일 전송, 빌드, 로그 회수, 원격 진단에만 사용한다.

## 테스트 기준

- Unit: strict bool parsing, hand slot edge, invalid click box, report source 구분, drift evidence serialization.
- CLI: static replay/verify는 live acceptance와 섞이지 않고 `acceptance_source=static_movie`를 출력한다.
- Integration fixture: fake hook IPC, fake window detector, fake input controller로 live replay success/drift/target mismatch/no-op을 검증한다.
- Checkpoint: invalid save/prefix/fingerprint에서는 prefix movie를 쓰지 않고 `acceptance_eligible=false`를 출력한다.
- Windows-facing: PowerShell native command, target guard, scheduled task interactive boundary를 검증한다.
- Full verification: `PYTHONPATH=src uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100`와 `git diff --check`.
