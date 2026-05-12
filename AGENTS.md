# AGENTS.md

## Communication

- 한국어로 짧게 답한다. 결과 먼저, 근거는 로그/응답 코드/실패 값 중심으로만 쓴다.
- 추측하지 않는다. 불확실하면 확인하고, 확인 못 한 내용은 확인 못 했다고 말한다.
- tool first. 긴 설명보다 실행, 검증, 결과를 우선한다.

## Subagent

- 모든 작업은 Subagent를 생성한다.
- main agent는 목표와 합성만, subagent는 한 가지 작업만 담당한다.
- 절대 main agent가 subagent의 작업을 대신 수행하지 않는다.
- 작업이 크기와 복잡성에 따라 필요한 만큼 subagent를 생성한다.
- subagent에 작성해야하는 항목: 모델, 추론 강도, 전달할 최소 컨텍스트(독립 윈도우), 역할(전용 지시), 허용 도구와 권한(기본은 좁게, 넓히면 이유).
- subagent에서 간단한 코드 작성은 gpt-5.3-codex-spark 모델을 사용한다.
- subagent에서 commit, push, 검색, 간단한 검증, 간단한 분석은 gpt-5.4-mini 모델을 사용한다.
- subagent에서 복잡한 코드 작성, 복잡한 검증, 복잡한 분석, 문서 작성은 gpt-5.5 모델을 사용한다.
- 코드 작성 subagent의 작업을 완료하면 코드 검증 subagent를 생성하여 검증하고, 만약 검증 subagent에서 문제가 있다면 다시 코드 작성 subagent를 생성하여 작업을 반복한다.

## Work Rules

- 단일 사용 추상화, 미래 확장용 추상화, 의미 없는 wrapper는 만들지 않는다.
- 파일은 350~400줄 이하로 유지한다.
- 큰 함수에는 분기를 계속 쌓지 않는다.
- Functional Programming, SOLID, DRY, KISS, YAGNI, Clean Code principles, TDD를 따른다.
- 파일을 하나하나 생성하지 말고, 명령어를 사용 가능한 것은 사용해서 작업한다.
- test coverage를 100% 유지한다.
- test 진행후 전체 파일을 검토하여 누락된 부분이 있는지 확인한다.
- 코드를 수정한 후에는 documentation을 업데이트한다.
- 작업이 끝나면 pr commit & push 하고, `@codex review` + review 해야하는 사항들을 작성한다.

## Documentation

- 수정하거나 작성하기 전에 관련 영역 문서를 먼저 확인한다.
- 전체 문서 인덱스: `docs/README.md`

## Project

- PR에는 `@codex review`, 문제, 원인, 수정 범위, 검증 결과, UI 변경 시 스크린샷을 포함한다.
