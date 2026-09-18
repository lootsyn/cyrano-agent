# UDH DREAM 설계 패키지

이 패키지는 DeepAgent Code/UDH에 통제된 자기개선 기능을 추가하기 위한 **설계와 계약 예시**다. 완성된 plugin/실행 엔진이 아니다.

## 읽는 순서

`FULL_DESIGN.ko.html` 또는 `FULL_DESIGN.ko.md`는 본문과 부록을 합친 독립 읽기용 문서다. 편집 원본은 `DESIGN.ko.md`, `contracts/`, `config/`, `tests/`, `prompts/`이다. 구현 담당자에게는 `IMPLEMENTATION_HANDOFF.ko.md`를 먼저 전달한다.

## 구성

| 경로 | 내용 |
|---|---|
| `DESIGN.ko.md` | 0–26장 상세 아키텍처·replay·실행·평가·승격·복구 명세 |
| `contracts/dream-contracts.schema.json` | JSON Schema: 8개 record family와 공통 정의 |
| `contracts/SEMANTICS.ko.md` | JSON 구조 밖에서 강제할 의미·권한 검사 |
| `config/dream.example.yaml` | 실행·자동 승격·canary가 꺼진 운영 예시 |
| `fixtures/contract-cases.json` | 정상 10개·거부 12개 합성 계약 fixture |
| `tests/acceptance-tests.yaml` | 미실행 제품 수용 테스트 시나리오 56개 |
| `prompts/roles.ko.md` | Analyst·Generator·Reviewer 역할 계약 |
| `tools/validate_design.py` | 문서 패키지/합성 계약 검증 도구 |
| `evidence/design-validation.json` | 실제 수행한 패키지 검사만 기록 |
| `SOURCES.md`, `sources.json` | 1차 출처와 기존 UDH 연결 |

## 검증 재실행

Python과 `jsonschema`, `PyYAML`이 설치된 별도 검증 환경에서 실행한다.

```bash
python tools/validate_design.py
```

이 명령은 dcode·LLM·sandbox를 실행하지 않으며, 외부 서비스·저장소·Library를 수정하지 않는다. 합성 fixture의 digest는 설명용 문자열의 SHA256 값으로, 실제 운영 artifact의 검증 증거가 아니다. 제품 dependency pin과 `uv.lock`은 실제 구현 저장소에서 WP-D00 이후 생성한다.

## 상태

문서/계약 예시 검증과 제품 검증을 혼동하지 않는다. dcode 연결, replay 엔진, 권한 우회 차단, 실제 모델 효과, canary와 rollback은 **구현 후 검증 대상**이다. 본 패키지에서 성능 향상 수치를 실측했다고 주장하지 않는다. 기존 UDH와 사용자 제품 저장소는 변경하지 않았다.
