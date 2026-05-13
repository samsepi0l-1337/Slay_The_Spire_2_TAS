# Implemented Work

현재 구현된 기능과 검증 범위를 작업 영역별로 정리한다. 이 문서는 실제 코드 기준의 현황 문서이며, 제외 항목은 [v1 gaps](v1-gaps.md)에 별도로 유지한다.

## CLI Commands

- `capture`: 색상 기반 화면 fixture를 감지해 unlabeled `DecisionSnapshot` JSONL을 기록한다.
- `parse-screen`: screenshot과 OCR provider 결과를 catalog-matched option JSON으로 변환한다.
- `capture-live`: OCR 결과를 `DecisionSnapshot` JSONL로 저장한다.
- `label`: dataset의 특정 snapshot에 `pick:<option_id>` 또는 `skip` 라벨을 붙인다.
- `train`: 라벨된 snapshot으로 캐릭터별 scikit-learn 추천 모델을 학습한다.
- `recommend`: 저장된 모델과 현재 snapshot으로 후보별 추천 점수를 출력한다.
- `act`: snapshot과 명시 choice로 dry-run/input event/native input action을 계획하거나 실행한다.
- `live-step`: 화면 capture 또는 fixture, OCR parsing, manual/model choice, input planning/execution을 한 번에 수행한다.
- `save-state backup`: 지정 save 파일을 backup directory로 복사한다.
- `save-state restore`: backup save를 원 위치로 복원하고 기존 save는 pre-restore copy로 보존한다.
- `run-loop`: seed 목록과 capture fixture/OCR로 seed episode JSONL을 생성한다.
- `evaluate-seeds`: seed episode JSONL에서 episode count, victory count, win rate, average steps를 요약한다.

## Data And Schema

- `ChoiceOption`: 카드/유물/skip 후보의 id, name, kind, tags, optional screen box를 보존한다.
- `DecisionChoice`: `pick`은 `option_id`를 요구하고, `skip`은 `option_id`를 금지한다.
- `DecisionSnapshot`: game version, branch, character, ascension, floor, deck, relics, hp, gold, options, chosen/skipped state, screenshot path를 JSON으로 round-trip한다.
- `RecognizedOption`/`ParsedScreen`: OCR에서 인식한 canonical option과 화면 resolution을 구조화한다.
- `AutomationAction`: action, option id, dry-run state, target box를 기반으로 click 또는 keypress `input_plan`을 만든다.
- 좌표 없는 `pick` action은 실행 계획 생성 시 실패한다. 좌표 없는 `skip`만 escape keypress 계획을 허용한다.

## Screen Recognition

- synthetic/stable screenshot용 색상 기반 detector가 card reward, relic choice, skip button layout을 구분한다.
- OCR provider protocol을 통해 fixture OCR과 Tesseract TSV adapter를 같은 parsing 경로로 사용한다.
- 영어/한국어 alias catalog로 카드, 유물, skip text를 canonical id로 매핑한다.
- 카드 보상 OCR은 3개 카드와 skip button이 모두 인식될 때만 `card_reward`로 처리한다.
- 같은 catalog id가 여러 슬롯에 나오면 `strike_1`, `strike_2`처럼 slot-specific id로 분리한다.
- Tesseract TSV의 단어 row를 line-level compound token으로 합쳐 `Burning Blood`, `Tiny House` 같은 multi-word 항목을 매칭한다.
- reward layout은 resolution-independent 위치 조건으로 필터링한다.
- 알 수 없는 layout이나 catalog에 없는 텍스트는 빈 학습 row로 저장하지 않고 실패하거나 무시한다.

## Machine Learning

- 라벨된 snapshot을 option candidate feature row로 변환한다.
- scikit-learn `DictVectorizer + DecisionTreeClassifier` 기반 supervised recommender를 사용한다.
- 캐릭터별 모델 학습을 지원하며, 추천 시 snapshot character와 모델 character mismatch를 거부한다.
- `joblib`로 모델 save/load를 수행한다.
- 추천 결과는 best candidate와 candidates list를 JSON으로 출력한다.

## Automation And Input

- 모든 입력 실행은 기본 dry-run이다.
- `--execute`가 있을 때만 controller를 사용한다.
- 기본 backend는 `jsonl`이며, input event를 JSONL로 기록한다.
- `--input-backend native --execute`는 platform command로 실제 입력 계획을 전달한다.
- macOS native backend는 `osascript` System Events를 사용한다.
- Linux native backend는 `xdotool`을 사용한다.
- Windows native backend는 keypress만 PowerShell SendKeys로 지원하고 click은 명시적으로 실패한다.
- 테스트에서는 runner/monkeypatch를 주입해 실제 OS 입력을 보내지 않는다.

## Live Step

- `--capture-fixture`로 deterministic screenshot을 사용하거나, `--screenshot-out`으로 Pillow `ImageGrab.grab()` 결과를 저장한다.
- OCR parsing으로 현재 선택지를 만들고 `DecisionSnapshot`을 구성한다.
- `--choice`가 있으면 manual choice를 사용한다.
- `--model`이 있으면 저장된 추천 모델의 best candidate를 choice로 변환한다.
- 결과 JSON에는 `choice`, `action`, `input_plan`, `screenshot_path`가 포함된다.
- native backend는 `--execute` 없이 사용할 수 없다.

## Runtime And Evaluation

- `capture_screen()`은 화면 캡처 실패를 OS screen recording permission/setup error로 감싸 보고한다.
- save backup/restore는 명시된 파일과 backup directory만 조작하며, save path hash를 포함한 backup 이름으로 같은 파일명 충돌을 막는다.
- seed loop는 현재 v1 boundary로, fixture/OCR 기반 episode row를 생성하고 실제 수행한 parsed choice 수를 `steps`로 기록한다.
- seed evaluation은 victories, win rate, average steps를 계산한다.

## Docker And Packaging

- Dockerfile은 CLI 실행 이미지를 만든다.
- `.dockerignore`는 local state와 generated output을 제외한다.
- README와 docker docs는 macOS/Linux/Windows 실행 경계를 설명한다.
- Python package entrypoint는 `sts2-tas = "sts2_tas.cli:main"`이다.

## Tests And Verification

- 현재 test suite는 schema, dataset, model, recognition, live OCR, automation CLI, native input backend, live-step CLI, Docker asset을 검증한다.
- coverage gate는 `sts2_tas` 전체 100%를 요구한다.
- 최종 검증 명령:

```bash
uv run --extra dev pytest --cov=sts2_tas --cov-fail-under=100
```

- 최근 확인된 결과: `73 passed`, total coverage `100.00%`.

## Safety Boundaries

- Steam/Godot process memory나 내부 runtime state는 읽지 않는다.
- 온라인/co-op/leaderboard 자동화는 구현하지 않았다.
- 실제 OS 입력은 `--execute`와 backend 명시가 필요하다.
- 실제 게임 창 end-to-end smoke와 OS permission provisioning은 자동 테스트에서 수행하지 않는다.
