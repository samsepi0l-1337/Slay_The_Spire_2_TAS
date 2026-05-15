# TAS Runtime V1

이 문서는 Windows Slay the Spire 2 TAS-grade runtime의 v1 구현 경계를 정리한다.

## Determinism Contract

v1의 결정성 기준은 mid-frame process memory savestate가 아니다. 현재 기준은 semantic movie, deterministic replay, cold checkpoint restore, repeated replay verification이다.

`tas-probe`가 hook canary에 붙지 못하면 Python fallback event를 기록하지만 `tas_grade=false`로 표시한다. 이 fallback은 운영 진단용이며 TAS-grade acceptance evidence로 쓰지 않는다.

## Public Commands

- `sts2-tas tas-probe --target-process SlayTheSpire2 --out probe.jsonl`: passive probe event를 JSONL로 쓴다.
- `sts2-tas tas-record --target-process SlayTheSpire2 --movie out.sts2movie`: semantic movie 파일을 생성한다.
- `sts2-tas tas-replay --movie run.sts2movie --target-process SlayTheSpire2 --verify`: 현재는 저장된 movie의 static verification report를 출력한다. live Windows replay drift 비교는 v1 gap이다.
- `sts2-tas tas-verify --movie run.sts2movie --runs 5`: 현재는 같은 static movie verification report를 N회 반복한다. 실제 5회 live victory acceptance는 v1 gap이다.
- `sts2-tas tas-search --checkpoint checkpoint.json --budget N --out best.sts2movie`: checkpoint와 prefix movie를 검증한다.
- `sts2-tas train --dataset data/experience.jsonl --label-policy verified`: `TasExperience` JSONL에서 verified supervised 후보 row 수를 검증한다.

기존 Torch 학습은 여전히 `GameStep` dataset과 `--model --character`를 사용한다. `TasExperience`를 Torch state tensor로 바꾸는 연결은 별도 구현 지점이다.

## Movie Format

`TasMovie`는 JSON 기반 `.sts2movie` 파일이다. 각 `TasFrame`은 `semantic_action`, `physical_input`, `screen_hash`, `state_fingerprint`, `decision_context`, `source_policy`, `label_source`, `outcome_ref`를 가진다. Movie prefix hash는 metadata와 prefix frame payload를 stable JSON으로 직렬화한 SHA-256이다.

## Input Mapping

Combat `play_card`는 hand slot을 숫자키로 변환한다.

- `hand-0-*` -> `1`
- `hand-1-*` -> `2`
- `hand-9-*` -> `0`

공격 카드처럼 `target_monster_id`가 있는 action은 `DigitN` key tap 뒤 `target_screen_box` 중심 클릭을 추가한다. 비공격 카드는 key tap만 쓴다. `end_turn`은 `E` key tap이다. 지도, 이벤트, 보상 skip, proceed 등 shortcut 검증이 없는 action은 기존 screen box click을 유지한다.

## Checkpoint

`TasCheckpoint`는 cold checkpoint만 표현한다.

- `save_hash`: explicit save file SHA-256
- `movie_prefix_hash`: prefix frame hash
- `movie_prefix_length`: replay해야 하는 prefix frame 수
- `screen_hash`, `state_fingerprint`: restore + prefix replay 후 도달해야 하는 decision fingerprint

검색은 checkpoint 검증 실패 시 branch candidate에서 제외해야 한다. 현재 구현은 hash/fingerprint 계약 검증까지만 수행하며, 실제 save restore + prefix replay는 v1 gap이다.

## ML Data Quality

`TasExperience`는 `GameStep`/`TrajectoryStep`을 대체하지 않는다. v1에서는 TAS/movie 기반 선택 provenance를 추가로 저장한다.

기본 supervised set에 포함되는 row 조건:

- `label_source in {"human", "search_success", "verified_heuristic"}`
- `changed_ack=true`
- `terminal_return is not None`
- `selected_action.legal=true`
- `failure_reason is None`
- `no_op=false`
- `drift_detected=false`

`model_self`, 실패 rollout, no-op, drift, illegal, terminal outcome 없는 row는 기본 학습에서 제외하고 evaluation/negative analysis 대상으로만 남긴다.

## Native Hook Canary

`native/sts2_tas_hook/`는 x64 Windows passive-only canary scaffold다. 현재 CI에서 빌드하지 않으며 Python package에 연결되어 있지 않다.

스캐폴드 계약:

- Detours 기반 `IDXGISwapChain::Present` hook 예정
- frame counter 증가
- foreground/window metadata 수집
- optional frame screenshot/hash 수집
- input hook 없음
- time hook 없음
- gameplay memory mutation 없음

hook이 green이 되기 전에는 입력 hook, time hook, RNG/tick 고정은 구현 범위 밖이다.
