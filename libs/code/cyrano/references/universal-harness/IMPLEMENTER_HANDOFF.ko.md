# 구현 에이전트에게 전달할 작업 지시

## 목표

첨부 UDH 설계에 따라 dcode 기반의 범용 개발 Harness를 구현하라. **모델별 특화만 제외한다. 기능을 간소화하지 않는다.** 인터뷰, 계획·독립 리뷰·승인, 적극적 메모리, 미들웨어 관측·Self-Improving, prompt-cache 친화적 context, 전체 모니터링, Python 품질, 복구·보안을 모두 구현 대상으로 유지한다.

## 먼저 읽을 내용

`FULL_DESIGN.ko.md`가 본문·계약·설정·테스트·첨부 원본을 묶은 통합본이다. 작업할 때는 `docs/01...06`과 `contracts/`, `fixtures/`, `sql/`, `prompts/` 원본 파일을 사용한다. 통합본은 원본 파일에서 생성한 읽기용 snapshot이며 코드 생성의 단일 편집 대상은 각 개별 파일이다. 한 파일의 JSON 계약을 바꾸면 관련 문서·fixture·테스트도 같이 갱신하라.

## 반드시 지킬 경계

대상 프로젝트에 harness 설치 목적으로 `.deepagents`, SDK dependency, config를 추가하지 않는다. dcode core를 fork/patch/monkey-patch하지 않는다. UDH는 사용자 영역의 extension/plugin과 외부 control service/Broker/sandbox로 구현한다. 실제 개발 변경은 승인된 외부 사본에서 수행하고 원본 반영은 별도 허가다.

`register_command` 또는 가정한 dcode CLI flag를 쓰지 않는다. 실제 설치 버전의 API/entrypoints/도구 이름·동작을 확인하고 `runtime-lock.json`과 `CompatibilityReport`를 먼저 생성한다. 모든 모델에 동일한 task/risk 기반 policy를 사용한다. 모델 ID는 재현/관측 정보일 뿐 자체 특화 분기 키가 아니다.

## 진행 순서

WP00의 연결 검사와 WP01의 순수 계약 구현부터 시작하라. 각 WP의 선행 산출물, 관련 파일, 요구사항 ID, acceptance case, 실패/권한 경계를 먼저 적고 구체 계획을 독립 리뷰받은 뒤 구현하라. 계획 승인은 실행 허가가 아니며 실행 범위는 별도로 확인한다. 독립 reviewer가 없는 환경에서는 그 검토가 완료됐다고 하지 말고 pending으로 남겨라.

원본 R01–R22를 삭제하거나 의미를 완화하지 않는다. 추가 102개 수용 사례를 실제 unit/component/governed/model/operational 테스트로 구현하라. `reference`의 35개 합성 테스트는 예시 kernel 의미를 검증할 뿐 실제 승인·dcode 연동·격리를 대신하지 않는다.

## 구현 원칙

순수 domain/kernel에 LLM 또는 dcode 의존성을 넣지 않는다. worker는 제안만 한다. 승인·권한·완료는 authenticated evidence에서 서버가 계산한다. same-user process 분리를 보안 경계로 간주하지 않는다. source directory 전체 writable mount와 사후 diff만으로 새 파일 사전 허가를 보장했다고 하지 않는다.

Memory는 scope filter·freshness·release view·적극 recall·실제 적용 증거를 구현하라. Self-Improving은 관측→후보→독립 평가→승인→불변 release→canary→rollback 전체 경로를 구현하라. 실패 사례를 피하려고 테스트/승인/보안 기준을 바꾸지 않는다.

PEP8 정책, Black 단일 formatter, Ruff lint, strict typing, 실제 테스트와 독립 리뷰를 적용하라. 기존 대상 프로젝트의 합의된 규약을 무단 덮어쓰지 않는다. 세션/모델 attempt/도구/파일/검증/메모리/개선 이벤트를 연결하고 missing usage를 0으로 만들지 않는다.

## 매 WP의 보고 형식

작업 목표와 requirement IDs, 실제 변경 파일, 실행한 명령과 exit code, 테스트 pass/fail/skip/not_run, evidence 경로와 hash, 독립 review 결과, 남은 blocker와 다음 WP를 보고한다. placeholder TODO, stubbed approval, fake runtime, schema-only permit을 production으로 사용하지 않는다.

지원되지 않는 dcode API가 발견되면 기능을 삭제하거나 core 수정으로 우회하지 말고 정확한 compatibility blocker를 보고하라. 가능한 호환 버전을 실제 확인해 운영자의 명시 선택을 받아라. 이 설계에 포함된 실행 상한은 조정 가능한 운영 policy이지 기능 축소 허가가 아니다.

## 최종 완료

WP00–WP21, 전체 필수 테스트, 요구사항 40점 증거표, hard gates, 비침습 설치 검증, 실제 dcode·memory·cache 관측·learning·dashboard·복구 검증 보고서가 모두 있어야 한다. 구성 파일 존재나 모델의 완료 문장만으로 완료 처리하지 않는다.
