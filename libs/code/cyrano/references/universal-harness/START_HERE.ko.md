# UDH 설계 패키지 시작점

**범위:** 모델별 특화 없이 기능을 유지·고도화한 dcode 개발 Harness. **산출물 종류:** 구현 명세·계약·참조 검증 패키지이며 완성된 dcode plugin이 아니다.

## 읽는 방법

`FULL_DESIGN.ko.md`는 상세 본문, schema appendix, 설정, DDL, 수용 테스트, 역할·skill prompt 및 첨부 원본 설계를 포함한 통합본이다. 사람은 함께 제공한 `UDH_FULL_DESIGN.ko.html`에서 목차로 탐색할 수 있다. 실제 구현 지시는 `IMPLEMENTER_HANDOFF.ko.md`를 사용한다.

| 경로 | 내용 |
|---|---|
| docs/01_ARCHITECTURE_AND_WORKFLOW.ko.md | 범위·요구·구조·상태기계·인터뷰·계획·profiles |
| docs/02_RUNTIME_MEMORY_AND_LEARNING.ko.md | 승인·미들웨어·캐시·메모리·Self-Improving |
| docs/03_OBSERVABILITY_QUALITY_AND_OPERATIONS.ko.md | 관측·Python 품질·40점 기준·운영·실패 |
| docs/04_MODULE_API_AND_IMPLEMENTATION.ko.md | 모듈·함수·API·DB·WP00–WP21 |
| docs/05_CONTRACT_DETAILS_AND_TESTING.ko.md | schema 의미·도구·결정적 알고리즘·평가 |
| docs/06_SOURCES_AND_TRACEABILITY.ko.md | 공식 출처·첨부본 보존·요구 추적 |
| contracts/ | 15개 JSON Schema, 이벤트 catalog, 40점 rubric |
| fixtures/ | 정상·오류 예시, 124개 수용 테스트 명세, 원본 해시 |
| config/ | 외부 정책·품질·runtime lock·extension 설정 template |
| sql/001_initial.sql | 초기 DB schema와 FTS5 index |
| prompts/ | 12개 역할, 공통 원칙, 8개 작업 Skill |
| reference/ | 실행 가능한 제한적 명세 oracle·35개 테스트 |
| tools/validate_package.py | 패키지 구조·예시·원본 보존 검증 |
| source_interview/ | 사용자가 첨부한 14개 원본 파일 그대로 |
| VALIDATION.ko.md / VALIDATION_REPORT.json | 실제 수행한 검사와 미수행 항목 |

통합본의 schema appendix는 중복을 줄이려고 공통 `$defs`를 한 번만 제시한다. 실제 `.schema.json` 파일은 각각 필요한 `$defs`를 포함한다. API DTO 파일은 endpoint별 `$defs/<DTO>`로 검사해야 한다.

## 설계의 핵심 경계

설치 때문에 대상 repository를 바꾸지 않는다. dcode core를 수정하지 않는다. 모델별 capability 점수·prompt 분기를 만들지 않는다. 반면 interview/계획/리뷰/승인/메모리/개선/평가/모니터링/복구 기능은 모두 포함한다.

`governed`는 실제 Broker·원장·OS 격리·어댑터 검증을 요구한다. 연결 실패 시 일반 advisory 모드로 몰래 내려가지 않는다. 스키마 검사나 reference test 통과가 실제 dcode 환경의 실행 보장을 뜻하지 않는다.
